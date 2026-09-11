from __future__ import annotations

import logging
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    import fitz  # type: ignore

from .color_management import prepare_color_management
from .errors import ExportCancelled
from .layout import compute_panel_layout
from .logging_config import log_event
from .output_io import StagedOutputSet, build_output_paths
from .pdf_io import force_page_boxes
from .raster_images import PIL_AVAILABLE, Image, pixmap_to_pil, save_raster_pil
from .units import compute_scale_matrix, estimate_pixels, mm_to_pt, pt_to_mm
from .verification import verify_pdf_output, verify_raster_output

MAX_MP = 150
MAX_RENDER_BYTES = 500_000_000
MIN_RASTER_DPI = 72
TIFF_BAND_ROWS = 256
MAX_TIFF_BAND_BYTES = 64_000_000
BIGTIFF_THRESHOLD = 3_800_000_000


def choose_safe_raster_dpi(panel_sizes_pt, requested_dpi: int, color_mode: str) -> tuple[int, float]:
    """Choose one safe DPI for full-frame JPG/PDF renders."""
    requested = int(requested_dpi)
    components = 4 if str(color_mode).upper() == "CMYK" else 3
    max_pixels = max(estimate_pixels(width, height, requested) for width, height in panel_sizes_pt)
    allowed_pixels = min(MAX_MP * 1_000_000, MAX_RENDER_BYTES / components)
    if max_pixels <= allowed_pixels:
        return requested, max_pixels
    adjusted = int(requested * (allowed_pixels / max_pixels) ** 0.5)
    if adjusted < MIN_RASTER_DPI:
        raise ValueError(
            f"The largest panel is too large to render safely even at {MIN_RASTER_DPI} DPI. "
            "Reduce its dimensions or use Lossless PDF."
        )
    return adjusted, max_pixels


def should_use_bigtiff(width: int, height: int, components: int) -> bool:
    return int(width) * int(height) * int(components) >= BIGTIFF_THRESHOLD


def tiff_band_rows(width: int, components: int) -> int:
    """Choose a strip height that keeps uncompressed TIFF bands near 64 MB or less."""
    row_bytes = max(1, int(width)) * max(1, int(components))
    return max(1, min(TIFF_BAND_ROWS, MAX_TIFF_BAND_BYTES // row_bytes))


def _pixmap_is_unicolor(pix) -> bool:
    value = getattr(pix, "is_unicolor", False)
    return bool(value() if callable(value) else value)


def _source_crop_varies(page, clip_src, sx: float, sy: float, color_mode: str) -> bool:
    colorspace = fitz.csCMYK if str(color_mode).upper() == "CMYK" else fitz.csRGB
    diagnostic_dpi = 12
    diagnostic = page.get_pixmap(
        matrix=fitz.Matrix(sx * diagnostic_dpi / 72.0, sy * diagnostic_dpi / 72.0),
        clip=clip_src,
        colorspace=colorspace,
        alpha=False,
    )
    return not _pixmap_is_unicolor(diagnostic)


def _raise_if_silent_blank_render(page, pix, clip_src, sx: float, sy: float, color_mode: str) -> None:
    """Detect MuPDF's oversized-image failure mode where it returns blank pixels without raising."""
    if not _pixmap_is_unicolor(pix):
        return
    if _source_crop_varies(page, clip_src, sx, sy, color_mode):
        raise RuntimeError(
            "The raster engine returned a blank high-resolution panel even though the source crop contains artwork. "
            "Try a lower DPI or use Lossless PDF."
        )


def _pixmap_from_pil(image):
    mode = "CMYK" if image.mode == "CMYK" else "RGB"
    colorspace = fitz.csCMYK if mode == "CMYK" else fitz.csRGB
    return fitz.Pixmap(colorspace, image.width, image.height, image.tobytes(), False)


def _embed_pdf_output_intent(doc, profile_bytes: bytes | None, profile_name: str, components: int) -> None:
    if not profile_bytes:
        return
    profile_xref = doc.get_new_xref()
    alternate = "/DeviceCMYK" if components == 4 else "/DeviceRGB"
    doc.update_object(profile_xref, f"<< /N {components} /Alternate {alternate} >>")
    doc.update_stream(profile_xref, profile_bytes)
    intent_xref = doc.get_new_xref()
    identifier = (profile_name or "Output ICC profile").encode("utf-8").hex().upper()
    doc.update_object(
        intent_xref,
        f"<< /Type /OutputIntent /S /GTS_PDFX /OutputConditionIdentifier <{identifier}> "
        f"/DestOutputProfile {profile_xref} 0 R >>",
    )
    doc.xref_set_key(doc.pdf_catalog(), "OutputIntents", f"[{intent_xref} 0 R]")


def _write_streaming_tiff(
    *,
    path: Path,
    page,
    src_rect,
    x0_t: float,
    w_t: float,
    h_t: float,
    sx: float,
    sy: float,
    dpi: int,
    color_mode: str,
    color_management,
    cancel_check=None,
    log_cb=None,
) -> tuple[tuple[int, int], bool]:
    if not PIL_AVAILABLE:
        raise RuntimeError("TIFF export requires Pillow.")
    try:
        import numpy as np
        import tifffile
        # Import the extension directly. imagecodecs' package-level lazy
        # loader cannot reliably resolve optional codecs in one-file builds.
        from imagecodecs._zlib import zlib_encode
    except ImportError as exc:
        raise RuntimeError("Streaming TIFF export requires numpy, tifffile, and imagecodecs.") from exc

    output_mode = color_management.output_mode
    components = 4 if output_mode == "CMYK" else 3
    width_px = max(1, int(round((w_t / 72.0) * dpi)))
    height_px = max(1, int(round((h_t / 72.0) * dpi)))
    band_rows = tiff_band_rows(width_px, components)
    clip_src = fitz.Rect(
        src_rect.x0 + x0_t / sx,
        src_rect.y0,
        src_rect.x0 + (x0_t + w_t) / sx,
        src_rect.y0 + h_t / sy,
    )
    source_varies = _source_crop_varies(page, clip_src, sx, sy, color_mode)
    render_colorspace = fitz.csRGB if color_management.transform is not None else (
        fitz.csCMYK if output_mode == "CMYK" else fitz.csRGB
    )
    matrix = fitz.Matrix(sx * dpi / 72.0, sy * dpi / 72.0)

    def strips():
        for row0 in range(0, height_px, band_rows):
            if cancel_check and cancel_check():
                raise ExportCancelled("Export cancelled.")
            row1 = min(height_px, row0 + band_rows)
            y0_t = row0 * 72.0 / dpi
            y1_t = row1 * 72.0 / dpi
            band_clip = fitz.Rect(
                src_rect.x0 + x0_t / sx,
                src_rect.y0 + y0_t / sy,
                src_rect.x0 + (x0_t + w_t) / sx,
                src_rect.y0 + y1_t / sy,
            )
            pix = page.get_pixmap(matrix=matrix, clip=band_clip, colorspace=render_colorspace, alpha=False)
            band = pixmap_to_pil(pix)
            expected = (width_px, row1 - row0)
            if band.size != expected:
                band = band.resize(expected, resample=Image.BICUBIC)
            band = color_management.apply(band)
            array = np.asarray(band, dtype=np.uint8)
            # Tifffile accepts pre-compressed strip bytes without materializing
            # the complete image. Each yielded item is one Deflate strip.
            yield zlib_encode(array.tobytes())

    bigtiff = should_use_bigtiff(width_px, height_px, components)
    with tifffile.TiffWriter(str(path), bigtiff=bigtiff) as writer:
        writer.write(
            strips(),
            shape=(height_px, width_px, components),
            dtype=np.uint8,
            photometric="separated" if output_mode == "CMYK" else "rgb",
            planarconfig="contig",
            compression="deflate",
            predictor=False,
            rowsperstrip=band_rows,
            resolution=(dpi, dpi),
            resolutionunit="inch",
            iccprofile=color_management.profile_bytes,
            metadata=None,
            software="Artboard Cutter",
        )
    if log_cb:
        kind = "BigTIFF" if bigtiff else "TIFF"
        log_cb(f"[TIFF] streamed in {band_rows}-row bands ({kind}, Deflate)")
    return (width_px, height_px), source_varies


def export_artboards_streaming_from_src(
    src_doc,
    widths_mm,
    height_mm,
    bleed_mm,
    overlap_mm,
    overlap_mode,
    base_name,
    outdir: Path,
    dpi: int,
    export_fmt: str = "pdf",
    log_cb=None,
    page_index: int = 0,
    structured_logger: logging.Logger | None = None,
    overwrite: bool = False,
    cleanup_stale: bool = False,
    cancel_check=None,
    color_mode: str = "RGB",
    source_path: Path | None = None,
    icc_mode: str = "Off",
    icc_profile_path: str = "",
    rendering_intent: str = "Perceptual",
    verify_outputs: bool = True,
):
    page = src_doc.load_page(page_index)
    src_rect = page.rect
    export_fmt_lc = (export_fmt or "pdf").lower()

    bleed_eff = max(0.0, float(bleed_mm))
    panel_layout, target_w_mm, overlap_mm = compute_panel_layout(widths_mm, bleed_eff, overlap_mm, overlap_mode)
    target_h_mm = height_mm + 2 * bleed_eff
    target_w_pt = mm_to_pt(target_w_mm)
    target_h_pt = mm_to_pt(target_h_mm)
    sx, sy = compute_scale_matrix(src_rect, target_w_pt, target_h_pt)
    final_paths = build_output_paths(outdir, base_name, len(panel_layout), export_fmt)
    panel_sizes_pt = [(mm_to_pt(p.outer_right - p.outer_left), target_h_pt) for p in panel_layout]
    # TIFF is rendered in bounded bands, so it can retain the requested DPI.
    eff_dpi, largest_requested_pixels = (int(dpi), max(estimate_pixels(w, h, dpi) for w, h in panel_sizes_pt))
    if export_fmt_lc not in ("tif", "tiff"):
        eff_dpi, largest_requested_pixels = choose_safe_raster_dpi(panel_sizes_pt, dpi, color_mode)

    if log_cb and eff_dpi != dpi:
        components = 4 if str(color_mode).upper() == "CMYK" else 3
        log_cb(
            f"[SAFE] Largest panel requested ~{largest_requested_pixels / 1e6:.1f} MP in {color_mode.upper()}; "
            f"using {eff_dpi} DPI for every panel to stay below the "
            f"{MAX_RENDER_BYTES / 1e6:.0f} MB render limit ({components} channels)."
        )

    color_management = prepare_color_management(
        source_path=Path(source_path or ""),
        color_mode=color_mode,
        icc_mode=icc_mode,
        output_profile_path=icc_profile_path,
        rendering_intent=rendering_intent,
    )
    if log_cb and color_management.mode != "Off":
        action = "converted to" if color_management.mode == "Convert" else "embedded"
        log_cb(f"[ICC] {action} {color_management.profile_name}")

    log_event(
        structured_logger,
        logging.INFO,
        "raster_export_start",
        base_name=base_name,
        target_size_mm=[target_w_mm, target_h_mm],
        overlap_mode=overlap_mode,
        scale=[sx, sy],
        requested_dpi=dpi,
        effective_dpi=eff_dpi,
        color_mode=color_mode,
        icc_mode=color_management.mode,
    )

    with StagedOutputSet(final_paths, overwrite=overwrite, cleanup_stale=cleanup_stale) as outputs:
        for idx, panel in enumerate(panel_layout):
            if cancel_check and cancel_check():
                raise ExportCancelled("Export cancelled.")
            left_mm, right_mm = panel.outer_left, panel.outer_right
            x0_t, x1_t = mm_to_pt(left_mm), mm_to_pt(right_mm)
            w_t, h_t = x1_t - x0_t, target_h_pt
            clip_src = fitz.Rect(
                src_rect.x0 + x0_t / sx,
                src_rect.y0,
                src_rect.x0 + x1_t / sx,
                src_rect.y0 + h_t / sy,
            )
            target_w_px = max(1, int(round((w_t / 72.0) * eff_dpi)))
            target_h_px = max(1, int(round((h_t / 72.0) * eff_dpi)))
            out_name = final_paths[idx].name
            out_path = outputs.stage_paths[idx]

            log_event(
                structured_logger,
                logging.INFO,
                "raster_compute_crop",
                panel=idx + 1,
                crop_rect_mm=[left_mm, 0.0, right_mm, target_h_mm],
                source_clip_pt=[clip_src.x0, clip_src.y0, clip_src.x1, clip_src.y1],
                output_size_pt=[w_t, h_t],
                dpi=eff_dpi,
            )

            if export_fmt_lc in ("tif", "tiff"):
                expected_size, source_varies = _write_streaming_tiff(
                    path=out_path,
                    page=page,
                    src_rect=src_rect,
                    x0_t=x0_t,
                    w_t=w_t,
                    h_t=h_t,
                    sx=sx,
                    sy=sy,
                    dpi=eff_dpi,
                    color_mode=color_mode,
                    color_management=color_management,
                    cancel_check=cancel_check,
                    log_cb=log_cb,
                )
                if verify_outputs:
                    result = verify_raster_output(
                        out_path,
                        expected_size=expected_size,
                        expected_dpi=eff_dpi,
                        expected_mode=color_management.output_mode,
                        source_varies=source_varies,
                        expect_icc=color_management.profile_bytes is not None,
                    )
                    if log_cb:
                        log_cb(f"[VERIFY] {result.summary}")
            else:
                render_colorspace = fitz.csRGB if color_management.transform is not None else (
                    fitz.csCMYK if color_management.output_mode == "CMYK" else fitz.csRGB
                )
                render_matrix = fitz.Matrix(sx * eff_dpi / 72.0, sy * eff_dpi / 72.0)
                pix = page.get_pixmap(matrix=render_matrix, clip=clip_src, colorspace=render_colorspace, alpha=False)
                _raise_if_silent_blank_render(page, pix, clip_src, sx, sy, color_mode)
                source_varies = not _pixmap_is_unicolor(pix)
                pil_im = pixmap_to_pil(pix) if PIL_AVAILABLE else None
                if pil_im is not None and pil_im.size != (target_w_px, target_h_px):
                    pil_im = pil_im.resize((target_w_px, target_h_px), resample=Image.BICUBIC)
                if pil_im is not None:
                    pil_im = color_management.apply(pil_im)

                if export_fmt_lc == "pdf":
                    output_pix = _pixmap_from_pil(pil_im) if pil_im is not None else pix
                    out = fitz.open()
                    try:
                        out_page = out.new_page(width=w_t, height=h_t)
                        force_page_boxes(out_page)
                        out_page.insert_image(out_page.rect, pixmap=output_pix, keep_proportion=False)
                        _embed_pdf_output_intent(
                            out,
                            color_management.profile_bytes,
                            color_management.profile_name,
                            4 if color_management.output_mode == "CMYK" else 3,
                        )
                        out.save(out_path)
                    finally:
                        out.close()
                    if verify_outputs:
                        result = verify_pdf_output(out_path, expected_size_pt=(w_t, h_t))
                        if source_varies and result.uniform:
                            raise RuntimeError(
                                f"Output verification failed for {out_name}: output is blank/uniform but source contains artwork."
                            )
                        if log_cb:
                            log_cb(f"[VERIFY] {result.summary}")
                else:
                    if pil_im is None:
                        raise RuntimeError("JPG export requires Pillow.")
                    save_raster_pil(
                        pil_im,
                        out_path,
                        export_fmt_lc,
                        eff_dpi,
                        log_cb,
                        icc_profile=color_management.profile_bytes,
                    )
                    if verify_outputs:
                        result = verify_raster_output(
                            out_path,
                            expected_size=(target_w_px, target_h_px),
                            expected_dpi=eff_dpi,
                            expected_mode=color_management.output_mode,
                            source_varies=source_varies,
                            expect_icc=color_management.profile_bytes is not None,
                        )
                        if log_cb:
                            log_cb(f"[VERIFY] {result.summary}")

            if log_cb:
                log_cb(
                    f"[CROP] {out_name}: x=[{pt_to_mm(x0_t):.3f},{pt_to_mm(x1_t):.3f}] mm  "
                    f"w={pt_to_mm(w_t):.3f} mm  h={pt_to_mm(h_t):.3f} mm  dpi={eff_dpi}"
                )
        if cancel_check and cancel_check():
            raise ExportCancelled("Export cancelled.")
        outputs.commit()
    return final_paths
