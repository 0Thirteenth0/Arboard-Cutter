import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from src.artboard_cutter_core.profiles import ArtworkProfile, create_artwork_profiles, sanitize_output_name, validate_output_name
from tests.helpers import make_multipage_pdf


class ArtworkProfileTests(unittest.TestCase):
    def test_reset_size_uses_original_dimensions(self):
        profile = ArtworkProfile(
            file_path="sample.pdf",
            original_width_mm=1200.0,
            original_height_mm=2000.0,
            panel_widths="500 500",
            height_mm="1000",
        )

        self.assertTrue(profile.reset_size_to_original())
        self.assertEqual(profile.panel_widths, "1200")
        self.assertEqual(profile.height_mm, "2000")

    def test_missing_original_size_cannot_reset(self):
        profile = ArtworkProfile(file_path="sample.pdf", panel_widths="500", height_mm="1000")

        self.assertFalse(profile.reset_size_to_original())
        self.assertEqual(profile.panel_widths, "500")
        self.assertEqual(profile.height_mm, "1000")

    def test_pdf_preserve_mode_forces_pdf_and_stretch(self):
        profile = ArtworkProfile(file_path="sample.pdf", export_mode="Vector", export_format="JPG")

        profile.apply_export_mode_rules()

        self.assertTrue(profile.preserve_vectors)
        self.assertEqual(profile.export_format, "PDF")
        self.assertEqual(profile.export_mode, "PDF Preserve")
        self.assertEqual(profile.vector_fit_mode, "stretch")

    def test_pdf_preserve_remembers_last_raster_image_format(self):
        profile = ArtworkProfile(
            file_path="sample.pdf",
            export_mode="PDF Preserve",
            export_format="TIFF",
        )
        profile.apply_export_mode_rules()
        self.assertEqual(profile.export_format, "PDF")
        self.assertEqual(profile.raster_export_format, "TIFF")

    def test_multipage_import_creates_one_profile_per_page(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Poster.pdf"
            make_multipage_pdf(path)

            profiles = create_artwork_profiles(path, bleed_mm="5", overlap_mm="10", dpi="96")

            self.assertEqual(len(profiles), 3)
            self.assertEqual([p.file_name for p in profiles], ["Poster1", "Poster2", "Poster3"])
            self.assertEqual([p.source_page_index for p in profiles], [0, 1, 2])
            self.assertEqual([p.source_page_count for p in profiles], [3, 3, 3])
            self.assertEqual(profiles[0].panel_widths, "100")
            self.assertEqual(profiles[1].panel_widths, "120")
            self.assertEqual(profiles[2].panel_widths, "140")

    def test_profile_import_keeps_overlap_mode_default(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Poster.pdf"
            make_multipage_pdf(path, page_specs=[(100, 80, (1, 0, 0))])

            profiles = create_artwork_profiles(path, overlap_mode="Left")

            self.assertEqual(profiles[0].overlap_mode, "Left")

    def test_single_page_import_uses_source_stem_as_queue_name(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Poster.pdf"
            make_multipage_pdf(path, page_specs=[(100, 80, (0.85, 0.10, 0.10))])

            profiles = create_artwork_profiles(path)

            self.assertEqual(len(profiles), 1)
            self.assertEqual(profiles[0].file_name, "Poster")

    def test_oversized_tiff_uses_strip_decoder_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Oversized.tif"
            Image.new("CMYK", (40, 20), (10, 20, 30, 40)).save(path, dpi=(100, 100), compression="tiff_lzw")
            rejected = MagicMock()
            rejected.load_page.side_effect = RuntimeError("Overly large image")

            with patch("src.artboard_cutter_core.pdf_io.fitz.open", return_value=rejected):
                profiles = create_artwork_profiles(path)

            rejected.close.assert_called_once()
            self.assertEqual(len(profiles), 1)
            self.assertAlmostEqual(profiles[0].original_width_mm, 10.16, places=2)
            self.assertAlmostEqual(profiles[0].original_height_mm, 5.08, places=2)

    def test_output_name_validation(self):
        self.assertEqual(validate_output_name(" Edited "), "Edited")
        for name in ["", "bad/name", "bad:name", "."]:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    validate_output_name(name)
        for name in ["CON", "nul.txt", "Panel.", "COM1"]:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    validate_output_name(name)

    def test_import_can_use_illustrator_artboard_names(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Poster.ai"
            make_multipage_pdf(path, page_specs=[(100, 80, (1, 0, 0)), (120, 90, (0, 1, 0))])

            profiles = create_artwork_profiles(path, artboard_names=["Main Backwall", "Counter/Desk"])

            self.assertEqual([p.file_name for p in profiles], ["Main Backwall", "Counter_Desk"])

    def test_duplicate_artboard_names_are_made_unique(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Poster.ai"
            make_multipage_pdf(path, page_specs=[(100, 80, (1, 0, 0)), (120, 90, (0, 1, 0))])

            profiles = create_artwork_profiles(path, artboard_names=["Panel", "Panel"])

            self.assertEqual([p.file_name for p in profiles], ["Panel", "Panel2"])

    def test_artboard_names_are_unique_even_with_case_and_suffix_collisions(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Poster.ai"
            make_multipage_pdf(
                path,
                page_specs=[(100, 80, (1, 0, 0)), (120, 90, (0, 1, 0)), (130, 90, (0, 0, 1))],
            )

            profiles = create_artwork_profiles(path, artboard_names=["Panel", "panel", "Panel2"])

            names = [profile.file_name for profile in profiles]
            self.assertEqual(len({name.casefold() for name in names}), 3)

    def test_sanitize_output_name_replaces_invalid_characters(self):
        self.assertEqual(sanitize_output_name("Counter/Desk:Left", "fallback"), "Counter_Desk_Left")
        self.assertEqual(sanitize_output_name("...", "fallback"), "fallback")


if __name__ == "__main__":
    unittest.main()
