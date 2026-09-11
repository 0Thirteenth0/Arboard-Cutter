# Architecture

Track program structure, data flow, and module responsibilities here.

## 2026-05-19 - Current architecture audit

The current application is a single-file tkinter desktop app in `artboard_cutter_gui_advanced.py`.

Current responsibilities inside that file:

- UI construction and event handling.
- File drag/drop and selection state.
- Per-file parameter memory for width/height only.
- Unit conversion.
- Panel layout calculation.
- Source file opening.
- Raster export.
- Vector export.
- Preview rendering.
- Theme styling.
- GUI log output.

The central behavior to preserve is `compute_panel_layout()`: outside-only bleed plus shared internal overlap. Preview, raster export, and vector export all call this same function today, which is good. The rebuild should preserve this as a dedicated engine function with tests.

Main architectural issue: UI and export engine are tightly coupled. Export functions receive GUI-oriented callbacks, and preview/export math is repeated in different forms. The next architecture should split engine code from presentation code before changing behavior deeply.

## 2026-05-19 - First modular structure

Added `src/artboard_cutter_core/`:

- `units.py`: point/mm conversion, scale helpers, pixel estimates, mm formatting.
- `layout.py`: `PanelLayout`, width parsing, shared-overlap layout, preview height helper.
- `pdf_io.py`: robust source opening, page box forcing, page box snapshots.
- `raster_images.py`: PyMuPDF pixmap to Pillow conversion plus JPG/TIFF save helpers.
- `raster_export.py`: raster panel export with DPI and megapixel cap behavior preserved.
- `vector_export.py`: vector panel export using explicit logged crop rectangles and page box snapshots.
- `export.py`: `ExportOptions` and file-level export orchestration.
- `settings.py`: initial JSON settings model and load/save helpers.
- `logging_config.py`: rotating JSON runtime logger.

The current GUI still exists in `artboard_cutter_gui_advanced.py`, but now routes the preserved helper names to the engine. This keeps the app runnable while allowing future UI cleanup.

## 2026-05-19 - Theme architecture

Added centralized theme definitions in `src/artboard_cutter_core/themes.py`.

Theme structure:

- `Theme`: immutable dataclass with name, dark/light flag, and color tokens.
- `THEMES`: built-in professional theme registry.
- `THEME_NAMES`: ordered list for UI selectors.
- `normalize_theme_name()`: maps legacy `dark`/`light` settings and invalid values to safe theme names.
- `get_theme()`: returns the active theme object.

Built-in themes:

- Professional Dark
- Professional Light
- Graphite
- Midnight
- Neutral Gray
- High Contrast
- Soft Blue
- Warm Dark

Color tokens include core UI colors and preview-specific overlay tokens so preview readability is maintained per theme:

- `preview_bg`
- `preview_border`
- `preview_panel`
- `preview_content`
- `preview_bleed`
- `preview_overlap`
- `preview_label_bg`
- `preview_label_fg`

Adding a new theme should only require adding one `Theme` entry with the full token set.

## 2026-05-19 - Current Architecture Snapshot

Current source of truth remains `artboard_cutter_gui_advanced.py`, with export/math functionality increasingly delegated into `src/artboard_cutter_core/`.

Current structure:

- `artboard_cutter_gui_advanced.py`: tkinter desktop shell, modern layout, preview canvas, file queue, settings controls, export status, activity log.
- `src/artboard_cutter_core/workflow.py`: typed validated profile values and pending export-job records shared by GUI workflow code.
- `src/artboard_cutter_core/layout.py`: panel layout source of truth, including outside-only bleed and shared overlap.
- `src/artboard_cutter_core/export.py`: file-level export orchestration and `ExportOptions`.
- `src/artboard_cutter_core/raster_export.py`: raster export path.
- `src/artboard_cutter_core/vector_export.py`: vector PDF export path; GUI-facing vector behavior is now always stretch-to-fit.
- `src/artboard_cutter_core/settings.py`: persisted app settings.
- `src/artboard_cutter_core/profiles.py`: session-only queued artwork profile model.
- `src/artboard_cutter_core/themes.py`: centralized professional theme definitions and preview overlay tokens.
- `tests/`: layout, export geometry, settings, and theme tests.
- `docs/testing.md`: local test notes, including GUI/Tcl skip behavior and visual diff artifact location.

Important transitional state:

- `artboard_cutter_gui_advanced.py` still contains legacy wrapper functions for compatibility, but the constructor dead branch has been removed.
- `artboard_cutter_gui.py` and `artboard_cutter_gui_v1.py` remain deleted in the working tree from cleanup.

## 2026-05-19 - ArtworkProfile state model

`ArtworkProfile` is the session model for one queued artwork. It is intentionally not persisted to disk.

Stored per-artwork fields:

- file path and derived file name
- editable output name
- source page/artboard index
- source page/artboard count
- original artwork width and height
- current panel widths and height
- bleed and overlap
- DPI
- export format
- export mode
- vector preservation flag
- vector fit mode, currently always `stretch`
- output status
- validation state
- selected-for-processing state

Global persisted fields remain in `AppSettings`: output folder, theme, last input path, last-used bleed/overlap/DPI/format/mode defaults, recent paths, and window geometry.

The GUI saves the active row back into its profile before switching rows, before persisting global defaults, and before export. Selecting a row loads that row's profile into the settings panel and preview. Removing or clearing rows deletes the corresponding profiles from memory.

Multi-page import behavior:

- `create_artwork_profiles()` opens the source document and creates one profile per page/artboard.
- Single-page files use the source filename stem as the queue/output name.
- Multi-page files use the source filename stem plus 1-based page number, for example `Poster1`, `Poster2`, `Poster3`.
- Export reads the profile's `source_page_index` so later pages are not silently ignored.
- Export reads the profile's editable `output_name` as the output base name.
- For `.ai` files on Windows, optional Illustrator COM integration can read real Illustrator artboard names when the user triggers `Get Names` from the queue group row.
- Illustrator names are sanitized for filesystem-safe output names and duplicates are made unique.

Queue grouping behavior:

- Multi-page imports create a parent Treeview row named with the original filename.
- Child rows under that parent are the actual exportable `ArtworkProfile` entries.
- The parent row can be expanded/collapsed with the native Treeview arrow in the File Name column.
- The Select column remains separate from the hierarchy and toggles parent/child processing state.
- Single-page imports remain as direct leaf rows.
- Parent row actions apply to the child profiles; export only iterates leaf profiles.

Reset size behavior:

- Reads `original_width_mm` and `original_height_mm` from the selected profile.
- Writes those values into the profile's current panel widths and height.
- Updates the visible fields and preview.
- Does not touch any other queued artwork.

Overlap behavior:

- `compute_panel_layout()` is still the canonical layout function for preview, raster export, and vector export.
- `Shared` overlap mode is the legacy behavior: each internal overlap is split equally across the neighboring panels.
- `Left` overlap mode keeps each panel's right edge at its content edge unless it is the final outside-bleed edge. The next panel extends left by the full overlap amount.
- `ArtworkProfile.overlap_mode` stores the per-queued-artwork mode for the current session.
- `AppSettings.overlap_mode` stores only the last-used global default for the next launch.

Settings persistence:

- App settings are saved to `%LOCALAPPDATA%/ArtboardCutter/settings.json`.
- Persisted global/default parameters now include `bleed_mm`, `overlap_mm`, `overlap_mode`, `dpi`, `export_format`, `export_mode`, output folder, theme, and window geometry.
- Per-artwork queue settings still remain session-only in `ArtworkProfile` and are not written to AppData.
- Older settings files that do not have `overlap_mode` load with the dataclass default `Shared`.

Runtime log access:

- Structured JSON logs are still written by `src/artboard_cutter_core/logging_config.py` under `logs/`.
- The GUI Run panel includes `Open Logs Folder`, which creates the folder if needed and opens it with the platform file browser.
- The app does not yet include an in-app log viewer; users inspect JSON logs in the opened folder.

Compatibility wrappers:

- `artboard_cutter_gui_advanced.py` keeps public wrapper functions for legacy callers and tests.
- Those wrappers now delegate directly to the extracted core engine without retaining unreachable old function bodies.
- New code should prefer importing from `src/artboard_cutter_core/` directly.

Current validation boundary:

- Geometry, export, profile, settings, theme contrast, Illustrator fallback, and wrapper delegation are covered by automated tests.
- GUI launch, preview screenshots, and high-DPI scaling are represented by guarded tests but currently skip because local Tcl/Tk cannot create a root window.
- Manual GUI validation should resume after the local Python/Tcl runtime is repaired.

Build/icon packaging:

- `assets/artboard_cutter.ico` is embedded as the Windows executable icon through PyInstaller.
- The same icon is bundled as runtime data so tkinter can apply it to the app window when available.
- `tools/generate_icon.py` regenerates the source PNG and multi-size ICO asset.
- `build_exe.bat` regenerates the icon before running PyInstaller through `ArtboardCutter.spec`.
- `ArtboardCutter.spec` is the single maintained PyInstaller spec.
- Shortcuts should inherit the embedded executable icon; generated shortcuts can also set `IconLocation` to `ArtboardCutter.exe,0` explicitly.

## 2026-05-19 - Test architecture additions

Added shared test helpers in `tests/helpers.py`:

- generated grid PDF fixture
- generated color stripe PDF fixture
- rotated PDF fixture
- unusual CropBox/TrimBox/BleedBox fixture
- PDF-to-RGB rendering helper
- pixel diff statistics helper
- PPM diff artifact writer
- guarded Tk availability helper

GUI tests intentionally skip instead of failing when Tk cannot create a root window. This keeps non-GUI CI stable while still allowing interactive smoke and preview snapshot validation to run automatically in a healthy Windows/Tk environment.

## 2026-05-26 - Interactive preview editor layer

The tkinter canvas preview now keeps lightweight interaction state in addition to drawing the preview:

- current canvas-to-millimeter transform
- current preview page size
- cached internal panel edge hit targets
- active pan state
- active internal-edge drag state

The edit model remains intentionally narrow:

- Panel geometry is still driven by `compute_panel_layout()`.
- The editable source of truth is still the active `ArtworkProfile.panel_widths` string.
- Interactive edge dragging updates adjacent panel widths while preserving total content width.
- The global overlap value remains global; the editor does not introduce per-edge overlap state.
- Outside bleed edges are not included in the hit-target cache, so they remain locked.

Core panel-editing helpers now live in `src/artboard_cutter_core/layout.py`:

- `split_last_panel_width()`
- `resize_adjacent_panel_widths()`

These helpers are independent of tkinter so future preview/editor features can share tested geometry behavior with the GUI.

## 2026-05-26 - PDF Preserve export mode

The fast PDF export path is now exposed as `PDF Preserve` in the UI.

Compatibility:

- Legacy profile/settings values of `Vector` normalize to `PDF Preserve`.
- The engine still uses `ExportOptions.preserve_vectors` internally to minimize churn in export call sites.

Behavior:

- PDF and AI-compatible PDF inputs are clipped through the existing stretch-master PDF pipeline, preserving vector operators where PyMuPDF can preserve them.
- Raster image inputs are converted by PyMuPDF to an in-memory PDF document before the same stretch-master pipeline runs.
- Raster image inputs remain embedded raster content inside PDF panels; no tracing/vectorization is attempted.
- JPG/TIFF output still requires Raster mode because those formats have no vector-preserving container.

## 2026-05-26 - Fixed two-column root layout

The global app scroll viewport was removed after review because root-level
horizontal and vertical scrollbars made the application feel like a web page
instead of a desktop production tool.

Current tkinter layout:

- The root window uses a fixed grid: topbar row plus a full-height horizontal
  `ttk.Panedwindow` body.
- The left pane contains the Live Preview label frame, a compact preview toolbar,
  and the preview canvas. Preview overflow remains handled by preview zoom/pan.
- The right pane contains a canvas-backed vertical scroll viewport for controls
  only: artwork queue, export settings, run controls, and activity log.
- The artwork queue keeps its own internal `ttk.Treeview` scrollbar.
- No global horizontal scrollbar is created.
- The right-side scrollbar is hidden when the control stack fits and shown only
  when the available window height is too short.

## 2026-05-26 - Theme token redesign

The theme system now exposes richer design tokens while preserving old aliases
used by existing code and tests.

Primary token groups:

- app background and card surfaces
- borders and stronger borders
- primary/secondary text
- accent and accent hover
- button and input states
- table background/header/selection
- warning/error/success
- preview workspace and overlay colors

Built-in themes now include the requested production-tool set:

- Soft Blue
- Minimal Light
- Dark Pro
- Industrial Gray
- Blueprint

Legacy theme names remain available for compatibility. `dark` maps to Dark Pro,
`light` maps to Minimal Light, and invalid theme names fall back to Soft Blue.

The tkinter styling layer still uses `ttk`, but styles are now driven by the
central token dictionary instead of scattered one-off color choices.

## 2026-05-26 - Reference-style UI polish

The current UI remains tkinter/ttk, but the visual structure now follows a
card-based production-tool layout:

- Major sections are explicit card frames instead of relying on heavy nested
  `ttk.LabelFrame` borders.
- Theme tokens now include app, card, canvas, button, primary button, input,
  table, scrollbar, status, and preview-specific aliases.
- Field labels use card-surface label styles so labels no longer look selected
  or highlighted when nested inside settings rows.
- Local action icons live under `assets/icons/` and are loaded with the same
  `resource_path()` helper used by packaged builds.
- The PyInstaller spec bundles `assets/icons/` so packaged executables can load
  UI button icons without network access or extra dependencies.

## 2026-08-08 - Reliability and workflow architecture

- `validation.py` is the shared validation boundary for GUI and engine exports.
- `output_io.py` centrally builds extensions and stages every panel before atomically replacing an output set. Existing panels are restored if commit fails; stale panels are removed only after success.
- GUI workers deliver import, preview, and export results through a main-thread event queue; `concurrency.py` serializes PyMuPDF operations.
- `jobs.py` atomically stores complete queue profiles in versioned `.artboard-job` files and still reads legacy `.artboard-job.json` files. Named presets remain in AppData settings.
- Raster rendering combines resize and requested DPI in one PyMuPDF matrix. The shared Pillow adapter writes explicit JPG/TIFF files and preserves RGB/CMYK where supported.
- Rotating runtime logs live under `%LOCALAPPDATA%\ArtboardCutter\logs`, with a temporary-directory fallback.

## 2026-08-08 - Large CMYK raster safety

- Raster limits now account for uncompressed render bytes, not only pixel count. CMYK uses four channels and therefore reaches MuPDF's internal image limit earlier than RGB.
- JPG and raster-PDF jobs calculate one effective safe DPI from the largest panel and apply it to the complete set. TIFF writes bounded strips and retains the requested DPI, selecting BigTIFF when the uncompressed sample size requires it.
- Staged verification runs before transactional commit. TIFF uniformity checks decode one strip at a time so verification does not undo the bounded-memory design.
- ICC handling supports conversion or assignment, embeds profiles in JPG/TIFF, and adds a PDF output intent for raster PDF.
- A high-resolution unicolor result is compared with a low-resolution render of the same crop. If the low-resolution crop contains artwork, the high-resolution result is treated as MuPDF's silent blank failure and the transactional export is aborted.

## 2026-08-11 - Windows Tcl/Tk packaging

- `packaging_hooks/` overrides PyInstaller's false-negative Tk detection for the standalone Python 3.14 Windows layout.
- The custom hooks collect `_tkinter.pyd`, Tcl/Tk DLLs, and the Tcl/Tk data trees, then point the one-file runtime at `_tcl_data` and `_tk_data`.
- `build_exe.bat` refuses to build if Tk cannot initialize in the build environment.
- The packaged `--self-test` initializes Tk/TkDND before exercising streamed TIFF output, so a release cannot pass while its GUI runtime is missing.

## 2026-08-26 - PDF layer state and Windows document launch

- PDF Preserve captures the source default optional-content configuration before panel generation and reconstructs `/OCProperties` after PyMuPDF imports the layer objects into each output document.
- Layer state matching uses the imported OCG names and stable occurrence order, preserving source default-hidden layers without flattening vector content.
- The GUI accepts a startup job path, delays loading until Tk initialization is complete, and suppresses the competing crash-recovery prompt for that launch.
- `.artboard-job` is the dedicated Windows document extension. The installer registers its icon and quoted open command; legacy compound `.artboard-job.json` files remain readable only through the in-app loader so Artboard Cutter never claims all JSON files.

## 2026-09-10 - Lossless oversized TIFF PDF path

- The existing preserve-mode decision remains the shared UI and settings contract; its visible label is now Lossless PDF.
- Ordinary PDF/AI and supported raster documents continue through PyMuPDF's page-clipping path.
- Oversized TIFF fallback documents route to a bounded TIFF-to-PDF writer that reads source strips once, divides rows among every panel, applies fast lossless Flate compression, and never creates a full-frame raster.
- Each panel contains only its required source columns, including overlap, instead of duplicating the complete source image behind every PDF crop.
