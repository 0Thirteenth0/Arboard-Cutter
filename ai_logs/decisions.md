# Decisions

Track product and implementation decisions here.

## 2026-05-19 - Source of truth

- Treat `artboard_cutter_gui_advanced.py` as the current source of truth.
- Keep `compute_panel_layout()` behavior unchanged until tests are in place.
- Do not rewrite the UI framework before isolating and testing the export engine.
- Do not commit or push unless explicitly requested by the user.

## 2026-05-19 - Incremental extraction strategy

- Keep tkinter GUI temporarily instead of switching frameworks immediately.
- Extract engine logic first so vector-mode fixes and tests can be developed independently of UI changes.
- Preserve legacy helper function names in `artboard_cutter_gui_advanced.py` for compatibility during the transition.
- Use standard-library `unittest` first to avoid adding tooling dependencies during the initial extraction.

## 2026-05-19 - Vector fit modes

- Add `stretch` as the default vector mode because production users expect vector output to match raster's user-input width and height when resizing.
- Keep `height` and `width` as uniform vector fit modes for cases where preserving aspect ratio is more important than matching both target dimensions.

## 2026-05-19 - User-facing vector mode simplification

- Removed user-facing `height` and `width` vector fit options.
- Vector export now always uses `stretch` from the GUI because this is the production behavior that matches raster dimensions and user expectations.
- Internal code can still retain uniform helpers temporarily for debugging, but they are not exposed in the app UI.

## 2026-05-19 - Export mode UI wording

- Use an explicit `Export mode` selector with `Raster` and `Vector` instead of a `Preserve vectors` checkbox.
- This is clearer for print/prepress users and makes the raster/vector choice visible.

## 2026-05-19 - Theme system

- Replace the binary dark/light toggle with a named theme selector.
- Keep all theme colors centralized in `themes.py` instead of scattering hardcoded UI colors.
- Preserve legacy saved `dark`/`light` values by mapping them to Professional Dark/Light.
- Block mouse-wheel changes on comboboxes so values change only from deliberate dropdown selection/clicks.

## 2026-05-19 - Session-only artwork profiles

- Add `ArtworkProfile` as the in-memory model for each queue row.
- Store per-artwork current settings in the profile, not in a shared global form state.
- Keep profile state session-only; do not write per-artwork settings to external files.
- Use persisted app settings only as defaults for newly added artwork.
- Delete the profile from memory when the queue row is removed.
- Export each checked row using that row's profile values.

## 2026-05-19 - Theme highlighting fix

- Removed broad `root.tk_setPalette(...)` usage because it made ordinary text look constantly highlighted.
- Keep selection colors limited to actual selected tree rows or selected text.
- Apply theme colors through centralized ttk styles and narrow direct widget patches.
- Use subdued hover states that preserve readable button foreground colors.

## 2026-05-19 - Guarded GUI tests

- GUI launch, preview snapshot, and Windows high-DPI tests should be automated, but skipped when Tk cannot initialize.
- The skip reason must include the exact Tcl/Tk exception so the environment problem is visible.
- This avoids turning a local Python installation issue into false application test failures.

## 2026-05-19 - Visual alignment tests

- Compare raster and vector outputs by rendering generated PDFs back to RGB pixels.
- Use simple deterministic stripe artwork to minimize antialiasing noise.
- Save diff artifacts only on failure under ignored `test_outputs/failures/`.
- Keep tolerances narrow enough to catch alignment drift but broad enough for renderer byte-level differences.

## 2026-05-19 - Multi-page import naming

- Treat every source page/artboard as its own queue profile.
- Use source stem plus 1-based page number for multi-page queue names.
- Use source stem for single-page queue names so output names do not include the source extension.
- Make the queue name the output base name; edited queue names control exported filenames.
- Keep panel suffixes such as `_1`, `_2`, etc. because the cutter still exports one or more panels per artwork profile.
- Use checkbox images in the Treeview select column because native embedded ttk checkboxes are not supported by Treeview cells.

## 2026-05-19 - Illustrator artboard names

- Use Adobe Illustrator COM automation as an optional Windows-only manual path for real `.ai` artboard names.
- Keep PyMuPDF as the geometry/page-count source so import still works without Illustrator.
- Default import uses deterministic numbered names; Illustrator naming only runs when the user asks for it.
- Keep numbered names if Illustrator, COM, or `pywin32` is unavailable.
- Sanitize Illustrator names for output filenames rather than allowing invalid Windows paths.
- Make duplicate names unique to avoid overwriting exports.

## 2026-05-19 - Grouped queue rows

- Group multi-page source files under a parent row named with the original filename.
- Do not group single-page files because a disclosure row adds unnecessary UI weight.
- Use the parent row action column for source-level actions such as `Get Names`.
- Keep each child row as the exportable profile so per-artwork settings remain independent.
- Keep the native Treeview expand/collapse control in the File Name column, not the Select column, so it matches production graphics tools.
- Use checkbox glyphs in the Select column because native checkbox widgets cannot be embedded in ttk Treeview data cells.
- Do not move Select before File Name while using native `ttk.Treeview`; doing so would move the expand/collapse affordance back into the Select area.

## 2026-05-19 - Illustrator lookup resilience

- Run manual Illustrator artboard-name lookup asynchronously from the GUI.
- Use a timeout wrapper around COM lookup during source/development runs.
- Treat timeout or COM failure as a non-fatal unavailable state and keep numbered names.
- Suppress Illustrator alerts when possible, but do not rely on Illustrator opening cleanly for the app to remain responsive.

## 2026-05-19 - Current Product Decisions

- Keep the rebuild incremental and keep the app runnable through `artboard_cutter_gui_advanced.py`.
- Do not switch away from tkinter until the export engine, vector behavior, and preview geometry are stable.
- Preserve `compute_panel_layout()` behavior as the canonical production rule.
- Raster mode remains DPI-based and can output PDF/JPG/TIFF.
- Vector mode is user-facing as `Vector` and always uses stretch-to-fit PDF export.
- The UI should expose Raster/Vector as a production choice, not as a technical `preserve vectors` checkbox.
- Theme selection should be explicit and persistent.
- No commits or pushes should be performed unless the user explicitly asks.

## 2026-05-19 - Overlap mode option

- Keep the original shared-overlap behavior as the default to preserve existing production behavior and tests.
- Add a second `Left` overlap mode for jobs where only the right-hand/later panel should carry the internal overlap.
- In `Left` mode, the first panel has outside bleed only and no internal overlap; every following panel extends left by the full overlap value.
- Persist the selected overlap mode as a global default while still storing the active value independently on each queued `ArtworkProfile`.
- Keep the queue hierarchy arrow in the File Name column while using `ttk.Treeview`; moving Select to the first visual column would require replacing the queue widget or accepting the disclosure arrow in the Select column.

## 2026-05-19 - Settings persistence verification

- Keep `export_mode` and `overlap_mode` in `AppSettings` because they are global defaults for newly imported files and should survive app restarts.
- Do not persist per-artwork profile values to AppData; queued artwork settings remain session-only by design.
- Let legacy settings files fall back to `Shared` overlap mode when the key is missing.
- Verified the local AppData settings file already contains `overlap_mode` and `export_mode`.

## 2026-05-19 - Known limitation cleanup

- Remove unreachable legacy bodies from GUI compatibility wrappers rather than carrying duplicate export implementations in the GUI file.
- Keep wrapper names available because earlier code/tests may import them from `artboard_cutter_gui_advanced.py`.
- Add a log-folder button instead of an in-app log viewer for now; this gives immediate access to structured JSON logs without building a second log UI surface.
- Continue to document Treeview checkbox and hierarchy-column limits because they are framework constraints, not bugs.

## 2026-05-19 - Current validation posture

- Treat automated engine/model tests as the current source of confidence while local Tcl/Tk is broken.
- Keep GUI-dependent tests in the suite with explicit skip reasons instead of deleting or weakening them.
- Do not mark preview/export visual equivalence fully complete until screenshots/manual checks pass in a working GUI runtime.
- Keep `Open Logs Folder` as the pragmatic first log-access feature; defer an in-app JSON log viewer until users need filtering/search inside the app.

## 2026-05-19 - App icon packaging

- Use a generated custom icon instead of a stock image so the executable has a distinct production-tool identity.
- Embed the `.ico` into the PyInstaller executable so Windows shortcuts inherit the icon from the target executable.
- Also bundle the `.ico` as runtime data so the tkinter window can use the same icon in development and packaged builds.
- Keep the icon generator in the repo so the asset can be reproduced or adjusted later.

## 2026-05-19 - Build path cleanup

- Use one maintained PyInstaller spec: `ArtboardCutter.spec`.
- Remove the duplicate `artboard_cutter_gui_advanced.spec` to avoid two divergent build paths.
- Keep generated `dist/` output out of Git; source, specs, icon assets, docs, tests, and AI logs are the tracked project state.

## 2026-05-26 - Interactive preview editing model

- Keep interactive panel edits as width edits, not per-edge overlap edits, because the export engine currently has one global overlap value and one list of panel widths.
- Preserve total content width during an internal edge drag by increasing one adjacent panel width and decreasing the next adjacent panel width.
- Treat only internal panel boundaries as draggable targets; outside bleed edges remain locked and non-interactive.
- Add `Add Panel` by increasing the panel count and evenly redistributing the full artwork width. This matches the production rule that the overall artwork dimension is divided by the requested panel count.
- Keep the preview editor on the existing tkinter canvas for now, but cache transform and hit-target state so future interactive tools do not need to reverse-engineer canvas drawings.
- Protect the configured overlap during mouse editing by rejecting drag results that would make either adjacent panel narrower than `overlap + 0.01 mm`. This prevents the layout engine from reducing effective overlap during interactive edits.

## 2026-05-26 - PDF Preserve naming and image behavior

- Rename the visible `Vector` export option to `PDF Preserve` because raster image inputs can use the fast PDF pipeline but cannot become true vector artwork.
- Continue using the internal `preserve_vectors` flag for compatibility with existing engine options, but normalize user/profile/settings values through `normalize_export_mode()`.
- Treat legacy `Vector` settings as `PDF Preserve` so existing AppData files keep working.
- Convert raster image documents to an in-memory PDF before clipping. This avoids expensive DPI panel rendering when the requested output is PDF while preserving the source image as embedded raster content.
- Keep Raster mode as the required path for JPG/TIFF output because those output formats must be rasterized.

## 2026-05-26 - Window overflow strategy

- Do not scroll the entire application root window. Global scrollbars made the
  desktop UI feel broken and caused the preview/settings areas to behave as one
  oversized page.
- Keep the root as a fixed two-column production-tool layout.
- Keep preview overflow inside the preview canvas through zoom and pan.
- Keep queue overflow inside the queue table.
- Allow only the right control column to scroll vertically when the window is
  too short for all controls.

## 2026-05-26 - Theme redesign direction

- Keep tkinter/ttk for this pass rather than replacing the UI framework, because
  the requested work is visual structure and theming rather than new export
  architecture.
- Add richer design tokens while retaining legacy aliases. This avoids breaking
  preview/export UI code that still references older token names.
- Make Soft Blue the default theme because it best matches the current product
  direction and the provided design reference.
- Keep older themes available for now so existing saved theme names still load.
- Use empty-state drawing in the preview canvas rather than introducing a
  separate overlay widget that could interfere with preview mouse interactions.
## 2026-05-26 - UI icon and card styling approach

- Kept tkinter/ttk instead of changing frameworks for this pass because the
  request was visual polish without export/geometry risk.
- Used local PNG icons instead of SVG at runtime because Tk loads PNG reliably
  without adding another dependency.
- Kept text labels next to icons so controls remain understandable if an icon
  fails to load or a theme lowers icon contrast.
- Bundled icons through the existing PyInstaller spec rather than relying on
  runtime-generated or downloaded assets.
- Used explicit card/root/field label styles to avoid accidental selected-looking
  label backgrounds across nested ttk containers.

## 2026-08-08 - Export safety and workflow decisions

- Keep the desktop application: local large-file access, Illustrator integration, and prepress output suit a local process better than a web rewrite.
- Treat JPG/TIFF as explicit Raster formats. PDF Preserve forces PDF and remembers the last Raster image format.
- Make output transactional at the whole-panel-set level and require explicit overwrite approval.
- Reject invalid typed overlap instead of silently changing it during export.
- Warn before non-uniform scaling when source and target aspect ratios differ by more than 1%.
- Render file probing and previews off the Tk thread and provide cooperative export cancellation.
- Offer RGB and CMYK pixel modes, but do not claim ICC-managed conversion until an output-profile workflow is production-tested.
- Pin runtime/build dependencies and include executable version metadata.

## 2026-08-08 - Export preset scope

- Presets contain reusable export behavior only: bleed, overlap, overlap mode, DPI, color mode, export format, and export mode.
- Panel widths and artwork height remain profile-specific and are never applied from a preset.
- The output folder remains an application-level choice and is never stored in or applied by a preset.

## 2026-08-09 - Production hardening decisions

- Use streamed TIFF strips instead of reducing TIFF DPI to control memory. JPG and raster PDF retain the shared safe-DPI rule.
- Verify staged outputs before commit and reject silent blank/uniform renders.
- Support explicit ICC conversion/assignment and preserve the selected output profile through TIFF/JPG embedding or a raster-PDF output intent.
- Persist an atomic recovery queue during active sessions; normal close removes it, while abnormal shutdown offers restore and retry.
- Complete artwork dimensions and paths belong in saved queue job files instead.

## 2026-08-11 - Remove Layout Template

- Remove the Layout Template control and saved-template model because the feature adds interface complexity without improving the normal production workflow.
- Use **Panels / Set** and **Add Panel** for equal division of the complete artwork width, or edit **Panel Widths** directly for custom unequal layouts.
- Keep export presets focused only on reusable export behavior; they still do not change artwork dimensions or the output folder.
- Ignore obsolete `layout_templates` keys when loading older settings files rather than requiring a manual migration.

## 2026-08-11 - Post-audit reliability pass

- Treat multi-page parent removal as one atomic queue operation; recursive child cleanup must not delete a parent that the caller is still processing.
- Mark every selected but unstarted job as Interrupted after cancellation so Retry Failed / Resume represents the entire unfinished batch.
- Reject all non-finite numeric production values before geometry or rendering.
- Estimate PDF Preserve disk use conservatively from source size and evaluate free space for the combined batch.
- Make requested ICC embedding and unexpected PDF Preserve blank output verification failures, not warnings.
- Bound preview rendering by its pixel budget and discard obsolete preview requests before they acquire the PDF lock.
- Use `src/artboard_cutter_core/version.py` as the single release-version source and generate installer/executable metadata during builds.

## 2026-08-11 - Make Tk a release gate

- Treat a PyInstaller `tkinter` exclusion as a failed release even when source-level GUI tests pass.
- Keep the explicit Windows Tcl/Tk collection hooks until upstream PyInstaller correctly detects the standalone Python 3.14 layout.
- Require the packaged self-test to initialize the actual Tk/TkDND runtime as well as export TIFF.

## 2026-08-26 - Preserve hidden layers and use a dedicated job extension

- Restore PDF optional-content default visibility after every `show_pdf_page` import rather than flattening Illustrator layers; this retains vector content and makes PDF Preserve match the live preview's default-visible artwork.
- Use `.artboard-job` for newly saved jobs and Windows association. Continue reading `.artboard-job.json`, but never associate the generic `.json` extension.
- Load an Explorer-provided job only after the main Tk UI exists, and skip crash-recovery prompting during that explicit document launch.

## 2026-08-30 - Keep distribution unsigned

- The user chose to skip code signing. Keep unsigned standalone/installer builds and document Windows publisher warnings; do not enroll in a paid signing service.
- Retain the optional certificate-based build switch for a future explicitly requested signing workflow, but use an empty certificate argument for the documented unsigned build.
- Keep executable/installer build products out of Git; binary release publishing is separate from committing source changes.

## 2026-08-31 - First public release licensing

- The owner explicitly approved licensing Artboard Cutter under GNU AGPLv3, version 3 only.
- Keep Windows binaries unsigned; do not purchase a certificate or commercial PyMuPDF license.
- Use GitHub Releases for installer/standalone downloads. GitHub Packages is not needed.
- Publish license notices, exact application source, official PyMuPDF and MuPDF source archives,
  and SHA-256 checksums alongside the binaries. Do not add local artwork or job files.

## 2026-09-10 - Treat preserve mode as lossless PDF, not editable vector output

- Name the user-facing mode Lossless PDF while retaining the internal `PDF Preserve` value for saved-setting and job compatibility.
- For oversized TIFFs, preserve original 8-bit RGB, CMYK, or grayscale samples and embedded ICC data; do not apply DPI rendering, resampling, or color conversion.
- Crop source columns into each panel PDF during one bounded strip pass rather than wrapping the full TIFF once per panel.
- Use fast lossless Flate compression to balance export time and output size.
