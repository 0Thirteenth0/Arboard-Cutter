from __future__ import annotations

from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    import fitz  # type: ignore


class _TiffDocument:
    """Small PyMuPDF-compatible adapter for TIFF pages MuPDF refuses as oversized."""

    is_pdf = False

    def __init__(self, path: Path):
        try:
            import tifffile
        except ImportError as exc:
            raise RuntimeError("Large TIFF support requires tifffile.") from exc
        self._path = Path(path)
        self._tiff = tifffile.TiffFile(str(self._path))
        if not self._tiff.pages:
            self._tiff.close()
            raise RuntimeError("TIFF contains no image pages.")
        self.page_count = len(self._tiff.pages)
        self.metadata = {"format": "TIFF"}

    def load_page(self, index: int):
        if index < 0 or index >= self.page_count:
            raise IndexError("TIFF page index out of range")
        return _TiffPage(self, index)

    def convert_to_pdf(self):
        raise RuntimeError("PDF Preserve is unavailable for oversized TIFF files; use Raster mode.")

    def close(self):
        self._tiff.close()


class _TiffPage:
    def __init__(self, document: _TiffDocument, index: int):
        self._document = document
        self._page = document._tiff.pages[index]
        shape = self._page.shape
        if len(shape) < 2:
            raise RuntimeError("Unsupported TIFF page shape.")
        self._height, self._width = int(shape[0]), int(shape[1])
        x_dpi = self._dpi("XResolution")
        y_dpi = self._dpi("YResolution")
        self.rect = fitz.Rect(0, 0, self._width * 72.0 / x_dpi, self._height * 72.0 / y_dpi)

    def _dpi(self, tag_name: str) -> float:
        tag = self._page.tags.get(tag_name)
        value = tag.value if tag is not None else 96.0
        if isinstance(value, tuple):
            value = value[0] / value[1] if value[1] else 96.0
        value = float(value or 96.0)
        unit_tag = self._page.tags.get("ResolutionUnit")
        unit = int(unit_tag.value) if unit_tag is not None else 2
        return value * 2.54 if unit == 3 else value

    def get_pixmap(self, matrix=None, clip=None, colorspace=None, alpha=False, **kwargs):
        try:
            import numpy as np
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError("Large TIFF rendering requires NumPy and Pillow.") from exc

        if self._page.is_tiled or int(self._page.planarconfig or 1) != 1:
            raise RuntimeError("This oversized TIFF layout is not supported; flatten it to a strip-based TIFF first.")
        if self._page.dtype != np.uint8:
            raise RuntimeError("Oversized TIFF fallback currently supports 8-bit images only.")

        source_rect = fitz.Rect(clip or self.rect) & self.rect
        if source_rect.is_empty:
            raise ValueError("TIFF render area is empty.")
        if kwargs.get("dpi"):
            scale_x = scale_y = float(kwargs["dpi"]) / 72.0
        else:
            matrix = matrix or fitz.Identity
            scale_x = abs(float(matrix.a))
            scale_y = abs(float(matrix.d))
        output_width = max(1, int(round(source_rect.width * scale_x)))
        output_height = max(1, int(round(source_rect.height * scale_y)))

        x0 = source_rect.x0 * self._width / self.rect.width
        x1 = source_rect.x1 * self._width / self.rect.width
        y0 = source_rect.y0 * self._height / self.rect.height
        y1 = source_rect.y1 * self._height / self.rect.height
        xs = np.clip(
            (x0 + (np.arange(output_width) + 0.5) * (x1 - x0) / output_width).astype(np.int64),
            0,
            self._width - 1,
        )
        ys = np.clip(
            (y0 + (np.arange(output_height) + 0.5) * (y1 - y0) / output_height).astype(np.int64),
            0,
            self._height - 1,
        )

        rows_per_strip = int(self._page.rowsperstrip or self._height)
        samples = int(self._page.samplesperpixel or 1)
        pixels = np.empty((output_height, output_width, samples), dtype=np.uint8)
        file_handle = self._document._tiff.filehandle
        for strip_index in np.unique(ys // rows_per_strip):
            strip_index = int(strip_index)
            file_handle.seek(self._page.dataoffsets[strip_index])
            encoded = file_handle.read(self._page.databytecounts[strip_index])
            decoded, _position, _shape = self._page.decode(encoded, strip_index)
            strip = decoded[0]
            selected = np.flatnonzero(ys // rows_per_strip == strip_index)
            local_rows = ys[selected] - strip_index * rows_per_strip
            pixels[selected] = strip[local_rows[:, None], xs[None, :], :]

        photometric = self._page.photometric.name
        if photometric == "SEPARATED" and samples >= 4:
            source_mode, pixels = "CMYK", pixels[:, :, :4]
        elif photometric == "RGB" and samples >= 3:
            source_mode, pixels = "RGB", pixels[:, :, :3]
        elif samples == 1:
            source_mode, pixels = "L", pixels[:, :, 0]
            if photometric == "MINISWHITE":
                pixels = 255 - pixels
        else:
            raise RuntimeError(f"Unsupported oversized TIFF color layout: {photometric}, {samples} samples.")

        target_space = colorspace or fitz.csRGB
        target_mode = {1: "L", 3: "RGB", 4: "CMYK"}.get(getattr(target_space, "n", 3), "RGB")
        if source_mode != target_mode:
            pixels = np.asarray(Image.fromarray(pixels, source_mode).convert(target_mode))
        return fitz.Pixmap(target_space, output_width, output_height, pixels.tobytes(), bool(alpha))


def force_page_boxes(page: fitz.Page) -> None:
    r = page.rect
    for name in ("set_mediabox", "set_cropbox", "set_bleedbox", "set_trimbox", "set_artbox"):
        setter = getattr(page, name, None)
        if callable(setter):
            try:
                setter(r)
            except Exception:
                pass


def open_pdf_robust(p: Path):
    p = Path(p)
    is_tiff = p.suffix.lower() in {".tif", ".tiff"}
    try:
        doc = fitz.open(str(p))
        if is_tiff:
            try:
                doc.load_page(0)
            except Exception:
                doc.close()
                return _TiffDocument(p)
        return doc
    except Exception:
        pass
    try:
        return fitz.open(p.as_posix())
    except Exception:
        pass
    try:
        with open(p, "rb") as fh:
            filetype = p.suffix.lstrip(".").lower() or "pdf"
            return fitz.open(stream=fh.read(), filetype=filetype)
    except Exception:
        pass
    if is_tiff:
        try:
            return _TiffDocument(p)
        except Exception:
            pass
    raise RuntimeError("Failed to open stream or unsupported format")


def page_box_snapshot(page: fitz.Page) -> dict[str, list[float] | int]:
    def rect_values(rect):
        return [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]

    data: dict[str, list[float] | int] = {
        "rotation": int(page.rotation),
        "rect": rect_values(page.rect),
    }
    for name in ("mediabox", "cropbox", "bleedbox", "trimbox", "artbox"):
        try:
            data[name] = rect_values(getattr(page, name))
        except Exception:
            pass
    return data
