# Artboard Cutter 1.2.2 changelog

## Fixed

- Load, preview, and raster-export oversized 8-bit strip-based TIFF composites that exceed PyMuPDF's image-page limit. (`a7eb2dd`)
- Preserve tagged physical dimensions and CMYK data while decoding the source in bounded strips. (`a7eb2dd`)
