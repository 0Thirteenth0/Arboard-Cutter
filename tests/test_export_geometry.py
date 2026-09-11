import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import pymupdf as fitz
except ImportError:
    import fitz  # type: ignore
from PIL import Image, ImageCms
import numpy as np
import tifffile

from src.artboard_cutter_core.export import ExportOptions, process_file
from src.artboard_cutter_core.errors import ExportCancelled, ExportError
from src.artboard_cutter_core.output_io import OutputConflictError, StagedOutputSet
from src.artboard_cutter_core.pdf_io import _TiffDocument
from src.artboard_cutter_core.raster_export import MAX_RENDER_BYTES, choose_safe_raster_dpi
from src.artboard_cutter_core.units import pt_to_mm
from tests.helpers import (
    make_grid_pdf,
    make_layered_pdf,
    make_multipage_pdf,
    make_rotated_pdf,
    make_unusual_page_box_pdf,
    render_pdf_page_rgb,
)


class ExportGeometryTests(unittest.TestCase):
    def test_cmyk_safety_limit_uses_one_dpi_for_large_panel_set(self):
        panel_sizes = [
            (3376.0431496062993, 10034.744881889765),
            (1726.5118110236226, 10034.744881889765),
        ]

        effective_dpi, _ = choose_safe_raster_dpi(panel_sizes, 150, "CMYK")

        self.assertLess(effective_dpi, 150)
        for width_pt, height_pt in panel_sizes:
            pixels = (width_pt / 72 * effective_dpi) * (height_pt / 72 * effective_dpi)
            self.assertLessEqual(pixels * 4, MAX_RENDER_BYTES)

    def test_same_large_panel_is_safe_at_requested_dpi_in_rgb(self):
        panel_sizes = [(3376.0431496062993, 10034.744881889765)]

        effective_dpi, _ = choose_safe_raster_dpi(panel_sizes, 150, "RGB")

        self.assertEqual(effective_dpi, 150)

    def assert_pdf_size_mm(self, pdf_path: Path, expected_w: float, expected_h: float, places=2):
        doc = fitz.open(pdf_path)
        try:
            rect = doc.load_page(0).rect
            self.assertAlmostEqual(pt_to_mm(rect.width), expected_w, places=places)
            self.assertAlmostEqual(pt_to_mm(rect.height), expected_h, places=places)
        finally:
            doc.close()

    def test_raster_pdf_panel_dimensions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "grid.pdf"
            make_grid_pdf(src)
            options = ExportOptions(
                bleed_mm=10,
                widths_mm=[100, 100],
                height_mm=100,
                overlap_mm=20,
                dpi=72,
                output_root=root / "out",
                export_fmt="pdf",
            )
            process_file(src, options)
            self.assert_pdf_size_mm(options.output_root / "grid_1.pdf", 120, 120)
            self.assert_pdf_size_mm(options.output_root / "grid_2.pdf", 120, 120)

    def test_vector_pdf_panel_dimensions_match_layout(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "grid.pdf"
            make_grid_pdf(src)
            options = ExportOptions(
                bleed_mm=10,
                widths_mm=[100, 100],
                height_mm=100,
                overlap_mm=20,
                dpi=72,
                output_root=root / "out",
                export_fmt="pdf",
                preserve_vectors=True,
                vector_fit_mode="stretch",
            )
            process_file(src, options)
            self.assert_pdf_size_mm(options.output_root / "grid_1.pdf", 120, 120)
            self.assert_pdf_size_mm(options.output_root / "grid_2.pdf", 120, 120)

    def test_pdf_preserve_keeps_default_hidden_layers_hidden(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "layered.pdf"
            make_layered_pdf(src)
            options = ExportOptions(
                bleed_mm=0,
                widths_mm=[100],
                height_mm=60,
                overlap_mm=0,
                dpi=72,
                output_root=root / "out",
                export_fmt="pdf",
                preserve_vectors=True,
                vector_fit_mode="stretch",
            )

            result = process_file(src, options)

            output = fitz.open(result.output_paths[0])
            try:
                states = {details["name"]: details["on"] for details in output.get_ocgs().values()}
                self.assertEqual(states, {"Visible artwork": True, "Hidden do not print": False})
                pix = output.load_page(0).get_pixmap(dpi=36, colorspace=fitz.csRGB, alpha=False)
                samples = bytes(pix.samples)
                right_half = []
                for y in range(pix.height):
                    start = (y * pix.width + pix.width // 2) * 3
                    end = (y * pix.width + pix.width) * 3
                    right_half.extend(samples[start:end])
                self.assertGreater(sum(right_half) / len(right_half), 245)
            finally:
                output.close()

    def test_left_overlap_panel_dimensions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "grid.pdf"
            make_grid_pdf(src, width_mm=320, height_mm=120)
            options = ExportOptions(
                bleed_mm=10,
                widths_mm=[100, 100, 100],
                height_mm=100,
                overlap_mm=20,
                overlap_mode="left",
                dpi=72,
                output_root=root / "out",
                export_fmt="pdf",
                preserve_vectors=True,
                vector_fit_mode="stretch",
            )
            process_file(src, options)
            self.assert_pdf_size_mm(options.output_root / "grid_1.pdf", 110, 120)
            self.assert_pdf_size_mm(options.output_root / "grid_2.pdf", 120, 120)
            self.assert_pdf_size_mm(options.output_root / "grid_3.pdf", 130, 120)

    def test_vector_stretch_supports_non_uniform_target_size(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "grid.pdf"
            make_grid_pdf(src, width_mm=220, height_mm=120)
            options = ExportOptions(
                bleed_mm=0,
                widths_mm=[80, 70],
                height_mm=100,
                overlap_mm=0,
                dpi=72,
                output_root=root / "out",
                export_fmt="pdf",
                preserve_vectors=True,
                vector_fit_mode="stretch",
            )
            process_file(src, options)
            self.assert_pdf_size_mm(options.output_root / "grid_1.pdf", 80, 100)
            self.assert_pdf_size_mm(options.output_root / "grid_2.pdf", 70, 100)

    def test_pdf_preserve_exports_raster_image_input_as_pdf_panels(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "image.png"
            Image.new("RGB", (320, 160), (20, 120, 220)).save(src)
            options = ExportOptions(
                bleed_mm=0,
                widths_mm=[80, 80],
                height_mm=80,
                overlap_mm=0,
                dpi=72,
                output_root=root / "out",
                export_fmt="pdf",
                preserve_vectors=True,
                vector_fit_mode="stretch",
            )
            process_file(src, options)
            self.assert_pdf_size_mm(options.output_root / "image_1.pdf", 80, 80)
            self.assert_pdf_size_mm(options.output_root / "image_2.pdf", 80, 80)

    def test_pdf_preserve_exports_oversized_tiff_pixels_losslessly(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "oversized.tif"
            pixels = np.array(
                [
                    [[255, 0, 0], [200, 0, 0], [150, 0, 0], [0, 0, 150], [0, 0, 200], [0, 0, 255]],
                    [[255, 50, 0], [200, 50, 0], [150, 50, 0], [0, 50, 150], [0, 50, 200], [0, 50, 255]],
                ],
                dtype=np.uint8,
            )
            tifffile.imwrite(
                src,
                pixels,
                photometric="rgb",
                compression="lzw",
                rowsperstrip=1,
                resolution=(25.4, 25.4),
            )
            options = ExportOptions(
                bleed_mm=0,
                widths_mm=[3, 3],
                height_mm=2,
                overlap_mm=0,
                dpi=1,
                output_root=root / "out",
                export_fmt="pdf",
                preserve_vectors=True,
            )

            with patch("src.artboard_cutter_core.export.open_pdf_robust", side_effect=lambda _path: _TiffDocument(src)):
                result = process_file(src, options)

            for index, expected in enumerate((pixels[:, :3], pixels[:, 3:]), start=1):
                doc = fitz.open(result.output_paths[index - 1])
                try:
                    page = doc.load_page(0)
                    images = page.get_images(full=True)
                    self.assertEqual(len(images), 1)
                    image = fitz.Pixmap(doc, images[0][0])
                    self.assertEqual((image.width, image.height, image.n), (3, 2, 3))
                    self.assertEqual(bytes(image.samples), expected.tobytes())
                finally:
                    doc.close()

    def test_lossless_tiff_pdf_keeps_cmyk_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "cmyk.tif"
            pixels = np.array([[[10, 20, 30, 40], [50, 60, 70, 80]]], dtype=np.uint8)
            tifffile.imwrite(
                src,
                pixels,
                photometric="separated",
                compression=None,
                resolution=(25.4, 25.4),
            )
            options = ExportOptions(
                bleed_mm=0,
                widths_mm=[2],
                height_mm=1,
                overlap_mm=0,
                dpi=1,
                output_root=root / "out",
                preserve_vectors=True,
            )

            with patch("src.artboard_cutter_core.export.open_pdf_robust", side_effect=lambda _path: _TiffDocument(src)):
                result = process_file(src, options)

            doc = fitz.open(result.output_paths[0])
            try:
                page = doc.load_page(0)
                image = fitz.Pixmap(doc, page.get_images(full=True)[0][0])
                self.assertEqual((image.width, image.height, image.n), (2, 1, 4))
                self.assertEqual(bytes(image.samples), pixels.tobytes())
            finally:
                doc.close()

    def test_lossless_tiff_pdf_preserves_embedded_icc_profile(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "profiled.tif"
            pixels = np.array([[[10, 20, 30], [50, 60, 70]]], dtype=np.uint8)
            profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
            tifffile.imwrite(
                src,
                pixels,
                photometric="rgb",
                compression=None,
                resolution=(25.4, 25.4),
                extratags=[(34675, "B", len(profile), profile, False)],
            )
            options = ExportOptions(
                bleed_mm=0,
                widths_mm=[2],
                height_mm=1,
                overlap_mm=0,
                dpi=1,
                output_root=root / "out",
                preserve_vectors=True,
            )

            with patch("src.artboard_cutter_core.export.open_pdf_robust", side_effect=lambda _path: _TiffDocument(src)):
                result = process_file(src, options)

            doc = fitz.open(result.output_paths[0])
            try:
                page = doc.load_page(0)
                image_xref = page.get_images(full=True)[0][0]
                image = fitz.Pixmap(doc, image_xref)
                self.assertEqual(bytes(image.samples), pixels.tobytes())
                self.assertIn("/ICCBased", doc.xref_object(image_xref, compressed=False))
            finally:
                doc.close()

    def test_rotated_pdf_fixture_exports_expected_panel_dimensions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "rotated.pdf"
            make_rotated_pdf(src)
            options = ExportOptions(
                bleed_mm=5,
                widths_mm=[40, 40],
                height_mm=60,
                overlap_mm=10,
                dpi=72,
                output_root=root / "out",
                export_fmt="pdf",
                preserve_vectors=True,
                vector_fit_mode="stretch",
            )
            process_file(src, options)
            self.assert_pdf_size_mm(options.output_root / "rotated_1.pdf", 50, 70)
            self.assert_pdf_size_mm(options.output_root / "rotated_2.pdf", 50, 70)

    def test_unusual_page_boxes_export_expected_panel_dimensions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "page_boxes.pdf"
            make_unusual_page_box_pdf(src)
            options = ExportOptions(
                bleed_mm=0,
                widths_mm=[100, 100],
                height_mm=120,
                overlap_mm=0,
                dpi=72,
                output_root=root / "out",
                export_fmt="pdf",
                preserve_vectors=True,
                vector_fit_mode="stretch",
            )
            process_file(src, options)
            self.assert_pdf_size_mm(options.output_root / "page_boxes_1.pdf", 100, 120)
            self.assert_pdf_size_mm(options.output_root / "page_boxes_2.pdf", 100, 120)

    def test_custom_output_name_controls_export_filename(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "source.pdf"
            make_grid_pdf(src, width_mm=100, height_mm=80)
            options = ExportOptions(
                bleed_mm=0,
                widths_mm=[100],
                height_mm=80,
                overlap_mm=0,
                dpi=72,
                output_root=root / "out",
                export_fmt="pdf",
                output_name="EditedQueueName",
            )
            process_file(src, options)
            self.assertTrue((options.output_root / "EditedQueueName_1.pdf").exists())
            self.assertFalse((options.output_root / "source_1.pdf").exists())

    def test_page_index_exports_requested_page_not_only_first_page(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "multipage.pdf"
            make_multipage_pdf(
                src,
                page_specs=[
                    (100, 80, (0.90, 0.05, 0.05)),
                    (100, 80, (0.05, 0.10, 0.90)),
                ],
            )
            options = ExportOptions(
                bleed_mm=0,
                widths_mm=[100],
                height_mm=80,
                overlap_mm=0,
                dpi=72,
                output_root=root / "out",
                export_fmt="pdf",
                page_index=1,
                output_name="SecondPage",
            )
            process_file(src, options)
            _, _, samples = render_pdf_page_rgb(options.output_root / "SecondPage_1.pdf", dpi=36)
            red = sum(samples[0::3]) / (len(samples) // 3)
            blue = sum(samples[2::3]) / (len(samples) // 3)
            self.assertGreater(blue, red, "Export appears to use page 1 instead of the requested second page.")


    def test_raster_jpg_outputs_jpg_with_requested_pixels_and_no_pdf(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "grid.pdf"
            make_grid_pdf(src, width_mm=100, height_mm=50)
            options = ExportOptions(0, [100], 50, 0, 100, root / "out", export_fmt="jpg")
            result = process_file(src, options)
            output = options.output_root / "grid_1.jpg"
            self.assertEqual(result.output_paths, (output,))
            self.assertTrue(output.exists())
            self.assertFalse((options.output_root / "grid_1.pdf").exists())
            with Image.open(output) as image:
                self.assertEqual(image.format, "JPEG")
                self.assertEqual(image.size, (394, 197))
                self.assertAlmostEqual(image.info["dpi"][0], 100, delta=1)

    def test_raster_tiff_outputs_tiff_with_requested_pixels_and_no_pdf(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "grid.pdf"
            make_grid_pdf(src, width_mm=100, height_mm=50)
            options = ExportOptions(0, [100], 50, 0, 100, root / "out", export_fmt="tiff")
            process_file(src, options)
            output = options.output_root / "grid_1.tif"
            self.assertTrue(output.exists())
            self.assertFalse((options.output_root / "grid_1.pdf").exists())
            with Image.open(output) as image:
                self.assertEqual(image.format, "TIFF")
                self.assertEqual(image.size, (394, 197))

    def test_every_multi_panel_tiff_from_raster_source_contains_artwork(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "gradient.jpg"
            source = Image.new("RGB", (300, 100))
            for x in range(source.width):
                for y in range(source.height):
                    source.putpixel((x, y), (x % 256, y * 2 % 256, (x + y) % 256))
            source.save(src, quality=95)

            result = process_file(
                src,
                ExportOptions(0, [100, 100, 100], 100, 0, 72, root / "out", export_fmt="tiff"),
            )

            self.assertEqual(len(result.output_paths), 3)
            for output in result.output_paths:
                with self.subTest(output=output.name), Image.open(output) as image:
                    extrema = image.convert("RGB").getextrema()
                    self.assertTrue(any(low != high for low, high in extrema), f"{output.name} is blank/uniform")

    def test_cmyk_raster_exports_preserve_cmyk_image_mode(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "grid.pdf"
            make_grid_pdf(src, width_mm=100, height_mm=50)
            for export_format, extension in (("jpg", "jpg"), ("tiff", "tif")):
                output_root = root / export_format
                process_file(
                    src,
                    ExportOptions(
                        0,
                        [100],
                        50,
                        0,
                        72,
                        output_root,
                        export_fmt=export_format,
                        color_mode="CMYK",
                    ),
                )
                with Image.open(output_root / f"grid_1.{extension}") as image:
                    self.assertEqual(image.mode, "CMYK")

    def test_raster_pdf_embeds_requested_pixel_dimensions_after_resize(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "grid.pdf"
            make_grid_pdf(src, width_mm=200, height_mm=100)
            options = ExportOptions(0, [100], 50, 0, 100, root / "out", export_fmt="pdf")
            process_file(src, options)
            doc = fitz.open(options.output_root / "grid_1.pdf")
            try:
                images = doc.load_page(0).get_images(full=True)
                self.assertEqual(len(images), 1)
                self.assertEqual((images[0][2], images[0][3]), (394, 197))
            finally:
                doc.close()

    def test_pdf_preserve_width_fit_uses_source_aspect_height(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "grid.pdf"
            make_grid_pdf(src, width_mm=100, height_mm=50)
            result = process_file(
                src,
                ExportOptions(
                    0,
                    [50, 50],
                    80,
                    0,
                    72,
                    root / "out",
                    preserve_vectors=True,
                    vector_fit_mode="width",
                ),
            )

            for output in result.output_paths:
                doc = fitz.open(output)
                try:
                    rect = doc.load_page(0).rect
                    self.assertAlmostEqual(pt_to_mm(rect.width), 50, places=2)
                    self.assertAlmostEqual(pt_to_mm(rect.height), 50, places=2)
                finally:
                    doc.close()

    def test_pdf_preserve_rejects_unknown_fit_mode(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "grid.pdf"
            make_grid_pdf(src, width_mm=100, height_mm=50)

            with self.assertRaisesRegex(ExportError, "Unsupported PDF Preserve fit mode"):
                process_file(
                    src,
                    ExportOptions(
                        0,
                        [100],
                        50,
                        0,
                        72,
                        root / "out",
                        preserve_vectors=True,
                        vector_fit_mode="diagonal",
                    ),
                )

    def test_source_open_failure_is_raised(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            options = ExportOptions(0, [100], 50, 0, 72, root / "out")
            with self.assertRaises(ExportError):
                process_file(root / "missing.pdf", options)

    def test_existing_outputs_require_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "grid.pdf"
            make_grid_pdf(src, width_mm=100, height_mm=50)
            options = ExportOptions(0, [100], 50, 0, 72, root / "out")
            process_file(src, options)
            with self.assertRaises(ExportError) as caught:
                process_file(src, options)
            self.assertIsInstance(caught.exception.__cause__, OutputConflictError)
            process_file(src, ExportOptions(0, [100], 50, 0, 72, root / "out", overwrite=True))

    def test_output_created_during_export_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            final = Path(td) / "panel_1.pdf"
            outputs = StagedOutputSet([final], overwrite=False)
            outputs.stage_paths[0].write_bytes(b"new export")
            final.write_bytes(b"external file")

            with self.assertRaisesRegex(OutputConflictError, "appeared during export"):
                outputs.commit()
            outputs.cleanup()

            self.assertEqual(final.read_bytes(), b"external file")

    def test_cancelled_export_leaves_no_partial_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "grid.pdf"
            make_grid_pdf(src, width_mm=100, height_mm=50)
            options = ExportOptions(
                0,
                [50, 50],
                50,
                0,
                72,
                root / "out",
                cancel_check=lambda: True,
            )
            with self.assertRaises(ExportCancelled):
                process_file(src, options)
            self.assertFalse((root / "out" / "grid_1.pdf").exists())
            self.assertFalse((root / "out" / "grid_2.pdf").exists())

    def test_failed_rollback_backup_is_never_deleted_by_cleanup(self):
        with tempfile.TemporaryDirectory() as td:
            final = Path(td) / "panel_1.pdf"
            outputs = StagedOutputSet([final], overwrite=True)
            backup = outputs._backup_paths[0]
            backup.write_bytes(b"recoverable old output")

            outputs.cleanup()

            self.assertTrue(backup.exists())

    def test_successful_overwrite_removes_stale_extra_panels(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "grid.pdf"
            make_grid_pdf(src, width_mm=150, height_mm=50)
            process_file(src, ExportOptions(0, [50, 50, 50], 50, 0, 72, root / "out"))
            self.assertTrue((root / "out" / "grid_3.pdf").exists())
            process_file(
                src,
                ExportOptions(
                    0,
                    [75, 75],
                    50,
                    0,
                    72,
                    root / "out",
                    overwrite=True,
                    cleanup_stale=True,
                ),
            )
            self.assertTrue((root / "out" / "grid_1.pdf").exists())
            self.assertTrue((root / "out" / "grid_2.pdf").exists())
            self.assertFalse((root / "out" / "grid_3.pdf").exists())

    def test_invalid_overlap_is_rejected_in_core(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "grid.pdf"
            make_grid_pdf(src, width_mm=100, height_mm=50)
            with self.assertRaisesRegex(ExportError, "must be smaller"):
                process_file(src, ExportOptions(0, [50, 50], 50, 50, 72, root / "out"))


if __name__ == "__main__":
    unittest.main()
