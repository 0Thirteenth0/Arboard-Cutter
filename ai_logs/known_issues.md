# Known Issues

Track bugs, limitations, and follow-up risks here.

## 2026-05-19 - Historical Audit Findings

These were initial audit risks. Several have since been addressed by the rebuild:

- Vector output now uses stretch-to-fit PDF export through a full-size vector master page before clipping panels.
- Page box and rotated PDF behavior have generated fixture tests.
- Runtime JSON logs are generated under `logs/`, and the GUI can open that folder.
- User settings are persisted through `%LOCALAPPDATA%/ArtboardCutter/settings.json`.
- Preview still needs hands-on visual equivalence validation in a working GUI runtime.
- `artboard_cutter_gui.py` and `artboard_cutter_gui_v1.py` are currently deleted in the working tree from cleanup, but not committed.

## 2026-05-19 - UI smoke test environment issue

- Running `App()` directly with the local Python interpreter failed because Tcl/Tk could not find `init.tcl`.
- This may not affect the PyInstaller build because the packaged app includes Tcl/Tk data, but the local development environment should be checked before relying on interactive GUI smoke tests.
- Rechecked during GUI test backlog work: `init.tcl` exists in `C:\Users\jiahu\AppData\Local\Programs\Python\Python313\tcl\tcl8.6`, but `_tkinter` still raises `TclError`.
- Added guarded GUI tests that skip with the exact Tcl/Tk error instead of failing CI.

## 2026-05-19 - Current Known Issues

- Interactive GUI smoke testing is blocked in the local Python environment by Tcl/Tk `init.tcl` resolution.
- Preview has improved overlays, zoom, and pan, but visual equivalence to final exports still needs screenshot/manual verification inside a working GUI runtime.
- Runtime JSON logs are generated and the UI can open the log folder, but the app does not yet include an in-app log viewer or log-level controls.
- Queue profile state is covered by model tests and compile checks, but still needs hands-on GUI verification once local Tk is usable.
- Queue checkboxes are rendered with checkbox glyphs inside `ttk.Treeview`; native embedded ttk checkbox widgets are not supported by Treeview cells.
- Real `.ai` artboard names require Windows, Adobe Illustrator, and `pywin32`; when unavailable the app falls back to numbered queue names.
- Native `ttk.Treeview` always places its hierarchy/expand arrow in the leftmost tree column. Keeping the arrow in File Name means File Name must be the first visible column unless the queue is rebuilt with a custom widget.
- Illustrator can still become unresponsive internally while opening files with missing links; Artboard Cutter now runs name lookup in the background with a timeout and does not launch Illustrator from a cold start, but it cannot repair Illustrator's own modal/loading state.
- `TEST.pdf`, generated logs, and `test_outputs/` are ignored/untracked local artifacts.

## 2026-05-19 - Resolved In Latest Pass

- Unreachable old export bodies were removed from `artboard_cutter_gui_advanced.py` compatibility wrappers.
- GUI-level wrapper behavior is covered by a delegation/export test.
- Illustrator fallback behavior is covered for non-AI files and `require_running=True` without a running Illustrator process.
- `docs/testing.md` now documents Tcl/Tk setup checks, manual GUI validation, preview/export equivalence checks, queue widget limits, Illustrator requirements, and runtime log access.
- Vector export with blank DPI no longer fails validation; Raster still requires DPI.

## 2026-08-08 - Remaining limitations

- ICC conversion can use an embedded RGB raster profile or an sRGB working-space assumption. PDF/AI source profiles are not fully discoverable through the current renderer, so confirm the assumed source space for color-critical legacy files.
- PDF Preserve fidelity for Illustrator-only constructs, linked assets, spot colors, overprint, transparency, and editability still requires representative customer artwork.
- The reproducible, versioned executable is not digitally signed because no code-signing certificate was supplied.
- The normal Windows host passed all GUI tests. A restricted sandbox may skip them because it cannot read the host Tcl library.
- Final production acceptance still requires visual/RIP checks for extreme dimensions, high DPI, BigTIFF, and real large-format jobs.

## 2026-08-11 - Audit closure

- Normal Windows Tk tests now run successfully; sandbox-only Tcl access skips remain environment guards rather than a host-development blocker.
- Queue deletion, cancellation/resume state, finite numeric validation, recovery cleanup, aggregate disk preflight, preview bounds, requested ICC verification, and PDF Preserve blank-output checks now have regressions.
- Remaining acceptance work is representative printer/RIP validation for customer artwork, Illustrator-only constructs, spot colors/overprint, and signed distribution when a certificate is available.

## 2026-08-11 - Post-diagnostic residual risk

- No reproducible application defects remain in the automated diagnostic matrix after 114 passing Windows tests.
- Real Adobe Illustrator COM automation is mocked at its process/timeout/parsing boundaries; final behavior still depends on the installed Illustrator version and document state.
- Very large TIFF export is streamed with adaptive memory-bounded strips, but final printer/RIP compatibility and multi-gigabyte BigTIFF performance require production hardware and representative artwork.
- PDF/AI color semantics such as spot colors, overprint, linked assets, and Illustrator-only constructs remain external fidelity checks rather than claims made by the automated suite.

## 2026-08-26 - Resolved reported issues

- PDF Preserve now restores the source PDF/Illustrator default layer visibility instead of allowing imported hidden OCGs to become visible in the output.
- Windows Explorer launches now load `.artboard-job` files passed to the executable. Existing `.artboard-job.json` files remain compatible through the in-app Load Job action.
- The installer association takes effect only after installing the rebuilt setup package; running a standalone executable does not register file types by itself.

## 2026-09-08 - Oversized TIFF fallback limits

- Oversized 8-bit, contiguous strip-based TIFF files can now import and export through the bounded fallback reader.
- Tiled, planar-separate, or higher-bit-depth TIFF files that also exceed MuPDF's page limit still require flattening to an 8-bit strip-based TIFF first.
- PDF Preserve is unavailable for TIFF files that require this fallback; use Raster mode. Layered TIFFs use their saved composite image rather than importing editable Photoshop layers.
