# Session Log

Track AI-assisted work sessions here.

## 2026-08-09 - Production hardening pass

- Replaced full-frame TIFF rendering with bounded 256-row Deflate strips and automatic BigTIFF selection.
- Added staged output verification, ICC conversion/assignment, embedded JPG/TIFF profiles, and PDF output intents.
- Added job/disk preflight, direct panel count, expanded export-only presets, retry/resume, and abnormal-shutdown recovery.

## 2026-08-11 - Layout workflow simplification

- Removed Layout Template from the interface because direct panel count, Add Panel, and manual Panel Widths already cover the production workflow more clearly.
- Removed layout-template persistence and normalization; legacy `layout_templates` keys in existing settings files are ignored safely.
- Kept export presets intentionally limited to production settings, without artwork dimensions or output folders.

## 2026-08-11 - Full application audit fixes

- Fixed grouped queue removal/Clear crashes and made queue selection/removal changes participate in recovery saves.
- Fixed cancellation so every unstarted selected job becomes resumable, and normal close-after-cancel removes recovery state.
- Added finite-number rejection, strict job-file types/page bounds, conservative PDF Preserve sizing, and aggregate disk checks.
- Added strict requested-ICC verification, PDF Preserve blank-output checks, bounded/cancellable previews, and named export-job records.
- Centralized release metadata generation, added Windows CI/package self-testing, and advanced the application version to 1.2.0.
- Added version 1.1.0 release metadata, an Inno Setup definition, optional Authenticode signing, and update-manifest support.

## 2026-05-19 - Rebuild audit kickoff

- Read the current source of truth: `artboard_cutter_gui_advanced.py`.
- Read supporting files: `artboard_cutter.py`, `build_exe.bat`, `requirements.txt`, `ArtboardCutter.spec`, and `artboard_cutter_gui_advanced.spec`.
- Compared deleted historical GUI files from Git history only; did not restore them.
- Confirmed current working tree has uncommitted deletions for `artboard_cutter_gui.py` and `artboard_cutter_gui_v1.py` from the prior cleanup.
- No commit or push was performed.

## 2026-05-19 - First modular extraction

- Added `src/artboard_cutter_core/` as the first engine package.
- Extracted units, layout, PDF opening/page boxes, raster image saving, raster export, vector export, export orchestration, settings, and structured logging modules.
- Bound `artboard_cutter_gui_advanced.py` to the extracted engine while keeping existing GUI structure and public helper names intact.
- Added `tests/` with layout tests and generated-PDF export dimension tests.
- Added `logs/.gitkeep`; generated runtime `.log` files are ignored.
- No commit or push was performed.

## 2026-05-19 - Persist last-used export parameters

- Added persisted settings fields for bleed, overlap, DPI, export format, and output folder.
- Updated the GUI to load those values on launch and save them on close/export.
- Added a non-GUI settings round-trip test.
- No commit or push was performed.

## 2026-05-19 - Session Rollup

- Tested `TEST.pdf` with actual-size and resized panel configurations.
- Confirmed raster non-uniform resize behavior and diagnosed vector uniform-fit mismatch.
- Implemented vector stretch-to-fit by creating a full-size stretched vector master and clipping panels from that master.
- Removed user-facing vector fit-by-height/fit-by-width choices.
- Added explicit Raster/Vector mode selection.
- Reworked the UI into a more polished production-tool layout.
- Added live preview labels and overlays for panels, bleed, overlap, and export edges.
- Added professional theme system with 8 themes and persistent selection.
- Prevented combobox values from changing through mouse-wheel scrolling.
- Ran automated tests and compile checks successfully after major changes.
- No commit or push was performed.

## 2026-05-19 - Queue profile and UI state cleanup

- Added session-only `ArtworkProfile` objects for queued files.
- Queue rows now store per-artwork settings in memory: original size, current panel widths/height, bleed, overlap, DPI, export format, export mode, vector preservation, fit mode, status, and validation state.
- Changed queue columns to separate `Select`, `File Name`, `Original Size`, `Current Size`, `Output Status`, and `Actions`.
- Replaced the old mixed checkbox/path display with a dedicated select column and row status column.
- Added `Reset Size`, which restores only the selected artwork from its stored original dimensions.
- Changed the label `Target height` to `Height`.
- Export now validates and runs each checked artwork using that artwork's saved profile settings, not the currently selected row's global form values.
- Removed aggressive Tk palette assignment that made labels and text look constantly highlighted in several themes.
- Kept app-level persisted settings limited to global defaults such as output folder, theme, and last-used parameter defaults.
- No commit or push was performed.

## 2026-05-19 - GUI/export testing backlog

- Added GUI smoke tests with explicit Tcl/Tk skip handling.
- Verified local Python 3.13 still cannot create a Tk root due Tcl `init.tcl` resolution, even though the file exists on disk.
- Added theme contrast-ratio tests across all built-in themes.
- Added preview overlay contrast checks.
- Added preview snapshot validation across themes, guarded by Tk availability.
- Added rendered raster/vector pixel alignment test.
- Added rotated PDF and unusual page box fixture tests.
- Added guarded Windows high-DPI scaling smoke test.
- Added `docs/testing.md` to document the Tcl/Tk blocker and test behavior.
- Ran the full suite: 23 tests passed/skipped cleanly, with 3 GUI tests skipped due local Tcl/Tk.
- No commit or push was performed.

## 2026-05-19 - Export settings row layout fix

- Replaced the `Export Settings` grid layout with explicit horizontal rows.
- Fixed a visual issue where a text field could occupy the label area above `Bleed (mm)`.
- Kept `Height (mm)`, the height input, and `Reset Size` on one row.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Multi-page import and queue output names

- Added page-aware artwork profile creation.
- Import now creates one `ArtworkProfile` per source page/artboard instead of using only page 1.
- Multi-page queue names use the source stem plus ascending page number, such as `Poster1`, `Poster2`, `Poster3`.
- Single-page queue names use the source stem.
- Added editable queue output names through double-clicking the File Name cell.
- Added output-name validation for empty names, Windows-invalid filename characters, and `.` / `..`.
- Export now passes both `source_page_index` and editable `output_name` into the core export pipeline.
- Raster and vector exporters now load the requested source page instead of hardcoding page 0.
- Replaced text `[ ]` / `[x]` queue selection values with checkbox images in the Select column.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Illustrator artboard name integration

- Added optional Windows Adobe Illustrator COM integration for `.ai` artboard names.
- Verified `AI_TEST.ai` through Illustrator COM returns:
  - `Artboard 1`
  - `Artboard 2`
  - `Artboard 2 copy`
  - `Artboard 2 copy 2`
  - `Artboard 2 copy 3`
  - `Artboard 2 copy 4`
- `create_artwork_profiles()` now uses Illustrator artboard names when available and falls back to stem-plus-page numbering otherwise.
- Added output-name sanitization for Windows-invalid filename characters.
- Added duplicate-name disambiguation.
- Added `pywin32` as a Windows-only dependency.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Grouped multi-page queue and manual artboard names

- Changed default multi-page import to use numbered names first instead of automatically asking Illustrator.
- Added parent queue rows for multi-page files; the parent row is named with the original filename and can be expanded/collapsed through the Treeview arrow.
- Child rows remain one `ArtworkProfile` per page/artboard.
- Parent rows show a `Get Names` action that manually reads Illustrator artboard names for `.ai` files.
- Single-page imports remain flat and do not get a group row.
- Group check/uncheck toggles all child profiles.
- Export remains profile-based and only exports child artwork profiles.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Queue group column and Illustrator alert handling

- Moved the Treeview hierarchy/expand arrow into the File Name column.
- Kept a separate Select column for parent and child selection state.
- Parent Select toggles all child profiles.
- Parent File Name now has the native expand/collapse arrow with a wider click target.
- Illustrator artboard-name lookup now sets Illustrator to no-alert mode before opening the `.ai` file, then restores the prior interaction level.
- Re-verified `AI_TEST.ai` artboard names through the updated Illustrator integration.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Illustrator name lookup timeout

- Moved manual Illustrator name lookup onto a background thread so the Artboard Cutter UI does not block.
- Wrapped Illustrator COM name lookup in a subprocess timeout for source/development runs.
- If Illustrator hangs while opening a document, the lookup returns unavailable instead of waiting forever.
- Verified a 5-second timeout returns cleanly when Illustrator is stuck.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Avoid fresh Illustrator startup for name lookup

- Changed GUI `Get Names` to require Illustrator to already be running.
- This avoids launching Illustrator from Artboard Cutter, which can freeze during Illustrator startup/loading on this machine.
- If Illustrator is not running or is unresponsive, the app keeps numbered names and shows a warning.
- Existing Illustrator processes are not force-closed by Artboard Cutter.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Left overlap mode

- Added `Overlap Mode` to the export settings with `Shared` and `Left` choices.
- `Shared` keeps the original half-overlap-on-each-side behavior.
- `Left` makes panel 2 and later overlap left by the full overlap amount; panel 1 has outside bleed only and no internal overlap.
- Passed overlap mode through preview, profile state, settings persistence, raster export, and vector export.
- Added tests for left-overlap layout, exported panel dimensions, settings persistence, and profile creation.
- Reconfirmed that `ttk.Treeview` cannot put a separate Select checkbox column before File Name while keeping the native expand/collapse arrow inside File Name.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Mode controls moved above bleed

- Moved `Export Mode` and `Overlap Mode` to the top of Export Settings before Bleed.
- Replaced both two-option dropdowns with radio selections because each setting only has two valid choices.
- Placed both mode selectors on the same line to reduce vertical space and make the main export behavior visible first.
- Kept the same backing variables so profile state, preview updates, export logic, and settings persistence continue to work.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Radio/check highlight fix

- Added explicit theme maps for `TRadiobutton` and `TCheckbutton`.
- Active, pressed, selected, and disabled toggle states now keep the theme panel background instead of using the operating-system default highlight color.
- This prevents mode selections from appearing as bright highlighted text blocks in dark themes such as Midnight.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Theme combobox and queue header hover polish

- Added combobox selection clearing for the theme selector so the current theme name does not stay visibly highlighted.
- Added combobox select-background tokens so readonly combobox text uses normal entry colors.
- Locked Treeview heading active/pressed colors to the normal heading colors so artwork queue column names do not change on hover.
- Updated button hover maps to use theme-aware hover backgrounds, readable foregrounds, and accent borders.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Settings persistence verification

- Verified `AppSettings` includes the new `overlap_mode` value along with existing export/session defaults.
- Verified the local AppData settings file already contains `overlap_mode: Left` and `export_mode: Vector`.
- Added a regression test confirming older settings files without `overlap_mode` load with the safe `Shared` default.
- Updated all AI journal files with the persistence check.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - Known issues cleanup

- Removed the settings persistence verification block from `known_issues.md`.
- Kept the Tcl/Tk runtime limitation as the active issue because it still affects local automated GUI smoke/screenshot tests.
- Left settings persistence documented in progress/test/session logs as verified behavior.
- No commit or push was performed.

## 2026-05-19 - Current known limitations pass

- Rechecked the Tcl/Tk blocker and kept GUI smoke/screenshot tests guarded with the exact Tk exception in skip output.
- Removed unreachable legacy export bodies after GUI compatibility wrapper delegation.
- Added `Open Logs Folder` to the Run panel with platform-specific folder opening and error handling.
- Added wrapper compatibility and Illustrator fallback tests.
- Expanded `docs/testing.md` with local Tk setup checks, manual GUI verification, preview/export equivalence checks, queue widget constraints, Illustrator requirements, and runtime log access.
- Verified `TEST.pdf`, `test_outputs/`, and generated `logs/*.log*` remain ignored.
- Ran compile and tests successfully.
- No commit or push was performed.

## 2026-05-19 - AI log refresh

- Reclassified old audit bullets in `known_issues.md` so resolved findings are not presented as current blockers.
- Updated `rebuild_progress.md` next steps to focus on the actual remaining validation work: local Tcl/Tk repair, manual GUI checks, preview/export review, and Windows executable testing.
- Confirmed the latest validation baseline remains 38 tests with 3 GUI/Tk skips.
- No commit or push was performed.

## 2026-05-19 - Blank DPI vector export fix

- Fixed export validation failing with `invalid literal for int() with base 10: ''` when Vector mode is selected and DPI is blank.
- Vector export does not use DPI, so blank or nonnumeric DPI now falls back to an internal placeholder value of 72 during validation.
- Raster export still requires a nonblank positive DPI and now reports `DPI is required for Raster export.` for an empty field.
- Added regression tests for blank-DPI Vector validation and blank-DPI Raster validation.
- Ran compile and tests successfully: 40 tests, 3 GUI/Tk skips.
- No commit or push was performed.

## 2026-05-19 - Application icon and executable build

- Added `tools/generate_icon.py` to generate a unique Artboard Cutter icon.
- Generated `assets/artboard_cutter.ico` and `assets/artboard_cutter_icon.png`.
- The icon concept uses staggered artboard panels, production colors, and a diagonal cutter blade.
- Embedded the icon into PyInstaller builds through both spec files and `build_exe.bat`.
- Added the icon as bundled data so the tkinter window can use it at runtime.
- Updated `artboard_cutter_gui_advanced.py` to set the window icon from `assets/artboard_cutter.ico` when available.
- Built `dist/ArtboardCutter.exe` successfully with PyInstaller.
- Verified Windows could extract an associated icon from the built executable.
- Created `dist/Artboard Cutter.lnk` with `IconLocation` pointing at `ArtboardCutter.exe,0`, so the shortcut uses the embedded executable icon.
- Ran compile and tests successfully before the build: 40 tests, 3 GUI/Tk skips.
- No commit or push was performed.

## 2026-05-19 - README screenshots and repository cleanup

- Added README screenshots under `docs/screenshots/`.
- Updated README with current feature summary, screenshots, project layout, development setup, test command, build command, and icon/shortcut notes.
- Consolidated PyInstaller configuration to `ArtboardCutter.spec` and removed the duplicate `artboard_cutter_gui_advanced.spec`.
- Updated `build_exe.bat` to regenerate the icon and build from `ArtboardCutter.spec`.
- Cleaned generated cache/test-output/build-log artifacts while keeping the finished `dist/ArtboardCutter.exe` available locally.
- Updated `.gitignore` so local `.ai` artwork and root `.log` files remain ignored, while documentation screenshots and icon assets are trackable.
- No commit or push was performed yet in this entry.

## 2026-05-26 - Interactive preview editor foundation

- Added pure layout helpers for interactive panel editing: split the last panel into two equal panels and resize adjacent panel widths while preserving total content width.
- Added layout tests covering Add Panel behavior, total-width preservation, min-width clamping, and rejection of non-internal bleed-edge indices.
- Reworked live preview input handling so middle mouse drag pans the canvas and left mouse drag is reserved for valid internal panel boundaries only.
- Added hover cursor feedback and cached preview transform/edge targets for overlap-edge hit detection.
- Added an `Add Panel` button inside the Live Preview header; it appends a panel by splitting the last panel width without changing overall artwork size.
- Dragging an internal boundary updates the Panel Widths field live, saves the active `ArtworkProfile`, and redraws the preview through the same layout path used by export.
- Validation run: compile passed; full unit suite passed with 44 tests and the existing 3 guarded GUI/Tk skips.

## 2026-05-26 - Preview seam overlap protection

- Updated interactive seam dragging so a drag cannot create panel widths smaller than the requested overlap value.
- When the dragged seam crosses that protected limit, the preview width list resets to the widths from before the drag movement instead of letting `compute_panel_layout()` shrink the effective overlap.
- Kept export/layout behavior unchanged for manually typed extreme values; the protection is specific to interactive preview editing.
- Added tests for non-clamping drag reset behavior and overlap-preserving minimum width behavior.
- Validation run: compile passed; full unit suite passed with 46 tests and the existing 3 guarded GUI/Tk skips.

## 2026-05-26 - PDF Preserve mode for raster image inputs

- Renamed the user-facing fast PDF export mode from `Vector` to `PDF Preserve` while keeping legacy `Vector` settings compatible.
- Added export-mode normalization so old AppData values load as `PDF Preserve` and new settings save with the clearer name.
- Updated the fast PDF export path to convert non-PDF sources such as PNG/JPG/TIFF into an in-memory PDF before using the existing stretch-and-clip pipeline.
- Clarified that raster image inputs remain embedded raster images inside PDF panels; they do not become editable vector paths.
- Added regression coverage for PNG input exported through PDF Preserve mode.
- Validation run: compile passed; full unit suite passed with 47 tests and the existing 3 guarded GUI/Tk skips.

## 2026-05-26 - PDF Preserve build and documentation refresh

- Rebuilt `dist/ArtboardCutter.exe` with PyInstaller after the PDF Preserve and interactive preview changes.
- Updated README feature notes to include interactive preview panel editing and the raster-image limitation of PDF Preserve mode.
- Updated `docs/testing.md` to use Raster/PDF Preserve terminology, include raster image PDF Preserve checks, and list interactive preview editing checks.
- Updated the GUI subtitle from vector-stretched panel exports to PDF-preserved panel exports.
- Validation run: compile passed; full unit suite passed with 47 tests and the existing 3 guarded GUI/Tk skips.

## 2026-05-26 - Fixed two-column layout with right-side scrolling

- Removed the global root-window scroll canvas and its bottom horizontal scrollbar.
- Restored a fixed desktop-style layout: topbar plus a two-column horizontal paned body.
- Kept Live Preview on the left with its own toolbar and canvas-based pan/zoom behavior.
- Moved queue, export settings, run controls, and Activity Log into a right-side control viewport that scrolls vertically only when the window is too short.
- Kept the artwork queue's own internal scrollbar independent from the right-side control scrollbar.
- Updated `docs/testing.md` with manual validation for no global scrollbars and right-side-only overflow.
- Validation run: compile passed; full unit suite passed with 47 tests and the existing 3 guarded GUI/Tk skips.

## 2026-05-26 - Theme and visual design refresh

- Rebuilt `src/artboard_cutter_core/themes.py` around centralized design tokens for surfaces, text, borders, accent states, inputs, tables, selections, status colors, and preview overlays.
- Added the requested polished theme set: Soft Blue, Minimal Light, Dark Pro, Industrial Gray, and Blueprint.
- Kept legacy themes and old token aliases so saved preferences and existing UI references remain compatible.
- Updated `apply_theme()` to style buttons, accent buttons, inputs, comboboxes, radio buttons, tree headings, rows, progress bars, text widgets, and canvases from the token system.
- Added a preview empty state with a workspace border, icon, message, and interaction tip.
- Added an artwork queue empty-state message.
- Refined spacing in preview toolbar, queue buttons, export settings rows, and run controls.
- Validation run: compile passed; full unit suite passed with 48 tests and the existing 3 guarded GUI/Tk skips.

## 2026-05-26 - Reference-matched UI polish pass

- Added local PNG action icons under `assets/icons/` for queue actions, preview
  tools, export, logs, browse, and section headers.
- Updated the PyInstaller spec to bundle `assets/icons/` with packaged builds.
- Reworked the main visual sections into softer card frames with explicit
  section headers, reduced nested borders, and cleaner button groups.
- Added icon+text buttons for Add Files, Remove, Clear, Check All, Uncheck All,
  Check Selected, Add Panel, Start Export, Open Logs Folder, and Browse.
- Expanded theme aliases to expose app/card/canvas/button/input/table/scrollbar
  tokens while keeping old token names compatible.
- Fixed the label-background source of the highlighted-text look by using
  explicit field/card/root/toolbar label styles.
- Updated the preview empty state and queue empty state to better match the
  Soft Blue design reference.

## 2026-08-08 - Reliability and usability implementation

- Corrected Raster export so JPG creates `.jpg` and TIFF creates `.tif`; neither selection emits PDF.
- Corrected DPI math after confirming PyMuPDF ignores `matrix` when `dpi` is also supplied.
- Replaced Add Panel's last-panel split rule with equal redistribution of total artwork width.
- Added transactional outputs, overwrite/stale-file preflight, clear validation, error states, cancellation, background import/preview/export, and serialized PDF operations.
- Added color mode, presets, saved jobs, recent paths, rotating AppData logs, safer defaults, pinned dependencies, and versioned packaging.
- Added regression tests and rebuilt/smoke-tested `dist/ArtboardCutter.exe`.

## 2026-08-08 - Blank first CMYK TIFF diagnosis

- Inspected a 20,552 x 41,339 source JPG and two generated CMYK TIFF panels.
- Confirmed panel 1 was all-white while panel 2 contained artwork; crop geometry and PDF Preserve output were correct.
- Reproduced MuPDF's `Overly large image` behavior: the 7,034 x 20,906 CMYK render required about 588 MB and MuPDF returned all-zero pixels without raising. The same crop rendered correctly through 145 DPI.
- Replaced the pixel-only cap with a channel-aware 500 MB render cap. This job now selects 138 DPI consistently for both panels instead of producing a blank 150 DPI first panel.
- Added a low-resolution content check to prevent any similar silent blank render from being saved.
- Corrected a PyInstaller lazy-import warning by making the packaged entry point import core modules explicitly; the final missing-module report is clean for application modules.

## 2026-08-08 - Queue empty-state drag-and-drop fix

- Fixed the centered empty-queue label intercepting file drops intended for the Treeview beneath it.
- Registered the queue container, Treeview, and empty-state label as equivalent file-drop targets.
- Stopped stripping literal braces after Tcl path parsing, preserving valid filenames such as `{proof}.pdf`.
- Added a regression test covering all visible queue layers and rebuilt the executable.

## 2026-08-11 - Function-by-function diagnostic and hardening pass

- Inventoried 233 application definitions and reviewed the GUI, persistence, layout, preflight, export, transaction, color, verification, update, and Illustrator-integration subsystems.
- Fixed stale asynchronous imports reappearing after Clear, case-insensitive queue/path collisions, non-finite preview/panel math, malformed settings/job/update JSON handling, invalid saved window geometry, output-name suffix collisions, and semantic version padding.
- Fixed Tk callback cleanup on window destruction and preserved compatibility with older in-memory queue keys.
- Added a commit-time output race check so files created by another process during an export are not overwritten without approval.
- Made TIFF strip height adaptive to output width so very wide/high-DPI exports retain bounded working memory.
- Added multi-panel raster-to-TIFF and end-to-end GUI TIFF checks that reopen every output and reject blank/uniform panels.
- Ran 5,000 randomized panel-layout and seam-resize invariant cases successfully.
- Final Windows suite passed 114 tests with no failures or skips; compile, dependency, static correctness, and diff checks passed.
- The first rebuild exposed PyInstaller incorrectly excluding `tkinter`; that binary was rejected after its self-test stalled at startup.
- Added explicit Tcl/Tk packaging hooks and a build-time Tk initialization gate, rebuilt successfully, and passed the packaged Tk/TkDND/TIFF self-test with exit code 0.

## 2026-08-26 - Illustrator hidden-layer and Explorer job-launch fixes

- Reproduced the supplied Illustrator file's mismatch: source OCGs marked `3D Logo (DO NOT PRINT)` and `bolt + tv + cabinet + cloud` default-hidden, while panel PDFs contained those OCG objects without a catalog-level default configuration.
- Rebuilt PDF Preserve output layer metadata so each panel retains the source default on/off states.
- Changed new saved jobs to `.artboard-job`, retained legacy `.artboard-job.json` loading, added startup-path queue loading, and registered the dedicated extension in the Windows installer.
- Added synthetic hidden-layer, argument parsing, GUI startup loading, and installer association regressions.
- Released the code and standalone executable as version 1.2.1; all 118 automated tests and the packaged self-test passed.
- Installed Inno Setup 6.7.3 through WinGet and successfully generated the 1.2.1 Windows setup package with the `.artboard-job` association.

## 2026-08-30 - README refresh and Git delivery

- Rewrote the README for v1.2.1: installer versus standalone use, unsigned distribution, current queue/panel controls, PDF Preserve hidden layers, raster/ICC behavior, job-file compatibility, safety, troubleshooting, and reproducible build commands.
- Kept the output/assembly screenshots and removed the misleading older application UI screenshot from the guide. No customer artwork was added.
- Added Git ignores for generated setup binaries and the abandoned local Project OS planning draft; existing local files remain on disk.
- Prepared the accumulated production-hardening fixes, tests, packaging hooks, workflow, and documentation for the existing `codex/artboard-cutter-production-hardening` branch. No merge into `main` was requested.

## 2026-08-31 - AGPLv3 release preparation

- Added the user-approved AGPLv3 license, copyright/warranty notice, dependency-source guide,
  and About-dialog notices. No commercial licensing or signing was purchased.
- Added a build-time notice collector, installer license display/files, and matching CI collection.
- Added four regression tests for license collection and installer/executable packaging.
- Prepared first-release notes, download links, maintainer instructions, and source-archive provenance.
- Built the unsigned Windows standalone executable and Inno installer with full notices.
- Verified all 122 Windows tests, dependency consistency, compilation, and the packaged Tk/TkDND/TIFF self-test.
- Kept clean-machine installation/uninstallation and production print/RIP proof as explicitly unverified.

## 2026-09-08 - Oversized layered TIFF input fix

- Reproduced `POSTER-6.tif` failing in PyMuPDF with `FzErrorLimit: Overly large image`; the valid 12,283 x 23,799 CMYK/LZW composite exceeds MuPDF's image-page limit.
- Added a bounded TIFF-strip decoder fallback at the shared document opener, covering queue import, original-size detection, live preview, and raster export without loading the 1.17 GB uncompressed image at once.
- Verified the supplied file imports at 2,079.921 x 4,029.964 mm, produces a nonblank preview, and exports readable nonblank CMYK JPG and TIFF samples.
- The fallback reads the TIFF composite image and ignores embedded Photoshop layer records. Oversized TIFF PDF Preserve remains unsupported; use Raster mode.

## 2026-09-08 - v1.2.2 release and installation

- Bumped the application and installer to 1.2.2; updated README, changelog, notices, packaging guide, and public release notes.
- Built unsigned Windows standalone and installer packages from commit `a7eb2dd8ae285b325c7acda647126ab6c6fc59b2` after all 123 tests passed.
- Published immutable GitHub release `v1.2.2` as Latest with the standalone EXE, installer, license archive, corresponding-source archive, and checksum manifest.
- Re-downloaded all five assets, verified their SHA-256 hashes, and passed the downloaded executable self-test.
- Installed the published setup package to `C:\Program Files\Artboard Cutter`; the installed 1.2.2 executable matches the published SHA-256 and passes self-test.

## 2026-09-08 - v1.2.3 packaged TIFF preview hotfix

- Reproduced the post-release gap: source rendering produced nonblank POSTER-4 and POSTER-6 previews, while the v1.2.2 PyInstaller archive omitted Imagecodecs' `_imcd` LZW module.
- Added the missing packaged module and a manifest regression test; no TIFF decoding or GUI behavior was changed.
- Built the unsigned 1.2.3 executable and installer, then launched the packaged executable with POSTER-4 and visually confirmed the artwork appears in Live Preview.

## 2026-09-10 - Oversized TIFF PDF fallback

- Inspected the running five-file TADA job and its persistent export log. The four failed profiles were set to PDF Preserve; the one successful profile was Raster. All sources were 1.42-1.97 GB TIFFs, and free disk space was not the constraint.
- Marked the oversized-TIFF adapter as unable to preserve PDF content and routed that capability through the shared exporter. PDF Preserve requests for these TIFFs now produce raster PDFs using the existing safe-DPI and output-verification path.
- Added an end-to-end regression that exercises an oversized-TIFF adapter through PDF output; the full non-GUI suite passed 113 tests and 12 GUI checks remained unavailable in the restricted Tcl host.

## 2026-09-10 - Oversized TIFF preview latency

- Timed the real TADA file path: the repeated MuPDF compatibility probe took 2.21 seconds, while rendering the bounded 1,479 x 1,600 preview took 0.38 seconds.
- Cached only the fallback decision by resolved path, size, and modification time in the shared document opener. Queue import still performs the compatibility probe once; subsequent previews skip it, and changed files are probed again.
- On a real 1.77 GB TADA TIFF, preview creation after the import probe completed in 0.40 seconds. No preview resolution or export-quality setting changed.

## 2026-09-10 - Lossless raster PDF export

- Replaced the temporary oversized-TIFF safe-DPI fallback with direct lossless PDF panel writing.
- The new path reads TIFF strips in bounded blocks, writes all requested panels in one pass, preserves RGB/CMYK/grayscale bytes and embedded ICC data, and ignores the Raster DPI field.
- Renamed the visible PDF Preserve option to Lossless PDF while retaining the old stored value for compatibility.
- A 1.42 GB uncompressed CMYK TADA TIFF exported into two verified PDFs in 6.81 seconds; supplied LZW `POSTER-6.tif` exported into two verified PDFs in 9.16 seconds.
- Updated README, changelog, known limitations, and release version for 1.2.4.

## 2026-09-10 - v1.2.4 release and installation

- Committed the lossless raster PDF implementation at `e1adc221389b3e87f50ae4735f442e6c2c5cf8e5` and pushed `main` plus tag `v1.2.4`.
- Built the unsigned standalone executable and Inno Setup installer, produced notices/corresponding-source archives, and published five verified GitHub assets.
- GitHub marks v1.2.4 immutable and Latest. Server digests and independently re-downloaded asset hashes match the local release manifest.
- Installed v1.2.4 to `C:\Program Files\Artboard Cutter`; its executable matches the packaged SHA-256 and both installed/downloaded self-tests passed.
