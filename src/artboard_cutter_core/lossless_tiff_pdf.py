from __future__ import annotations

import math
import zlib
from pathlib import Path

import numpy as np
import tifffile

from .errors import ExportCancelled
from .layout import compute_panel_layout
from .output_io import StagedOutputSet, build_output_paths
from .units import mm_to_pt
from .verification import verify_pdf_output


_ROW_BLOCK_BYTES = 16 * 1024 * 1024


class _PdfImageWriter:
    """Write one lossless, single-image PDF without holding its pixels in memory."""

    def __init__(
        self,
        path: Path,
        *,
        pixel_width: int,
        pixel_height: int,
        pixel_x0: int,
        pixel_x1: int,
        components: int,
        page_width_pt: float,
        page_height_pt: float,
        image_x_pt: float,
        image_width_pt: float,
        decode: str | None,
        icc_profile: bytes | None,
    ):
        self._file = Path(path).open("wb")
        self._offsets: dict[int, int] = {}
        self._compressor = zlib.compressobj(level=1)
        self._stream_length = 0
        self._components = components
        self.pixel_x0 = pixel_x0
        self.pixel_x1 = pixel_x1
        self._icc_profile = icc_profile
        self._expected_bytes = pixel_width * pixel_height * components
        self._input_bytes = 0

        user_unit = max(1, math.ceil(max(page_width_pt, page_height_pt) / 14_400.0))
        page_width = page_width_pt / user_unit
        page_height = page_height_pt / user_unit
        image_x = image_x_pt / user_unit
        image_width = image_width_pt / user_unit

        self._file.write(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        self._write_object(1, b"<< /Type /Catalog /Pages 2 0 R >>")
        self._write_object(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
        box = f"[0 0 {page_width:.8f} {page_height:.8f}]"
        self._write_object(
            3,
            (
                "<< /Type /Page /Parent 2 0 R "
                f"/MediaBox {box} /CropBox {box} /BleedBox {box} /TrimBox {box} /ArtBox {box} "
                f"/UserUnit {user_unit} /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>"
            ).encode("ascii"),
        )
        color_space = "[/ICCBased 7 0 R]" if icc_profile else {1: "/DeviceGray", 3: "/DeviceRGB", 4: "/DeviceCMYK"}[components]
        decode_entry = f" /Decode {decode}" if decode else ""
        self._offsets[4] = self._file.tell()
        self._file.write(
            (
                "4 0 obj\n<< /Type /XObject /Subtype /Image "
                f"/Width {pixel_width} /Height {pixel_height} /ColorSpace {color_space} "
                f"/BitsPerComponent 8 /Filter /FlateDecode /Length 6 0 R{decode_entry} >>\nstream\n"
            ).encode("ascii")
        )
        self._content = (
            f"q\n{image_width:.8f} 0 0 {page_height:.8f} {image_x:.8f} 0 cm\n/Im0 Do\nQ\n"
        ).encode("ascii")

    def _write_object(self, number: int, body: bytes) -> None:
        self._offsets[number] = self._file.tell()
        self._file.write(f"{number} 0 obj\n".encode("ascii"))
        self._file.write(body)
        self._file.write(b"\nendobj\n")

    def write(self, pixels: bytes) -> None:
        self._input_bytes += len(pixels)
        encoded = self._compressor.compress(pixels)
        self._file.write(encoded)
        self._stream_length += len(encoded)

    def finish(self) -> None:
        if self._input_bytes != self._expected_bytes:
            raise RuntimeError(
                f"Lossless PDF received {self._input_bytes} image bytes; expected {self._expected_bytes}."
            )
        encoded = self._compressor.flush()
        self._file.write(encoded)
        self._stream_length += len(encoded)
        self._file.write(b"\nendstream\nendobj\n")
        self._write_object(5, f"<< /Length {len(self._content)} >>\nstream\n".encode("ascii") + self._content + b"endstream")
        self._write_object(6, str(self._stream_length).encode("ascii"))
        if self._icc_profile:
            self._offsets[7] = self._file.tell()
            self._file.write(
                f"7 0 obj\n<< /N {self._components} /Alternate ".encode("ascii")
                + {1: b"/DeviceGray", 3: b"/DeviceRGB", 4: b"/DeviceCMYK"}[self._components]
                + f" /Length {len(self._icc_profile)} >>\nstream\n".encode("ascii")
            )
            self._file.write(self._icc_profile)
            self._file.write(b"\nendstream\nendobj\n")

        xref = self._file.tell()
        max_object = max(self._offsets)
        self._file.write(f"xref\n0 {max_object + 1}\n".encode("ascii"))
        self._file.write(b"0000000000 65535 f \n")
        for number in range(1, max_object + 1):
            self._file.write(f"{self._offsets.get(number, 0):010d} 00000 {'n' if number in self._offsets else 'f'} \n".encode("ascii"))
        self._file.write(
            f"trailer\n<< /Size {max_object + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
        )
        self._file.close()

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()


def _page_layout(page) -> tuple[int, int, int, str | None, bytes | None]:
    if page.is_tiled or int(page.planarconfig or 1) != 1:
        raise RuntimeError("Lossless Raster PDF requires a strip-based, contiguous TIFF.")
    if page.dtype != np.uint8:
        raise RuntimeError("Lossless Raster PDF currently supports 8-bit TIFF artwork.")
    orientation = page.tags.get("Orientation")
    if orientation is not None and int(orientation.value) != 1:
        raise RuntimeError("Lossless Raster PDF requires top-left TIFF orientation.")

    height, width = map(int, page.shape[:2])
    samples = int(page.samplesperpixel or 1)
    photometric = page.photometric.name
    if photometric == "SEPARATED" and samples == 4:
        components, decode = 4, None
    elif photometric == "RGB" and samples == 3:
        components, decode = 3, None
    elif photometric in {"MINISBLACK", "MINISWHITE"} and samples == 1:
        components, decode = 1, "[1 0]" if photometric == "MINISWHITE" else None
    else:
        raise RuntimeError(f"Unsupported lossless TIFF color layout: {photometric}, {samples} samples.")
    profile_tag = page.tags.get(34675)
    icc_profile = bytes(profile_tag.value) if profile_tag is not None else None
    return width, height, components, decode, icc_profile


def _iter_rows(tiff, page, *, width: int, height: int, components: int):
    rows_per_strip = int(page.rowsperstrip or height)
    row_bytes = width * components
    block_rows = max(1, _ROW_BLOCK_BYTES // row_bytes)
    file_handle = tiff.filehandle
    compression = int(page.compression)

    for strip_index, (offset, byte_count) in enumerate(zip(page.dataoffsets, page.databytecounts, strict=True)):
        first_row = strip_index * rows_per_strip
        rows = min(rows_per_strip, height - first_row)
        if rows <= 0:
            break
        if compression == 1:
            for relative_row in range(0, rows, block_rows):
                count = min(block_rows, rows - relative_row)
                file_handle.seek(offset + relative_row * row_bytes)
                data = file_handle.read(count * row_bytes)
                if len(data) != count * row_bytes:
                    raise RuntimeError("TIFF pixel data ended unexpectedly.")
                yield np.frombuffer(data, dtype=np.uint8).reshape(count, width, components)
            continue

        # Compressed strips must be decoded as a unit. Normal TIFFs use small
        # strips; oversized single-strip compressed TIFFs should be flattened
        # to uncompressed or multi-strip TIFF before this lossless path.
        if rows * row_bytes > 512 * 1024 * 1024:
            raise RuntimeError("Compressed TIFF strip is too large for lossless export; save it as uncompressed TIFF first.")
        file_handle.seek(offset)
        encoded = file_handle.read(byte_count)
        decoded, _position, _shape = page.decode(encoded, strip_index)
        pixels = np.asarray(decoded[0], dtype=np.uint8).reshape(rows, width, components)
        for relative_row in range(0, rows, block_rows):
            yield pixels[relative_row : relative_row + block_rows]


def export_lossless_tiff_pdf(
    source_path: Path,
    *,
    page_index: int,
    widths_mm: list[float],
    height_mm: float,
    bleed_mm: float,
    overlap_mm: float,
    overlap_mode: str,
    base_name: str,
    outdir: Path,
    overwrite: bool = False,
    cleanup_stale: bool = False,
    cancel_check=None,
    verify_outputs: bool = True,
    log_cb=None,
) -> list[Path]:
    """Split TIFF pixels into PDF panels without resampling or color conversion."""
    panel_layout, target_width_mm, _ = compute_panel_layout(widths_mm, bleed_mm, overlap_mm, overlap_mode)
    target_width_pt = mm_to_pt(target_width_mm)
    target_height_pt = mm_to_pt(height_mm + 2 * bleed_mm)
    final_paths = build_output_paths(outdir, base_name, len(panel_layout), "pdf", preserve_vectors=True)

    with tifffile.TiffFile(str(source_path)) as tiff:
        page = tiff.pages[page_index]
        width, height, components, decode, icc_profile = _page_layout(page)
        writers: list[_PdfImageWriter] = []
        with StagedOutputSet(final_paths, overwrite=overwrite, cleanup_stale=cleanup_stale) as outputs:
            try:
                x_scale = target_width_pt / width
                for panel, stage_path in zip(panel_layout, outputs.stage_paths, strict=True):
                    panel_x0_pt = mm_to_pt(panel.outer_left)
                    panel_x1_pt = mm_to_pt(panel.outer_right)
                    pixel_x0 = max(0, math.floor(panel_x0_pt / target_width_pt * width))
                    pixel_x1 = min(width, math.ceil(panel_x1_pt / target_width_pt * width))
                    writers.append(
                        _PdfImageWriter(
                            stage_path,
                            pixel_width=pixel_x1 - pixel_x0,
                            pixel_height=height,
                            pixel_x0=pixel_x0,
                            pixel_x1=pixel_x1,
                            components=components,
                            page_width_pt=panel_x1_pt - panel_x0_pt,
                            page_height_pt=target_height_pt,
                            image_x_pt=pixel_x0 * x_scale - panel_x0_pt,
                            image_width_pt=(pixel_x1 - pixel_x0) * x_scale,
                            decode=decode,
                            icc_profile=icc_profile,
                        )
                    )
                for rows in _iter_rows(tiff, page, width=width, height=height, components=components):
                    if cancel_check and cancel_check():
                        raise ExportCancelled("Export cancelled.")
                    for writer in writers:
                        writer.write(rows[:, writer.pixel_x0 : writer.pixel_x1, :].tobytes())

                for writer in writers:
                    writer.finish()
                if verify_outputs:
                    for path, panel in zip(outputs.stage_paths, panel_layout, strict=True):
                        verify_pdf_output(
                            path,
                            expected_size_pt=(mm_to_pt(panel.outer_width), target_height_pt),
                        )
                outputs.commit()
            finally:
                for writer in writers:
                    writer.close()

    if log_cb:
        log_cb(f"[LOSSLESS] Embedded original TIFF pixels into {len(final_paths)} PDF panel(s); no DPI rendering or resampling.")
    return final_paths
