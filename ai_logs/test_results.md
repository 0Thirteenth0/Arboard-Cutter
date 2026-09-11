# Test Results

Track manual and automated test results here.

## 2026-08-09 - Production hardening coverage

- Added tests for streamed TIFF ICC embedding, raster-PDF output intents, blank-output verification, BigTIFF selection, and large-job preflight.

## 2026-08-11 - Layout Template removal

- Removed the obsolete layout-template normalization test.
- Added legacy-settings coverage confirming old `layout_templates` data is ignored without preventing settings from loading.
- Full restricted suite passed: 73 tests, 5 guarded Tk/screenshot skips.
- Real Windows Tk checks passed for launch, Layout Template absence, themed Panels spinbox rendering, and high-DPI scaling.
- PyInstaller produced `dist/layout-removal/ArtboardCutter.exe`; its packaged TIFF self-test exited successfully.
- The standard `dist/ArtboardCutter.exe` was not replaced because existing app processes were still using it.

## 2026-08-11 - Full post-audit reliability validation

- Complete real Windows host suite passed: 86 tests, 0 failures, 0 skips.
- Confirmed the former grouped-parent removal crash is covered by a real Tk regression.
- Added coverage for interrupted remaining jobs, clean recovery removal, finite numeric inputs, strict ICC presence, PDF Preserve blank detection, PDF Preserve size estimates, combined free-space warnings, preview pixel bounds, job-file types/page bounds, and generated version metadata.
- Rebuilt the standard `dist/ArtboardCutter.exe` successfully.
- Packaged TIFF self-test exited 0.
- Windows executable FileVersion and ProductVersion both report 1.2.0.

## 2026-05-19 - Baseline checks

- Prior syntax check passed for `artboard_cutter.py` and `artboard_cutter_gui_advanced.py` before this audit.
- No vector/raster alignment tests exist yet.
- No automated layout tests exist yet.

## 2026-05-19 - Engine extraction tests

- `python -m unittest discover -s tests`: passed, 7 tests.
- `python -m compileall -q artboard_cutter.py artboard_cutter_gui_advanced.py src tests`: passed.

Coverage added:

- outside-only bleed
- shared internal overlap
- custom-width panel layout
- overlap clamping
- width parsing
- raster PDF output dimensions for generated fixture
- vector PDF output dimensions for generated fixture

Remaining test gaps:

- raster/vector pixel alignment comparison
- unusual page boxes
- rotated PDFs
- preview/export visual equivalence

## 2026-05-19 - Settings persistence tests

- `python -m unittest discover -s tests`: passed, 8 tests.
- `python -m compileall -q artboard_cutter.py artboard_cutter_gui_advanced.py src tests`: passed.
- Added `tests/test_settings.py` to verify export parameter settings round-trip.

## 2026-05-19 - Manual TEST.pdf export checks

Source:

- `TEST.pdf`
- 1 page
- effective PyMuPDF page size: about `7000 x 2450 mm`
- rotation: `0`

Generated output folder:

- `test_outputs/`

Case 1:

- widths: `3500, 3500`
- height: `2450`
- bleed: `0`
- overlap: `0`
- DPI: `36`
- raster PDF and vector PDF outputs both produced two panels at `3500 x 2450 mm`.

Case 2:

- widths: `3500, 3500`
- height: `2450`
- bleed: `20`
- overlap: `40`
- DPI: `36`
- expected panel width: `3540 mm` because internal overlap is shared as `20 mm` on the adjoining side and outside bleed is `20 mm`.
- raster PDF and vector PDF outputs both produced two panels at `3540 x 2490 mm`.

Case 3:

- widths: `1200, 1200, 1100, 1230`
- total requested width: `4730 mm`
- height: `2000 mm`
- bleed: `0`
- overlap: `0`
- DPI: `36`
- raster PDF output page sizes:
  - `1200 x 2000 mm`
  - `1200 x 2000 mm`
  - `1100 x 2000 mm`
  - `1230 x 2000 mm`
- vector fit-by-height output page sizes matched the requested page sizes, but this does not prove content alignment because the source aspect ratio differs from the requested target aspect ratio.
- vector fit-by-width diagnostic output page height was about `1655.501 mm`, showing the uniform vector scale required to preserve full source width.

Case 4:

- same resize setup as Case 3
- vector fit mode: `stretch`
- output page sizes:
  - `1200 x 2000 mm`
  - `1200 x 2000 mm`
  - `1100 x 2000 mm`
  - `1230 x 2000 mm`
- This confirms non-uniform vector stretch now honors the same requested panel dimensions as raster mode.

Automated tests:

- `python -m unittest discover -s tests`: passed, 9 tests.
- `python -m compileall -q artboard_cutter.py artboard_cutter_gui_advanced.py src tests`: passed.

Case 5:

- same resize setup as Case 4
- vector stretch pipeline changed to create a full-size stretched vector master before clipping panels
- output folder: `test_outputs/resize_vector_stretch_master/`
- output page sizes:
  - `1200 x 2000 mm`
  - `1200 x 2000 mm`
  - `1100 x 2000 mm`
  - `1230 x 2000 mm`
- `python -m unittest discover -s tests`: passed, 9 tests.
- `python -m compileall -q artboard_cutter.py artboard_cutter_gui_advanced.py src tests`: passed.

## 2026-05-19 - Vector fit selector removal validation

- `python -m unittest discover -s tests`: passed, 9 tests.
- `python -m compileall -q artboard_cutter.py artboard_cutter_gui_advanced.py src tests`: passed.
- Updated automated vector dimension test to use `stretch`.

## 2026-05-19 - Export mode selector validation

- `python -m unittest discover -s tests`: passed, 9 tests.
- `python -m compileall -q artboard_cutter.py artboard_cutter_gui_advanced.py src tests`: passed.
- Settings round-trip now includes `export_mode`.

## 2026-05-19 - Modern UI validation

- `python -m unittest discover -s tests`: passed, 9 tests.
- `python -m compileall -q artboard_cutter.py artboard_cutter_gui_advanced.py src tests`: passed.
- GUI smoke test attempted with `App()` creation, but this local Python/Tk install failed before app code with `TclError: Can't find a usable init.tcl`.
- The smoke test failure appears to be local Tcl/Tk installation/configuration, not a syntax failure.

## 2026-05-19 - Theme system validation

- `python -m unittest discover -s tests`: passed, 12 tests.
- `python -m compileall -q artboard_cutter.py artboard_cutter_gui_advanced.py src tests`: passed.
- Added `tests/test_themes.py` to verify required themes, legacy fallback, invalid fallback, and preview overlay token coverage.

## 2026-05-19 - Current Test Status

Latest automated validation:

- `python -m unittest discover -s tests -v`: passed, 31 tests, 3 skipped.
- `python -m compileall -q artboard_cutter_gui_advanced.py src tests`: passed.

Current test files:

- `tests/test_layout.py`: panel layout, bleed, overlap, parsing.
- `tests/test_export_geometry.py`: generated PDF output dimensions for raster/vector paths.
- `tests/test_settings.py`: persisted settings round-trip.
- `tests/test_themes.py`: built-in theme registry and preview token coverage.
- `tests/test_profiles.py`: session profile reset behavior and vector mode rules.
- `tests/test_gui_smoke.py`: guarded interactive GUI launch, preview snapshot, and Windows scaling checks.
- `tests/test_export_visual_alignment.py`: rendered raster/vector pixel alignment comparison.

Most recent change validation:

- Added `ArtworkProfile` model tests.
- Verified reset-to-original uses per-profile original dimensions.
- Verified missing original dimensions do not overwrite current values.
- Verified vector profile rules force PDF and `stretch`.
- Added contrast-ratio checks for text and preview overlay token pairs across every built-in theme.
- Added generated rotated PDF and unusual page box fixture export tests.
- Added raster/vector rendered pixel comparison using generated stripe artwork.
- Added GUI smoke tests that skip cleanly when Tk cannot create an interactive root.
- Added multi-page import/profile tests.
- Added custom output-name export filename test.
- Added regression test verifying `page_index=1` exports the second page rather than the first page.
- Added output name validation tests.
- Added Illustrator artboard-name import tests using injected artboard names so tests do not require Illustrator.
- Manually verified optional Illustrator COM integration against `AI_TEST.ai`.
- Added left-overlap layout regression coverage.
- Added left-overlap vector export dimension coverage.
- Added overlap-mode settings/profile coverage.
- Added legacy settings regression coverage for files missing `overlap_mode`.
- Verified the current AppData settings file already contains `overlap_mode` and `export_mode`.

Latest automated run:

- `python -m compileall -q artboard_cutter_gui_advanced.py src tests` passed.
- `python -m unittest discover -s tests` passed: 38 tests run, 3 skipped.
- `python -m unittest tests.test_gui_smoke -v` confirmed all GUI tests skip with the explicit local Tcl/Tk `init.tcl` error.
- `git check-ignore -v TEST.pdf test_outputs logs\app.log logs\export.log gude-2026-05-19.log` confirmed local PDF, test output, and generated log artifacts are ignored.
- Added GUI wrapper compatibility coverage.
- Added Illustrator fallback coverage for non-AI files and `require_running=True` without an Illustrator process.
- Added blank-DPI validation coverage: Vector allows blank DPI, Raster rejects blank DPI with a clear message.

Most recent hotfix run:

- `python -m compileall -q artboard_cutter_gui_advanced.py src tests` passed.
- `python -m unittest discover -s tests` passed: 40 tests run, 3 skipped.

Executable/icon validation:

- `python tools\generate_icon.py` wrote `assets/artboard_cutter.ico` and `assets/artboard_cutter_icon.png`.
- `pyinstaller --clean --noconfirm ArtboardCutter.spec` completed successfully.
- Built executable: `dist/ArtboardCutter.exe`.
- PyInstaller reported `Copying icon to EXE`.
- Extracted the associated icon from the built executable successfully.
- Created shortcut: `dist/Artboard Cutter.lnk`, with `IconLocation` set to `dist/ArtboardCutter.exe,0`.

README/repo cleanup validation:

- README screenshots generated under `docs/screenshots/`.
- Build path consolidated to `ArtboardCutter.spec`.
- Generated `dist/` output remains ignored/local while icon assets and README screenshots are trackable.

Skipped tests:

- `tests.test_gui_smoke.GuiSmokeTests.test_interactive_app_can_launch_and_close`
- `tests.test_gui_smoke.GuiSmokeTests.test_preview_snapshot_across_themes`
- `tests.test_gui_smoke.GuiSmokeTests.test_high_dpi_windows_scaling_smoke`

Skip reason:

- Local Python/Tk cannot create `Tk()` because Tcl reports it cannot find a usable `init.tcl` under `C:\Users\jiahu\AppData\Local\Programs\Python\Python313\tcl\tcl8.6`.
- `init.tcl` exists at that path, so this is documented as a local Tcl/Tk runtime resolution issue rather than an application import or syntax issue.

Manual checks performed:

- `TEST.pdf` actual-size split.
- `TEST.pdf` resized raster split.
- `TEST.pdf` vector stretch split.
- `TEST.pdf` vector stretch-master split.

Remaining validation needs:

- Interactive GUI launch after local Tcl/Tk issue is resolved.
- Screenshot-based preview validation across themes.
- Hands-on queue profile behavior checks in a working GUI runtime.
- Hands-on preview/export equivalence review across themes and real artwork.
- High-DPI Windows scaling check.

Already covered by automated tests:

- Rendered raster/vector pixel alignment comparison with generated fixture artwork.
- Rotated PDF fixture behavior.
- Unusual page box fixture behavior.
- Theme contrast-token checks.
- Settings persistence and legacy settings fallback.

## 2026-05-26 - Interactive preview editor tests

Commands:

- `python -m compileall -q artboard_cutter_gui_advanced.py src tests`
- `python -m unittest tests.test_layout`
- `python -m unittest discover -s tests`

Results:

- Compile passed.
- Layout tests passed: 10 tests.
- Full suite passed: 44 tests, 3 skipped.

New automated coverage:

- Splitting the last panel preserves total content width.
- Drag-style adjacent panel resizing preserves total content width.
- Adjacent resize clamps to a minimum panel width.
- Non-internal edge indices are rejected so bleed edges are not treated as draggable panel edges.

Skipped tests:

- The same 3 GUI/Tk smoke and screenshot tests remain skipped because this local Python/Tk runtime still cannot initialize Tcl/Tk.

## 2026-05-26 - Seam overlap protection tests

Commands:

- `python -m compileall -q artboard_cutter_gui_advanced.py src tests`
- `python -m unittest tests.test_layout`
- `python -m unittest discover -s tests`

Results:

- Compile passed.
- Layout tests passed: 12 tests.
- Full suite passed: 46 tests, 3 skipped.

New automated coverage:

- Interactive-style adjacent resize can return the original widths instead of clamping when a drag exceeds the allowed boundary.
- The protected minimum width can preserve the requested overlap value so preview seam dragging does not shrink overlap near neighboring seams or bleed edges.

## 2026-05-26 - PDF Preserve image input tests

Commands:

- `python -m compileall -q artboard_cutter_gui_advanced.py src tests`
- `python -m unittest tests.test_export_geometry tests.test_profiles tests.test_settings tests.test_gui_wrappers`
- `python -m unittest discover -s tests`

Results:

- Compile passed.
- Focused export/profile/settings/wrapper tests passed: 24 tests.
- Full suite passed: 47 tests, 3 skipped.

New automated coverage:

- PNG input can export through PDF Preserve mode into PDF panel outputs with expected panel dimensions.
- Legacy `Vector` settings normalize to `PDF Preserve`.
- PDF Preserve profile mode still forces PDF output and stretch behavior.
- Blank DPI remains valid for PDF Preserve mode.

## 2026-05-26 - Build and documentation refresh validation

Commands:

- `python tools\generate_icon.py`
- `pyinstaller --clean --noconfirm ArtboardCutter.spec`
- `python -m compileall -q artboard_cutter_gui_advanced.py src tests`
- `python -m unittest discover -s tests`

Results:

- Icon generation passed.
- PyInstaller build passed and produced `dist/ArtboardCutter.exe`.
- Compile passed.
- Full suite passed: 47 tests, 3 skipped.

## 2026-05-26 - Fixed layout overflow validation

Commands:

- `python -m compileall -q artboard_cutter_gui_advanced.py src tests`
- `python -m unittest discover -s tests`

Results:

- Compile passed.
- Full suite passed: 47 tests, 3 skipped.

Manual validation still needed:

- Shrink the app window and confirm no global horizontal scrollbar appears.
- Confirm the right-side vertical scrollbar appears only when the control stack is taller than the available window height.
- Confirm the preview canvas remains usable with its own zoom/pan behavior.

## 2026-05-26 - Theme redesign validation

Commands:

- `python -m compileall -q artboard_cutter_gui_advanced.py src tests`
- `python -m unittest tests.test_themes`
- `python -m unittest discover -s tests`

Results:

- Compile passed.
- Theme tests passed: 6 tests.
- Full suite passed: 48 tests, 3 skipped.

Covered:

- Required polished themes exist.
- Central design tokens exist for every built-in theme.
- Text, input, table, selection, and preview overlay contrast ratios pass.

Manual validation still needed:

- Launch the GUI in a working Tk runtime and visually inspect all themes,
  especially empty preview state, queue empty state, selected rows, button hover
  states, right-side scrolling, and long output folder paths.
## 2026-05-26 - Reference UI polish validation

Commands run:

```powershell
python -m compileall -q artboard_cutter_gui_advanced.py src tests
python -m unittest tests.test_themes
python -m unittest discover -s tests
python -m unittest tests.test_gui_smoke -v
```

Results:

- Compile check passed.
- Theme tests passed: 6 tests.
- Full unit discovery passed: 48 tests, 3 skipped.
- Direct GUI smoke file passed through guarded skips: 3 skipped.

Notes:

- The skipped GUI tests still report the local Tcl/Tk `init.tcl` runtime
  resolution issue before application code can create a Tk root window.
- Automated checks cover token presence, contrast pairs, and existing export/
  layout/profile behavior.
- Manual visual comparison against the reference still requires a working local
  Tk runtime or packaged executable launch.

## 2026-08-08 - Full improvement pass validation

- Compile passed.
- Full suite passed in the normal Windows host runtime: 63 tests, 0 failures, 0 skips.
- Restricted sandbox-equivalent coverage passed 60 tests with 3 guarded GUI/Tk skips caused by sandbox Tcl access.
- Coverage verifies JPG/TIFF extensions and dimensions, CMYK mode, equal Add Panel distribution, jobs/presets, overlap validation, collision/overwrite behavior, cancellation rollback and backup preservation, stale cleanup, fixtures, visual alignment, themes, and GUI smoke behavior.
- PyInstaller produced `dist/ArtboardCutter.exe`; a hidden launch stayed alive and was then stopped intentionally.
- The final package analysis reports no missing `src.artboard_cutter_core` modules after the entry point was changed to explicit imports.

## 2026-08-08 - Empty queue drop-target regression

- Focused GUI/wrapper suite passed: 7 tests.
- Full Windows suite passed: 64 tests, 0 failures, 0 skips.
- Verified app initialization registers all three queue layers without a TkDND error.
- Rebuilt `dist/ArtboardCutter.exe` successfully with the fix.

## 2026-08-08 - Export-only preset scope regression

- Added settings migration that removes legacy artwork dimensions and folder keys from presets.
- Added a real GUI regression confirming Apply leaves panel widths, artwork height, and output folder unchanged while applying export fields.
- Focused settings/GUI suite passed: 7 tests.
- Full Windows suite passed: 65 tests, 0 failures, 0 skips.
- Rebuilt and smoke-launched `dist/ArtboardCutter.exe` successfully.

## 2026-08-08 - Large CMYK TIFF regression

- Verified the reported first TIFF was uniformly white and the second contained normal artwork.
- Reproduced the source crop successfully at 5, 25, 75, 100, 125, 140, and 145 DPI; at 150 DPI MuPDF reported `Overly large image` and returned an all-zero 588 MB CMYK pixmap.
- Added automated coverage for channel-aware safe DPI selection and RGB/CMYK differences.
- Focused export suite passed: 22 tests.
- Full Windows suite passed: 67 tests, 0 failures, 0 skips.
- Rebuilt and smoke-launched `dist/ArtboardCutter.exe` successfully.
- `git diff --check` passed with line-ending notices only.

## 2026-08-11 - Comprehensive diagnostic baseline

Commands/checks:

- Full real-Windows `unittest` discovery, including live Tk and threaded GUI export.
- Branch coverage across GUI and core modules.
- `compileall`, `pip check`, Ruff fatal/bugbear checks, and `git diff --check`.
- 5,000 deterministic randomized layout/resize invariant cases.
- Multi-panel raster-source TIFF content verification and GUI-driven TIFF export.

Results:

- 114 tests passed, 0 failures, 0 skips.
- Core statement coverage: 83.8%; core branch coverage: 70.2%.
- GUI statement coverage: approximately 61.5%; GUI branch coverage: approximately 36.8% (the packaged-only self-test gate is measured separately).
- No syntax errors, broken dependencies, fatal static-analysis findings, or whitespace errors.
- Remaining uncovered paths are primarily platform/error fallbacks, dialogs, and real Adobe Illustrator COM behavior; they remain subject to manual integration acceptance.
- Final `dist/ArtboardCutter.exe` is 56,576,840 bytes with FileVersion/ProductVersion 1.2.0.
- PyInstaller no longer reports `tkinter` or Artboard Cutter core modules as missing.
- Packaged Tk/TkDND/TIFF self-test passed with exit code 0.

## 2026-08-26 - Layer visibility and Explorer job launch validation

- Synthetic PDF Preserve regression confirmed a default-hidden OCG stays hidden in both output metadata and rendered pixels.
- The supplied `BookingsCloud_VRMA26_A_2693x3416.ai` integration check passed: output preserved `backwall` as visible and both `3D Logo (DO NOT PRINT)` and `bolt + tv + cabinet + cloud` as hidden.
- GUI startup regression loaded a `.artboard-job` whose filename contained spaces through the same delayed path used by Windows Explorer.
- Installer regression confirmed the dedicated `.artboard-job` association and quoted `%1` open command, with no generic `.json` association.
- Full Windows suite passed: 118 tests, 0 failures, 0 skips.
- `compileall`, `pip check`, Ruff fatal/bugbear checks, and `git diff --check` passed.
- Rebuilt `dist/ArtboardCutter.exe`: 57,633,319 bytes, FileVersion/ProductVersion 1.2.1, SHA-256 `01B3B3A648C4C5F952CD3EE968AA5C144E8CECC17FCB6D8E35282A6011E4F5E9`.
- Packaged Tk/TkDND/TIFF self-test passed with exit code 0; the PyInstaller warning report contains no missing Tk or Artboard Cutter core modules.
- The workstation initially lacked Inno Setup. Inno Setup 6.7.3 was installed for the current user, then the installer compiled successfully as `release/ArtboardCutter-1.2.1-Setup.exe`.
- Final rebuilt standalone EXE: 57,633,720 bytes, FileVersion/ProductVersion 1.2.1, SHA-256 `AD11791EA859FCEA9E97F209EE0FC2615D6AD1C582AF91C023F1FF7F5B3AD0EE`.
- Final setup package: 58,882,029 bytes, ProductVersion 1.2.1, SHA-256 `68AC3E67D3CD2DC76B8E09114475E7C10AFD962BE8BA7DAAF60FD37E9911FE92`.
- The rebuilt standalone executable again passed the packaged self-test with exit code 0. Both release files are unsigned because no code-signing certificate was supplied.

## 2026-08-30 - Pre-commit verification

- Fresh unrestricted Windows suite: 118 tests passed, 0 failures, 0 skips (8.007 seconds).
- Initial sandbox run: 106 passed and 12 Tk GUI tests skipped because the sandbox could not load the host Tcl runtime; the unrestricted rerun exercised all of them.
- Compilation, dependency integrity, Ruff fatal/bugbear checks, and whitespace checks passed.
- Checked all 19 README links/anchors, including the three screenshot files; the documented 3-panel bleed/overlap example matched the layout engine.
- Scanned the intended source/documentation paths for common private-key and token patterns; no matches. Generated installers, local artwork, runtime logs, and the abandoned planning draft are excluded from the commit.
- Scope: code/documentation commit and branch push, not a new binary build, installer deployment, or new printer/RIP acceptance test.

## 2026-08-31 - Public release packaging checks

- Full Windows suite after release changes: 122 tests passed, 0 failures, 0 skips (9.110 seconds).
- New release-license regression file: 4 tests passed; first run failed as expected before the collector existed.
- `compileall`, `pip check`, and `git diff --check`: passed (only Git line-ending notices).
- Fresh PyInstaller and Inno Setup builds: successful; both executables report version 1.2.1 and are unsigned.
- Packaged Tk/TkDND/TIFF self-test: exit 0. Embedded LICENSE, NOTICE, and third-party guide matched source.
- Executable archive contains 112 dependency/runtime notice entries. Its third-party Python module roots
  match the dependency set covered by the collector.
- PyMuPDF source archive matches the PyPI SHA-256. Separate MuPDF source archive has 8,689 entries,
  including 7,170 third-party entries and 2,024 C/C++ source entries.
- Not performed: clean-machine install/uninstall and production print/RIP proof.

## 2026-09-08 - Oversized layered TIFF input validation

- Supplied-file reproduction before repair: container opened, but `load_page(0)` raised `FzErrorLimit: Overly large image`.
- Supplied-file verification after repair: one 12,283 x 23,799 CMYK page imported at its tagged 150 DPI; 590 x 1,142 RGB preview was non-uniform.
- Supplied-file 30 DPI smoke exports: 118 x 118 CMYK JPEG and TIFF outputs reopened successfully and had varying channel extrema.
- Automated suite: 123 tests passed with no failures or skips in the unrestricted Windows run. The restricted sandbox run passed the non-GUI tests and skipped 12 Tk checks because it could not resolve `init.tcl`.
- Entry-point self-test, compilation, and `git diff --check` passed.

## 2026-09-08 - v1.2.2 release verification

- Pre-release unrestricted Windows suite: 123 tests passed with no failures or skips; compilation, `pip check`, Ruff fatal/bugbear checks, and `git diff --check` passed.
- Independent GitHub Actions Windows build for commit `a7eb2dd8ae285b325c7acda647126ab6c6fc59b2`: passed.
- Standalone EXE: 57,875,762 bytes, ProductVersion 1.2.2, SHA-256 `8F592F2DE787F2FD0AE14FCB32E7761AAE489D2D6276184650F5F3CCB6555736`.
- Setup package: 59,135,363 bytes, ProductVersion 1.2.2, SHA-256 `642F1C1E937F19D2F643587826A0EF1AF8F6428A2D3BA282FB33079CB17B3EA7`.
- GitHub marks `v1.2.2` immutable and Latest. API asset digests and re-downloaded bytes match every local release file.
- Downloaded and installed executable self-tests passed. Installed path: `C:\Program Files\Artboard Cutter\ArtboardCutter.exe`.
- Both executables remain intentionally unsigned. Clean-machine install/uninstall and production printer/RIP validation remain unverified.

## 2026-09-08 - v1.2.3 packaged LZW preview verification

- Regression test failed before the fix because `ArtboardCutter.spec` omitted `imagecodecs._imcd`, then passed after the module was added.
- Supplied POSTER-4 and POSTER-6 source renders were nonblank; the rebuilt 1.2.3 executable visually displayed POSTER-4 in Live Preview.
- Full unrestricted Windows run: 124 tests executed, 123 passed, 1 desktop screenshot-comparison skip, 0 failures. Compilation, `pip check`, Ruff fatal/bugbear checks, and `git diff --check` passed.
- Packaged self-test exited 0. Standalone SHA-256: `06088C60D9658B99C0A0AF59731F3C7D168A1AA7D8C1E61167AC857A28771B13`; setup SHA-256: `31DA0894E26461990768A1E5770C6BD19587BD75826D348ACD3416B6828A012D`.

## 2026-09-10 - Oversized TIFF PDF fallback verification

- Live incident evidence: four profiles failed with `PDF Preserve is unavailable for oversized TIFF files`; the fifth profile used Raster and completed at 124 effective DPI.
- Regression failed before the fix at `_TiffDocument.convert_to_pdf`, then passed after the shared exporter routed unsupported preserve requests into raster PDF.
- Related export/profile tests: 51 passed, 0 failed. Full restricted-host suite: 125 executed, 113 passed, 12 Tk GUI checks skipped because the host Tcl runtime could not initialize.

## 2026-09-10 - Oversized TIFF preview latency verification

- Regression proved the same unchanged oversized TIFF invokes the expensive MuPDF probe once across repeated opens; it failed at two calls before the repair and passed at one afterward.
- Real-file timing on `2026_G2E_TADA_04.tif`: 2.49 seconds for the initial import compatibility probe, then 0.40 seconds to reopen and render the 1,600-pixel preview.
- Focused profile/export/GUI-wrapper suite: 30 passed, 0 failed.
- Full restricted-host suite: 126 executed, 114 passed, 12 Tk GUI checks skipped; compilation, dependency integrity, Ruff fatal/bugbear checks, and whitespace checks passed.

## 2026-09-10 - Lossless raster PDF verification

- Exact-byte regressions passed for RGB/LZW and CMYK/uncompressed TIFF pixels after panel extraction from the generated PDFs.
- A valid embedded sRGB TIFF profile remained attached through an ICCBased PDF image color space.
- Real 1.42 GB TADA CMYK TIFF: two output panels completed in 6.81 seconds and passed PDF dimension/render verification; output sizes were 134,377,224 and 127,249,001 bytes.
- Supplied `POSTER-6.tif` LZW CMYK composite: two output panels completed in 9.16 seconds, passed verification, and rendered with artwork continuing across the panel boundary.
- Full restricted-host suite: 129 executed, 117 passed, 12 Tk GUI checks skipped; compilation, dependency integrity, Ruff fatal/bugbear checks, and whitespace checks passed.
- Rebuilt packaged v1.2.4 self-test passed, including Tk/TkDND startup, TIFF writing, LZW decoding, and exact-byte Lossless PDF embedding.
- Standalone EXE: 57,989,031 bytes, ProductVersion 1.2.4, SHA-256 `0BA8AFCB2A14655D0F83436C07CBE8219EDCF6EBC7ECB5E4C72DB04FC44882BA`.
- Setup package: 59,249,683 bytes, ProductVersion 1.2.4, SHA-256 `F2A7747714322605D1E0EF58B43D15DAEE639E226B3514E3C1BBFAED22466DBC`.
- Both binaries remain intentionally unsigned.
