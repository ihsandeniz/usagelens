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

    def test_acikca_hepsi_istenince_gizli_de_sorgulanir(self):
        """`providers --all` / `?all=1` "gizli kartları da göster" diyor (docs/CLI.md)."""
        from unittest import mock
        from usage import engine, viewconfig
        from usage.providers import openai
        self.assertTrue(viewconfig.save_config({'hidden_providers': ['openai']}))
        kart = {'id': 'openai', 'name': 'OpenAI', 'kind': 'spend', 'status': 'ok', 'available': True}
        with mock.patch.object(openai, 'collect', return_value=kart) as cagri:
            ids = [c['id'] for c in engine.compute_providers(30, include_hidden=True)]
            self.assertIn('openai', ids)
            ids = [c['id'] for c in engine.compute_providers(30, only_hidden=True)]
        self.assertEqual(ids, ['openai'])
        self.assertEqual(cagri.call_count, 2)

    def test_claude_gizlenemez_ve_gizli_liste_ayarda_gorunur(self):
        from usage import providers
        self.assertEqual(providers.name_of('openai'), 'OpenAI')
        self.assertIsNone(providers.name_of('yok-boyle'))

    def test_sihirbaz_metni_kodu_anlatir(self):
        from usage import wizard
        metin = ' '.join(wizard._preview_keys()['lines'])
        self.assertNotIn('only when you ask', metin)
        self.assertIn('hide', metin.lower())


class StartShEnvTest(unittest.TestCase):
    """SEC-F001: start.sh anahtar dosyasını `. "$ENV_FILE"` ile kabuk kodu olarak çalıştırıyordu;
    değerdeki `$(…)` ya da `;` komut olarak koşuyordu."""

    def _kos(self, env_metni):
        import os, tempfile
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / 'cfg' / 'usage-tracker').mkdir(parents=True)
            (td / 'cfg' / 'usage-tracker' / 'env').write_text(env_metni, encoding='utf-8')
            (td / 'bin').mkdir()
            sahte = td / 'bin' / 'python3'     # server.py yerine ortamı döken sahte yorumlayıcı
            sahte.write_text('#!/bin/sh\nenv > "$DOKUM"\n', encoding='utf-8')
            sahte.chmod(0o755)
            env = {'PATH': f"{td / 'bin'}:/usr/bin:/bin", 'HOME': str(td),
                   'XDG_CONFIG_HOME': str(td / 'cfg'), 'DOKUM': str(td / 'dokum'), 'KANIT': str(td)}
            r = subprocess.run(['timeout', '20', 'bash', str(ROOT / 'start.sh')], env=env,
                               cwd=td, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            dokum = dict(l.split('=', 1) for l in (td / 'dokum').read_text().splitlines() if '=' in l)
            return dokum, sorted(x.name for x in td.iterdir())

    def test_deger_komut_olarak_calismaz(self):
        dokum, dosyalar = self._kos('OPENAI_API_KEY=$(touch "$KANIT/pwn1")\n'
                                    'DEEPINFRA_API_KEY=a; touch "$KANIT/pwn2"\n'
                                    'touch "$KANIT/pwn3"\n')
        self.assertEqual([d for d in dosyalar if d.startswith('pwn')], [])
        self.assertEqual(dokum.get('OPENAI_API_KEY'), '$(touch "$KANIT/pwn1")')
        self.assertEqual(dokum.get('DEEPINFRA_API_KEY'), 'a; touch "$KANIT/pwn2"')

    def test_normal_dosya_okunur(self):
        dokum, _ = self._kos('# yorum\n\nOPENROUTER_API_KEY=sk-or-123\n# OPENAI_API_KEY=\n'
                             'ELEVENLABS_API_KEY="tirnakli"\nexport HF_TOKEN=hf_x\n')
        self.assertEqual(dokum.get('OPENROUTER_API_KEY'), 'sk-or-123')
        self.assertEqual(dokum.get('ELEVENLABS_API_KEY'), 'tirnakli')
        self.assertEqual(dokum.get('HF_TOKEN'), 'hf_x')
        self.assertNotIn('OPENAI_API_KEY', dokum)


class GuardBilinmeyenPencereTest(unittest.TestCase):
    """MNT-F001: Codex 5 saatlik pencere dolup değeri bilinmez olunca, haftalık biliniyorsa
    guard `ok`/0 dönüyordu; docs/CLI.md bu durum için 3 (unknown) vaat ediyor."""

    TH = {'warn': 75, 'crit': 90}

    def _wire(self, session, weekly):
        return {'thresholds': self.TH, 'providers': [
            {'id': 'claude', 'name': 'Claude', 'limits': {
                'session': {'pct': 10.0}, 'weekly': {'pct': 20.0}, 'weeklyModel': {'pct': None}}},
            {'id': 'codex', 'name': 'Codex', 'limits': {'session': session, 'weekly': weekly}}]}

    def test_suresi_dolmus_pencere_bilinmeyen(self):
        from usage import cli
        v = cli.evaluate(self._wire({'pct': None, 'expired': True}, {'pct': 40.0}), provider='codex')
        self.assertEqual((v['level'], v['exitCode']), ('unknown', 3), v['message'])

    def test_esik_asan_bilinen_pencere_yine_kazanir(self):
        from usage import cli
        v = cli.evaluate(self._wire({'pct': None, 'expired': True}, {'pct': 95.0}), provider='codex')
        self.assertEqual(v['exitCode'], 2)

    def test_uygulanamaz_pencere_claude_guard_bozmaz(self):
        """Claude weeklyModel normalde pct:null (model başı pencere yok) — bu 'bilinmeyen' değil."""
        from usage import cli
        v = cli.evaluate(self._wire({'pct': 5.0}, {'pct': 5.0}), provider='claude')
        self.assertEqual((v['level'], v['exitCode']), ('ok', 0))
        v = cli.evaluate(self._wire({'pct': 5.0}, {'pct': 5.0}), provider='all')
        self.assertEqual(v['exitCode'], 0)


if __name__ == '__main__':
    unittest.main()
