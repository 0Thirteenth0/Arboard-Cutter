# Windows release packaging

The v1.2.2 release is an unsigned Windows x64 AGPLv3 release. GitHub Releases
hosts end-user downloads; GitHub Packages is not used for this desktop app.

## Release files

- `ArtboardCutter-1.2.2-Setup.exe`: Inno installer with file association and notices.
- `ArtboardCutter.exe`: standalone executable with embedded runtime and notices.
- `ArtboardCutter-1.2.2-Licenses.zip`: `LICENSE`, `NOTICE`, `THIRD_PARTY_NOTICES.md`,
  and `licenses/` for reading notices without installing the app.
- `ArtboardCutter-1.2.2-Source.zip`: exact tagged application source ZIP, the official
  PyMuPDF 1.28.2 and MuPDF 1.28.2 source distributions, and rebuild directions.
- `SHA256SUMS.txt`: SHA-256 of each of the four files above.

The source/notices downloads are not needed to run the installer, but must remain
available with the binaries. No customer artwork, local job files, runtime logs,
credentials, or development environment files are added to release assets.
Repository documentation already tracked by Git remains in the application source.

## Maintainer procedure

1. Confirm the release version, clean Git state, source commit, and permission to publish.
2. Run the full Windows test suite, compile checks, and `pip check`.
3. Add Inno Setup's folder to `PATH`; run `tools/build_release.ps1 -CertificateThumbprint ''`.
4. Run `dist/ArtboardCutter.exe --self-test` and require exit 0. Inspect embedded
   `LICENSE`, `NOTICE`, `THIRD_PARTY_NOTICES.md`, and `licenses/` in the PyInstaller archive.
5. Verify executable/installer version resources and unsigned status. Test installation
   and uninstallation on a disposable Windows machine when available; do not silently
   replace the developer's installed application as a substitute for that test.
6. Use `git archive --format=zip HEAD` for application source; include the exact upstream
   source distribution below. Keep scripts and pinned dependency files in the source ZIP.
7. Generate SHA-256 checksums after all assets are final. Create a draft GitHub release
   pinned to the exact commit, upload the explicit asset list, and verify names/hashes.
8. Publish the draft as latest only after verification. Re-download and hash-check assets.
   Never replace an already-published release silently; use a new version for later changes.

## Source provenance

PyMuPDF's unmodified source distribution was obtained from PyPI:

- Filename: `pymupdf-1.28.2.tar.gz`
- URL: https://files.pythonhosted.org/packages/a3/fb/b6761fa2d5266f2cdb24c3b91f4023070ab7848381417678e7a289a1d52a/pymupdf-1.28.2.tar.gz
- SHA-256: `5e0be7908a715aa20333caddd73f1d6f01e4cd0c26e869fa2dd0b7f344da2249`

The separate MuPDF archive, including third-party sources, was downloaded from
the official MuPDF server:

- URL: https://mupdf.com/downloads/archive/mupdf-1.28.2-source.tar.gz
- SHA-256: `44075a84e329db55b9bef5f342a70fd26d69e48ad1d33cb89d9664581c641156`

`tools/collect_licenses.py` copies upstream notices verbatim from the pinned build
environment into `build/licenses/` and writes a version manifest. Both the batch
build and CI run it before PyInstaller; missing required notices fail the build.
The installer then includes the same license directory. No signing certificate,
commercial PyMuPDF key, or signing charge is involved.
