import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.collect_licenses import collect_licenses, is_license_file


class ReleaseLicenseTests(unittest.TestCase):
    def test_recognizes_notices_and_embedded_license_directories(self):
        for name in ('pkg.dist-info/licenses/LICENSE', 'pkg/COPYING',
                     'pkg/NOTICE.md', 'pkg/licenses/PATENTS-rav1e'):
            self.assertTrue(is_license_file(Path(name)), name)
        self.assertFalse(is_license_file(Path('pkg/license_check.py')))

    def test_collects_installed_runtime_notices_without_absolute_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'licenses'
            manifest = collect_licenses(target)
            self.assertTrue((target / 'Python' / 'LICENSE.txt').is_file())
            self.assertTrue((target / 'TkDND' / 'tkdnd.tcl').is_file())
            self.assertIn('PyMuPDF', manifest['distributions'])
            self.assertEqual(manifest['distributions']['PyMuPDF']['version'], '1.28.2')
            for entry in manifest['distributions'].values():
                self.assertTrue(entry['files'])
                for relative in entry['files']:
                    self.assertFalse(Path(relative).is_absolute())
                    self.assertTrue((target / relative).is_file())
            self.assertEqual(json.loads((target / 'manifest.json').read_text()), manifest)

    def test_missing_dependency_notices_fail_the_build(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('tools.collect_licenses.metadata.files', return_value=[]):
                with self.assertRaisesRegex(RuntimeError, 'No license'):
                    collect_licenses(Path(directory) / 'licenses')

    def test_installer_and_executable_include_legal_notices(self):
        root = Path(__file__).resolve().parents[1]
        installer = (root / 'installer' / 'ArtboardCutter.iss').read_text()
        spec = (root / 'ArtboardCutter.spec').read_text()
        for name in ('LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md'):
            self.assertIn(name, installer)
            self.assertIn(name, spec)
        self.assertIn('build\\licenses', installer)
        self.assertIn('build/licenses', spec)

    def test_executable_bundles_large_tiff_lzw_decoder(self):
        root = Path(__file__).resolve().parents[1]
        spec = (root / 'ArtboardCutter.spec').read_text()

        self.assertIn('imagecodecs._imcd', spec)


if __name__ == '__main__':
    unittest.main()
