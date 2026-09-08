# Third-party notices and source

Artboard Cutter is distributed under AGPL-3.0-only; see [LICENSE](LICENSE) and
[NOTICE](NOTICE). Dependencies are used unmodified and retain their own terms.
This notice does not replace any dependency's full license text.

The installer installs a `licenses/` directory; the standalone download is
accompanied by `ArtboardCutter-1.2.2-Licenses.zip`. The executable also embeds
these notices. `licenses/manifest.json` records the exact installed dependency
versions and the license files copied from their distributions at build time.
Some upstream notices cover optional codecs that the application does not use.

## Components

| Component | Version in this release | License / upstream source |
| --- | --- | --- |
| PyMuPDF and MuPDF | 1.28.2 | AGPLv3; [PyMuPDF source](https://pypi.org/project/PyMuPDF/1.28.2/#files) and [MuPDF source](https://mupdf.com/downloads/archive/mupdf-1.28.2-source.tar.gz) |
| Pillow | 12.3.0 | MIT-CMU/Pillow license and bundled-library notices; [source](https://pypi.org/project/Pillow/12.3.0/#files) |
| tkinterdnd2 | 0.6.2 | MIT; [source](https://pypi.org/project/tkinterdnd2/0.6.2/#files) |
| TkDND | Supplied by tkinterdnd2 | Tcl-style permissive notice in `licenses/TkDND/tkdnd.tcl`; [upstream](https://github.com/petasis/tkdnd) |
| pywin32 | 312 | Python/PSF-style and component-specific notices; [source](https://github.com/mhammond/pywin32/tree/b312) |
| NumPy | 2.5.1 | BSD-3-Clause and bundled-library notices/exceptions; [source](https://pypi.org/project/numpy/2.5.1/#files) |
| tifffile | 2026.7.31 | BSD-3-Clause; [source](https://pypi.org/project/tifffile/2026.7.31/#files) |
| imagecodecs | 2026.6.26 | BSD-3-Clause and codec-specific terms; [source](https://pypi.org/project/imagecodecs/2026.6.26/#files) |
| CPython | 3.14.6 (local Windows build) | PSF and bundled-library notices; [source](https://www.python.org/downloads/release/python-3146/) |
| Tcl/Tk | 8.6 (CPython runtime) | Tcl/Tk permissive terms; Python's license and Tk's `license.terms` are included |
| PyInstaller bootloader/runtime | 6.22.0 | GPL with bootloader distribution exception; [source](https://pypi.org/project/pyinstaller/6.22.0/#files) |

## Corresponding source and rebuilding

The [v1.2.2 release](https://github.com/0Thirteenth0/Arboard-Cutter/releases/tag/v1.2.2)
provides `ArtboardCutter-1.2.2-Source.zip`: the exact tagged application source,
build scripts, and the official `pymupdf-1.28.2.tar.gz` and
`mupdf-1.28.2-source.tar.gz` source distributions. MuPDF's archive includes its
third-party sources. See the
archive's `README-SOURCE.md`, PyMuPDF's `setup.py`, and MuPDF's build instructions.
The release also provides GitHub's ordinary source archives for the application
alone. The other unmodified dependencies' source locations are listed above.

To rebuild the app, follow the source repository's README and pinned
`requirements.txt` / `requirements-dev.txt`. No signing certificate or license
key is needed for the AGPL build. Do not remove license/source notices when
redistributing. Keep the corresponding sources available alongside binaries.
