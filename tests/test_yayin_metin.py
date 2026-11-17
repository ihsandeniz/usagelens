"""Yayın metni kapısı (v0.6.2 bağımsız denetim, G-g6ymim → G-g79loy).

README "no extra request goes to Anthropic" diyordu; kod ise durum satırı kaydı 10 dakikadan
eskiyse `api/oauth/usage`'a gidiyor (`usage/live.py`). Bu dosya o cümlenin geri gelmesini,
metindeki sürelerin koddan kopmasını ve yayın notlarının (kaldırma sırası, models.dev atfı,
PKGBUILD iç yolu, sürüme sabit pipx satırı, deneysel sayısı) düşmesini kırmızıya çevirir.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# İddia taşıyan bütün yüzeyler (belge + kurulum ekranları).
YUZEYLER = ['README.md', 'README.tr.md', 'docs/GUIDE.md', 'setup.sh', 'web/setup.js',
            'web/wizard.js']
YASAK = [r'no extra request', r'ek istek gitmez', r'ek istek yok', r'ek istek atmadan',
         r'ek istek yapılmaz', r'rate-limit\\?\'li uca ek istek']


def oku(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


class YanlisIddiaGeriGelmez(unittest.TestCase):
    def test_eski_cumle_hicbir_yuzeyde_yok(self):
        for rel in YUZEYLER:
            metin = oku(rel)
            for desen in YASAK:
                with self.subTest(dosya=rel, desen=desen):
                    self.assertIsNone(re.search(desen, metin, re.I),
                                      f'{rel}: yanlış "ek istek yok" iddiası geri geldi')

    def test_readme_gercegi_soyluyor_ve_sureler_kodla_ayni(self):
        from usage import live
        self.assertEqual(live.LIVE_FRESHNESS_SEC, 600.0)   # metin "10 dakika" diyor
        self.assertEqual(live.CACHE_TTL, 120.0)            # metin "2 dakika" diyor
        self.assertIn('/api/oauth/usage', live.USAGE_URL)
        en, tr = oku('README.md'), oku('README.tr.md')
        for metin, on_dk, iki_dk in ((en, '10 minutes', '2 minutes'),
                                     (tr, '10 dakika', '2 dakika')):
            self.assertIn('api.anthropic.com/api/oauth/usage', metin)
            self.assertIn(on_dk, metin)
            self.assertIn(iki_dk, metin)
            self.assertIn(f'User-Agent: {live.UA}', metin)   # istemci kimliği açıkça yazılı
            self.assertIn(f'anthropic-beta: {live.BETA}', metin)


class KurulumEkranlariAyristirilir(unittest.TestCase):
    """Metin düzeltmesi tırnak kaçışını bozarsa sihirbaz sayfası hiç açılmaz (G-g79loy'da
    `Claude Code'u` kaçışsız kaldı, 712 test yeşilken `node --check` yakaladı)."""

    def test_js_sozdizimi(self):
        import shutil
        import subprocess
        node = shutil.which('node')
        if not node:
            self.skipTest('node yok')
        for rel in ('web/setup.js', 'web/wizard.js', 'web/app.js'):
            with self.subTest(dosya=rel):
                r = subprocess.run([node, '--check', str(ROOT / rel)], capture_output=True,
                                   text=True, encoding='utf-8', errors='replace', timeout=60)
                self.assertEqual(r.returncode, 0, r.stderr[-400:])


class YayinNotlari(unittest.TestCase):
    def test_kaldirma_sirasi_iki_readme_de(self):
        self.assertRegex(oku('README.md'), r'setup --uninstall`\s+\*\*before\*\*\s+`pipx uninstall')
        self.assertRegex(oku('README.tr.md'), r'setup --uninstall`, \*\*sonra\*\* `pipx uninstall')

    def test_models_dev_lisansi_pakette_ve_atifli(self):
        lic = ROOT / 'data' / 'MODELS_DEV_LICENSE'
        self.assertTrue(lic.is_file())
        self.assertIn('Copyright (c) 2025 models.dev', lic.read_text(encoding='utf-8'))
        for rel in ('README.md', 'README.tr.md'):
            self.assertIn('data/MODELS_DEV_LICENSE', oku(rel))
        # wheel `data/`'yı bütün olarak taşır, sdist `graft data` ile
        self.assertIn("'data'", oku('setup.py'))
        self.assertIn('graft data', oku('MANIFEST.in'))

    def test_pkgbuild_ic_yol_tasimaz(self):
        for rel in ('packaging/aur/PKGBUILD', 'packaging/aur/PKGBUILD-git'):
            self.assertNotIn('reports/', oku(rel))

    def test_pipx_satiri_surume_sabit(self):
        import server
        for rel in ('README.md', 'README.tr.md'):
            satirlar = [s for s in oku(rel).splitlines() if s.startswith('pipx install git+')]
            self.assertTrue(satirlar, rel)
            for s in satirlar:
                # Etiket atılmadan main'deki satır sürümsüz kalır (yoksa 'ref yok' hatası);
                # sürüme sabitlenmişse yalnız bu sürüme sabitlenebilir.
                self.assertRegex(s, r'github\.com/ihsandeniz/usagelens\.git(@v[0-9.]+)? ', rel)
                m = re.search(r'usagelens\.git@v([0-9.]+) ', s)
                if m:
                    self.assertEqual(m.group(1), server.VERSION, rel)

    def test_deneysel_listesi_belgeyle_ayni(self):
        from usage.providers import EXPERIMENTAL
        # Aider ve Continue: adaptörlerin kendi başlığı "alan adları ADAY — canlı doğrulanacak"
        # diyor; gerçek bir kurulumda doğrulanmadan ana listede durmasınlar.
        self.assertEqual(len(EXPERIMENTAL), 9)
        adlar = {'deepseek': 'DeepSeek', 'novita': 'Novita', 'deepinfra': 'DeepInfra',
                 'huggingface': 'Hugging Face', 'together': 'Together', 'cody': 'Cody',
                 'windsurf': 'Windsurf', 'aider': 'Aider', 'continue': 'Continue'}
        self.assertEqual(set(adlar), set(EXPERIMENTAL))
        for rel in ('README.md', 'README.tr.md', 'docs/GUIDE.md'):
            metin = oku(rel)
            for ad in adlar.values():
                with self.subTest(dosya=rel, ad=ad):
                    self.assertIn(ad, metin)


    def test_deneysel_adlar_ana_listede_degil(self):
        """Belgedeki 'doğrulanmış' bölüm (deneysel parantezinden önceki kısım) deneysel bir
        adaptörü saymamalı — eskiden Aider ve Continue orada duruyordu."""
        for rel, ayrac in (('README.tr.md', '**deneysel**'), ('docs/GUIDE.md', 'experimental ones')):
            satir = next(s for s in oku(rel).splitlines() if '16 ad' in s)
            ana = satir.split(ayrac, 1)[0]
            for ad in ('Aider', 'Continue', 'Cody', 'Windsurf', 'DeepSeek'):
                with self.subTest(dosya=rel, ad=ad):
                    self.assertNotIn(ad, ana)

    def test_aider_ve_continue_kartlari_deneysel(self):
        import json, tempfile
        from pathlib import Path
        from unittest import mock
        from usage import providers
        from usage.providers import aider, continuedev
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / 'analytics.jsonl'
            log.write_text(json.dumps({'event': 'message_send', 'time': 1_900_000_000,
                                       'properties': {'total_tokens_sent': 10,
                                                      'total_tokens_received': 5,
                                                      'model': 'm'}}) + '\n', encoding='utf-8')
            dev = Path(td) / 'dev_data'
            dev.mkdir()
            (dev / 'tokens_generated.jsonl').write_text(json.dumps(
                {'model': 'm', 'promptTokens': 3, 'generatedTokens': 4}) + '\n', encoding='utf-8')
            with mock.patch.object(aider, 'LOG_PATH', log), mock.patch.object(aider, '_CACHE', None), \
                 mock.patch.object(continuedev, 'DATA_DIR', dev), \
                 mock.patch.object(continuedev, '_CACHE', None):
                kartlar = providers.collect(30, only=['aider', 'continue'])
        self.assertEqual(sorted(k['id'] for k in kartlar), ['aider', 'continue'])
        for k in kartlar:
            self.assertIs(k.get('experimental'), True, k['id'])


    def test_demo_kartlari_deneysel_listeyi_izler(self):
        """Demo kartları elle yazılıyor; Aider rozetsiz kalmış, demo ekranı onu doğrulanmış
        gibi gösteriyordu (ikinci göz bulgu 3). Rozet tek listeden gelmeli."""
        from usage import demo
        from usage.providers import EXPERIMENTAL
        kartlar = demo.collect(30)
        self.assertIn('aider', [k['id'] for k in kartlar])
        for k in kartlar:
            self.assertIs(bool(k.get('experimental')), k['id'] in EXPERIMENTAL, k['id'])

    def test_changelog_ad_degisikligini_yaziyor(self):
        """`--version` çıktısı `usage-tracker X` → `usagelens X` oldu; kullanıcının görebileceği
        bir değişiklik, yayımlanmamış bölümde yazılı olmalı (ikinci göz bulgu 4)."""
        metin = oku('CHANGELOG.md')
        bas = metin.index('## Unreleased')
        bolum = metin[bas:metin.index('\n## ', bas + 1)]
        for parca in ('--version', '--help', 'usagelens X.Y.Z', 'usage-tracker X.Y.Z'):
            self.assertIn(parca, bolum)

    def test_readme_linux_ikilisini_ve_dogrulamayi_anlatir(self):
        """Yayında `usage-tracker-<sürüm>-linux-x64` + SHA256SUMS.txt var; README yalnız .exe'yi
        söylüyordu, Linux ikilisini ve nasıl doğrulanacağını hiç anmıyordu."""
        metin = oku('README.md')
        self.assertIn('usage-tracker-<version>-linux-x64', metin)
        self.assertIn('SHA256SUMS.txt', metin)
        self.assertIn('sha256sum -c SHA256SUMS.txt --ignore-missing', metin)


if __name__ == '__main__':
    unittest.main()
