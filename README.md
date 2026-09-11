# Artboard Cutter

Windows desktop tool for resizing large-format artwork and cutting it into numbered print panels, with outside bleed and repeated artwork at panel seams.

**Version 1.2.4 · Windows x64 · AGPLv3 · Unsigned distribution**

**[Download the latest Windows release](https://github.com/0Thirteenth0/Arboard-Cutter/releases/latest)**

Choose `ArtboardCutter-1.2.4-Setup.exe` for installation or `ArtboardCutter.exe` for
standalone use. Release assets also include license notices, corresponding source,
and `SHA256SUMS.txt` for verifying downloads.

Import PDF, PDF-compatible Adobe Illustrator files, JPG, PNG, or TIFF. Export vector-preserving PDF panels or raster PDF/JPG/TIFF panels. Artwork is processed locally; Illustrator is not required for ordinary import, preview, or export.

## Contents

- [Install and run](#install-and-run)
- [Quick start](#quick-start)
- [Queue and live preview](#queue-and-live-preview)
- [Dimensions, bleed, and overlap](#dimensions-bleed-and-overlap)
- [Export modes and color](#export-modes-and-color)
- [Presets and saved jobs](#presets-and-saved-jobs)
- [Export safety and recovery](#export-safety-and-recovery)
- [Output examples](#output-examples)
- [Troubleshooting and limitations](#troubleshooting-and-limitations)
- [Development and builds](#development-and-builds)
- [Recent changes](#recent-changes)
- [License and source](#license-and-source)

## Install and run

### Windows installer

Download and run `ArtboardCutter-1.2.4-Setup.exe` from [Releases](https://github.com/0Thirteenth0/Arboard-Cutter/releases/latest), or [build it from source](#build-the-installer). Setup installs the application, license notices, a Start menu shortcut, an optional desktop shortcut, and the `.artboard-job` file association. Installation requests administrator permission.

### Standalone executable

Download `ArtboardCutter.exe` and the accompanying `ArtboardCutter-1.2.4-Licenses.zip` from the release page. Extract the notices beside the executable and run it directly. The packaged application includes Python, Tcl/Tk, and its runtime dependencies; Python does not need to be installed separately. The standalone executable does not register Windows file associations by itself.

Both distribution formats are intentionally **unsigned**. Windows may display an unknown-publisher or SmartScreen warning. Only run a build from a source you trust, and follow any company security policy. Signing is not required for the application to work.

Built binaries are not checked into this Git repository. Local build outputs are:

```text
dist\ArtboardCutter.exe
release\ArtboardCutter-1.2.4-Setup.exe
```

## Quick start

1. Click **Add Files...** or drag artwork anywhere inside **Artwork Queue**, including the empty-queue message.
2. Click an artwork row to edit it. Multi-page documents have a separate row for each page/artboard.
3. Enter **Panel Widths (mm)** and **Height (mm)**. For three equal panels across 3000 mm, enter `1000 1000 1000`.
4. Set **Bleed**, **Overlap**, and **Shared** or **Left** overlap mode.
5. Choose **Raster** for DPI-rendered PDF/JPG/TIFF output, or **Lossless PDF** to keep source pixels or PDF content without rerendering.
6. In Raster mode, set DPI, RGB/CMYK, and optional ICC handling.
7. Choose the **Output Folder** and tick the rows to export. Highlighting a row is not the same as ticking it.
8. Click **Start Export**, review the preflight and replacement prompts, then confirm.

A queue item named `Lobby_Wall` produces files such as `Lobby_Wall_1.tif`, `Lobby_Wall_2.tif`, and `Lobby_Wall_3.tif`.

## Queue and live preview

The preview is on the left. The right-hand column contains the queue, settings, run controls, and Activity Log; it scrolls vertically when needed.

### Queue actions

- **Add Files...** accepts `.pdf`, PDF-compatible `.ai`, `.jpg`, `.jpeg`, `.png`, `.tif`, and `.tiff`.
- Click a row to load its independent settings and preview; tick its checkbox to include it in an export.
- **Check All**, **Uncheck All**, and **Check Selected** control batch selection.
- Double-click an artwork name to change the output filename base. Names must be valid Windows filenames and unique across the planned outputs.
- **Remove** removes selected rows; **Clear** empties the queue, including pending imports.
- **Get Names** optionally reads artboard names from an already-running Adobe Illustrator installation. If unavailable or busy, the app keeps numbered fallback names.

Import, preview rendering, and export use background workers. Preview images are resolution-limited for display; they do not represent the export DPI.

### Preview controls

- **Fit** shows the complete artwork.
- **+ / -** or the mouse wheel zooms; middle-mouse drag pans.
- Drag an internal seam to change its two neighboring widths while keeping their combined width unchanged.
- **Add Panel** adds one panel and redistributes the full current content width evenly.
- **Panels / Set** evenly divides the full current content width into the requested count.

Changing the panel count replaces any unequal widths. The preview reports target dimensions, panel count, bleed/overlap, and X/Y scale percentages. Different X/Y percentages mean non-uniform stretching; the app asks for confirmation before export.

## Dimensions, bleed, and overlap

All production dimensions use **millimetres**.

**Panel Widths** contains one finished content width per panel, separated by spaces or commas. Their sum is the full content width. **Height** is the finished content height for every panel. **Reset Size** restores the original source width and height, returning to a single full-width panel.

For example, `600 400` totals 1000 mm. Setting **Panels** to `4` produces `250 250 250 250`; Add Panel does not split only the last panel.

### Outside bleed

Bleed extends the left edge of the first panel, the right edge of the last panel, and the top/bottom of every panel. It is not inserted repeatedly at internal seams.

The full source artwork is scaled to the target extent including outside bleed, then clipped into panels. The app does not invent missing edge artwork or generate mirrored bleed; check that the source is suitable for this sizing method.

### Internal overlap

- **Shared:** split the overlap equally around a seam. With 40 mm overlap, the left panel extends 20 mm right of the seam and the right panel extends 20 mm left of it.
- **Left:** place the complete overlap on the left edge of the right-hand panel. The preceding panel ends at its content edge.

Overlap must be smaller than the narrowest panel. A blank Overlap field defaults to twice the bleed; enter `0` explicitly when no overlap is wanted.

With widths `1000 1000 1000`, height `2000`, bleed `10`, and Shared overlap `40`, the full target is 3020 × 2020 mm. Exported panel widths are 1030, 1040, and 1030 mm. Their sum is larger than the assembled width because seam artwork repeats.

## Export modes and color

| Setting | Raster | Lossless PDF |
| --- | --- | --- |
| Output | PDF, JPG, TIFF/BigTIFF | PDF only |
| Vector text/shapes | Rendered to pixels | Retained when already present in the source PDF/AI |
| DPI | Controls raster resolution | Not applicable |
| RGB/CMYK and ICC controls | Available | Disabled; original color samples and embedded TIFF profile are retained |
| Raster source images | Resampled to the target | Original pixels are embedded without DPI rendering or resampling |

**Lossless PDF** scales the full artwork to the entered physical dimensions, then clips it into panels. Raster TIFF pixels are divided and embedded directly, preserving RGB/CMYK samples and an embedded TIFF ICC profile without using the DPI field. PDF/AI content follows the same clipping route and retains source vectors and default layer visibility when available. You do not need to wrap a TIFF in Illustrator first.

**Raster** writes the selected format: JPG creates `.jpg`, TIFF creates `.tif`, and raster PDF creates `.pdf`. Large JPG/raster-PDF panels may use a lower common effective DPI to stay within the full-frame memory limit. TIFF streams width-adaptive strips to retain the requested DPI and uses BigTIFF for sufficiently large outputs.

### ICC handling in Raster mode

- **Off:** no selected output-profile conversion or embedding.
- **Embed only:** attach the selected profile without changing pixel values.
- **Convert:** transform pixels into the selected output profile, then embed it.

Choose an RGB profile for RGB output or a CMYK profile for CMYK output. Supported files use `.icc` or `.icm`. JPG/TIFF embed the profile; raster PDF uses an output intent.

Conversion uses an embedded RGB source profile from supported raster inputs when available, otherwise an sRGB working-space assumption. PDF/AI source profiles are not fully discoverable through this workflow. Use the profile and rendering intent supplied by the printer/RIP operator for color-critical work.

Rendering intents are Perceptual, Relative Colorimetric, Saturation, and Absolute Colorimetric. They affect conversion, not Embed only.

## Presets and saved jobs

### Export presets

Presets store reusable export behavior: bleed, overlap/mode, DPI, color mode, export mode/format, and ICC settings. Select a preset and click **Apply**; choosing its name alone does not apply it. **Save** stores the current export settings under a name, and **Delete** removes that preset.

Presets do **not** change panel widths, height, output name, or output folder. The former **Layout Template** feature has been removed; use Panels / Set, Add Panel, or direct width editing instead.

### Save Job / Load Job

**Save Job...** writes the queue and each artwork's settings to a versioned `.artboard-job` file. **Load Job...** restores it and asks before replacing an existing queue.

Job files preserve source paths, page selection, output names, dimensions, panel widths, selection state, and export settings. They do **not** embed source artwork or save the application-level output folder. Keep source files available and check the destination before exporting a loaded job.

- After installer registration, double-click an `.artboard-job` file to launch the app and load it.
- With the standalone executable, use **Open with** or pass a job path on the command line.
- Older `.artboard-job.json` files still load through Load Job or an explicit Open With. Re-save them as `.artboard-job` for the dedicated Windows association.
- Artboard Cutter does not associate itself with every `.json` file.
- Missing artwork paths are marked **Source missing**; a saved job is not a backup of the artwork.

```powershell
.\dist\ArtboardCutter.exe "C:\Artwork Jobs\Lobby.artboard-job"
```

## Export safety and recovery

Before exporting, preflight checks dimensions and formats, output names, folder write access, existing panel files, estimated disk usage, and large-raster memory requirements. It asks before replacing existing or stale numbered panels.

Each artwork's full panel set is written to temporary staged files first. Verification checks applicable formats, dimensions, DPI, color modes, requested profiles, and unexpected blank/uniform output. Only a successfully verified panel set replaces the destination files. This is a safety check, not a substitute for a visual print proof.

**Cancel Export** stops at a safe processing boundary. Previously completed jobs remain available; the incomplete panel set is discarded and unstarted jobs become **Interrupted**. **Retry Failed / Resume** selects unfinished/failed rows and regenerates those jobs, rather than resuming halfway through an individual file.

The queue is periodically saved for crash recovery. After an abnormal shutdown, a normal launch offers to restore it; closing normally removes the recovery snapshot. Opening a specific saved job at startup takes precedence over the recovery prompt.

The **Activity Log** shows preflight, crop, DPI, writer, ICC, verification, and error details. **Open Logs Folder** opens persistent logs. Settings and recovery data normally live alongside them:

```text
%LOCALAPPDATA%\ArtboardCutter\settings.json
%LOCALAPPDATA%\ArtboardCutter\session-recovery.artboard-job.json
%LOCALAPPDATA%\ArtboardCutter\logs\
```

## Output examples

These screenshots illustrate numbered panel output and assembly in Illustrator; they are output examples, not screenshots of the current application controls.

![Numbered panel PDFs in the output folder](docs/screenshots/output_panel_names.png)

![Six exported panels arranged with their outlines in Adobe Illustrator](docs/screenshots/output_panels_showing%20outline.png)

![Combined artwork assembled from exported panels in Adobe Illustrator](docs/screenshots/output_combined_adobe_illustrator.png)

## Troubleshooting and limitations

| Symptom | Check |
| --- | --- |
| JPG/TIFF export makes PDF | Select **Raster** first. Lossless PDF always exports PDF. |
| Hidden Illustrator layer reappears | Use v1.2.1 or newer, save the AI file, and confirm the source's saved PDF-compatible layer state. |
| Double-clicking a job does not load it | Use the current executable or install the current setup package. Legacy JSON jobs need Load Job or explicit Open With. |
| A preset appears to do nothing | Click **Apply** and inspect export settings. Dimensions and output folder intentionally stay unchanged. |
| Files cannot be dropped | Drop inside Artwork Queue. Avoid running only Artboard Cutter as Administrator while Explorer runs normally. |
| A TIFF panel is blank or verification fails | Check the source crop and Activity Log. Review disk space and try a small proof export. |
| A very large TIFF will not load, preview, or export | Oversized 8-bit strip-based TIFFs support preview, streamed Raster output, and Lossless PDF. Tiled, planar-separate, higher-bit-depth, or very large compressed single-strip TIFFs still need flattening. |
| Raster DPI is lower than entered | Check preflight's effective DPI. Large JPG/raster-PDF panels share a reduced safe DPI; TIFF is streamed. |
| Illustrator names are unavailable | Illustrator must already be running and free of modal/missing-link dialogs. Numbered names remain usable. |
| Check for Updates is unavailable | No hosted update manifest is configured by default. Install a new supplied build or rebuild from source. |

Production acceptance still requires checks in the intended printer/RIP, particularly for spot colors, overprint, transparency, linked assets, Illustrator-only constructs, very large TIFF/BigTIFF files, and extreme dimensions. Lossless PDF preserves source pixels or PDF content but does not promise native Illustrator editability or remove hidden source content permanently; it retains default layer visibility in PDFs.

## Development and builds

### Run from source

Use 64-bit Python with a working Tk runtime. CI is configured for Python 3.13; the local v1.2.4 Windows build was tested with Python 3.14.6. Dependencies are pinned in `requirements.txt` and `requirements-dev.txt`.

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe artboard_cutter_gui_advanced.py
```

### Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q artboard_cutter_gui_advanced.py src tests tools packaging_hooks
.\.venv\Scripts\python.exe -m pip check
```

The v1.2.4 suite contains 129 tests covering geometry, export formats, lossless TIFF-to-PDF content, oversized input, hidden layers, settings/jobs, startup loading, transactional writes, queue lifecycle, themes, and release packaging. GUI tests can skip if the host cannot initialize Tk or capture a desktop. See [testing notes](docs/testing.md) for manual integration checks and [recorded results](ai_logs/test_results.md) for dated evidence.

### Build the standalone executable

```powershell
.\build_exe.bat
```

The build validates Tk initialization, generates icon/version resources, and packages the app with PyInstaller. Custom hooks in `packaging_hooks/` collect Tcl/Tk for Windows. Test the packaged application after building:

```powershell
$process = Start-Process .\dist\ArtboardCutter.exe -ArgumentList '--self-test' -WindowStyle Hidden -PassThru
if (-not $process.WaitForExit(60000)) {
    Stop-Process -Id $process.Id
    throw 'Packaged self-test timed out.'
}
if ($process.ExitCode -ne 0) { throw 'Packaged self-test failed.' }
```

The self-test initializes Tk/TkDND and exercises TIFF output. The Windows GitHub Actions workflow also tests and builds the standalone EXE, then uploads it as a workflow artifact. It does not automatically publish a GitHub release or build the Inno installer.

### Build the installer

Install Inno Setup 6 and make `ISCC.exe` available on `PATH`. For a default current-user installation, the following also works:

```powershell
$env:PATH = "$env:LOCALAPPDATA\Programs\Inno Setup 6;$env:PATH"
.\tools\build_release.ps1 -CertificateThumbprint ''
```

This rebuilds the standalone executable and compiles `installer/ArtboardCutter.iss` into `release/ArtboardCutter-1.2.4-Setup.exe`. The empty certificate argument explicitly keeps the build unsigned. If ISCC is not on PATH, the script leaves the standalone EXE and prints a warning instead of producing an installer.

`APP_VERSION` in `src/artboard_cutter_core/version.py` is the version source. `tools/generate_version_metadata.py` generates `version_info.txt` and `installer/version.iss`. `update-manifest.example.json` is only a template; automatic update checking requires a configured HTTPS manifest URL.

Build outputs (`build/`, `dist/`, `release/`), source artwork, runtime logs, and test exports stay out of Git. Share binaries separately as release assets when publishing a release.

### Project layout

```text
artboard_cutter_gui_advanced.py   Desktop entry point and UI
src/artboard_cutter_core/         Export engine, geometry, profiles, settings, jobs
tests/                            Unit, export, and Windows GUI regressions
docs/                             Testing guide and output screenshots
ai_logs/                          Development history and verification records
assets/                           Application icon and UI icons
installer/                        Inno Setup definition and generated version
packaging_hooks/                  Tcl/Tk PyInstaller collection/runtime hooks
tools/                            Build and metadata utilities
.github/workflows/                Windows test/build automation
```

## Recent changes

### 1.2.4

- Export oversized TIFFs as lossless raster PDFs without DPI rendering, resampling, or color conversion.
- Open previews faster after importing oversized TIFFs by reusing the file-revision-aware fallback decision.

### 1.2.3

- Restore oversized LZW TIFF artwork in the packaged application's live preview by bundling the required decoder.

### 1.2.2

- Load and preview oversized layered TIFF artwork that exceeds PyMuPDF's image-page limit.
- Stream the saved TIFF composite through bounded strips for raster PDF/JPG/TIFF export without materializing the full source image.
- Report unsupported oversized TIFF layouts and PDF Preserve mode clearly instead of leaving the queue in a failed-probe state.

### 1.2.1

- Preserve default-hidden Illustrator/PDF layers in PDF Preserve panels.
- Load saved jobs passed to the executable by Windows Explorer.
- Save new jobs as `.artboard-job`, retain legacy JSON-job compatibility, and add installer file association.
- Supply an unsigned standalone EXE and Inno Setup installer.

### Earlier reliability and usability updates included in this branch

- Correct JPG/TIFF output formats; stream large TIFF panels with blank-output verification.
- Evenly redistribute the full artwork width when adding/setting panels.
- Keep presets separate from dimensions/output folder; remove Layout Template.
- Improve panel-count field contrast across themes and queue drop targets.
- Harden cancellation, recovery, stale imports, numeric validation, output-name collisions, and output replacement.
- Bundle Tcl/Tk explicitly and test the packaged runtime before distribution.

See [development decisions](ai_logs/decisions.md) and the [session log](ai_logs/session_log.md) for the implementation history.

## License and source

Artboard Cutter is free software under **GNU AGPLv3 (AGPL-3.0-only)**, with no
warranty. See [LICENSE](LICENSE), [NOTICE](NOTICE), and
[third-party notices and source locations](THIRD_PARTY_NOTICES.md).
This license covers the program, not your imported/exported artwork.

The release page provides the exact application source and build scripts, plus
the PyMuPDF/MuPDF source distribution, in `ArtboardCutter-1.2.4-Source.zip`.
The ordinary GitHub source-code ZIP contains only this repository.
License texts for bundled components are included with the installer and in
`ArtboardCutter-1.2.4-Licenses.zip`. **About** in the application also identifies
the license, warranty disclaimer, and source location.

See [release packaging notes](docs/releasing.md) for artifact contents and checks.
