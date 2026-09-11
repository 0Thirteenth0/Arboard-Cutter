# Testing Notes

## Local Tcl/Tk Runtime

GUI smoke tests are guarded so restricted environments without access to the
local Tcl library report a skip. On the Windows host, the current Python 3.14
Tk 8.6.15 runtime was verified successfully and all GUI smoke tests passed.

Observed command:

```powershell
python -m unittest tests.test_gui_smoke -v
```

Observed skip reason:

```text
Tk unavailable for interactive GUI smoke tests: Can't find a usable init.tcl in the following directories:
    {C:\Users\jiahu\AppData\Local\Programs\Python\Python313\tcl\tcl8.6}

This probably means that Tcl wasn't installed properly.
```

The sandbox-only skip is an environment access limitation, not an application
failure. Run the suite from a normal Windows terminal for the complete result.

Local setup checks:

```powershell
.\.venv\Scripts\python.exe -c "import tkinter as tk; root=tk.Tk(); print(root.tk.call('info','patchlevel')); root.destroy()"
.\.venv\Scripts\python.exe -m unittest tests.test_gui_smoke -v
```

If the first command fails before application code runs, repair or reinstall the
local Python Tcl/Tk runtime. On Windows, also check that `TCL_LIBRARY` and
`TK_LIBRARY` are not pointing at stale Tcl/Tk folders from another Python
installation. The guarded GUI tests are designed to report the exact exception
instead of failing unrelated CI jobs.

## Test Coverage Added

- Streaming RGB/CMYK TIFF, ICC embedding, and raster-PDF output-intent checks.
- Automatic output verification and blank/uniform-output rejection.
- BigTIFF and large-job preflight decisions.
- PDF Preserve size estimation and combined-batch disk-space warnings.
- Direct panel-count redistribution across the unchanged overall artwork width.
- Recovery-job serialization, clean-close cleanup, grouped queue removal, and retry/resume state coverage.
- Finite numeric validation, strict ICC verification, and PDF Preserve blank-output rejection.

- Theme WCAG contrast checks for all built-in theme foreground/background pairs.
- Theme token presence checks for centralized design tokens such as background,
  card, canvas, text, accent, input, button, table, scrollbar, selection,
  warning, error, and success.
- Preview overlay contrast checks for all built-in themes.
- Interactive GUI launch smoke test, skipped when Tk is unavailable.
- Preview screenshot/snapshot smoke test across themes, skipped when Tk or screenshot capture is unavailable.
- Windows high-DPI scaling smoke test, skipped outside Windows or when Tk is unavailable.
- Raster/PDF Preserve rendered pixel alignment test.
- Raster image input through PDF Preserve mode.
- Rotated PDF fixture export test.
- Unusual page box fixture export test.
- GUI wrapper compatibility test that verifies legacy public wrappers still
  delegate into the extracted export engine.
- Illustrator integration fallback tests that do not require Illustrator.

## Manual GUI Validation

Run these checks after `tkinter.Tk()` works locally:

- Set the panel count directly and confirm every panel is redistributed across the unchanged total artwork width.
- Export ICC-managed JPG, TIFF, and raster PDF and inspect the embedded profile/output intent in the production color tool.
- Cancel a multi-job run, restart the app abnormally, restore the recovery queue, and use `Retry Failed / Resume`.
- Review the preflight panel count, effective DPI, estimated size, BigTIFF status, and free-space warning before continuing.

- Launch `python artboard_cutter_gui_advanced.py`.
- Add one single-page file and one multi-page/AI-compatible file.
- Confirm selecting different queue rows restores each row's independent width,
  height, bleed, overlap, overlap mode, DPI, export format, and export mode.
- Confirm parent queue selection toggles all child rows and child row selection
  updates the parent `n/n selected` status.
- Use `Reset Size` on one child row and confirm no other child row changes.
- Switch every built-in theme and confirm labels, radio selections, buttons,
  queue rows, queue headings, and preview overlays remain readable.
- Confirm field labels blend into their card surface and do not appear as
  selected/highlighted blocks.
- Confirm toolbar/action icons appear for preview, queue, export, browse, and
  log actions in both Soft Blue and Dark Pro.
- Confirm the empty preview workspace and empty artwork queue message remain
  readable in every theme.
- Export both Raster and PDF Preserve with `Shared` and `Left` overlap modes; compare
  panel dimensions and visible overlap zones against the live preview.
- In PDF Preserve mode, test both PDF/AI-compatible PDF content and raster image
  inputs. Raster images should stay embedded raster content inside PDF panels,
  not become traced vector paths.
- Test interactive preview editing: mouse wheel zoom, middle mouse pan, Add
  Panel evenly dividing total artwork width across all panels, internal seam dragging, and seam-limit reset near neighboring seams or
  outside bleed edges.
- Export one JPG and one TIFF and confirm no PDF is produced for those jobs.
- Check both RGB and CMYK output in the target prepress software. When ICC
  handling is enabled, confirm conversion or embedding matches the selected profile.
- Cancel a multi-panel export and confirm no partial replacement set remains.
- Save/apply/delete a preset, then save and reload a complete queue job.
- Shrink the application window vertically and horizontally. Confirm there are
  no global root-window scrollbars, the preview remains in the left panel, and
  the right control column exposes queue/settings/run/log content through its
  own vertical scrollbar only when needed.

## Preview/Export Equivalence

The preview and export paths share `compute_panel_layout()`, so geometry should
match for panel boundaries, outside-only bleed, and overlap zones. Screenshot
validation is guarded by Tk availability in `tests/test_gui_smoke.py`.

Manual visual checks should include:

- Equal-width and custom-width panels.
- Outside bleed visible only on the full artwork's outside edges.
- `Shared` overlap split between neighbors.
- `Left` overlap where only the right/later panel extends left.
- Raster and PDF Preserve output rendered back to pixels for visible alignment.
- Theme changes without preview overlay loss.

## Runtime Logs

JSON runtime logs are written under:

```text
%LOCALAPPDATA%\ArtboardCutter\logs\
```

The GUI includes an `Open Logs Folder` button in the Run panel. The action
creates the folder if needed and opens it with the platform file browser. If the
platform opener fails, the GUI shows a readable error dialog.

## Queue Widget Limits

The queue uses `ttk.Treeview` for native row grouping, selection, scrolling, and
editing behavior. `Treeview` cells cannot embed real native ttk checkbox widgets,
so the Select column uses checkbox glyph/image indicators and click handling.

`ttk.Treeview` also always places the hierarchy expand/collapse arrow in the
special tree column `#0`, which is the leftmost tree column. Keeping the arrow in
File Name means File Name must remain the first visible column. Moving Select to
the first visible column while keeping the arrow in File Name would require a
custom queue widget or a different UI framework.

## Illustrator-Dependent Behavior

Default import does not require Illustrator. PyMuPDF reads the PDF-compatible
content and the app falls back to deterministic numbered names such as
`Poster1`, `Poster2`, `Poster3`.

Real `.ai` artboard names require all of the following:

- Windows
- Adobe Illustrator installed and already running
- `pywin32`

The `Get Names` queue action runs Illustrator lookup in the background with a
timeout and does not cold-start Illustrator. If Illustrator is unavailable,
unresponsive, or blocked by its own missing-link/modal state, the app keeps the
numbered names and shows a user-facing warning.

## Diff Artifacts

Raster/PDF Preserve alignment failures write a PPM diff image under:

```text
test_outputs/failures/
```

`test_outputs/` is intentionally ignored by Git.

Other local artifacts intentionally ignored by Git:

- `TEST.pdf`
- generated files under `logs/`
- generated PDF/image exports

## Comprehensive Diagnostic Pass

The 2026-08-11 baseline runs the complete suite on a real Windows desktop so Tk, screenshot, threaded queue, and GUI-driven TIFF export checks do not skip:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m compileall -q artboard_cutter_gui_advanced.py src tests tools
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Expected baseline: 129 tests executed with 12 GUI skips when Tk is unavailable. Coverage includes every output format, lossless RGB/CMYK TIFF-to-PDF bytes, Shared/Left overlap, PDF layer visibility, multi-page input, cancellation/rollback, overwrite/stale cleanup, malformed persistence data, Explorer job launch, queue lifecycle, themes, recovery, and multi-panel TIFF content checks.

For release acceptance, install the generated setup package and verify that double-clicking a `.artboard-job` file with spaces in its path launches Artboard Cutter and loads the saved queue. Legacy `.artboard-job.json` files should remain loadable from **Load Job...** but are intentionally not registered as the system-wide `.json` handler.

Automated tests cannot prove the absence of every possible defect. Production acceptance still includes representative printer/RIP output, real Illustrator COM behavior, extreme BigTIFF jobs, linked assets, spot colors, overprint, and signed-installer checks.
