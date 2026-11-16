"""surface/statusline.py — oturumlar arası birleştirme: bayat oturum taze sayıyı ezmez."""
import importlib.util
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    'statusline', Path(__file__).resolve().parent.parent / 'surface' / 'statusline.py')
sl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sl)

NOW = 1_791_148_000.0
W5, W7 = NOW + 18_000, NOW + 280_000


def w(pct, reset):
    return {'used_percentage': pct, 'resets_at': reset}


class MergeTest(unittest.TestCase):
    def test_ayni_pencerede_buyuk_kalir(self):
        out = sl.merge({'seven_day': w(69.0, W7)}, {'seven_day': w(59.0, W7)}, NOW)
        self.assertEqual(out['seven_day']['used_percentage'], 69.0)
        out = sl.merge({'seven_day': w(59.0, W7)}, {'seven_day': w(70.0, W7 + 1)}, NOW)
        self.assertEqual(out['seven_day']['used_percentage'], 70.0)

    def test_eksik_pencere_mevcudu_silmez(self):
        out = sl.merge({'five_hour': w(12.0, W5), 'seven_day': w(69.0, W7)},
                       {'seven_day': w(69.0, W7)}, NOW)
        self.assertEqual(out['five_hour']['used_percentage'], 12.0)

    def test_eski_penceredeki_bayat_kayit_yok_sayilir(self):
        out = sl.merge({'five_hour': w(3.0, W5)}, {'five_hour': w(80.0, W5 - 18_000)}, NOW)
        self.assertEqual(out['five_hour']['used_percentage'], 3.0)

    def test_yeni_pencere_dusuk_yuzdeyle_gecer(self):
        out = sl.merge({'five_hour': w(90.0, NOW + 60)}, {'five_hour': w(0.0, W5)}, NOW)
        self.assertEqual(out['five_hour']['used_percentage'], 0.0)

    def test_suresi_dolmus_kayit_atilir(self):
        out = sl.merge({'five_hour': w(90.0, NOW - 10), 'seven_day': w(69.0, W7)},
                       {'seven_day': w(69.0, W7)}, NOW)
        self.assertNotIn('five_hour', out)

    def test_bozuk_eski_kayit(self):
        out = sl.merge({'five_hour': 'x', 'seven_day': {'used_percentage': None}},
                       {'five_hour': w(1.0, W5)}, NOW)
        self.assertEqual(out, {'five_hour': w(1.0, W5)})


    def test_suresi_dolmus_gelen_kabul_edilmez(self):
        """F003: sıfırlanmadan sonra boşta oturum eski %95'i geçmiş resets_at ile getirir."""
        self.assertEqual(sl.merge({}, {'five_hour': w(95.0, NOW - 3000)}, NOW), {})
        out = sl.merge({'five_hour': w(2.0, W5)}, {'five_hour': w(95.0, NOW - 3000)}, NOW)
        self.assertEqual(out['five_hour']['used_percentage'], 2.0)

    def test_esit_yuzdede_yeni_gozlem_kalir(self):
        o, n = dict(w(40.0, W7), at=NOW - 900), dict(w(40.0, W7), at=NOW - 5)
        self.assertEqual(sl.merge({'seven_day': o}, {'seven_day': n}, NOW)['seven_day']['at'], NOW - 5)
        self.assertEqual(sl.merge({'seven_day': n}, {'seven_day': o}, NOW)['seven_day']['at'], NOW - 5)


class GozlemAniTest(unittest.TestCase):
    """F004: kayıt zamanı yazım anı değil, verinin gözlendiği an."""

    def test_bosta_oturum_eski_zaman_getirir(self):
        import os, tempfile
        with tempfile.NamedTemporaryFile() as f:
            os.utime(f.name, (NOW - 3600, NOW - 3600))
            self.assertEqual(sl.gozlem_ani({'transcript_path': f.name}, NOW), NOW - 3600)

    def test_transcript_yoksa_simdi(self):
        self.assertEqual(sl.gozlem_ani({}, NOW), NOW)
        self.assertEqual(sl.gozlem_ani({'transcript_path': '/yok/boyle/bir/dosya'}, NOW), NOW)

    def test_uctan_uca_bosta_oturum_kaydi_bayat_kalir(self):
        import io, json, os, tempfile
        from unittest import mock
        from usage import live
        with tempfile.TemporaryDirectory() as td, tempfile.NamedTemporaryFile() as tp:
            eski = time_now() - 3600
            os.utime(tp.name, (eski, eski))
            payload = {'transcript_path': tp.name, 'rate_limits': {
                'five_hour': {'used_percentage': 40, 'resets_at': time_now() + 9000}}}
            with mock.patch('usage.platform.state_dir', return_value=Path(td)), \
                    mock.patch('sys.stdin', io.StringIO(json.dumps(payload))), \
                    mock.patch('sys.stdout', io.StringIO()):
                sl.main()
                at, _ = live._load_statusline()
            self.assertAlmostEqual(at, eski, delta=1)
            self.assertGreater(time_now() - at, live.LIVE_FRESHNESS_SEC)


class CompactHedefTest(unittest.TestCase):
    def test_override_yoksa_tampon(self):
        """F006: override'sız compact %95'te değil, pencere - ~33k'da."""
        from unittest import mock
        with mock.patch.dict('os.environ', {}, clear=True):
            self.assertEqual(sl.compact_hedef(200_000), 167_000)
            self.assertEqual(sl.compact_hedef(1_000_000), 967_000)

    def test_override(self):
        from unittest import mock
        with mock.patch.dict('os.environ', {'CLAUDE_AUTOCOMPACT_PCT_OVERRIDE': '55'}):
            self.assertEqual(sl.compact_hedef(1_000_000), 550_000)
        for bozuk in ('nan', 'inf', '0', '150', 'x'):
            with mock.patch.dict('os.environ', {'CLAUDE_AUTOCOMPACT_PCT_OVERRIDE': bozuk}):
                self.assertEqual(sl.compact_hedef(200_000), 167_000, bozuk)


class BudaTest(unittest.TestCase):
    def test_eski_gecmis_dosyalari_silinir(self):
        """F009: oturum başı dosyalar sınırsız birikiyordu."""
        import os, tempfile
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            for ad, yas in (('statusline-ctx-eski.json', 8 * 86400), ('statusline-ctx-yeni.json', 60),
                            ('statusline-limits.json', 30 * 86400)):
                (d / ad).write_text('[]', encoding='utf-8')
                os.utime(d / ad, (NOW - yas, NOW - yas))
            sl.buda(d, NOW)
            self.assertEqual(sorted(p.name for p in d.iterdir()),
                             ['statusline-ctx-yeni.json', 'statusline-limits.json'])


class ElleSifirlamaTest(unittest.TestCase):
    """G-gb59vs: haftalık limit ELLE sıfırlandı; pencere (resets_at) aynı kaldı, yüzde 98→14 düştü.
    'Aynı pencerede yüzde yalnız artar' kuralı %14'ü reddedip %98'i günlerce tuttu."""

    def test_buyuk_dusus_yeni_gozlemse_kabul(self):
        o = dict(w(98.0, W7), at=NOW - 12 * 3600)
        n = dict(w(14.0, W7), at=NOW - 5)
        out = sl.merge({'seven_day': o}, {'seven_day': n}, NOW)
        self.assertEqual(out['seven_day']['used_percentage'], 14.0)

    def test_sifira_inis_kucuk_yuzdede_de_kabul(self):
        o = dict(w(15.0, W7), at=NOW - 3600)
        n = dict(w(0.0, W7), at=NOW - 5)
        self.assertEqual(sl.merge({'seven_day': o}, {'seven_day': n}, NOW)['seven_day']['used_percentage'], 0.0)

    def test_buyuk_dusus_eski_gozlemse_red(self):
        o = dict(w(98.0, W7), at=NOW - 5)
        n = dict(w(14.0, W7), at=NOW - 3600)
        self.assertEqual(sl.merge({'seven_day': o}, {'seven_day': n}, NOW)['seven_day']['used_percentage'], 98.0)

    def test_kucuk_dusus_gurultu_sayilir(self):
        o = dict(w(69.0, W7), at=NOW - 900)
        n = dict(w(59.0, W7), at=NOW - 5)
        self.assertEqual(sl.merge({'seven_day': o}, {'seven_day': n}, NOW)['seven_day']['used_percentage'], 69.0)

    def test_sifirlamadan_onceki_bayat_oturum_geri_getiremez(self):
        sifir = sl.merge({'seven_day': dict(w(98.0, W7), at=NOW - 7200)},
                         {'seven_day': dict(w(14.0, W7), at=NOW - 60)}, NOW)
        bayat = {'seven_day': dict(w(98.0, W7), at=NOW - 3600)}   # sıfırlamadan önce gözlenmiş
        out = sl.merge(sifir, bayat, NOW)
        self.assertEqual(out['seven_day']['used_percentage'], 14.0)
        # sıfırlamadan SONRA gözlenen artış normal kurala döner
        out = sl.merge(out, {'seven_day': dict(w(16.0, W7), at=NOW - 10)}, NOW)
        self.assertEqual(out['seven_day']['used_percentage'], 16.0)


class KayitTazeligiTest(unittest.TestCase):
    """G-gb59vs: dosyanın üst `at`'i en taze pencereden geliyordu; 12 saattir güncellenmeyen
    seven_day, five_hour taze diye 'live:true stale:false' görünüyordu."""

    def _yaz(self, td, d):
        import json
        (Path(td) / 'statusline-limits.json').write_text(json.dumps(d), encoding='utf-8')

    def test_tazelik_en_eski_pencereden(self):
        import tempfile
        from unittest import mock
        from usage import live
        t = time_now()
        with tempfile.TemporaryDirectory() as td:
            self._yaz(td, {'at': t, 'windows': {
                'five_hour': {'used_percentage': 10.0, 'resets_at': t + 9000, 'at': t},
                'seven_day': {'used_percentage': 98.0, 'resets_at': t + 200000, 'at': t - 12 * 3600}}})
            with mock.patch('usage.platform.state_dir', return_value=Path(td)):
                at, _ = live._load_statusline()
        self.assertAlmostEqual(at, t - 12 * 3600, delta=1)

    def test_uctan_uca_sifirlama_kayda_gecer(self):
        import io, json, os, tempfile
        from unittest import mock
        from usage import live
        t = time_now()
        with tempfile.TemporaryDirectory() as td, tempfile.NamedTemporaryFile() as tp:
            self._yaz(td, {'at': t - 60, 'windows': {
                'five_hour': {'used_percentage': 9.0, 'resets_at': t + 9000, 'at': t - 60},
                'seven_day': {'used_percentage': 98.0, 'resets_at': t + 200000, 'at': t - 12 * 3600}}})
            payload = {'transcript_path': tp.name, 'rate_limits': {
                'five_hour': {'used_percentage': 10, 'resets_at': t + 9000},
                'seven_day': {'used_percentage': 14, 'resets_at': t + 200000}}}
            with mock.patch('usage.platform.state_dir', return_value=Path(td)), \
                    mock.patch('sys.stdin', io.StringIO(json.dumps(payload))), \
                    mock.patch('sys.stdout', io.StringIO()):
                sl.main()
                at, res = live._load_statusline()
        self.assertEqual(res['windows']['seven_day']['utilization'], 14.0)
        self.assertLess(time_now() - at, live.LIVE_FRESHNESS_SEC)


def time_now():
    import time
    return time.time()

if __name__ == '__main__':
    unittest.main()
