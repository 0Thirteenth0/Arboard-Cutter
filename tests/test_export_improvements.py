import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageCms
try:
    import pymupdf as fitz
except ImportError:
    import fitz  # type: ignore

from src.artboard_cutter_core.export import ExportOptions, process_file
from src.artboard_cutter_core.pdf_io import _TiffDocument
from src.artboard_cutter_core.preflight import combined_disk_space_warning, estimate_export_job
from src.artboard_cutter_core.raster_export import should_use_bigtiff, tiff_band_rows
from src.artboard_cutter_core.validation import validate_export_values
from src.artboard_cutter_core.verification import VerificationResult, verify_raster_output
from tests.helpers import make_grid_pdf


class ExportImprovementTests(unittest.TestCase):
    def test_pdf_preserve_falls_back_to_raster_pdf_for_oversized_tiff(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "oversized.tif"
            Image.new("CMYK", (40, 20), (10, 20, 30, 40)).save(source, dpi=(100, 100))

            with patch(
                "src.artboard_cutter_core.export.open_pdf_robust",
                side_effect=lambda _path: _TiffDocument(source),
            ):
                result = process_file(
                    source,
                    ExportOptions(
                        0,
                        [10.16],
                        5.08,
                        0,
                        72,
                        root / "out",
                        export_fmt="pdf",
                        preserve_vectors=True,
                    ),
                )

            self.assertEqual(result.output_paths, (root / "out" / "oversized_1.pdf",))
            self.assertTrue(result.output_paths[0].is_file())

    def test_streaming_tiff_embeds_selected_rgb_profile(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "gradient.jpg"
            image = Image.new("RGB", (120, 80))
            for x in range(image.width):
                for y in range(image.height):
                    image.putpixel((x, y), (x * 2, y * 3, (x + y) % 256))
            image.save(source, quality=95)
            profile_bytes = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            profile_path = root / "sRGB.icc"
            profile_path.write_bytes(profile_bytes)

            result = process_file(
                source,
                ExportOptions(
                    bleed_mm=0,
                    widths_mm=[120],
                    height_mm=80,
                    overlap_mm=0,
                    dpi=100,
                    output_root=root / "out",
                    export_fmt="tiff",
                    icc_mode="Convert",
                    icc_profile_path=str(profile_path),
                ),
            )

            with Image.open(result.output_paths[0]) as output:
                self.assertEqual(output.mode, "RGB")
                self.assertTrue(output.info.get("icc_profile"))

    def test_raster_pdf_embeds_output_intent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.jpg"
            Image.new("RGB", (40, 30), (20, 80, 160)).save(source)
            profile_path = root / "sRGB.icc"
            profile_path.write_bytes(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
            result = process_file(
                source,
                ExportOptions(
                    0, [40], 30, 0, 72, root / "out",
                    export_fmt="pdf",
                    icc_mode="Embed only",
                    icc_profile_path=str(profile_path),
                ),
            )
            doc = fitz.open(result.output_paths[0])
            try:
                kind, value = doc.xref_get_key(doc.pdf_catalog(), "OutputIntents")
                self.assertEqual(kind, "array")
                self.assertIn(" R", value)
            finally:
                doc.close()

    def test_verifier_rejects_uniform_output_for_varying_source(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "blank.tif"
            Image.new("RGB", (20, 10), "white").save(path, dpi=(100, 100))
            with self.assertRaisesRegex(RuntimeError, "blank/uniform"):
                verify_raster_output(
                    path,
                    expected_size=(20, 10),
                    expected_dpi=100,
                    expected_mode="RGB",
                    source_varies=True,
                )

    def test_verifier_rejects_missing_requested_icc_profile(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "unprofiled.jpg"
            Image.new("RGB", (20, 10), "white").save(path, dpi=(100, 100))
            with self.assertRaisesRegex(RuntimeError, "ICC profile was not embedded"):
                verify_raster_output(
                    path,
                    expected_size=(20, 10),
                    expected_dpi=100,
                    expected_mode="RGB",
                    source_varies=False,
                    expect_icc=True,
                )

    def test_pdf_preserve_verification_rejects_uniform_output_for_varying_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "grid.pdf"
            make_grid_pdf(source, width_mm=100, height_mm=100)
            fake_result = VerificationResult(root / "stage.pdf", None, None, None, "PDF", True)
            with patch("src.artboard_cutter_core.vector_export.verify_pdf_output", return_value=fake_result):
                with self.assertRaisesRegex(Exception, "blank/uniform"):
                    process_file(
                        source,
                        ExportOptions(
                            0,
                            [100],
                            100,
                            0,
                            72,
                            root / "out",
                            preserve_vectors=True,
                        ),
                    )

    def test_tiff_preflight_retains_requested_dpi_and_flags_large_jobs(self):
        estimate = estimate_export_job(
            widths_mm=[5000, 5000],
            height_mm=4000,
            bleed_mm=0,
            overlap_mm=0,
            overlap_mode="shared",
            dpi=300,
            color_mode="CMYK",
            export_format="TIFF",
            preserve_vectors=False,
        )
        self.assertEqual(estimate.effective_dpi, 300)
        self.assertTrue(estimate.uses_streaming_tiff)
        self.assertTrue(estimate.warnings)

    def test_pdf_preserve_preflight_estimates_panel_output_size(self):
        estimate = estimate_export_job(
            widths_mm=[500, 500, 500],
            height_mm=1000,
            bleed_mm=0,
            overlap_mm=0,
            overlap_mode="shared",
            dpi=None,
            color_mode="RGB",
            export_format="PDF",
            preserve_vectors=True,
            source_size_bytes=2_000_000,
        )
        self.assertEqual(estimate.panel_count, 3)
        self.assertGreaterEqual(estimate.estimated_disk_bytes, 6_000_000)
        self.assertIn("Estimated output space", "\n".join(estimate.summary_lines()))

    def test_preflight_warns_when_combined_jobs_exceed_free_space(self):
        estimates = [
            estimate_export_job(
                widths_mm=[100],
                height_mm=100,
                bleed_mm=0,
                overlap_mm=0,
                overlap_mode="shared",
                dpi=None,
                color_mode="RGB",
                export_format="PDF",
                preserve_vectors=True,
                source_size_bytes=4_000_000,
            )
            for _ in range(2)
        ]
        estimates = [
            estimate.__class__(
                **{
                    **estimate.__dict__,
                    "free_disk_bytes": 6_000_000,
                }
            )
            for estimate in estimates
        ]
        self.assertIn("Combined batch", combined_disk_space_warning(estimates) or "")

    def test_non_finite_export_numbers_are_rejected(self):
        common = dict(
            output_name="test",
            bleed_mm=0,
            widths_mm=[100],
            height_mm=100,
            overlap_mm=0,
            overlap_mode="Shared",
            dpi=150,
            export_format="PDF",
            preserve_vectors=False,
            color_mode="RGB",
        )
        cases = {
            "bleed": {"bleed_mm": float("nan")},
            "width": {"widths_mm": [float("nan")]},
            "height": {"height_mm": float("inf")},
            "overlap": {"overlap_mm": float("nan")},
        }
        for name, override in cases.items():
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "finite"):
                validate_export_values(**{**common, **override})

    def test_bigtiff_decision_uses_uncompressed_sample_size(self):
        self.assertFalse(should_use_bigtiff(1000, 1000, 4))
        self.assertTrue(should_use_bigtiff(50_000, 20_000, 4))

    def test_tiff_band_height_shrinks_for_extremely_wide_outputs(self):
        self.assertEqual(tiff_band_rows(1_000, 4), 256)
        self.assertLess(tiff_band_rows(1_000_000, 4), 256)
        self.assertEqual(tiff_band_rows(100_000_000, 4), 1)


if __name__ == "__main__":
    unittest.main()
