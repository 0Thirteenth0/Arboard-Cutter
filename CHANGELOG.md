# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [1.2.3] - 2026-09-08

### Fixed

- Bundle the Imagecodecs LZW decoder so oversized LZW TIFF artwork renders in the packaged application's live preview.

## [1.2.2] - 2026-09-08

### Fixed

- Load, preview, and raster-export oversized 8-bit strip-based TIFF composites that exceed PyMuPDF's image-page limit. (`a7eb2dd`)
- Preserve tagged physical dimensions and CMYK data while decoding the source in bounded strips. (`a7eb2dd`)

## [1.2.1] - 2026-08-31

### Added

- First public Windows installer, standalone executable, license bundle, and corresponding-source package.

### Fixed

- Preserve default-hidden Illustrator/PDF layers in PDF Preserve output.
- Load `.artboard-job` files opened from Windows Explorer.
