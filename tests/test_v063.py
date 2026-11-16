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


class GizliSaglayiciIstekTest(unittest.TestCase):
    """API-F001: kart gizli olsa da anahtar ortamdaysa o servise istek gidiyordu
    (`hidden_providers` yalnız çıktıyı süzüyordu); sihirbaz metni tersini söylüyordu."""

    def setUp(self):
        import tempfile
        from unittest import mock
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.p = mock.patch.dict('os.environ', {'XDG_CONFIG_HOME': self.td.name,
                                                'XDG_STATE_HOME': self.td.name,
                                                'OPENAI_API_KEY': 'sk-test-yok'})
        self.p.start()
        self.addCleanup(self.p.stop)
        from usage import viewconfig      # yol import anında sabitlenir: gerçek ~/.config'e yazmasın
        for ad in ('CONFIG_PATH', 'LEGACY_CONFIG_PATH'):
            q = mock.patch.object(viewconfig, ad, Path(self.td.name) / f'{ad}.json')
            q.start()
            self.addCleanup(q.stop)

    def test_gizli_saglayiciya_istek_gitmez(self):
        from unittest import mock
        from usage import engine, viewconfig
        from usage.providers import openai
        self.assertTrue(viewconfig.save_config({'hidden_providers': ['openai']}))
        with mock.patch.object(openai, 'collect', return_value=None) as cagri:
            engine.compute_providers(30)
        cagri.assert_not_called()

    def test_gizli_olmayan_sorgulanir(self):
        from unittest import mock
        from usage import engine, viewconfig
        from usage.providers import openai
        self.assertTrue(viewconfig.save_config({'hidden_providers': []}))
        with mock.patch.object(openai, 'collect', return_value=None) as cagri:
            engine.compute_providers(30)
        cagri.assert_called_once()

    def test_claude_gizlenemez_ve_gizli_liste_ayarda_gorunur(self):
        from usage import providers
        self.assertEqual(providers.name_of('openai'), 'OpenAI')
        self.assertIsNone(providers.name_of('yok-boyle'))

    def test_sihirbaz_metni_kodu_anlatir(self):
        from usage import wizard
        metin = ' '.join(wizard._preview_keys()['lines'])
        self.assertNotIn('only when you ask', metin)
        self.assertIn('hide', metin.lower())


if __name__ == '__main__':
    unittest.main()
