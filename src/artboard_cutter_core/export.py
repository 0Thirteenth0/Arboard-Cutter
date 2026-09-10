from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .concurrency import PDF_OPERATION_LOCK
from .errors import ExportCancelled, ExportError
from .layout import compute_panel_layout
from .logging_config import get_logger, log_event
from .pdf_io import open_pdf_robust
from .profiles import validate_output_name
from .raster_export import export_artboards_streaming_from_src
from .units import mm_to_pt, pt_to_mm
from .vector_export import export_artboards_vector_uniform
from .validation import validate_export_values


@dataclass(frozen=True)
class ExportOptions:
    bleed_mm: float
    widths_mm: list[float]
    height_mm: float
    overlap_mm: float
    dpi: int
    output_root: Path
    overlap_mode: str = "shared"
    export_fmt: str = "pdf"
    preserve_vectors: bool = False
    vector_fit_mode: str = "stretch"
    page_index: int = 0
    output_name: str | None = None
    overwrite: bool = False
    cleanup_stale: bool = False
    cancel_check: Callable[[], bool] | None = None
    color_mode: str = "RGB"
    icc_mode: str = "Off"
    icc_profile_path: str = ""
    rendering_intent: str = "Perceptual"
    verify_outputs: bool = True


@dataclass(frozen=True)
class ExportResult:
    file_path: Path
    output_paths: tuple[Path, ...]
    panel_count: int


def process_file(file_path: Path, options: ExportOptions, log_cb=None) -> ExportResult:
    with PDF_OPERATION_LOCK:
        return _process_file_locked(file_path, options, log_cb=log_cb)


def _process_file_locked(file_path: Path, options: ExportOptions, log_cb=None) -> ExportResult:
    app_logger = get_logger("export", filename="export.log")
    vector_logger = get_logger("vector_export", filename="vector_mode.log")

    try:
        src = open_pdf_robust(file_path)
    except Exception as e:
        log_event(app_logger, 40, "source_open_failed", file=str(file_path), error=str(e))
        if log_cb:
            log_cb(f"[ERROR] {file_path}: {e}")
            log_cb("Tip: If this is a OneDrive file, right-click -> 'Always keep on this device'.")
        raise ExportError(f"Could not open source file: {file_path}") from e

    try:
        base_name = validate_output_name(options.output_name or file_path.stem)
        values = validate_export_values(
            output_name=base_name,
            bleed_mm=options.bleed_mm,
            widths_mm=options.widths_mm,
            height_mm=options.height_mm,
            overlap_mm=options.overlap_mm,
            overlap_mode=options.overlap_mode,
            dpi=options.dpi,
            export_format=options.export_fmt,
            preserve_vectors=options.preserve_vectors,
            color_mode=options.color_mode,
        )
        if options.page_index < 0 or options.page_index >= src.page_count:
            raise ValueError(
                f"Source page index {options.page_index} is outside the document's {src.page_count} page(s)."
            )
        if options.cancel_check and options.cancel_check():
            raise ExportCancelled("Export cancelled.")

        bleed_eff = values.bleed_mm
        panel_layout, target_w_mm, overlap_mm = compute_panel_layout(
            values.widths_mm,
            bleed_eff,
            values.overlap_mm,
            values.overlap_mode,
        )
        target_h_mm = values.height_mm + 2 * bleed_eff
        target_w_pt = mm_to_pt(target_w_mm)
        target_h_pt = mm_to_pt(target_h_mm)

        export_fmt = values.export_format
        preserve_vectors = values.preserve_vectors and getattr(src, "supports_pdf_preserve", True)

        if values.preserve_vectors and not preserve_vectors and log_cb:
            log_cb(
                "[FALLBACK] This oversized TIFF cannot use PDF Preserve; "
                "exporting it as a raster PDF at the safest available DPI."
            )

        if log_cb:
            log_cb("")
            log_cb("=" * 60)
            log_cb(f"Input: {file_path}")
            log_cb(
                f"Bleed: {values.bleed_mm:.1f} mm   Overlap: {overlap_mm:.1f} mm   "
                f"Mode: {values.overlap_mode}   Height: {values.height_mm:.1f} mm   Artboards: {len(values.widths_mm)}"
            )
            log_cb(f"Widths: {', '.join(str(int(w)) if float(w).is_integer() else str(w) for w in values.widths_mm)} mm")
            if preserve_vectors and options.vector_fit_mode == "width":
                page = src.load_page(options.page_index)
                scale = (target_w_pt / float(page.rect.width)) if page.rect.width else 1.0
                calc_h_mm = pt_to_mm(scale * float(page.rect.height))
                log_cb(f"Target full size (vector/fit WIDTH): {pt_to_mm(target_w_pt):.1f} x {calc_h_mm:.1f} mm")
            else:
                log_cb(f"Target full size: {pt_to_mm(target_w_pt):.1f} x {pt_to_mm(target_h_pt):.1f} mm")
            preserve_mode = "PDF PRESERVE (stretch)" if options.vector_fit_mode == "stretch" else f"PDF PRESERVE (fit {options.vector_fit_mode})"
            mode = preserve_mode if preserve_vectors else "RASTER (non-uniform)"
            color_note = "" if preserve_vectors else f"  Color: {values.color_mode}"
            log_cb(f"Mode: {mode}  Export as: {export_fmt.upper()}{color_note}  Output dir: {options.output_root}")

        log_event(
            app_logger,
            20,
            "export_file_start",
            file=str(file_path),
            page_index=options.page_index,
            panels=len(panel_layout),
            target_size_mm=[target_w_mm, target_h_mm],
            preserve_vectors=preserve_vectors,
            preserve_vectors_requested=values.preserve_vectors,
        )

        outdir = options.output_root
        outdir.mkdir(parents=True, exist_ok=True)

        if preserve_vectors:
            output_paths = export_artboards_vector_uniform(
                src,
                values.widths_mm,
                values.height_mm,
                values.bleed_mm,
                values.overlap_mm,
                values.overlap_mode,
                base_name,
                outdir,
                fit_mode=options.vector_fit_mode,
                page_index=options.page_index,
                log_cb=log_cb,
                structured_logger=vector_logger,
                overwrite=options.overwrite,
                cleanup_stale=options.cleanup_stale,
                cancel_check=options.cancel_check,
                verify_outputs=options.verify_outputs,
            )
        else:
            output_paths = export_artboards_streaming_from_src(
                src,
                values.widths_mm,
                values.height_mm,
                values.bleed_mm,
                values.overlap_mm,
                values.overlap_mode,
                base_name,
                outdir,
                values.dpi,
                export_fmt,
                log_cb,
                page_index=options.page_index,
                structured_logger=app_logger,
                overwrite=options.overwrite,
                cleanup_stale=options.cleanup_stale,
                cancel_check=options.cancel_check,
                color_mode=values.color_mode,
                source_path=file_path,
                icc_mode=options.icc_mode,
                icc_profile_path=options.icc_profile_path,
                rendering_intent=options.rendering_intent,
                verify_outputs=options.verify_outputs,
            )

        log_event(app_logger, 20, "export_file_done", file=str(file_path))
        if log_cb:
            log_cb(f"Done: {file_path.name}")
        return ExportResult(Path(file_path), tuple(output_paths), len(output_paths))
    except ExportCancelled:
        log_event(app_logger, 30, "export_file_cancelled", file=str(file_path))
        raise
    except Exception as exc:
        app_logger.exception(
            "export_file_failed",
            extra={"extra_data": {"action": "export_file_failed", "file": str(file_path), "error": str(exc)}},
        )
        raise ExportError(f"Export failed for {Path(file_path).name}: {exc}") from exc
    finally:
        try:
            src.close()
        except Exception:
            pass
