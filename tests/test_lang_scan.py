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


class NoTurkishLiteralsInTheBackend(unittest.TestCase):
    """Static half of the gate: provider notes only appear when that provider is installed
    (LM Studio's card needs `lms` on PATH), so the runtime scan cannot see all of them.
    Every human string in usage/ and server.py is English; Turkish lives in usage/i18n.py
    (and the panel's own dictionary). Docstrings and comments are not strings shown to anyone."""

    def test_no_turkish_string_constants(self):
        import ast
        import re
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        tr = re.compile('[çğıöşüÇĞİÖŞÜ]')
        files = [root / 'server.py', *sorted((root / 'usage').glob('*.py')),
                 *sorted((root / 'usage' / 'providers').glob('*.py'))]
        hits = []
        for f in files:
            if f.name == 'i18n.py':
                continue
            tree = ast.parse(f.read_text(encoding='utf-8'))
            docs = {id(n.body[0].value) for n in ast.walk(tree)
                    if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                      ast.AsyncFunctionDef))
                    and n.body and isinstance(n.body[0], ast.Expr)
                    and isinstance(n.body[0].value, ast.Constant)}
            for n in ast.walk(tree):
                if (isinstance(n, ast.Constant) and isinstance(n.value, str)
                        and id(n) not in docs and tr.search(n.value)):
                    hits.append(f'{f.relative_to(root)}:{n.lineno}: {n.value[:70]!r}')
        self.assertEqual(hits, [], '\n'.join(hits))
