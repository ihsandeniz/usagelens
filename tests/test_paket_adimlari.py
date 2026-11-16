"""package.yml'in sihirbaz adım kontrolü — sabit sayı yerine kaynaktan okunan liste.

v0.6.2 etiketindeki `package` koşusu (43739610513) iki işte de düştü: sihirbaza 0.6.2'de
`statusline` adımı eklendi, iş akışı hâlâ "5 adım" bekliyordu. Ürün doğruydu, ölçüt bayattı.
Bu test, Linux işindeki gömülü Python kontrolünü iş akışından **olduğu gibi** çıkarıp
sahte bir `probe.json` ve sahte bir kaynak ağacıyla koşar:

  P1  Paketteki adımlar kaynaktakiyle aynıysa geçer.
  P2  Kaynağa yeni adım eklenince (paket de onu taşıyınca) geçer — sabit sayı yok.
  P3  Paket kaynaktaki bir adımı kaybetmişse düşer.
  P4  Kaynaktan taban bir adım silinirse (paket de onsuzsa) yine düşer.
  P5  İş akışında "6"/"5" gibi sabit adım sayısı kalmadı (iki iş için de).

Windows (pwsh) yarısı burada koşulmuyor — yalnız metin düzeyinde P5 ile denetleniyor.
"""
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
WF = ROOT / '.github' / 'workflows' / 'package.yml'


def _linux_check_script() -> str:
    """Linux işindeki 'The setup wizard runs from inside the package' adımının ilk heredoc'u."""
    text = WF.read_text(encoding='utf-8')
    start = text.index('- name: The setup wizard runs from inside the package')
    block = text[start:]
    m = re.search(r"python - <<'PY'\n(.*?)\n\s*PY\n", block, re.S)
    assert m, 'Linux sihirbaz adımında Python heredoc bulunamadı'
    lines = m.group(1).splitlines()
    indent = min(len(l) - len(l.lstrip()) for l in lines if l.strip())
    return '\n'.join(l[indent:] for l in lines) + '\n'


def _fake_tree(tmp: pathlib.Path, source_ids, probe_ids) -> None:
    pkg = tmp / 'usage'
    pkg.mkdir()
    (pkg / '__init__.py').write_text('', encoding='utf-8')
    (pkg / 'wizard.py').write_text(
        'def steps():\n'
        f'    return [{{"id": i, "title": i}} for i in {list(source_ids)!r}]\n',
        encoding='utf-8')
    (tmp / 'probe.json').write_text(json.dumps({
        'platform': 'linux', 'frozen': True,
        'steps': [{'id': i, 'title': i} for i in probe_ids]}), encoding='utf-8')


BASE = ['install', 'autostart', 'shortcut', 'statusline', 'keys', 'verify']


class PaketAdimKontrolu(unittest.TestCase):

    def _run(self, source_ids, probe_ids):
        script = _linux_check_script()
        with tempfile.TemporaryDirectory() as d:
            tmp = pathlib.Path(d)
            _fake_tree(tmp, source_ids, probe_ids)
            (tmp / 'check.py').write_text(script, encoding='utf-8')
            return subprocess.run([sys.executable, 'check.py'], cwd=tmp,
                                  capture_output=True, text=True, timeout=30)

    def test_p1_ayni_liste_gecer(self):
        r = self._run(BASE, BASE)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_p2_yeni_adim_kirmaz(self):
        ids = BASE[:-1] + ['tray', 'verify']
        r = self._run(ids, ids)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_p3_pakette_eksik_adim_duser(self):
        r = self._run(BASE, [i for i in BASE if i != 'statusline'])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('differ from source', r.stderr)

    def test_p4_tabandan_silinen_adim_duser(self):
        ids = [i for i in BASE if i != 'keys']
        r = self._run(ids, ids)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('disappeared', r.stderr)

    def test_p5_sabit_adim_sayisi_kalmadi(self):
        text = WF.read_text(encoding='utf-8')
        self.assertNotRegex(text, r"steps\.Count\s+-ne\s+\d")
        self.assertNotRegex(text, r"len\(probe\['steps'\]\)\s*!=\s*\d")
        # Windows yarısı da kaynaktan okumalı
        self.assertIn('from usage.wizard import steps', text.split('shell: pwsh', 1)[1])

    def test_gercek_kaynak_taban_kumeyi_tasiyor(self):
        from usage import wizard
        ids = [s['id'] for s in wizard.steps()]
        self.assertTrue(set(BASE) <= set(ids), ids)


if __name__ == '__main__':
    unittest.main()
