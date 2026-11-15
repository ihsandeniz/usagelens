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
                self.assertIn(f'usage-tracker.git@v{server.VERSION} ', s, rel)

    def test_deneysel_listesi_belgeyle_ayni(self):
        from usage.providers import EXPERIMENTAL
        self.assertEqual(len(EXPERIMENTAL), 7)
        adlar = {'deepseek': 'DeepSeek', 'novita': 'Novita', 'deepinfra': 'DeepInfra',
                 'huggingface': 'Hugging Face', 'together': 'Together', 'cody': 'Cody',
                 'windsurf': 'Windsurf'}
        self.assertEqual(set(adlar), set(EXPERIMENTAL))
        for rel in ('README.tr.md', 'docs/GUIDE.md'):
            metin = oku(rel)
            for ad in adlar.values():
                with self.subTest(dosya=rel, ad=ad):
                    self.assertIn(ad, metin)


if __name__ == '__main__':
    unittest.main()
