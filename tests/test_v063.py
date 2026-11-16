"""0.6.3 hazırlık (G-gb59vs) — denetim bulgularının önce-kırmızı kilitleri."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _widget_sel():
    m = re.search(r"^SEL='(.*)'\s*$", (ROOT / 'surface' / 'usage-widget').read_text(encoding='utf-8'), re.M)
    return m.group(1)


def _sayfa_basliklari():
    js = (ROOT / 'web' / 'app.js').read_text(encoding='utf-8')
    out = re.findall(r"pageTitle:\s*'([^']+)'", js)
    out.append(re.search(r'<title>([^<]+)</title>',
                         (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')).group(1)
               .replace('&amp;', '&'))
    return out


@unittest.skipUnless(shutil.which('jq'), 'jq yok')
class WidgetBaslikTest(unittest.TestCase):
    """UI-F003: 0.6.2'de sayfa başlığı 'usagelens · …' oldu; widget 'usage-tracker' arıyordu →
    toggle her tıkta yeni pencere açıyor, close hiçbir şeyi kapatmıyordu."""

    def _eslesen(self, basliklar):
        clients = [{'address': f'0x{i}', 'class': 'chrome-127.0.0.1__-Default', 'title': t}
                   for i, t in enumerate(basliklar)]
        r = subprocess.run(['jq', '-r', '--arg', 'c', 'usage-tracker-widget', _widget_sel() + '|.title'],
                           input=json.dumps(clients), capture_output=True, text=True, check=True)
        return [s for s in r.stdout.splitlines() if s]

    def test_panel_basliklari_eslesir(self):
        basliklar = _sayfa_basliklari()
        self.assertGreaterEqual(len(basliklar), 3)
        self.assertEqual(sorted(self._eslesen(basliklar)), sorted(basliklar))

    def test_ilgisiz_pencere_eslesmez(self):
        self.assertEqual(self._eslesen(['Gmail - Chromium', 'usage notes.txt']), [])


if __name__ == '__main__':
    unittest.main()
