#!/usr/bin/env python3
import threading
import queue
import os
import math
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

# Optional drag-and-drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    BaseTk = TkinterDnD.Tk
    DND_AVAILABLE = True
except Exception:
    BaseTk = tk.Tk
    DND_AVAILABLE = False
    DND_FILES = None

try:
    import pymupdf as fitz
except ImportError:  # PyMuPDF before the pymupdf import name was introduced.
    import fitz  # type: ignore

from src.artboard_cutter_core.concurrency import PDF_OPERATION_LOCK
from src.artboard_cutter_core.errors import ExportCancelled
from src.artboard_cutter_core.export import ExportOptions, process_file as core_process_file
from src.artboard_cutter_core.layout import (
    add_evenly_distributed_panel as core_add_evenly_distributed_panel,
    compute_panel_layout as core_compute_panel_layout,
    compute_preview_page_height,
    parse_widths_list as core_parse_widths_list,
    resize_adjacent_panel_widths as core_resize_adjacent_panel_widths,
    redistribute_panel_widths as core_redistribute_panel_widths,
)
from src.artboard_cutter_core.lossless_tiff_pdf import export_lossless_tiff_pdf
from src.artboard_cutter_core.color_management import ICC_MODES, RENDERING_INTENTS
from src.artboard_cutter_core.modes import (
    PDF_PRESERVE_EXPORT_MODE,
    is_pdf_preserve_mode as core_is_pdf_preserve_mode,
    normalize_export_mode as core_normalize_export_mode,
)
from src.artboard_cutter_core.output_io import build_output_paths, find_duplicate_paths, find_stale_panel_outputs
from src.artboard_cutter_core.validation import validate_export_values
from src.artboard_cutter_core.illustrator_integration import get_illustrator_artboard_names
from src.artboard_cutter_core.jobs import default_recovery_job_path, load_job, save_job, startup_job_path
from src.artboard_cutter_core.preflight import combined_disk_space_warning, estimate_export_job, format_bytes
from src.artboard_cutter_core.pdf_io import force_page_boxes as core_force_page_boxes, open_pdf_robust as core_open_pdf_robust
from src.artboard_cutter_core.profiles import (
    ArtworkProfile,
    create_artwork_profiles as core_create_artwork_profiles,
    make_unique_output_names,
    sanitize_output_name,
    validate_output_name as core_validate_output_name,
)
from src.artboard_cutter_core.raster_export import export_artboards_streaming_from_src as core_export_raster
from src.artboard_cutter_core.raster_images import pixmap_to_pil
from src.artboard_cutter_core.settings import AppSettings, default_log_dir, default_output_dir, load_settings, save_settings
from src.artboard_cutter_core.themes import THEME_NAMES, get_theme, normalize_theme_name
from src.artboard_cutter_core.units import (
    compute_scale_matrix as core_compute_scale_matrix,
    estimate_pixels as core_estimate_pixels,
    fmt_mm as core_fmt_mm,
    mm_to_pt as core_mm_to_pt,
    pt_to_mm as core_pt_to_mm,
    preview_render_scale,
)
from src.artboard_cutter_core.vector_export import export_artboards_vector_uniform as core_export_vector
from src.artboard_cutter_core.version import APP_VERSION
from src.artboard_cutter_core.workflow import PendingExportJob, ProfileExportValues

# --- TIFF / JPG helpers via Pillow (NO TiffImagePlugin usage) ---
try:
    from PIL import Image
    PIL_AVAILABLE = True
    try:
        Image.MAX_IMAGE_PIXELS = None  # allow very large images
    except Exception:
        pass
except Exception:
    PIL_AVAILABLE = False

# Optional: ImageTk for drawing preview images on Canvas
try:
    from PIL import ImageTk  # type: ignore
    IMAGE_TK_AVAILABLE = True
except Exception:
    IMAGE_TK_AVAILABLE = False

# ---------------------- Units & helpers ----------------------

def mm_to_pt(mm: float) -> float:
    return core_mm_to_pt(mm)

def pt_to_mm(pt: float) -> float:
    return core_pt_to_mm(pt)

def force_page_boxes(page):
    return core_force_page_boxes(page)

def open_pdf_robust(p: Path):
    return core_open_pdf_robust(p)

def compute_scale_matrix(src_rect, target_w_pt, target_h_pt):
    return core_compute_scale_matrix(src_rect, target_w_pt, target_h_pt)

def estimate_pixels(w_pt, h_pt, dpi):
    return core_estimate_pixels(w_pt, h_pt, dpi)

def fmt_mm(v: float) -> str:
    return core_fmt_mm(v)

def parse_widths_list(s: str):
    return core_parse_widths_list(s)

def validate_output_name(name: str) -> str:
    return core_validate_output_name(name)

def resource_path(relative_path: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path

def normalize_overlap_mode(mode: str) -> str:
    return "Left" if (mode or "").strip().lower().startswith("left") else "Shared"

def overlap_mode_key(mode: str) -> str:
    return "left" if normalize_overlap_mode(mode) == "Left" else "shared"

def normalize_export_mode(mode: str) -> str:
    return core_normalize_export_mode(mode)

def compute_panel_layout(widths_mm, bleed_mm, overlap_mm, overlap_mode="Shared"):
    """
    Build per-panel horizontal extents so that:
      - bleed applies only to the outer edges (first/last panel)
      - shared mode overlaps are split equally between adjacent panels
      - left mode places full internal overlap on the right-hand panel's left edge
    Returns (layout, total_width_mm, overlap_eff) where layout is a list of dicts:
      {"outer_left", "outer_right", "content_left", "content_right", "width"}
    """
    layout, total_width, overlap_eff = core_compute_panel_layout(widths_mm, bleed_mm, overlap_mm, overlap_mode_key(overlap_mode))
    return [panel.to_legacy_dict() for panel in layout], total_width, overlap_eff


# ---------------------- Core processing ----------------------
# Raster path resamples to exact pixels and writes DPI metadata.
def export_artboards_streaming_from_src(
    src_doc,
    widths_mm,
    height_mm,
    bleed_mm,
    overlap_mm,
    base_name,
    outdir: Path,
    dpi: int,
    export_fmt: str = "pdf",
    log_cb=None,
    overlap_mode="Shared",
):
    return core_export_raster(
        src_doc,
        widths_mm,
        height_mm,
        bleed_mm,
        overlap_mm,
        overlap_mode_key(overlap_mode),
        base_name,
        outdir,
        dpi,
        export_fmt,
        log_cb=log_cb,
    )

# Vector (uniform) path with fit mode (unchanged)
def export_artboards_vector_uniform(
    src_doc,
    widths_mm,
    height_mm,
    bleed_mm,
    overlap_mm,
    base_name,
    outdir: Path,
    fit_mode: str = "height",  # "height" or "width"
    log_cb=None,
    overlap_mode="Shared",
):
    return core_export_vector(
        src_doc,
        widths_mm,
        height_mm,
        bleed_mm,
        overlap_mm,
        overlap_mode_key(overlap_mode),
        base_name,
        outdir,
        fit_mode,
        log_cb=log_cb,
    )

def process_file(
    file_path: Path,
    bleed_mm: float,
    widths_mm,
    height_mm: float,
    overlap_mm: float,
    dpi: int,
    output_root: Path,
    overlap_mode: str = "Shared",
    export_fmt: str = "pdf",
    preserve_vectors: bool = False,
    vector_fit_mode: str = "stretch",  # "stretch", "height", or "width"
    page_index: int = 0,
    output_name: str | None = None,
    overwrite: bool = False,
    cleanup_stale: bool = False,
    cancel_check=None,
    color_mode: str = "RGB",
    icc_mode: str = "Off",
    icc_profile_path: str = "",
    rendering_intent: str = "Perceptual",
    verify_outputs: bool = True,
    log_cb=None,
):
    return core_process_file(
        file_path,
        ExportOptions(
            bleed_mm=bleed_mm,
            widths_mm=list(widths_mm),
            height_mm=height_mm,
            overlap_mm=overlap_mm,
            overlap_mode=overlap_mode_key(overlap_mode),
            dpi=dpi,
            output_root=output_root,
            export_fmt=export_fmt,
            preserve_vectors=preserve_vectors,
            vector_fit_mode=vector_fit_mode,
            page_index=page_index,
            output_name=output_name,
            overwrite=overwrite,
            cleanup_stale=cleanup_stale,
            cancel_check=cancel_check,
            color_mode=color_mode,
            icc_mode=icc_mode,
            icc_profile_path=icc_profile_path,
            rendering_intent=rendering_intent,
            verify_outputs=verify_outputs,
        ),
        log_cb=log_cb,
    )


# ---------------------- THEME ----------------------
def apply_theme(root: tk.Tk, style: ttk.Style, theme_name: str):
    theme = get_theme(theme_name)
    C = theme.colors
    root._theme_tokens = C
    # base window + text
    root.configure(bg=C["app_bg"])
    root.option_clear()
    style.theme_use("clam")

    # General fonts/colors
    font = ("Segoe UI", 9)
    style.configure(
        ".",
        background=C["card_bg"],
        foreground=C["text_primary"],
        font=font,
        bordercolor=C["card_border"],
        lightcolor=C["card_border"],
        darkcolor=C["card_border"],
    )

    # Containers / frames
    style.configure("TFrame", background=C["app_bg"])
    style.configure("Root.TFrame", background=C["app_bg"])
    style.configure("CardBody.TFrame", background=C["card_bg"])
    style.configure("Toolbar.TFrame", background=C["toolbar_bg"])
    style.configure("FieldGrid.TFrame", background=C["card_bg"])
    style.configure(
        "Card.TFrame",
        background=C["card_bg"],
        bordercolor=C["card_border"],
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "TLabelframe",
        background=C["card_bg"],
        foreground=C["text_primary"],
        bordercolor=C["card_border"],
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "TLabelframe.Label",
        background=C["card_bg"],
        foreground=C["text_primary"],
        font=("Segoe UI", 10, "bold"),
    )

    # Labels
    style.configure("TLabel", background=C["card_bg"], foreground=C["text_primary"])
    style.configure("Root.TLabel", background=C["app_bg"], foreground=C["text_primary"])
    style.configure("Title.TLabel", background=C["app_bg"], foreground=C["text_primary"], font=("Segoe UI", 15, "bold"))
    style.configure("Muted.TLabel", background=C["card_bg"], foreground=C["text_secondary"])
    style.configure("RootMuted.TLabel", background=C["app_bg"], foreground=C["text_secondary"])
    style.configure("Section.TLabel", background=C["card_bg"], foreground=C["text_primary"], font=("Segoe UI", 10, "bold"))
    style.configure("Field.TLabel", background=C["card_bg"], foreground=C["text_primary"])
    style.configure("Toolbar.TLabel", background=C["toolbar_bg"], foreground=C["text_primary"])
    style.configure("ToolbarMuted.TLabel", background=C["toolbar_bg"], foreground=C["text_secondary"])
    style.configure("Empty.TLabel", background=C["table_row_bg"], foreground=C["text_secondary"], font=("Segoe UI", 10))
    style.configure("Badge.TLabel", background=C["tip_bg"], foreground=C["text_secondary"], padding=(6, 2))

    # Buttons
    button_hover = C["button_hover"]
    style.configure(
        "TButton",
        background=C["button_bg"],
        foreground=C["text_primary"],
        bordercolor=C["button_border"],
        focusthickness=1,
        padding=(11, 7),
        relief="flat",
    )
    style.configure(
        "Tool.TButton",
        background=C["button_bg"],
        foreground=C["text_primary"],
        bordercolor=C["button_border"],
        padding=(8, 6),
        relief="flat",
    )
    style.configure(
        "Danger.TButton",
        background=C["button_bg"],
        foreground=C["danger"],
        bordercolor=C["button_border"],
        padding=(11, 7),
        relief="flat",
    )
    style.configure(
        "Accent.TButton",
        background=C["primary_button_bg"],
        foreground="#ffffff",
        bordercolor=C["primary_button_bg"],
        focusthickness=1,
        padding=(13, 8),
        relief="flat",
    )
    style.map("TButton",
              background=[("disabled", C["card_bg_raised"]), ("active", button_hover), ("pressed", C["selection_bg"])],
              foreground=[("disabled", C["text_secondary"]), ("active", C["text_primary"]), ("pressed", C["selection_fg"])],
              bordercolor=[("active", C["accent"]), ("pressed", C["accent"])],
              relief=[("pressed", "flat")])
    style.map("Tool.TButton",
              background=[("disabled", C["card_bg_raised"]), ("active", button_hover), ("pressed", C["selection_bg"])],
              foreground=[("disabled", C["text_secondary"]), ("active", C["text_primary"]), ("pressed", C["selection_fg"])],
              bordercolor=[("active", C["accent"]), ("pressed", C["accent"])])
    style.map("Danger.TButton",
              background=[("disabled", C["card_bg_raised"]), ("active", button_hover), ("pressed", C["selection_bg"])],
              foreground=[("disabled", C["text_secondary"]), ("active", C["danger"]), ("pressed", C["danger"])],
              bordercolor=[("active", C["danger"]), ("pressed", C["danger"])])
    style.map("Accent.TButton",
              background=[("disabled", C["card_bg_raised"]), ("active", C["primary_button_hover"]), ("pressed", C["primary_button_bg"])],
              foreground=[("disabled", C["text_secondary"]), ("active", "#ffffff"), ("pressed", "#ffffff")],
              bordercolor=[("active", C["primary_button_hover"]), ("pressed", C["primary_button_bg"])])

    # Entries / Combobox / Spinbox
    style.configure(
        "TEntry",
        fieldbackground=C["input_bg"],
        foreground=C["text_primary"],
        bordercolor=C["input_border"],
        insertcolor=C["text_primary"],
        padding=(8, 6),
        relief="flat",
    )
    style.configure(
        "TCombobox",
        fieldbackground=C["input_bg"],
        foreground=C["text_primary"],
        bordercolor=C["input_border"],
        selectbackground=C["input_bg"],
        selectforeground=C["text_primary"],
        padding=(7, 5),
    )
    style.configure(
        "PanelCount.TSpinbox",
        fieldbackground=C["input_bg"],
        background=C["input_bg"],
        foreground=C["text_primary"],
        arrowcolor=C["text_primary"],
        bordercolor=C["input_border"],
        lightcolor=C["input_border"],
        darkcolor=C["input_border"],
        insertcolor=C["text_primary"],
        selectbackground=C["selection_bg"],
        selectforeground=C["selection_fg"],
        padding=(5, 4),
        relief="flat",
    )
    style.map("TEntry",
              fieldbackground=[("disabled", C["card_bg_raised"]), ("readonly", C["input_bg"])],
              foreground=[("disabled", C["text_secondary"])])
    style.map("TCombobox",
              fieldbackground=[("disabled", C["card_bg_raised"]), ("readonly", C["input_bg"]), ("active", C["input_bg"])],
              background=[("disabled", C["card_bg_raised"]), ("readonly", C["input_bg"]), ("active", C["input_bg"])],
              foreground=[("disabled", C["text_secondary"]), ("readonly", C["text_primary"]), ("active", C["text_primary"])])
    style.map(
        "PanelCount.TSpinbox",
        fieldbackground=[
            ("disabled", C["card_bg_raised"]),
            ("readonly", C["input_bg"]),
            ("focus", C["input_bg"]),
            ("active", C["input_bg"]),
        ],
        background=[
            ("disabled", C["card_bg_raised"]),
            ("readonly", C["input_bg"]),
            ("focus", C["input_bg"]),
            ("active", C["button_hover"]),
        ],
        foreground=[
            ("disabled", C["text_secondary"]),
            ("readonly", C["text_primary"]),
            ("focus", C["text_primary"]),
            ("active", C["text_primary"]),
        ],
        arrowcolor=[
            ("disabled", C["text_secondary"]),
            ("active", C["accent"]),
            ("pressed", C["selection_fg"]),
        ],
        bordercolor=[("focus", C["accent"]), ("active", C["border_strong"])],
    )

    # Toggle controls. Explicit active/selected maps prevent native ttk from
    # painting radio/check labels with a bright platform highlight.
    for toggle_style in ("TCheckbutton", "TRadiobutton"):
        style.configure(
            toggle_style,
            background=C["card_bg"],
            foreground=C["text_primary"],
            indicatorbackground=C["input_bg"],
            indicatorforeground=C["text_primary"],
            focuscolor=C["card_bg"],
            bordercolor=C["input_border"],
        )
        style.map(
            toggle_style,
            background=[
                ("disabled", C["card_bg"]),
                ("pressed", C["card_bg"]),
                ("active", C["card_bg"]),
                ("selected", C["card_bg"]),
            ],
            foreground=[
                ("disabled", C["text_secondary"]),
                ("pressed", C["text_primary"]),
                ("active", C["text_primary"]),
                ("selected", C["text_primary"]),
            ],
            indicatorbackground=[
                ("disabled", C["card_bg_raised"]),
                ("selected", C["input_bg"]),
                ("active", C["input_bg"]),
            ],
        )

    # Progressbar
    style.configure("TProgressbar", background=C["accent"], troughcolor=C["card_bg_raised"], bordercolor=C["card_border"])
    style.configure(
        "Vertical.TScrollbar",
        background=C["scrollbar"],
        troughcolor=C["card_bg_raised"],
        bordercolor=C["card_bg_raised"],
        arrowcolor=C["text_secondary"],
        relief="flat",
    )
    style.map(
        "Vertical.TScrollbar",
        background=[("active", C["border_strong"]), ("pressed", C["border_strong"])],
        arrowcolor=[("active", C["text_primary"])],
    )

    # Treeview
    style.configure("Treeview",
                    background=C["table_row_bg"],
                    fieldbackground=C["table_row_bg"],
                    foreground=C["text_primary"],
                    bordercolor=C["card_border"],
                    rowheight=30,
                    relief="flat")
    style.map("Treeview",
              background=[("selected", C["table_selected_bg"])],
              foreground=[("selected", C["table_selected_fg"])])
    style.configure("Treeview.Heading",
                    background=C["table_header_bg"],
                    foreground=C["text_primary"],
                    bordercolor=C["card_border"],
                    font=("Segoe UI", 9, "bold"),
                    padding=(7, 8),
                    relief="flat")
    style.map("Treeview.Heading",
              background=[("active", C["table_header_bg"]), ("pressed", C["table_header_bg"])],
              foreground=[("active", C["text_primary"]), ("pressed", C["text_primary"])],
              bordercolor=[("active", C["card_border"]), ("pressed", C["card_border"])],
              relief=[("pressed", "flat")])

    # Patch Text widgets (manually)
    for child in root.winfo_children():
        _patch_text_colors(child, C, root)
    if hasattr(root, "_side_scroll_canvas"):
        root._side_scroll_canvas.configure(bg=C["app_bg"])
    if hasattr(root, "preview_canvas"):
        root.preview_canvas.configure(bg=C["canvas_bg"])

def _patch_text_colors(widget, C, root):
    if isinstance(widget, tk.Text):
        widget.configure(
            bg=C["input_bg"],
            fg=C["text_primary"],
            insertbackground=C["text_primary"],
            selectbackground=C["selection_bg"],
            selectforeground=C["selection_fg"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=C["card_border"],
            highlightcolor=C["accent"],
        )
    # Patch Canvas background to match theme panel
    if isinstance(widget, tk.Canvas):
        widget.configure(bg=C.get("canvas_bg", C["card_bg"]))
    for ch in widget.winfo_children():
        _patch_text_colors(ch, C, root)


class PreflightCancelled(Exception):
    """Raised when the operator deliberately stops before export begins."""


# ---------------------- GUI ----------------------
class App(BaseTk):
    def __init__(self, startup_job: Path | None = None):
        super().__init__()
        self.title("Artboard Cutter")
        icon_path = resource_path("assets/artboard_cutter.ico")
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass
        self._settings = load_settings()
        self.geometry(self._settings.window_geometry or "1060x840")
        self.minsize(760, 520)

        self._style = ttk.Style(self)
        self.theme_var = tk.StringVar(value=normalize_theme_name(self._settings.theme))
        self.dark_mode = tk.BooleanVar(value=get_theme(self.theme_var.get()).is_dark)
        apply_theme(self, self._style, self.theme_var.get())
        self.theme_var.trace_add("write", self._on_theme_changed)
        self._icons = self._load_icons()

        # state for aspect ratio sync
        self._src_w_mm = None
        self._src_h_mm = None
        self._src_ar = None
        self._syncing = False
        self._profiles = {}
        self._file_groups = {}
        self._active_iid = None
        self._loading_profile = False
        self._export_events = queue.Queue()
        self._export_thread = None
        self._export_cancel_event = threading.Event()
        self._export_running = False
        self._close_after_export = False
        self._settings_enabled = False
        self._pending_import_paths = set()
        self._import_generation = 0
        self._preview_request = None
        self._recovery_save_after_id = None
        self._poll_after_id = None
        self._recovery_offer_after_id = None
        self._startup_job_after_id = None
        self._startup_job_path = Path(startup_job) if startup_job is not None else None
        self._recovery_path = default_recovery_job_path()
        self._build_modern_ui()
        self._poll_after_id = self.after(50, self._poll_export_events)
        if self._startup_job_path is not None:
            self._startup_job_after_id = self.after(100, self._load_startup_job)
        else:
            self._recovery_offer_after_id = self.after(400, self._offer_session_recovery)

    def destroy(self):
        for attribute in (
            "_poll_after_id",
            "_recovery_offer_after_id",
            "_recovery_save_after_id",
            "_startup_job_after_id",
        ):
            after_id = getattr(self, attribute, None)
            if after_id is not None:
                try:
                    self.after_cancel(after_id)
                except Exception:
                    pass
                setattr(self, attribute, None)
        super().destroy()

    def _load_icons(self) -> dict[str, tk.PhotoImage]:
        icons: dict[str, tk.PhotoImage] = {}
        names = [
            "add_files",
            "trash",
            "clear",
            "check_all",
            "uncheck",
            "check_selected",
            "zoom_in",
            "zoom_out",
            "fit",
            "add_panel",
            "export",
            "folder",
            "browse_folder",
            "settings",
            "queue",
            "preview",
            "warning",
        ]
        for name in names:
            path = resource_path(f"assets/icons/icon_{name}.png")
            if path.exists():
                try:
                    icons[name] = tk.PhotoImage(file=str(path))
                except Exception:
                    pass
        return icons

    def _icon(self, name: str):
        return getattr(self, "_icons", {}).get(name)

    def _button(self, parent, text: str, command, icon: str | None = None, style: str = "TButton", **kwargs):
        image = self._icon(icon) if icon else None
        if image is not None:
            kwargs.setdefault("compound", "left")
            kwargs.setdefault("image", image)
        return ttk.Button(parent, text=text, command=command, style=style, **kwargs)

    # ---------- Settings persistence ----------
    def _selected_or_recent_file_path(self) -> str:
        sel = self.files_tree.selection()
        if sel:
            profile = self._profiles.get(sel[-1])
            if profile:
                return profile.file_path
        children = self.files_tree.get_children("")
        if children:
            leaf = self._first_profile_iid(children[-1]) or children[-1]
            profile = self._profiles.get(leaf)
            if profile:
                return profile.file_path
        return self._settings.last_input_path

    def _collect_settings(self) -> AppSettings:
        self._save_selected_profile_settings()
        recent_files = list(dict.fromkeys(
            [profile.file_path for profile in self._profiles.values()] + (self._settings.recent_files or [])
        ))[:10]
        recent_output_dirs = list(dict.fromkeys(
            [self.outdir_var.get()] + (self._settings.recent_output_dirs or [])
        ))[:10]
        return AppSettings(
            last_input_path=self._selected_or_recent_file_path(),
            last_output_dir=self.outdir_var.get(),
            bleed_mm=self.bleed_var.get(),
            overlap_mm=self.overlap_var.get(),
            overlap_mode=self.overlap_mode_var.get(),
            dpi=self.dpi_var.get(),
            color_mode=self.color_mode_var.get(),
            export_format=self.format_var.get(),
            export_mode=self.export_mode_var.get(),
            icc_mode=self.icc_mode_var.get(),
            icc_profile_path=self.icc_profile_var.get(),
            rendering_intent=self.rendering_intent_var.get(),
            recent_files=recent_files,
            recent_output_dirs=recent_output_dirs,
            presets=self._settings.presets or {},
            theme=self.theme_var.get(),
            window_geometry=self.geometry(),
        )

    def _save_settings(self):
        self._settings = self._collect_settings()
        try:
            save_settings(self._settings)
        except Exception as e:
            if hasattr(self, "log"):
                self.log_print(f"[WARN] Could not save settings: {e}")

    def _schedule_recovery_save(self):
        if not hasattr(self, "_recovery_path"):
            return
        if self._recovery_save_after_id is not None:
            try:
                self.after_cancel(self._recovery_save_after_id)
            except Exception:
                pass
        self._recovery_save_after_id = self.after(500, self._write_recovery_session)

    def _write_recovery_session(self):
        self._recovery_save_after_id = None
        profiles = list(self._profiles.values())
        try:
            if profiles:
                save_job(self._recovery_path, profiles)
            else:
                self._recovery_path.unlink(missing_ok=True)
        except Exception as exc:
            if hasattr(self, "log"):
                self.log_print(f"[WARN] Could not save session recovery: {exc}")

    def _offer_session_recovery(self):
        self._recovery_offer_after_id = None
        if self._profiles or not self._recovery_path.exists():
            return
        try:
            profiles = load_job(self._recovery_path)
        except Exception as exc:
            try:
                self._recovery_path.unlink(missing_ok=True)
            except OSError as unlink_exc:
                if hasattr(self, "log"):
                    self.log_print(f"[WARN] Could not discard invalid session recovery: {unlink_exc}")
            if hasattr(self, "log"):
                self.log_print(f"[WARN] Ignored invalid session recovery: {exc}")
            return
        if not messagebox.askyesno(
            "Recover previous session?",
            f"Artboard Cutter found {len(profiles)} queue item(s) from an interrupted session. Restore them?",
        ):
            try:
                self._recovery_path.unlink(missing_ok=True)
            except OSError as exc:
                if hasattr(self, "log"):
                    self.log_print(f"[WARN] Could not discard session recovery: {exc}")
            return
        grouped = {}
        for profile in profiles:
            if profile.output_status == "Processing":
                profile.output_status = "Interrupted"
            grouped.setdefault(profile.file_path, []).append(profile)
        defaults = {
            "bleed_mm": "0", "overlap_mm": "0", "overlap_mode": "Shared", "dpi": "150",
            "color_mode": "RGB", "export_format": "PDF", "export_mode": "Raster",
            "icc_mode": "Off", "icc_profile_path": "", "rendering_intent": "Perceptual",
        }
        for source_path, source_profiles in grouped.items():
            self._insert_imported_profiles(source_path, source_profiles, None, defaults)
        self.status_var.set("Recovered the previous queue. Use Retry Failed / Resume for interrupted jobs.")

    def _close_cleanly(self):
        self._save_settings()
        try:
            self._recovery_path.unlink(missing_ok=True)
        except Exception:
            pass
        self.destroy()

    def _on_close(self):
        if self._export_running:
            if messagebox.askyesno(
                "Export in progress",
                "Cancel the active export and close after the current panel stops?",
            ):
                self._close_after_export = True
                self.on_cancel_export()
            return
        self._close_cleanly()

    def _build_modern_ui(self):
        self.rowconfigure(0, weight=0)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        topbar = ttk.Frame(self, style="Root.TFrame")
        topbar.grid(row=0, column=0, sticky="ew", padx=18, pady=(12, 10))

        title_col = ttk.Frame(topbar, style="Root.TFrame")
        title_col.pack(side="left", fill="x", expand=True)
        ttk.Label(title_col, text=f"Artboard Cutter  v{APP_VERSION}", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_col,
            text="Split production artwork into raster or PDF-preserved panel exports.",
            style="RootMuted.TLabel",
        ).pack(anchor="w")
        self.theme_combo = ttk.Combobox(topbar, textvariable=self.theme_var, values=THEME_NAMES, state="readonly", width=22, takefocus=False)
        self.theme_combo.pack(side="right")
        self._button(topbar, "About", self.on_about, style="Tool.TButton").pack(side="right", padx=(0, 10))
        self._bind_combobox_clear_selection(self.theme_combo)
        ttk.Label(topbar, text="Theme", style="RootMuted.TLabel").pack(side="right", padx=(0, 8))

        main = ttk.Panedwindow(self, orient="horizontal")
        main.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 14))

        def make_card(parent, title: str, icon: str | None = None):
            outer = ttk.Frame(parent, style="Card.TFrame")
            header = ttk.Frame(outer, style="CardBody.TFrame")
            header.pack(fill="x", padx=14, pady=(12, 8))
            label_kwargs = {"text": title, "style": "Section.TLabel"}
            image = self._icon(icon) if icon else None
            if image is not None:
                label_kwargs.update({"image": image, "compound": "left"})
            ttk.Label(header, **label_kwargs).pack(side="left")
            body = ttk.Frame(outer, style="CardBody.TFrame")
            body.pack(fill="both", expand=True, padx=14, pady=(0, 14))
            return outer, header, body

        preview_group, preview_card_header, preview_body = make_card(main, "Live Preview", "preview")
        side_outer = ttk.Frame(main, style="Root.TFrame")
        side_outer.rowconfigure(0, weight=1)
        side_outer.columnconfigure(0, weight=1)
        self._side_scroll_canvas = tk.Canvas(side_outer, highlightthickness=0, borderwidth=0)
        self._side_scroll_y = ttk.Scrollbar(side_outer, orient="vertical", command=self._side_scroll_canvas.yview)
        self._side_scroll_canvas.configure(yscrollcommand=self._side_scroll_y.set)
        self._side_scroll_canvas.grid(row=0, column=0, sticky="nsew")
        self._side_scroll_y.grid(row=0, column=1, sticky="ns")
        side = ttk.Frame(self._side_scroll_canvas, style="Root.TFrame")
        self._side_scroll_content = side
        self._side_scroll_window = self._side_scroll_canvas.create_window((0, 0), window=side, anchor="nw")
        side.bind("<Configure>", self._on_side_scroll_content_configure)
        self._side_scroll_canvas.bind("<Configure>", self._on_side_scroll_canvas_configure)
        self._side_scroll_canvas.bind("<MouseWheel>", self._on_side_mousewheel)
        side.bind("<MouseWheel>", self._on_side_mousewheel)
        self._side_scroll_canvas.bind("<Button-4>", self._on_side_mousewheel)
        self._side_scroll_canvas.bind("<Button-5>", self._on_side_mousewheel)
        side.bind("<Button-4>", self._on_side_mousewheel)
        side.bind("<Button-5>", self._on_side_mousewheel)
        self.bind_all("<MouseWheel>", self._on_side_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_side_mousewheel, add="+")
        self.bind_all("<Button-5>", self._on_side_mousewheel, add="+")
        main.add(preview_group, weight=4)
        main.add(side_outer, weight=2)

        self.preview_var = tk.StringVar(value="Target: -")
        ttk.Label(preview_card_header, text="  Live", style="ToolbarMuted.TLabel").pack(side="left", padx=(8, 12))
        ttk.Label(preview_card_header, textvariable=self.preview_var, style="ToolbarMuted.TLabel").pack(side="left", fill="x", expand=True)
        self.add_panel_button = self._button(preview_card_header, "Add Panel", self.on_add_panel, icon="add_panel", style="Accent.TButton", width=11)
        self.add_panel_button.pack(side="right", padx=(8, 0))
        self.panel_count_var = tk.StringVar(value="1")
        self.set_panel_count_button = self._button(preview_card_header, "Set", self.on_set_panel_count, style="Tool.TButton", width=4)
        self.set_panel_count_button.pack(side="right", padx=(4, 0))
        self.panel_count_spin = ttk.Spinbox(
            preview_card_header,
            from_=1,
            to=999,
            textvariable=self.panel_count_var,
            width=5,
            justify="center",
            style="PanelCount.TSpinbox",
        )
        self.panel_count_spin.pack(side="right", padx=(8, 0))
        ttk.Label(preview_card_header, text="Panels", style="ToolbarMuted.TLabel").pack(side="right", padx=(8, 0))
        self._button(preview_card_header, "Fit", self._preview_fit, icon="fit", style="Tool.TButton", width=6).pack(side="right", padx=(4, 0))
        self._button(preview_card_header, "", lambda: self._preview_zoom_by(1.2), icon="zoom_in", style="Tool.TButton", width=3).pack(side="right", padx=(4, 0))
        self._button(preview_card_header, "", lambda: self._preview_zoom_by(1 / 1.2), icon="zoom_out", style="Tool.TButton", width=3).pack(side="right")

        self.preview_canvas = tk.Canvas(preview_body, highlightthickness=0, width=720, height=560)
        self.preview_canvas.pack(fill="both", expand=True)
        self.preview_canvas.bind("<Configure>", lambda e: self._update_preview())
        self.preview_canvas.bind("<ButtonPress-1>", self._preview_left_press)
        self.preview_canvas.bind("<B1-Motion>", self._preview_left_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self._preview_left_release)
        self.preview_canvas.bind("<Motion>", self._preview_motion)
        self.preview_canvas.bind("<Leave>", self._preview_leave)
        self.preview_canvas.bind("<ButtonPress-2>", self._preview_pan_start)
        self.preview_canvas.bind("<B2-Motion>", self._preview_pan_move)
        self.preview_canvas.bind("<ButtonRelease-2>", self._preview_pan_release)
        self.preview_canvas.bind("<MouseWheel>", self._preview_mousewheel)
        self._bg_preview_im = None
        self._bg_preview_tk = None
        self._preview_zoom = 1.0
        self._preview_pan = [0.0, 0.0]
        self._preview_drag = None
        self._preview_edge_drag = None
        self._preview_view = None
        self._preview_edge_targets = []

        files_card, _queue_header, files_frame = make_card(side, "Artwork Queue", "queue")
        files_card.pack(fill="both", expand=True, pady=(0, 10))
        queue_columns = ("select", "original_size", "current_size", "status", "actions", "path")
        self.files_tree = ttk.Treeview(files_frame, columns=queue_columns, show="tree headings", selectmode="extended", height=10)
        headings = {
            "select": "Select",
            "name": "File Name",
            "original_size": "Original Size",
            "current_size": "Current Size",
            "status": "Output Status",
            "actions": "Actions",
            "path": "Path",
        }
        widths = {
            "select": 58,
            "name": 210,
            "original_size": 130,
            "current_size": 170,
            "status": 120,
            "actions": 70,
            "path": 0,
        }
        self.files_tree.heading("#0", text=headings["name"])
        self.files_tree.column("#0", width=widths["name"], minwidth=120, anchor="w", stretch=True)
        for col in queue_columns:
            self.files_tree.heading(col, text=headings[col])
            self.files_tree.column(col, width=widths[col], minwidth=0 if col == "path" else 40, anchor="center" if col in ("select", "actions") else "w", stretch=(col != "path"))
        self.files_tree.grid(row=0, column=0, sticky="nsew")
        files_frame.rowconfigure(0, weight=1)
        files_frame.columnconfigure(0, weight=1)
        sb = ttk.Scrollbar(files_frame, orient="vertical", command=self.files_tree.yview)
        self.files_tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")
        self.queue_empty_label = ttk.Label(
            files_frame,
            text="No artwork files added yet\nAdd files to get started.",
            style="Empty.TLabel",
            anchor="center",
            justify="center",
            image=self._icon("queue"),
            compound="top",
        )
        self.queue_empty_label.place(relx=0.5, rely=0.42, anchor="center")

        btns = ttk.Frame(files_frame, style="CardBody.TFrame")
        btns.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self._button(btns, "Add Files...", self.on_add_files, icon="add_files").grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=3)
        self._button(btns, "Remove", self.on_remove_selected, icon="trash", style="Danger.TButton").grid(row=0, column=1, sticky="ew", padx=5, pady=3)
        self._button(btns, "Clear", self.on_clear, icon="clear").grid(row=0, column=2, sticky="ew", padx=(5, 0), pady=3)
        self._button(btns, "Check All", self.on_check_all, icon="check_all").grid(row=1, column=0, sticky="ew", padx=(0, 5), pady=3)
        self._button(btns, "Uncheck All", self.on_uncheck_all, icon="uncheck").grid(row=1, column=1, sticky="ew", padx=5, pady=3)
        self._button(btns, "Check Selected", self.on_check_selected, icon="check_selected").grid(row=1, column=2, sticky="ew", padx=(5, 0), pady=3)
        self._button(btns, "Save Job...", self.on_save_job).grid(row=2, column=0, sticky="ew", padx=(0, 5), pady=3)
        self._button(btns, "Load Job...", self.on_load_job).grid(row=2, column=1, sticky="ew", padx=5, pady=3)
        for c in range(3):
            btns.columnconfigure(c, weight=1)

        self.files_tree.bind("<Button-1>", self.on_tree_click)
        self.files_tree.bind("<Double-1>", self.on_tree_double_click)
        self.files_tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self._register_file_drop_targets(files_frame, self.files_tree, self.queue_empty_label)

        params_card, _settings_header, params = make_card(side, "Export Settings", "settings")
        params_card.pack(fill="x", pady=(0, 10))
        self._settings_widgets = []

        def make_param_row(label_text, top_pad=False, bottom_pad=False):
            row = ttk.Frame(params, style="CardBody.TFrame")
            row.pack(fill="x", pady=((10 if top_pad else 5), (10 if bottom_pad else 5)))
            ttk.Label(row, text=label_text, width=17, anchor="w", style="Field.TLabel").pack(side="left", padx=(0, 8))
            return row

        mode_row = ttk.Frame(params, style="CardBody.TFrame")
        mode_row.pack(fill="x", pady=(2, 8))
        mode_row.columnconfigure(1, weight=1)
        mode_row.columnconfigure(3, weight=1)

        saved_mode = normalize_export_mode(self._settings.export_mode)
        self.export_mode_var = tk.StringVar(value=saved_mode)
        ttk.Label(mode_row, text="Export Mode", width=12, anchor="w", style="Field.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        export_mode_choices = ttk.Frame(mode_row, style="CardBody.TFrame")
        export_mode_choices.grid(row=0, column=1, sticky="w")
        self.export_mode_raster = ttk.Radiobutton(export_mode_choices, text="Raster", variable=self.export_mode_var, value="Raster")
        self.export_mode_vector = ttk.Radiobutton(export_mode_choices, text="Lossless PDF", variable=self.export_mode_var, value=PDF_PRESERVE_EXPORT_MODE)
        self.export_mode_raster.pack(side="left", padx=(0, 10))
        self.export_mode_vector.pack(side="left")
        self._settings_widgets.extend([self.export_mode_raster, self.export_mode_vector])

        saved_overlap_mode = normalize_overlap_mode(getattr(self._settings, "overlap_mode", "Shared"))
        self.overlap_mode_var = tk.StringVar(value=saved_overlap_mode)
        ttk.Label(mode_row, text="Overlap Mode", width=13, anchor="w", style="Field.TLabel").grid(row=0, column=2, sticky="w", padx=(18, 8))
        overlap_mode_choices = ttk.Frame(mode_row, style="CardBody.TFrame")
        overlap_mode_choices.grid(row=0, column=3, sticky="w")
        self.overlap_mode_shared = ttk.Radiobutton(overlap_mode_choices, text="Shared", variable=self.overlap_mode_var, value="Shared")
        self.overlap_mode_left = ttk.Radiobutton(overlap_mode_choices, text="Left", variable=self.overlap_mode_var, value="Left")
        self.overlap_mode_shared.pack(side="left", padx=(0, 10))
        self.overlap_mode_left.pack(side="left")
        self._settings_widgets.extend([self.overlap_mode_shared, self.overlap_mode_left])

        self.preserve_vectors_var = tk.BooleanVar(value=core_is_pdf_preserve_mode(saved_mode))
        self.fit_mode_var = tk.StringVar(value="stretch")

        preset_row = make_param_row("Preset")
        self.preset_var = tk.StringVar(value="")
        self.preset_combo = ttk.Combobox(
            preset_row,
            textvariable=self.preset_var,
            values=sorted((self._settings.presets or {}).keys(), key=str.casefold),
            state="readonly",
            width=16,
        )
        self.preset_combo.pack(side="left", fill="x", expand=True)
        self.apply_preset_button = self._button(preset_row, "Apply", self.on_apply_preset)
        self.apply_preset_button.pack(side="left", padx=(6, 0))
        self.save_preset_button = self._button(preset_row, "Save", self.on_save_preset)
        self.save_preset_button.pack(side="left", padx=(6, 0))
        self.delete_preset_button = self._button(preset_row, "Delete", self.on_delete_preset, style="Danger.TButton")
        self.delete_preset_button.pack(side="left", padx=(6, 0))
        self._settings_widgets.extend(
            [self.preset_combo, self.apply_preset_button, self.save_preset_button, self.delete_preset_button]
        )

        row = make_param_row("Bleed (mm)", top_pad=True)
        self.bleed_var = tk.StringVar(value=self._settings.bleed_mm)
        self.bleed_entry = ttk.Entry(row, textvariable=self.bleed_var, width=12)
        self.bleed_entry.pack(side="left", fill="x", expand=True)
        self._settings_widgets.append(self.bleed_entry)

        row = make_param_row("Overlap (mm)")
        self.overlap_var = tk.StringVar(value=self._settings.overlap_mm)
        self.overlap_entry = ttk.Entry(row, textvariable=self.overlap_var, width=12)
        self.overlap_entry.pack(side="left", fill="x", expand=True)
        self._settings_widgets.append(self.overlap_entry)

        row = make_param_row("Panel Widths (mm)")
        self.widths_var = tk.StringVar(value="")
        self.widths_entry = ttk.Entry(row, textvariable=self.widths_var, width=24)
        self.widths_entry.pack(side="left", fill="x", expand=True)
        self._settings_widgets.append(self.widths_entry)

        row = make_param_row("Height (mm)")
        self.height_var = tk.StringVar(value="")
        self.height_entry = ttk.Entry(row, textvariable=self.height_var, width=12)
        self.height_entry.pack(side="left", fill="x", expand=True)
        self.reset_size_button = self._button(row, "Reset Size", self.on_reset_size)
        self.reset_size_button.pack(side="left", padx=(6, 0))
        self._settings_widgets.extend([self.height_entry, self.reset_size_button])

        row = make_param_row("DPI")
        self.dpi_var = tk.StringVar(value=self._settings.dpi)
        self.dpi_entry = ttk.Entry(row, textvariable=self.dpi_var, width=12)
        self.dpi_entry.pack(side="left", fill="x", expand=True)
        self._settings_widgets.append(self.dpi_entry)

        row = make_param_row("Color Mode")
        saved_color_mode = "CMYK" if self._settings.color_mode.upper() == "CMYK" else "RGB"
        self.color_mode_var = tk.StringVar(value=saved_color_mode)
        self.color_mode_combo = ttk.Combobox(
            row,
            textvariable=self.color_mode_var,
            values=["RGB", "CMYK"],
            state="readonly",
            width=10,
        )
        self.color_mode_combo.pack(side="left", fill="x", expand=True)
        self._settings_widgets.append(self.color_mode_combo)

        row = make_param_row("ICC Handling")
        self.icc_mode_var = tk.StringVar(value=getattr(self._settings, "icc_mode", "Off"))
        self.icc_mode_combo = ttk.Combobox(row, textvariable=self.icc_mode_var, values=ICC_MODES, state="readonly", width=14)
        self.icc_mode_combo.pack(side="left", fill="x", expand=True)
        self._settings_widgets.append(self.icc_mode_combo)

        row = make_param_row("Output ICC Profile")
        self.icc_profile_var = tk.StringVar(value=getattr(self._settings, "icc_profile_path", ""))
        self.icc_profile_entry = ttk.Entry(row, textvariable=self.icc_profile_var)
        self.icc_profile_entry.pack(side="left", fill="x", expand=True)
        self._button(row, "Browse...", self.on_browse_icc_profile).pack(side="left", padx=(6, 0))
        self._settings_widgets.append(self.icc_profile_entry)

        row = make_param_row("Rendering Intent")
        self.rendering_intent_var = tk.StringVar(value=getattr(self._settings, "rendering_intent", "Perceptual"))
        self.rendering_intent_combo = ttk.Combobox(
            row, textvariable=self.rendering_intent_var, values=RENDERING_INTENTS, state="readonly", width=20
        )
        self.rendering_intent_combo.pack(side="left", fill="x", expand=True)
        self._settings_widgets.append(self.rendering_intent_combo)

        row = make_param_row("Export Format")
        saved_format = self._settings.export_format if self._settings.export_format in ("PDF", "JPG", "TIFF") else "PDF"
        self.format_var = tk.StringVar(value=saved_format)
        self.format_combo = ttk.Combobox(row, textvariable=self.format_var, values=["PDF", "JPG", "TIFF"], state="readonly", width=10)
        self.format_combo.pack(side="left", fill="x", expand=True)
        self._settings_widgets.append(self.format_combo)

        row = make_param_row("Output Folder", bottom_pad=True)
        self.outdir_var = tk.StringVar(value=self._settings.last_output_dir or str(default_output_dir()))
        ttk.Entry(row, textvariable=self.outdir_var).pack(side="left", fill="x", expand=True)
        self._button(row, "Browse...", self.on_browse_outdir, icon="browse_folder").pack(side="left", padx=(6, 0))

        run_card, _run_header, status_frame = make_card(side, "Run", "export")
        run_card.pack(fill="x", pady=(0, 10))
        self.status_var = tk.StringVar(value="Add files, check items to process, then start export.")
        ttk.Label(status_frame, textvariable=self.status_var, style="Muted.TLabel", wraplength=360).pack(fill="x", pady=(0, 8))
        self.progress = ttk.Progressbar(status_frame, mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=(0, 10))
        self.start_export_button = self._button(status_frame, "Start Export", self.on_start, icon="export", style="Accent.TButton")
        self.start_export_button.pack(fill="x", pady=(0, 8))
        self.retry_failed_button = self._button(status_frame, "Retry Failed / Resume", self.on_retry_failed)
        self.retry_failed_button.pack(fill="x", pady=(0, 8))
        self.cancel_export_button = self._button(status_frame, "Cancel Export", self.on_cancel_export, style="Danger.TButton")
        self.cancel_export_button.pack(fill="x", pady=(0, 8))
        self.cancel_export_button.configure(state="disabled")
        self._button(status_frame, "Open Logs Folder", self.on_open_logs_folder, icon="folder").pack(fill="x")

        log_card, _log_header, log_frame = make_card(side, "Activity Log", None)
        log_card.pack(fill="both", expand=False, pady=(0, 8))
        self.log = tk.Text(log_frame, height=9, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)

        apply_theme(self, self._style, self.theme_var.get())
        self._disable_combobox_wheel_changes()
        self._create_checkbox_images()

        try:
            self.tk.call("tk", "scaling", 1.25)
        except Exception:
            pass

        self.widths_var.trace_add("write", self._on_widths_changed)
        self.height_var.trace_add("write", self._on_height_changed)
        self.bleed_var.trace_add("write", self._on_profile_setting_changed)
        self.overlap_var.trace_add("write", self._on_profile_setting_changed)
        self.overlap_mode_var.trace_add("write", self._on_profile_setting_changed)
        self.dpi_var.trace_add("write", self._on_profile_setting_changed)
        self.color_mode_var.trace_add("write", self._on_profile_setting_changed)
        self.icc_mode_var.trace_add("write", self._on_profile_setting_changed)
        self.icc_profile_var.trace_add("write", self._on_profile_setting_changed)
        self.rendering_intent_var.trace_add("write", self._on_profile_setting_changed)
        self.export_mode_var.trace_add("write", self._on_export_mode_changed)
        self.format_var.trace_add("write", self._on_profile_setting_changed)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._set_settings_enabled(False)
        self._render_preview_empty("No artwork loaded", "Add files to the queue to see preview.")

    def _on_side_scroll_content_configure(self, _event=None):
        if not hasattr(self, "_side_scroll_canvas"):
            return
        self._side_scroll_canvas.configure(scrollregion=self._side_scroll_canvas.bbox("all"))
        self._on_side_scroll_canvas_configure()

    def _on_side_scroll_canvas_configure(self, _event=None):
        if not hasattr(self, "_side_scroll_canvas") or not hasattr(self, "_side_scroll_content"):
            return
        needs_scroll = self._side_scroll_content.winfo_reqheight() > max(1, self._side_scroll_canvas.winfo_height())
        if needs_scroll:
            self._side_scroll_y.grid()
        else:
            self._side_scroll_y.grid_remove()
            self._side_scroll_canvas.yview_moveto(0)
        canvas_width = max(1, self._side_scroll_canvas.winfo_width())
        self._side_scroll_canvas.itemconfigure(self._side_scroll_window, width=canvas_width)
        self._side_scroll_canvas.configure(scrollregion=self._side_scroll_canvas.bbox("all"))

    def _widget_contains(self, parent, child) -> bool:
        try:
            widget = child
            while widget is not None:
                if widget == parent:
                    return True
                widget = widget.master
        except Exception:
            pass
        return False

    def _should_skip_side_scroll(self, widget) -> bool:
        for attr in ("preview_canvas", "files_tree", "log", "format_combo", "theme_combo"):
            target = getattr(self, attr, None)
            if target is not None and self._widget_contains(target, widget):
                return True
        return False

    def _on_side_mousewheel(self, event):
        if not hasattr(self, "_side_scroll_canvas") or self._should_skip_side_scroll(getattr(event, "widget", None)):
            return None
        if not self._widget_contains(self._side_scroll_content, getattr(event, "widget", None)):
            return None
        if getattr(event, "num", None) == 4:
            delta = -1
        elif getattr(event, "num", None) == 5:
            delta = 1
        else:
            delta = -1 if event.delta > 0 else 1
        self._side_scroll_canvas.yview_scroll(delta, "units")
        return "break"

    def _create_checkbox_images(self):
        colors = getattr(self, "_theme_tokens", get_theme(self.theme_var.get()).colors)
        self._checkbox_images = {}
        for state, checked in (("checked", True), ("unchecked", False)):
            image = tk.PhotoImage(width=16, height=16)
            border = colors.get("fg", "#000000")
            bg = colors.get("tree_bg", colors.get("panel", "#ffffff"))
            fill = colors.get("accent", "#357abd")
            image.put(bg, to=(0, 0, 16, 16))
            image.put(border, to=(2, 2, 14, 3))
            image.put(border, to=(2, 13, 14, 14))
            image.put(border, to=(2, 2, 3, 14))
            image.put(border, to=(13, 2, 14, 14))
            if checked:
                for x, y in [(5, 8), (6, 9), (7, 10), (8, 9), (9, 8), (10, 7), (11, 6)]:
                    image.put(fill, to=(x, y, x + 2, y + 2))
            self._checkbox_images[state] = image

    def _checkbox_text(self, selected: bool) -> str:
        return "☑" if selected else "☐"

    def _update_queue_empty_state(self):
        if not hasattr(self, "queue_empty_label"):
            return
        has_items = bool(self.files_tree.get_children(""))
        if has_items:
            self.queue_empty_label.place_forget()
        else:
            self.queue_empty_label.place(relx=0.5, rely=0.42, anchor="center")

    def _disable_combobox_wheel_changes(self):
        def block_scroll(_event):
            return "break"

        self.bind_class("TCombobox", "<MouseWheel>", block_scroll)
        self.bind_class("TCombobox", "<Button-4>", block_scroll)
        self.bind_class("TCombobox", "<Button-5>", block_scroll)

    def _bind_combobox_clear_selection(self, combo):
        def clear_selection(_event=None):
            try:
                combo.selection_clear()
            except Exception:
                pass

        combo.bind("<FocusIn>", clear_selection, add="+")
        combo.bind("<ButtonRelease-1>", lambda _event: self.after_idle(clear_selection), add="+")
        combo.bind("<<ComboboxSelected>>", lambda _event: self.after_idle(clear_selection), add="+")

    def on_open_logs_folder(self):
        log_dir = default_log_dir()
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            if sys.platform.startswith("win"):
                os.startfile(str(log_dir))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(log_dir)], check=False)
            else:
                subprocess.run(["xdg-open", str(log_dir)], check=False)
            self.status_var.set(f"Opened logs folder: {log_dir}")
        except Exception as exc:
            messagebox.showerror("Could not open logs folder", f"{log_dir}\n\n{exc}")

    def on_about(self):
        messagebox.showinfo(
            "About Artboard Cutter",
            f"Artboard Cutter {APP_VERSION}\n\n"
            "Production artwork panel export with streamed TIFF, lossless PDF, ICC color management, "
            "staged verification, job recovery, and reusable export presets.\n\n"
            "Copyright (C) 2026 Artboard Cutter contributors\n"
            "Licensed under GNU AGPLv3. You may redistribute and modify this program "
            "under that license. This program comes with NO WARRANTY.\n\n"
            "License: https://www.gnu.org/licenses/agpl-3.0.html\n"
            "Source and notices: https://github.com/0Thirteenth0/Arboard\n"
            "See LICENSE and THIRD_PARTY_NOTICES.md in the release downloads.",
        )

    # ---------- Theme ----------
    def _on_theme_changed(self, *_):
        normalized = normalize_theme_name(self.theme_var.get())
        if normalized != self.theme_var.get():
            self.theme_var.set(normalized)
            return
        self.dark_mode.set(get_theme(self.theme_var.get()).is_dark)
        apply_theme(self, self._style, self.theme_var.get())
        if hasattr(self, "files_tree"):
            self._create_checkbox_images()
            for iid in self.files_tree.get_children(""):
                self._update_profile_row(iid)
            self._update_queue_empty_state()
        self._update_preview()

    def _on_export_mode_changed(self, *_):
        if self._syncing:
            return
        mode = normalize_export_mode(self.export_mode_var.get())
        if self.export_mode_var.get() != mode:
            self.export_mode_var.set(mode)
            return
        is_pdf_preserve = core_is_pdf_preserve_mode(mode)
        self.preserve_vectors_var.set(is_pdf_preserve)
        profile = self._profiles.get(self._active_iid)
        if is_pdf_preserve:
            current_format = self.format_var.get().upper()
            if current_format in {"JPG", "TIFF"} and profile:
                profile.raster_export_format = current_format
            if current_format != "PDF":
                self.format_var.set("PDF")
        elif profile and self.format_var.get() == "PDF" and profile.raster_export_format in {"JPG", "TIFF"}:
            self.format_var.set(profile.raster_export_format)
        self._sync_format_controls()
        if hasattr(self, "status_var"):
            self.status_var.set(
                "Lossless PDF clips PDF content or embeds original TIFF pixels without DPI rendering."
                if is_pdf_preserve
                else "Raster mode renders panels at the selected DPI."
            )
        self._save_selected_profile_settings()
        self._update_preview()

    def _refresh_preset_choices(self):
        if not hasattr(self, "preset_combo"):
            return
        names = sorted((self._settings.presets or {}).keys(), key=str.casefold)
        self.preset_combo.configure(values=names)
        if self.preset_var.get() not in names:
            self.preset_var.set("")

    def on_save_preset(self):
        if not self._active_iid:
            return
        name = simpledialog.askstring("Save export preset", "Preset name:", parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        presets = dict(self._settings.presets or {})
        if name in presets and not messagebox.askyesno("Replace preset?", f"Replace the existing preset '{name}'?"):
            return
        presets[name] = {
            "bleed_mm": self.bleed_var.get(),
            "overlap_mm": self.overlap_var.get(),
            "overlap_mode": self.overlap_mode_var.get(),
            "dpi": self.dpi_var.get(),
            "color_mode": self.color_mode_var.get(),
            "export_format": self.format_var.get(),
            "export_mode": self.export_mode_var.get(),
            "icc_mode": self.icc_mode_var.get(),
            "icc_profile_path": self.icc_profile_var.get(),
            "rendering_intent": self.rendering_intent_var.get(),
        }
        self._settings.presets = presets
        self._refresh_preset_choices()
        self.preset_var.set(name)
        self._save_settings()
        self.status_var.set(f"Saved export preset: {name}. Artwork size and output folder are not included.")

    def on_apply_preset(self):
        preset = (self._settings.presets or {}).get(self.preset_var.get())
        if not preset or not self._active_iid:
            return
        self._loading_profile = True
        self._syncing = True
        try:
            self.bleed_var.set(preset.get("bleed_mm", "0"))
            self.overlap_var.set(preset.get("overlap_mm", "0"))
            self.overlap_mode_var.set(normalize_overlap_mode(preset.get("overlap_mode", "Shared")))
            self.dpi_var.set(preset.get("dpi", "150"))
            self.color_mode_var.set(preset.get("color_mode", "RGB"))
            self.format_var.set(preset.get("export_format", "PDF"))
            self.export_mode_var.set(normalize_export_mode(preset.get("export_mode", "Raster")))
            self.icc_mode_var.set(preset.get("icc_mode", "Off"))
            self.icc_profile_var.set(preset.get("icc_profile_path", ""))
            self.rendering_intent_var.set(preset.get("rendering_intent", "Perceptual"))
        finally:
            self._syncing = False
            self._loading_profile = False
        self._on_export_mode_changed()
        self._save_selected_profile_settings()
        self._update_preview()
        self.status_var.set(f"Applied export preset: {self.preset_var.get()}. Artwork size is unchanged.")

    def on_delete_preset(self):
        name = self.preset_var.get()
        if not name or name not in (self._settings.presets or {}):
            return
        if not messagebox.askyesno("Delete preset?", f"Delete the preset '{name}'?"):
            return
        presets = dict(self._settings.presets or {})
        presets.pop(name, None)
        self._settings.presets = presets
        self._refresh_preset_choices()
        self._save_settings()
        self.status_var.set(f"Deleted preset: {name}")

    # ---------- Files tree helpers ----------
    def _profile_iids(self):
        return list(self._profiles.keys())

    def _first_profile_iid(self, iid):
        if iid in self._profiles:
            return iid
        for child in self.files_tree.get_children(iid):
            found = self._first_profile_iid(child)
            if found:
                return found
        return None

    def _child_profile_iids(self, iid):
        if iid in self._profiles:
            return [iid]
        return [child for child in self.files_tree.get_children(iid) if child in self._profiles]

    @staticmethod
    def _file_path_key(path: str) -> str:
        return os.path.normcase(os.path.abspath(path))

    def _add_file_item(self, path: str):
        path = str(Path(path).expanduser().resolve())
        path_key = self._file_path_key(path)
        if path_key in self._file_groups:
            iid = self._file_groups[path_key]
            self.files_tree.selection_set(iid)
            self.files_tree.focus(iid)
            self.files_tree.see(iid)
            return iid
        if path_key in self._pending_import_paths:
            return None
        self._pending_import_paths.add(path_key)
        import_generation = self._import_generation
        defaults = {
            "bleed_mm": self.bleed_var.get(),
            "overlap_mm": self.overlap_var.get(),
            "overlap_mode": self.overlap_mode_var.get(),
            "dpi": self.dpi_var.get(),
            "color_mode": self.color_mode_var.get(),
            "export_format": self.format_var.get(),
            "export_mode": self.export_mode_var.get(),
            "icc_mode": self.icc_mode_var.get(),
            "icc_profile_path": self.icc_profile_var.get(),
            "rendering_intent": self.rendering_intent_var.get(),
        }
        self.status_var.set(f"Reading artwork information: {Path(path).name}...")

        def work():
            try:
                profiles = core_create_artwork_profiles(Path(path), **defaults)
                error = None
            except Exception as exc:
                profiles = []
                error = str(exc)
            self._export_events.put(("import_ready", import_generation, path, profiles, error, defaults))

        threading.Thread(target=work, daemon=True).start()
        return None

    def _insert_imported_profiles(
        self,
        path: str,
        profiles: list[ArtworkProfile],
        error: str | None,
        defaults: dict,
        *,
        import_generation: int | None = None,
    ):
        if import_generation is not None and import_generation != self._import_generation:
            return None
        path_key = self._file_path_key(path)
        self._pending_import_paths.discard(path_key)
        if error:
            self.log_print(f"[WARN] Cannot probe {path}: {error}")
            profiles = [
                ArtworkProfile(
                    file_path=path,
                    output_name=Path(path).stem,
                    **defaults,
                    raster_export_format=defaults["export_format"],
                    output_status="Probe failed",
                    validation_state="error",
                )
            ]

        parent = ""
        if len(profiles) > 1:
            parent = self.files_tree.insert(
                "",
                "end",
                text=Path(path).name,
                values=(self._checkbox_text(False), "", "", f"0/{len(profiles)} selected", "Get Names", path),
                open=True,
            )
            self._file_groups[path_key] = parent
        last_iid = None
        for profile in profiles:
            iid = self.files_tree.insert(parent, "end")
            self._profiles[iid] = profile
            self._update_profile_row(iid)
            last_iid = iid
        if len(profiles) == 1 and last_iid:
            self._file_groups[path_key] = last_iid
        if last_iid:
            first_new = self.files_tree.get_children(parent)[0] if parent else last_iid
            self.files_tree.selection_set(first_new)
            self.files_tree.focus(first_new)
            self.files_tree.see(first_new)
        self._update_queue_empty_state()
        self.status_var.set(f"Added {Path(path).name} to the artwork queue.")
        for profile in profiles:
            page_label = (
                f" page {profile.source_page_index + 1}/{profile.source_page_count}"
                if profile.source_page_count > 1
                else ""
            )
            self.log_print(
                f"[INFO] Source size {Path(path).name}{page_label}: "
                f"width={fmt_mm(profile.original_width_mm)} mm, height={fmt_mm(profile.original_height_mm)} mm"
                if profile.original_width_mm is not None and profile.original_height_mm is not None
                else f"[WARN] Source dimensions unavailable for {Path(path).name}{page_label}."
            )
        self._schedule_recovery_save()
        return last_iid

    def _update_profile_row(self, iid):
        profile = self._profiles.get(iid)
        if not profile:
            return
        self.files_tree.item(
            iid,
            text=profile.file_name,
            values=(
                self._checkbox_text(profile.selected),
                profile.original_size_label(),
                profile.current_size_label(),
                profile.output_status,
                "Remove",
                profile.file_path,
            ),
        )

    def _update_group_row(self, group_iid):
        children = self._child_profile_iids(group_iid)
        if not children:
            return
        path = self._profiles[children[0]].file_path
        selected = sum(1 for child in children if self._profiles[child].selected)
        status = f"{selected}/{len(children)} selected"
        all_selected = selected == len(children)
        self.files_tree.item(
            group_iid,
            text=Path(path).name,
            values=(self._checkbox_text(all_selected), "", "", status, "Get Names", path),
        )

    def _toggle_item(self, iid):
        profile = self._profiles.get(iid)
        if not profile:
            return
        profile.selected = not profile.selected
        self._update_profile_row(iid)
        parent = self.files_tree.parent(iid)
        if parent:
            self._update_group_row(parent)
        self._schedule_recovery_save()

    def _toggle_group(self, iid):
        children = self._child_profile_iids(iid)
        if not children:
            return
        new_state = not all(self._profiles[child].selected for child in children)
        for child in children:
            self._profiles[child].selected = new_state
            self._update_profile_row(child)
        self._update_group_row(iid)
        self._schedule_recovery_save()

    def on_tree_click(self, event):
        region = self.files_tree.identify("region", event.x, event.y)
        col = self.files_tree.identify_column(event.x)
        iid = self.files_tree.identify_row(event.y)
        if not iid:
            return None
        if region == "cell" and col == "#1":
            if iid in self._profiles:
                self._toggle_item(iid)
            else:
                self._toggle_group(iid)
            return "break"
        if region == "cell" and col == "#5":
            if iid in self._profiles:
                self._remove_iid(iid)
            else:
                self._apply_illustrator_names_to_group(iid)
            return "break"
        return None

    def on_tree_double_click(self, event):
        region = self.files_tree.identify("region", event.x, event.y)
        col = self.files_tree.identify_column(event.x)
        iid = self.files_tree.identify_row(event.y)
        if region != "tree" or col != "#0" or not iid or iid not in self._profiles:
            return None
        self._begin_name_edit(iid)
        return "break"

    def _begin_name_edit(self, iid):
        profile = self._profiles.get(iid)
        if not profile:
            return
        bbox = self.files_tree.bbox(iid, "#0")
        if not bbox:
            return
        x, y, w, h = bbox
        editor = ttk.Entry(self.files_tree)
        editor.insert(0, profile.file_name)
        editor.select_range(0, "end")
        editor.focus_set()
        editor.place(x=x, y=y, width=w, height=h)

        def commit(_event=None):
            try:
                new_name = validate_output_name(editor.get())
            except Exception as exc:
                messagebox.showerror("Invalid output name", str(exc))
                editor.focus_set()
                return "break"
            profile.output_name = new_name
            self._update_profile_row(iid)
            editor.destroy()
            return "break"

        def cancel(_event=None):
            editor.destroy()
            return "break"

        editor.bind("<Return>", commit)
        editor.bind("<FocusOut>", commit)
        editor.bind("<Escape>", cancel)

    def _apply_illustrator_names_to_group(self, group_iid):
        children = self._child_profile_iids(group_iid)
        if not children:
            return
        source_path = Path(self._profiles[children[0]].file_path)
        if source_path.suffix.lower() != ".ai":
            messagebox.showinfo("Artboard names", "Illustrator artboard names are only available for .ai files.")
            return
        self.status_var.set(f"Reading Illustrator artboard names from {source_path.name}...")
        self.files_tree.set(group_iid, "actions", "Loading...")

        def finish(names):
            if group_iid not in self.files_tree.get_children("") and not self.files_tree.exists(group_iid):
                return
            if not names:
                self.files_tree.set(group_iid, "actions", "Get Names")
                messagebox.showwarning(
                    "Artboard names unavailable",
                    "Could not read artboard names from Adobe Illustrator. Open Illustrator first, make sure it is responsive, then try again. Numbered queue names were kept.",
                )
                self.status_var.set("Could not read Illustrator artboard names.")
                return
            current_children = self._child_profile_iids(group_iid)
            sanitized_names = []
            for idx, child in enumerate(current_children):
                profile = self._profiles[child]
                fallback = f"{source_path.stem}{profile.source_page_index + 1}" if profile.source_page_count > 1 else source_path.stem
                raw_name = names[idx] if idx < len(names) else fallback
                sanitized_names.append(sanitize_output_name(raw_name, fallback))
            for child, name in zip(current_children, make_unique_output_names(sanitized_names), strict=True):
                profile = self._profiles[child]
                profile.output_name = name
                self._update_profile_row(child)
            self._update_group_row(group_iid)
            self.status_var.set(f"Loaded Illustrator artboard names for {source_path.name}.")

        def work():
            names = get_illustrator_artboard_names(source_path, timeout_seconds=20, require_running=True)
            self._export_events.put(("call", lambda: finish(names)))

        threading.Thread(target=work, daemon=True).start()

    def on_tree_select(self, _event=None):
        sel = self.files_tree.selection()
        if not sel:
            self._save_selected_profile_settings()
            self._active_iid = None
            self._set_settings_enabled(False)
            self._preview_request = None
            self._bg_preview_im = None
            self._bg_preview_tk = None
            self._update_preview()
            return
        iid = sel[-1]
        if iid not in self._profiles:
            leaf = self._first_profile_iid(iid)
            if not leaf:
                return
            iid = leaf
            self.files_tree.selection_set(iid)
            self.files_tree.focus(iid)
            return
        if iid == self._active_iid:
            return
        self._save_selected_profile_settings()
        self._active_iid = iid
        self._load_profile_into_settings(iid)

    def on_check_selected(self):
        for iid in self.files_tree.selection():
            for child in self._child_profile_iids(iid):
                self._profiles[child].selected = True
                self._update_profile_row(child)
                parent = self.files_tree.parent(child)
                if parent:
                    self._update_group_row(parent)
        self._schedule_recovery_save()

    def on_uncheck_selected(self):
        for iid in self.files_tree.selection():
            for child in self._child_profile_iids(iid):
                self._profiles[child].selected = False
                self._update_profile_row(child)
                parent = self.files_tree.parent(child)
                if parent:
                    self._update_group_row(parent)
        self._schedule_recovery_save()

    def on_check_all(self):
        for iid in self._profile_iids():
            profile = self._profiles.get(iid)
            if profile:
                profile.selected = True
                self._update_profile_row(iid)
        for group in self.files_tree.get_children(""):
            if group not in self._profiles:
                self._update_group_row(group)
        self._schedule_recovery_save()

    def on_uncheck_all(self):
        for iid in self._profile_iids():
            profile = self._profiles.get(iid)
            if profile:
                profile.selected = False
                self._update_profile_row(iid)
        for group in self.files_tree.get_children(""):
            if group not in self._profiles:
                self._update_group_row(group)
        self._schedule_recovery_save()
    # ---------- Drag & drop / file buttons ----------
    def _register_file_drop_targets(self, *widgets):
        """Make every visible layer of the queue accept operating-system file drops."""
        if not DND_AVAILABLE:
            return
        for widget in widgets:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self.on_drop)

    def on_drop(self, event):
        raw = self.tk.splitlist(event.data)
        for p in raw:
            # splitlist already removes Tcl grouping braces. Stripping braces
            # again would corrupt valid filenames such as "{proof}.pdf".
            p = str(p).strip()
            if p.lower().endswith((".pdf", ".ai", ".jpg", ".jpeg", ".png", ".tif", ".tiff")):
                self._add_file_item(p)
        return getattr(event, "action", None)

    def on_add_files(self):
        last_input = Path(self._settings.last_input_path) if self._settings.last_input_path else None
        initial_dir = last_input.parent if last_input and last_input.exists() else Path.cwd()
        files = filedialog.askopenfilenames(
            title="Select files",
            initialdir=str(initial_dir),
            filetypes=[
                ("Supported files", "*.pdf *.ai *.jpg *.jpeg *.png *.tif *.tiff"),
                ("PDF files", "*.pdf"),
                ("AI files", "*.ai"),
                ("Images", "*.jpg *.jpeg *.png *.tif *.tiff"),
                ("All files", "*.*"),
            ]
        )
        for f in files:
            self._add_file_item(f)

    def on_remove_selected(self):
        if self._export_running:
            messagebox.showwarning("Export in progress", "Cancel or finish the export before removing queue items.")
            return
        for iid in list(self.files_tree.selection()):
            self._remove_iid(iid)
        self._schedule_recovery_save()

    def on_clear(self):
        if self._export_running:
            messagebox.showwarning("Export in progress", "Cancel or finish the export before clearing the queue.")
            return
        self._import_generation += 1
        self._pending_import_paths.clear()
        for iid in list(self.files_tree.get_children("")):
            self._remove_iid(iid, select_next=False)
        self._active_iid = None
        self._profiles.clear()
        self._file_groups.clear()
        self._set_settings_enabled(False)
        self._preview_request = None
        self._bg_preview_im = None
        self._bg_preview_tk = None
        self._update_queue_empty_state()
        self._update_preview()
        self._schedule_recovery_save()

    def on_save_job(self):
        if self._export_running:
            messagebox.showwarning("Export in progress", "Finish or cancel the export before saving the job.")
            return
        self._save_selected_profile_settings()
        profiles = list(self._profiles.values())
        if not profiles:
            messagebox.showwarning("Empty queue", "Add artwork before saving a job.")
            return
        path = filedialog.asksaveasfilename(
            title="Save Artboard Cutter job",
            defaultextension=".artboard-job",
            filetypes=[("Artboard Cutter jobs", "*.artboard-job"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            save_job(Path(path), profiles)
        except Exception as exc:
            messagebox.showerror("Could not save job", str(exc))
            return
        self.status_var.set(f"Saved job: {Path(path).name}")

    def on_load_job(self):
        if self._export_running:
            messagebox.showwarning("Export in progress", "Finish or cancel the export before loading a job.")
            return
        path = filedialog.askopenfilename(
            title="Load Artboard Cutter job",
            filetypes=[
                ("Artboard Cutter jobs", "*.artboard-job *.artboard-job.json"),
                ("Legacy job files", "*.artboard-job.json"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self.load_job_path(Path(path))

    def _load_startup_job(self):
        self._startup_job_after_id = None
        path = self._startup_job_path
        self._startup_job_path = None
        if path is not None:
            self.load_job_path(path, confirm_replace=False)

    def load_job_path(self, path: Path, *, confirm_replace: bool = True) -> bool:
        """Load a job selected in the GUI or passed by Windows Explorer."""
        if self._export_running:
            messagebox.showwarning("Export in progress", "Finish or cancel the export before loading a job.")
            return False
        path = Path(path)
        try:
            profiles = load_job(path)
        except Exception as exc:
            messagebox.showerror("Could not load job", str(exc))
            return False
        if (
            confirm_replace
            and self._profiles
            and not messagebox.askyesno("Replace current queue?", "Replace the current artwork queue with this job?")
        ):
            return False
        self.on_clear()
        grouped = {}
        for profile in profiles:
            if not Path(profile.file_path).exists():
                profile.output_status = "Source missing"
                profile.validation_state = "error"
            grouped.setdefault(profile.file_path, []).append(profile)
        defaults = {
            "bleed_mm": "0",
            "overlap_mm": "0",
            "overlap_mode": "Shared",
            "dpi": "150",
            "color_mode": "RGB",
            "export_format": "PDF",
            "export_mode": "Raster",
            "icc_mode": "Off",
            "icc_profile_path": "",
            "rendering_intent": "Perceptual",
        }
        for source_path, source_profiles in grouped.items():
            self._insert_imported_profiles(source_path, source_profiles, None, defaults)
        self.status_var.set(f"Loaded job: {path.name}")
        return True

    def _remove_iid(self, iid, select_next=True, remove_empty_parent=True):
        if not self.files_tree.exists(iid):
            return
        if iid not in self._profiles:
            path = self.files_tree.set(iid, "path")
            for child in list(self.files_tree.get_children(iid)):
                self._remove_iid(child, select_next=False, remove_empty_parent=False)
            self._file_groups.pop(path, None)
            self._file_groups.pop(self._file_path_key(path), None)
            try:
                if self.files_tree.exists(iid):
                    self.files_tree.delete(iid)
            except Exception:
                pass
        else:
            if iid == self._active_iid:
                self._active_iid = None
            profile = self._profiles.pop(iid, None)
            parent = self.files_tree.parent(iid)
            try:
                self.files_tree.delete(iid)
            except Exception:
                pass
            if parent and self.files_tree.exists(parent):
                if self.files_tree.get_children(parent):
                    self._update_group_row(parent)
                elif remove_empty_parent:
                    path = self.files_tree.set(parent, "path")
                    self._file_groups.pop(path, None)
                    self._file_groups.pop(self._file_path_key(path), None)
                    self.files_tree.delete(parent)
            elif profile:
                self._file_groups.pop(profile.file_path, None)
                self._file_groups.pop(self._file_path_key(profile.file_path), None)
        if not select_next:
            self._update_queue_empty_state()
            return
        children = self._profile_iids()
        if children:
            next_iid = children[0]
            self.files_tree.selection_set(next_iid)
            self.files_tree.focus(next_iid)
        else:
            self._set_settings_enabled(False)
            self._preview_request = None
            self._bg_preview_im = None
            self._bg_preview_tk = None
            self._update_preview()
        self._update_queue_empty_state()
        self._schedule_recovery_save()

    def on_browse_outdir(self):
        initial = Path(self.outdir_var.get()).expanduser()
        if not initial.exists():
            initial = Path.cwd()
        d = filedialog.askdirectory(title="Choose output folder", initialdir=str(initial))
        if d:
            self.outdir_var.set(d)
            self._save_settings()

    def on_browse_icc_profile(self):
        initial = Path(self.icc_profile_var.get()).expanduser().parent if self.icc_profile_var.get() else Path.cwd()
        path = filedialog.askopenfilename(
            title="Choose output ICC profile",
            initialdir=str(initial if initial.exists() else Path.cwd()),
            filetypes=[("ICC profiles", "*.icc *.icm"), ("All files", "*.*")],
        )
        if path:
            self.icc_profile_var.set(path)

    # ---------- Log & parsing ----------
    def log_print(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        self.update_idletasks()

    # ---------- Artwork profile state ----------
    def _set_settings_enabled(self, enabled: bool):
        self._settings_enabled = bool(enabled)
        state = "normal" if enabled else "disabled"
        combo_state = "readonly" if enabled else "disabled"
        for widget in getattr(self, "_settings_widgets", []):
            try:
                if isinstance(widget, ttk.Combobox):
                    widget.configure(state=combo_state)
                else:
                    widget.configure(state=state)
            except Exception:
                pass
        if hasattr(self, "reset_size_button"):
            can_reset = enabled and self._active_profile_has_original_size()
            self.reset_size_button.configure(state=("normal" if can_reset else "disabled"))
        if hasattr(self, "add_panel_button"):
            self.add_panel_button.configure(state=("normal" if enabled else "disabled"))
        for name in ("panel_count_spin", "set_panel_count_button"):
            if hasattr(self, name):
                getattr(self, name).configure(state=("normal" if enabled else "disabled"))
        self._sync_format_controls()

    def _sync_format_controls(self):
        if not hasattr(self, "format_combo"):
            return
        preserve = core_is_pdf_preserve_mode(self.export_mode_var.get())
        if not self._settings_enabled or self._export_running or preserve:
            self.format_combo.configure(state="disabled")
        else:
            self.format_combo.configure(state="readonly")
        if hasattr(self, "dpi_entry"):
            self.dpi_entry.configure(
                state="disabled" if (not self._settings_enabled or self._export_running or preserve) else "normal"
            )
        if hasattr(self, "color_mode_combo"):
            self.color_mode_combo.configure(
                state="disabled" if (not self._settings_enabled or self._export_running or preserve) else "readonly"
            )
        icc_disabled = not self._settings_enabled or self._export_running or preserve
        if hasattr(self, "icc_mode_combo"):
            self.icc_mode_combo.configure(state="disabled" if icc_disabled else "readonly")
        if hasattr(self, "icc_profile_entry"):
            self.icc_profile_entry.configure(
                state="disabled" if icc_disabled or self.icc_mode_var.get() == "Off" else "normal"
            )
        if hasattr(self, "rendering_intent_combo"):
            self.rendering_intent_combo.configure(
                state="disabled" if icc_disabled or self.icc_mode_var.get() != "Convert" else "readonly"
            )

    def _active_profile_has_original_size(self) -> bool:
        profile = self._profiles.get(self._active_iid)
        return bool(profile and profile.original_width_mm is not None and profile.original_height_mm is not None)

    def _load_profile_into_settings(self, iid):
        profile = self._profiles.get(iid)
        if not profile:
            self._set_settings_enabled(False)
            return
        self._loading_profile = True
        self._syncing = True
        try:
            self.bleed_var.set(profile.bleed_mm)
            self.overlap_var.set(profile.overlap_mm)
            self.overlap_mode_var.set(normalize_overlap_mode(profile.overlap_mode))
            self.widths_var.set(profile.panel_widths)
            self.height_var.set(profile.height_mm)
            self.dpi_var.set(profile.dpi)
            self.color_mode_var.set(profile.color_mode)
            self.icc_mode_var.set(profile.icc_mode)
            self.icc_profile_var.set(profile.icc_profile_path)
            self.rendering_intent_var.set(profile.rendering_intent)
            self.format_var.set(profile.export_format)
            self.export_mode_var.set(profile.export_mode)
            self.preserve_vectors_var.set(profile.preserve_vectors)
            self.fit_mode_var.set(profile.vector_fit_mode)
            try:
                self.panel_count_var.set(str(len(parse_widths_list(profile.panel_widths))))
            except Exception:
                self.panel_count_var.set("1")
            self._src_w_mm = profile.original_width_mm
            self._src_h_mm = profile.original_height_mm
            self._src_ar = (self._src_w_mm / self._src_h_mm) if self._src_w_mm and self._src_h_mm else None
            self._load_preview_image(Path(profile.file_path), profile.source_page_index)
        finally:
            self._syncing = False
            self._loading_profile = False
        self._set_settings_enabled(True)
        self._sync_format_controls()
        self._update_preview()

    def _load_preview_image(self, p: Path, page_index: int = 0):
        request = (self._active_iid, str(p), int(page_index))
        self._preview_request = request
        self._bg_preview_im = None
        self._bg_preview_tk = None

        def work():
            if request != self._preview_request:
                return
            doc = None
            try:
                with PDF_OPERATION_LOCK:
                    if request != self._preview_request:
                        return
                    doc = open_pdf_robust(p)
                    page = doc.load_page(page_index)
                    rect = page.rect
                    if PIL_AVAILABLE:
                        max_dim_pt = max(float(rect.width), float(rect.height)) or 1.0
                        scale = preview_render_scale(max_dim_pt)
                        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                        image = pixmap_to_pil(pix)
                    else:
                        image = None
                error = None
            except Exception as exc:
                image = None
                error = str(exc)
            finally:
                if doc is not None:
                    try:
                        with PDF_OPERATION_LOCK:
                            doc.close()
                    except Exception:
                        pass
            self._export_events.put(("preview_ready", request, image, error))

        threading.Thread(target=work, daemon=True).start()

    def _save_selected_profile_settings(self):
        if self._loading_profile:
            return
        profile = self._profiles.get(self._active_iid)
        if not profile:
            return
        profile.panel_widths = self.widths_var.get()
        profile.height_mm = self.height_var.get()
        profile.bleed_mm = self.bleed_var.get()
        profile.overlap_mm = self.overlap_var.get()
        profile.overlap_mode = normalize_overlap_mode(self.overlap_mode_var.get())
        profile.dpi = self.dpi_var.get()
        profile.color_mode = self.color_mode_var.get()
        profile.icc_mode = self.icc_mode_var.get()
        profile.icc_profile_path = self.icc_profile_var.get()
        profile.rendering_intent = self.rendering_intent_var.get()
        profile.export_format = self.format_var.get()
        profile.export_mode = self.export_mode_var.get()
        if not core_is_pdf_preserve_mode(profile.export_mode) and profile.export_format.upper() in {"PDF", "JPG", "TIFF"}:
            profile.raster_export_format = profile.export_format.upper()
        profile.apply_export_mode_rules()
        self._update_profile_row(self._active_iid)
        self._schedule_recovery_save()

    def on_reset_size(self):
        profile = self._profiles.get(self._active_iid)
        if not profile or not profile.reset_size_to_original():
            return
        self._loading_profile = True
        self._syncing = True
        try:
            self.widths_var.set(profile.panel_widths)
            self.height_var.set(profile.height_mm)
        finally:
            self._syncing = False
            self._loading_profile = False
        self._update_profile_row(self._active_iid)
        self._update_preview()
    # ---------- Aspect sync (preserve vectors) ----------
    def _on_widths_changed(self, *_):
        try:
            self.panel_count_var.set(str(len(parse_widths_list(self.widths_var.get()))))
        except Exception:
            pass
        self._save_selected_profile_settings()
        self._update_preview()

    def _on_height_changed(self, *_):
        self._save_selected_profile_settings()
        self._update_preview()

    def _on_profile_setting_changed(self, *_):
        self._save_selected_profile_settings()
        self._sync_format_controls()
        self._update_preview()

    def _preview_fit(self):
        self._preview_zoom = 1.0
        self._preview_pan = [0.0, 0.0]
        self._update_preview()

    def _preview_zoom_by(self, factor: float):
        self._preview_zoom = max(0.25, min(8.0, self._preview_zoom * factor))
        self._update_preview()

    def _preview_mousewheel(self, event):
        self._preview_zoom_by(1.12 if event.delta > 0 else 1 / 1.12)

    def _preview_pan_start(self, event):
        self._preview_drag = (event.x, event.y, self._preview_pan[0], self._preview_pan[1])

    def _preview_pan_move(self, event):
        if not self._preview_drag:
            return
        x0, y0, pan_x, pan_y = self._preview_drag
        self._preview_pan = [pan_x + event.x - x0, pan_y + event.y - y0]
        self._update_preview()

    def _preview_pan_release(self, _event=None):
        self._preview_drag = None

    def _preview_screen_to_mm(self, x: float, y: float) -> tuple[float, float] | None:
        view = self._preview_view or {}
        scale = view.get("scale")
        if not scale:
            return None
        return ((x - view["x0"]) / scale, (y - view["y0"]) / scale)

    def _find_preview_edge_target(self, event, tolerance_px: int = 8):
        view = self._preview_view or {}
        if not view or not self._preview_edge_targets:
            return None
        scale = view.get("scale") or 0
        if scale <= 0:
            return None
        y_mm_pair = self._preview_screen_to_mm(event.x, event.y)
        if not y_mm_pair:
            return None
        _x_mm, y_mm = y_mm_pair
        if y_mm < 0 or y_mm > view.get("page_h_mm", 0):
            return None
        best = None
        best_distance = tolerance_px + 1
        for target in self._preview_edge_targets:
            edge_x_px = view["x0"] + target["x_mm"] * scale
            distance = abs(event.x - edge_x_px)
            if distance <= tolerance_px and distance < best_distance:
                best = target
                best_distance = distance
        return best

    def _preview_left_press(self, event):
        target = self._find_preview_edge_target(event)
        if not target:
            return None
        try:
            widths = parse_widths_list(self.widths_var.get())
            overlap = self.overlap_var.get().strip()
            overlap = (2 * float(self.bleed_var.get())) if overlap == "" else float(overlap)
        except Exception:
            return None
        self._preview_edge_drag = {
            "edge_index": target["edge_index"],
            "start_x": event.x,
            "start_widths": widths,
            "min_width": max(1.0, max(0.0, overlap) + 0.01),
        }
        self.preview_canvas.configure(cursor="sb_h_double_arrow")
        return "break"

    def _preview_left_drag(self, event):
        if not self._preview_edge_drag:
            return None
        view = self._preview_view or {}
        scale = view.get("scale") or 0
        if scale <= 0:
            return "break"
        delta_mm = (event.x - self._preview_edge_drag["start_x"]) / scale
        try:
            widths = core_resize_adjacent_panel_widths(
                self._preview_edge_drag["start_widths"],
                self._preview_edge_drag["edge_index"],
                delta_mm,
                min_width_mm=self._preview_edge_drag["min_width"],
                clamp=False,
            )
        except Exception:
            return "break"
        self.widths_var.set(" ".join(fmt_mm(width) for width in widths))
        return "break"

    def _preview_left_release(self, _event=None):
        if not self._preview_edge_drag:
            return None
        self._preview_edge_drag = None
        self._save_selected_profile_settings()
        self._update_preview()
        self._preview_motion(_event) if _event is not None else self.preview_canvas.configure(cursor="")
        return "break"

    def _preview_motion(self, event):
        if self._preview_edge_drag:
            self.preview_canvas.configure(cursor="sb_h_double_arrow")
            return
        self.preview_canvas.configure(cursor="sb_h_double_arrow" if self._find_preview_edge_target(event) else "")

    def _preview_leave(self, _event=None):
        if not self._preview_edge_drag:
            self.preview_canvas.configure(cursor="")

    def on_add_panel(self):
        if not self._profiles.get(self._active_iid):
            return
        try:
            widths = parse_widths_list(self.widths_var.get())
            widths = core_add_evenly_distributed_panel(widths)
        except Exception as exc:
            messagebox.showerror("Cannot add panel", str(exc))
            return
        self.widths_var.set(" ".join(fmt_mm(width) for width in widths))
        self._save_selected_profile_settings()
        self._update_preview()

    def on_set_panel_count(self):
        if not self._profiles.get(self._active_iid):
            return
        try:
            widths = parse_widths_list(self.widths_var.get())
            count = int(self.panel_count_var.get())
            redistributed = core_redistribute_panel_widths(sum(widths), count)
        except Exception as exc:
            messagebox.showerror("Cannot set panel count", str(exc))
            return
        self.widths_var.set(" ".join(fmt_mm(width) for width in redistributed))
        self._save_selected_profile_settings()
        self._update_preview()

    # ---------- Preview ----------
    def _update_preview(self, *_):
        try:
            bleed = float(self.bleed_var.get())
        except Exception:
            bleed = 0.0
        try:
            overlap = self.overlap_var.get().strip()
            overlap = (2 * bleed) if overlap == "" else float(overlap)
        except Exception:
            overlap = 0.0

        try:
            widths = parse_widths_list(self.widths_var.get())
        except Exception:
            self.preview_var.set("Target: -")
            # Clear visual preview on parse error
            if hasattr(self, "preview_canvas"):
                self._render_preview_empty("No artwork loaded", "Add files to the queue to see preview.")
            self._preview_view = None
            self._preview_edge_targets = []
            return
        try:
            height = float(self.height_var.get())
        except Exception:
            height = 0.0

        if not widths:
            self.preview_var.set("Target: -")
            if hasattr(self, "preview_canvas"):
                self._render_preview_empty("No artwork loaded", "Add files to the queue to see preview.")
            self._preview_view = None
            self._preview_edge_targets = []
            return

        if (
            not math.isfinite(bleed)
            or not math.isfinite(overlap)
            or not math.isfinite(height)
            or bleed < 0
            or overlap < 0
            or height <= 0
            or any(not math.isfinite(width) or width <= 0 for width in widths)
        ):
            self.preview_var.set("Invalid dimensions: use positive finite panel widths and height; bleed/overlap must be finite and non-negative.")
            if hasattr(self, "preview_canvas"):
                self._render_preview_empty("Invalid artwork dimensions", "Correct the highlighted size values to restore the preview.")
            self._preview_view = None
            self._preview_edge_targets = []
            return

        bleed_eff = max(0.0, bleed)
        overlap_mode = normalize_overlap_mode(self.overlap_mode_var.get())
        if len(widths) > 1 and overlap >= min(widths):
            self.preview_var.set(
                f"Invalid overlap: {fmt_mm(overlap)} mm must be smaller than the narrowest panel ({fmt_mm(min(widths))} mm)."
            )
            self._render_preview_empty("Invalid panel overlap", "Reduce overlap or increase the narrowest panel width.")
            self._preview_view = None
            self._preview_edge_targets = []
            return
        panel_layout, total_w, overlap = compute_panel_layout(widths, bleed_eff, overlap, overlap_mode)
        n = len(panel_layout)
        fit_mode = "stretch"
        pv = core_is_pdf_preserve_mode(self.export_mode_var.get())
        page_h = compute_preview_page_height(total_w, height, bleed_eff, pv, fit_mode, self._src_w_mm, self._src_h_mm)

        if pv and fit_mode == "width":
            h_txt = "(auto by width)"
        else:
            h_txt = fmt_mm(page_h)

        w_txt = fmt_mm(total_w)
        scale_text = ""
        if self._src_w_mm and self._src_h_mm and self._src_w_mm > 0 and self._src_h_mm > 0 and height > 0:
            scale_x = (sum(widths) / self._src_w_mm) * 100.0
            scale_y = (height / self._src_h_mm) * 100.0
            distortion = abs((scale_x / scale_y) - 1.0) if scale_y else 0.0
            warning = " - ASPECT STRETCH" if distortion > 0.01 else ""
            scale_text = f"   |   Scale X {scale_x:.1f}% / Y {scale_y:.1f}%{warning}"
        self.preview_var.set(
            f"Target: {w_txt} x {h_txt} mm   |   Panels: {n}   "
            f"(Bleed {fmt_mm(bleed_eff)} / Overlap {fmt_mm(overlap)} {overlap_mode}){scale_text}"
        )

        # Draw the visual preview on the canvas
        try:
            self._render_preview_canvas(panel_layout, bleed_eff, page_h, total_w)
        except Exception:
            # Ignore drawing errors in preview
            pass

    def _render_preview_empty(self, title: str, detail: str):
        if not hasattr(self, "preview_canvas"):
            return
        cv = self.preview_canvas
        cv.delete("all")
        C = getattr(self, "_theme_tokens", get_theme(self.theme_var.get()).colors)
        cw = max(1, int(cv.winfo_width()))
        ch = max(1, int(cv.winfo_height()))
        pad = 22
        cv.create_rectangle(
            pad,
            pad,
            max(pad + 1, cw - pad),
            max(pad + 1, ch - pad),
            outline=C.get("workspace_border", C["card_border"]),
            dash=(6, 5),
            width=1,
        )
        cx = cw / 2
        cy = ch / 2
        icon_w = 92
        icon_h = 72
        icon_x0 = cx - icon_w / 2
        icon_y0 = cy - 92
        icon_border = C.get("card_border", C["border"])
        icon_fill = C.get("tip_bg", C["card_bg_raised"])
        cv.create_rectangle(icon_x0, icon_y0, icon_x0 + icon_w, icon_y0 + icon_h, outline=icon_border, fill=icon_fill, width=2)
        cv.create_polygon(
            icon_x0 + 12,
            icon_y0 + icon_h - 12,
            icon_x0 + 36,
            icon_y0 + 38,
            icon_x0 + 58,
            icon_y0 + 58,
            icon_x0 + 78,
            icon_y0 + 28,
            icon_x0 + icon_w - 10,
            icon_y0 + icon_h - 12,
            fill=icon_border,
            outline="",
        )
        cv.create_oval(icon_x0 + icon_w - 30, icon_y0 + 16, icon_x0 + icon_w - 14, icon_y0 + 32, fill=icon_border, outline="")
        cv.create_text(cx, cy + 8, text=title, fill=C["text_primary"], font=("Segoe UI", 13, "bold"))
        cv.create_text(cx, cy + 34, text=detail, fill=C["text_secondary"], font=("Segoe UI", 10))
        cv.create_rectangle(40, max(40, ch - 58), max(41, cw - 40), max(41, ch - 22), outline=C["card_border"], fill=C["tip_bg"])
        cv.create_text(
            58,
            max(58, ch - 40),
            text="Tip: middle mouse pans - mouse wheel zooms - drag internal seams to edit panels",
            anchor="w",
            fill=C["text_secondary"],
            font=("Segoe UI", 9),
        )

    def _render_preview_canvas(self, panel_layout, bleed_mm, page_h_mm, total_w_mm):
        if not hasattr(self, "preview_canvas"):
            return
        cv = self.preview_canvas
        cv.delete("all")
        self._preview_view = None
        self._preview_edge_targets = []

        cw = max(1, int(cv.winfo_width()))
        ch = max(1, int(cv.winfo_height()))
        pad = 24
        if total_w_mm <= 0 or page_h_mm <= 0 or cw <= 2 * pad or ch <= 2 * pad:
            return

        # Theme colors
        C = getattr(self, "_theme_tokens", get_theme(self.theme_var.get()).colors)
        border = C.get("preview_border", C.get("border", "#888888"))
        accent = C.get("preview_panel", C.get("accent", "#4da3ff"))
        muted = C.get("preview_content", C.get("muted", "#b7b7b7"))
        overlap_fill = C.get("preview_overlap", "#f5b642")
        bleed_fill = C.get("preview_bleed", "#d64a4a")
        label_bg = C.get("panel", "#222222")
        label_fg = C.get("fg", "#ffffff")
        cv.create_rectangle(10, 10, max(11, cw - 10), max(11, ch - 10), outline=C["card_border"], fill=C["canvas_bg"])

        # Scale to fit and center
        sx = (cw - 2 * pad) / float(total_w_mm)
        sy = (ch - 2 * pad) / float(page_h_mm)
        s = min(sx, sy) * self._preview_zoom
        x0 = pad + (cw - 2 * pad - total_w_mm * s) / 2.0 + self._preview_pan[0]
        y0 = pad + (ch - 2 * pad - page_h_mm * s) / 2.0 + self._preview_pan[1]
        self._preview_view = {
            "x0": x0,
            "y0": y0,
            "scale": s,
            "page_h_mm": page_h_mm,
            "total_w_mm": total_w_mm,
        }
        self._preview_edge_targets = [
            {"edge_index": idx, "x_mm": panel_layout[idx]["content_right"]}
            for idx in range(max(0, len(panel_layout) - 1))
        ]

        def xx(mm):
            return x0 + mm * s

        def yy(mm):
            return y0 + mm * s

        # Background graphic (if available)
        if IMAGE_TK_AVAILABLE and self._bg_preview_im is not None:
            try:
                dest_w = max(1, int(round(total_w_mm * s)))
                dest_h = max(1, int(round(page_h_mm * s)))
                # Resize background to page area
                bg_resized = self._bg_preview_im.resize((dest_w, dest_h), resample=Image.BILINEAR)
                self._bg_preview_tk = ImageTk.PhotoImage(bg_resized)
                cv.create_image(xx(0), yy(0), image=self._bg_preview_tk, anchor="nw")
            except Exception:
                self._bg_preview_tk = None

        # Bleed bands
        if bleed_mm > 0:
            cv.create_rectangle(xx(0), yy(0), xx(bleed_mm), yy(page_h_mm), fill=bleed_fill, stipple="gray25", outline="")
            cv.create_rectangle(xx(max(0.0, total_w_mm - bleed_mm)), yy(0), xx(total_w_mm), yy(page_h_mm), fill=bleed_fill, stipple="gray25", outline="")
            cv.create_rectangle(xx(0), yy(0), xx(total_w_mm), yy(bleed_mm), fill=bleed_fill, stipple="gray25", outline="")
            cv.create_rectangle(xx(0), yy(max(0.0, page_h_mm - bleed_mm)), xx(total_w_mm), yy(page_h_mm), fill=bleed_fill, stipple="gray25", outline="")

        # Shared overlap zones
        for left_panel, right_panel in zip(panel_layout, panel_layout[1:], strict=False):
            overlap_left = right_panel["outer_left"]
            overlap_right = left_panel["outer_right"]
            if overlap_right > overlap_left:
                cv.create_rectangle(
                    xx(overlap_left),
                    yy(0),
                    xx(overlap_right),
                    yy(page_h_mm),
                    fill=overlap_fill,
                    stipple="gray25",
                    outline=overlap_fill,
                )

        # Page outline / final full artwork size
        cv.create_rectangle(xx(0), yy(0), xx(total_w_mm), yy(page_h_mm), outline=border, width=2)

        # Panels
        for idx, panel in enumerate(panel_layout, 1):
            outer_left = panel["outer_left"]
            outer_right = panel["outer_right"]
            cv.create_rectangle(xx(outer_left), yy(0), xx(outer_right), yy(page_h_mm), outline=accent, width=2)
            mid_x = (outer_left + outer_right) / 2.0
            label_y = 12 / max(s, 0.01)
            label = f"Panel {idx}"
            text_id = cv.create_text(xx(mid_x), yy(label_y), text=label, fill=label_fg, font=("Segoe UI", 10, "bold"))
            bx0, by0, bx1, by1 = cv.bbox(text_id)
            cv.create_rectangle(bx0 - 5, by0 - 3, bx1 + 5, by1 + 3, fill=label_bg, outline=accent)
            cv.tag_raise(text_id)

            content_left = panel["content_left"]
            content_right = panel["content_right"]
            top_bleed = bleed_mm
            bottom_bleed = bleed_mm
            cv.create_rectangle(
                xx(content_left),
                yy(top_bleed),
                xx(content_right),
                yy(max(0.0, page_h_mm - bottom_bleed)),
                outline=muted,
                width=1,
            )
            cv.create_line(xx(outer_left), yy(0), xx(outer_left), yy(page_h_mm), fill=accent, width=1)
            cv.create_line(xx(outer_right), yy(0), xx(outer_right), yy(page_h_mm), fill=accent, width=1)

    # ---------- Run ----------
    def _validate_profile_for_export(self, profile: ArtworkProfile):
        bleed_mm = float(profile.bleed_mm)
        widths_mm = parse_widths_list(profile.panel_widths)
        height_mm = float(profile.height_mm)
        overlap_txt = profile.overlap_mm.strip()
        overlap_mm = (2 * bleed_mm) if overlap_txt == "" else float(overlap_txt)
        preserve_vectors = core_is_pdf_preserve_mode(profile.export_mode)
        dpi_txt = profile.dpi.strip()
        try:
            dpi = int(dpi_txt) if dpi_txt else None
        except ValueError as exc:
            if preserve_vectors:
                dpi = None
            else:
                raise ValueError("DPI must be a whole number.") from exc
        values = validate_export_values(
            output_name=profile.file_name,
            bleed_mm=bleed_mm,
            widths_mm=widths_mm,
            height_mm=height_mm,
            overlap_mm=overlap_mm,
            overlap_mode=profile.overlap_mode,
            dpi=dpi,
            export_format=profile.export_format,
            preserve_vectors=preserve_vectors,
            color_mode=profile.color_mode,
        )
        if not preserve_vectors and profile.icc_mode != "Off":
            if not profile.icc_profile_path.strip() or not Path(profile.icc_profile_path).expanduser().is_file():
                raise ValueError("Choose a valid output ICC profile, or set ICC Handling to Off.")
        return ProfileExportValues(
            bleed_mm=values.bleed_mm,
            widths_mm=values.widths_mm,
            height_mm=values.height_mm,
            overlap_mm=values.overlap_mm,
            overlap_mode=values.overlap_mode,
            dpi=values.dpi,
            export_format=values.export_format,
            preserve_vectors=values.preserve_vectors,
            color_mode=values.color_mode,
            icc_mode=profile.icc_mode,
            icc_profile_path=profile.icc_profile_path,
            rendering_intent=profile.rendering_intent,
        )

    def _set_export_busy(self, busy: bool):
        self._export_running = busy
        if hasattr(self, "start_export_button"):
            self.start_export_button.configure(state="disabled" if busy else "normal")
        if hasattr(self, "cancel_export_button"):
            self.cancel_export_button.configure(state="normal" if busy else "disabled")
        if hasattr(self, "retry_failed_button"):
            self.retry_failed_button.configure(state="disabled" if busy else "normal")
        self._set_settings_enabled(bool(self._active_iid) and not busy)

    def on_cancel_export(self):
        if not self._export_running:
            return
        self._export_cancel_event.set()
        self.cancel_export_button.configure(state="disabled")
        self.status_var.set("Cancelling after the current panel finishes...")

    def on_retry_failed(self):
        if self._export_running:
            return
        retry_iids = []
        for iid, profile in self._profiles.items():
            retry = profile.output_status in {"Error", "Cancelled", "Processing", "Interrupted"}
            profile.selected = retry
            if retry:
                retry_iids.append(iid)
            self._update_profile_row(iid)
        if not retry_iids:
            messagebox.showinfo("Nothing to retry", "There are no failed or interrupted queue items.")
            return
        self.status_var.set(f"Ready to retry {len(retry_iids)} failed/interrupted job(s).")
        self.on_start()

    def _mark_jobs_interrupted(self, export_jobs, start_index: int):
        for pending in export_jobs[start_index:]:
            self._export_events.put(("job_state", pending.iid, "Interrupted", "pending"))

    def _preflight_output_plan(self, outdir: Path, export_jobs):
        if not str(self.outdir_var.get()).strip():
            raise ValueError("Choose an output folder before exporting.")
        try:
            outdir.mkdir(parents=True, exist_ok=True)
            if not outdir.is_dir():
                raise ValueError(f"Output path is not a folder: {outdir}")
            with tempfile.NamedTemporaryFile(prefix=".artboard-cutter-write-test-", dir=outdir, delete=True):
                pass
        except Exception as exc:
            raise ValueError(f"Output folder is not writable: {outdir}\n{exc}") from exc

        estimates = []
        for job in export_jobs:
            values = job.values
            try:
                source_size_bytes = job.source_path.stat().st_size
            except OSError:
                source_size_bytes = None
            estimate = estimate_export_job(
                widths_mm=values.widths_mm,
                height_mm=values.height_mm,
                bleed_mm=values.bleed_mm,
                overlap_mm=values.overlap_mm,
                overlap_mode=values.overlap_mode,
                dpi=values.dpi,
                color_mode=values.color_mode,
                export_format=values.export_format,
                preserve_vectors=values.preserve_vectors,
                output_root=outdir,
                source_size_bytes=source_size_bytes,
            )
            estimates.append((job.output_name, estimate))
        total_panels = sum(estimate.panel_count for _name, estimate in estimates)
        total_disk = sum(estimate.estimated_disk_bytes for _name, estimate in estimates)
        warnings = [f"{name}: {warning}" for name, estimate in estimates for warning in estimate.warnings]
        combined_warning = combined_disk_space_warning([estimate for _name, estimate in estimates])
        if combined_warning:
            warnings.append(combined_warning)
        details = [
            f"Jobs: {len(estimates)}   Panels: {total_panels}",
            f"Estimated output space: {format_bytes(total_disk)}",
        ]
        if warnings:
            details.extend(["", *warnings[:8]])
        if not messagebox.askyesno(
            "Export preflight",
            "\n".join(details) + "\n\nContinue with export?",
        ):
            raise PreflightCancelled("Export cancelled during preflight.")
        for name, estimate in estimates:
            self.log_print(f"[PREFLIGHT] {name}: " + "; ".join(estimate.summary_lines()))

        planned_paths = []
        stale_paths = []
        for job in export_jobs:
            values = job.values
            paths = build_output_paths(
                outdir,
                job.output_name,
                len(values.widths_mm),
                values.export_format,
                preserve_vectors=values.preserve_vectors,
            )
            planned_paths.extend(paths)
            stale_paths.extend(find_stale_panel_outputs(paths))

        duplicates = find_duplicate_paths(planned_paths)
        if duplicates:
            raise ValueError(
                f"Two selected jobs would write the same file:\n{duplicates[0]}\n"
                "Rename one of the queue items before exporting."
            )

        existing = [path for path in planned_paths if path.exists()]
        conflicts = sorted({*existing, *stale_paths}, key=lambda path: str(path).casefold())
        if not conflicts:
            return False, False
        preview = "\n".join(str(path.name) for path in conflicts[:8])
        if len(conflicts) > 8:
            preview += f"\n...and {len(conflicts) - 8} more"
        approved = messagebox.askyesno(
            "Replace existing panel outputs?",
            "The following existing panel files belong to these output names:\n\n"
            f"{preview}\n\nReplace the planned files and remove stale extra panels only after each job succeeds?",
        )
        if not approved:
            raise PreflightCancelled("Export cancelled because output files already exist.")
        return True, True

    def _poll_export_events(self):
        self._poll_after_id = None
        while True:
            try:
                event = self._export_events.get_nowait()
            except queue.Empty:
                break
            kind = event[0]
            if kind == "log":
                self.log_print(event[1])
            elif kind == "call":
                try:
                    event[1]()
                except Exception as exc:
                    self.log_print(f"[WARN] Background UI action failed: {exc}")
            elif kind == "import_ready":
                _, import_generation, path, profiles, error, defaults = event
                self._insert_imported_profiles(
                    path,
                    profiles,
                    error,
                    defaults,
                    import_generation=import_generation,
                )
            elif kind == "preview_ready":
                _, request, image, error = event
                if request == self._preview_request:
                    self._bg_preview_im = image
                    self._bg_preview_tk = None
                    if error:
                        self.log_print(f"[WARN] Could not render preview: {request[1]} ({error})")
                    self._update_preview()
            elif kind == "status":
                self.status_var.set(event[1])
            elif kind == "job_state":
                _, iid, output_status, validation_state = event
                profile = self._profiles.get(iid)
                if profile:
                    profile.output_status = output_status
                    profile.validation_state = validation_state
                    self._update_profile_row(iid)
                    self._schedule_recovery_save()
            elif kind == "progress":
                self.progress["value"] = event[1]
            elif kind in {"done", "cancelled"}:
                _, count, errors, outdir = event
                self._set_export_busy(False)
                self._export_thread = None
                if kind == "cancelled":
                    message = f"Cancelled. {count} succeeded, {errors} failed. Completed outputs: {outdir}"
                else:
                    message = f"Done. {count} succeeded, {errors} failed. Outputs: {outdir}"
                self.log_print("")
                self.log_print(message)
                self.status_var.set(message)
                if self._close_after_export:
                    self._close_cleanly()
                    return
        self._poll_after_id = self.after(50, self._poll_export_events)

    def on_start(self):
        if self._export_running:
            return
        self._save_selected_profile_settings()
        checked_items = [(iid, p) for iid, p in self._profiles.items() if p.selected]
        if not checked_items:
            msg = "Tick the checkbox next to the file(s) you want to process."
            self.status_var.set(msg)
            messagebox.showwarning("No files selected", msg)
            return

        export_jobs = []
        distortion_warnings = []
        try:
            for iid, profile in checked_items:
                values = self._validate_profile_for_export(profile)
                export_jobs.append(
                    PendingExportJob(
                        iid=iid,
                        source_path=Path(profile.file_path),
                        output_name=profile.file_name,
                        page_index=profile.source_page_index,
                        values=values,
                    )
                )
                profile.validation_state = "valid"
                self._update_profile_row(iid)
                if profile.original_width_mm and profile.original_height_mm:
                    scale_x = sum(values.widths_mm) / profile.original_width_mm
                    scale_y = values.height_mm / profile.original_height_mm
                    if scale_y and abs((scale_x / scale_y) - 1.0) > 0.01:
                        distortion_warnings.append(
                            f"{profile.file_name}: X {scale_x * 100:.1f}% / Y {scale_y * 100:.1f}%"
                        )
        except Exception as e:
            msg = str(e) if str(e) else "Please check bleed, overlap, panel widths, height, DPI, and format."
            self.status_var.set(msg)
            messagebox.showerror("Invalid parameters", msg)
            return

        if distortion_warnings:
            preview = "\n".join(distortion_warnings[:8])
            if len(distortion_warnings) > 8:
                preview += f"\n...and {len(distortion_warnings) - 8} more"
            if not messagebox.askyesno(
                "Non-uniform artwork stretch",
                "The target proportions differ from the source, so these jobs will be stretched differently on X and Y:\n\n"
                f"{preview}\n\nContinue with the requested dimensions?",
            ):
                self.status_var.set("Export cancelled before stretching artwork.")
                return

        outdir = Path(self.outdir_var.get()).expanduser()
        try:
            overwrite, cleanup_stale = self._preflight_output_plan(outdir, export_jobs)
        except PreflightCancelled as exc:
            self.status_var.set(str(exc))
            return
        except Exception as exc:
            self.status_var.set(str(exc))
            messagebox.showerror("Cannot start export", str(exc))
            return
        self._save_settings()

        self.progress["value"] = 0
        self.progress["maximum"] = len(export_jobs)
        self.status_var.set(f"Exporting {len(export_jobs)} file(s)...")
        self._export_cancel_event.clear()
        self._close_after_export = False
        self._set_export_busy(True)

        def work():
            count = 0
            errors = 0
            cancelled = False
            for job_index, job in enumerate(export_jobs):
                i = job_index + 1
                if self._export_cancel_event.is_set():
                    cancelled = True
                    self._mark_jobs_interrupted(export_jobs, job_index)
                    break
                values = job.values
                try:
                    self._export_events.put(("job_state", job.iid, "Processing", "valid"))
                    self._export_events.put(("status", f"Processing {job.output_name} ({i}/{len(export_jobs)})"))
                    process_file(
                        job.source_path,
                        bleed_mm=values.bleed_mm,
                        widths_mm=values.widths_mm,
                        height_mm=values.height_mm,
                        overlap_mm=values.overlap_mm,
                        overlap_mode=values.overlap_mode,
                        dpi=values.dpi,
                        output_root=outdir,
                        export_fmt=values.export_format,
                        preserve_vectors=values.preserve_vectors,
                        vector_fit_mode="stretch",
                        page_index=job.page_index,
                        output_name=job.output_name,
                        overwrite=overwrite,
                        cleanup_stale=cleanup_stale,
                        cancel_check=self._export_cancel_event.is_set,
                        color_mode=values.color_mode,
                        icc_mode=values.icc_mode,
                        icc_profile_path=values.icc_profile_path,
                        rendering_intent=values.rendering_intent,
                        log_cb=lambda message: self._export_events.put(("log", message)),
                    )
                    self._export_events.put(("job_state", job.iid, "Done", "valid"))
                    count += 1
                except ExportCancelled:
                    self._export_events.put(("job_state", job.iid, "Cancelled", "pending"))
                    self._mark_jobs_interrupted(export_jobs, job_index + 1)
                    cancelled = True
                    break
                except Exception as e:
                    errors += 1
                    self._export_events.put(("job_state", job.iid, "Error", "error"))
                    self._export_events.put(("log", f"[ERROR] {job.source_path}: {e}"))
                finally:
                    self._export_events.put(("progress", i))
            self._export_events.put(("cancelled" if cancelled else "done", count, errors, outdir))

        self._export_thread = threading.Thread(target=work, daemon=False)
        self._export_thread.start()

def run_packaged_self_test() -> None:
    """Exercise the packaged Tk/DnD runtime and lazy-loaded TIFF codec path."""
    root = BaseTk()
    try:
        root.withdraw()
        root.update_idletasks()
    finally:
        root.destroy()
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow is unavailable in the packaged application.")
    with tempfile.TemporaryDirectory(prefix="artboard-cutter-self-test-") as td:
        root = Path(td)
        source = root / "source.png"
        image = Image.new("RGB", (48, 32))
        for x in range(image.width):
            for y in range(image.height):
                image.putpixel((x, y), (x * 5 % 256, y * 7 % 256, (x + y) * 3 % 256))
        image.save(source)
        result = process_file(
            source,
            bleed_mm=0,
            widths_mm=[48],
            height_mm=32,
            overlap_mm=0,
            dpi=72,
            output_root=root / "out",
            export_fmt="tiff",
            output_name="self-test",
        )
        output = result.output_paths[0]
        with Image.open(output) as checked:
            checked.load()
            if checked.format != "TIFF" or checked.mode != "RGB":
                raise RuntimeError("Packaged TIFF self-test produced an invalid output.")

        import numpy as np
        import tifffile

        lossless_source = root / "lossless-source.tif"
        pixels = np.array([[[10, 20, 30], [40, 50, 60]]], dtype=np.uint8)
        tifffile.imwrite(lossless_source, pixels, photometric="rgb", compression="lzw", rowsperstrip=1)
        lossless_outputs = export_lossless_tiff_pdf(
            lossless_source,
            page_index=0,
            widths_mm=[2],
            height_mm=1,
            bleed_mm=0,
            overlap_mm=0,
            overlap_mode="shared",
            base_name="lossless-self-test",
            outdir=root / "lossless-out",
        )
        pdf = fitz.open(lossless_outputs[0])
        try:
            page = pdf.load_page(0)
            embedded = fitz.Pixmap(pdf, page.get_images(full=True)[0][0])
            if bytes(embedded.samples) != pixels.tobytes():
                raise RuntimeError("Packaged Lossless PDF self-test changed TIFF pixels.")
        finally:
            pdf.close()


def main():
    if "--self-test" in sys.argv:
        try:
            run_packaged_self_test()
        except Exception:
            Path("packaged-self-test-error.log").write_text(traceback.format_exc(), encoding="utf-8")
            os._exit(1)
        os._exit(0)
    app = App(startup_job=startup_job_path(sys.argv[1:]))
    app.mainloop()


if __name__ == "__main__":
    main()
