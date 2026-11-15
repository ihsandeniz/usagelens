"""Gate: in English mode no user-facing surface prints Turkish (v0.6.2, "karışık dil 0").

Runs `tests/lang_scan.py` — every CLI command, the server banner, the panel's JSON, the
waybar badge (server up / down / curl+jq missing) and setup.sh's machine interface, in a
throwaway HOME. Linux only (bash + sh feeder); about 20 s.
"""
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import lang_scan  # noqa: E402


@unittest.skipIf(os.name == 'nt' or not shutil.which('bash'), 'bash surfaces')
class EnglishModeHasNoTurkish(unittest.TestCase):
    def test_scan_finds_nothing(self):
        home = lang_scan.make_home()
        try:
            hits = lang_scan.collect(home)
        finally:
            shutil.rmtree(home, ignore_errors=True)
        self.assertEqual(hits, [], 'Turkish text in English mode:\n' + '\n'.join(hits))

    def test_the_scanner_still_sees_turkish(self):
        """The gate is only worth something if it can fail."""
        self.assertTrue(lang_scan.hits_in('x', 'sunucu yanıt vermedi'))
        self.assertTrue(lang_scan.hits_in('x', 'catalog: pakete gomulu snapshot'))
        self.assertFalse(lang_scan.hits_in('x', 'server did not answer'))


if __name__ == '__main__':
    unittest.main()
