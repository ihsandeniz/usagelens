"""v0.6.2 kurulum kusurları (değerlendirme 2026-11-15) — her biri bir kapı.

  K1  rozet curl/jq yokken "offline" diyordu → eksik aracı ve kurulum komutunu söylesin
  K2  önerilen paket adları dağıtıma göre yanlıştı (`apt install python-pyqt5`, `apt install python`)
  K3  Python < 3.9'da "too old" deyip `--auto` ile devam edip "setup verified" diyordu
  K4  panel canlı limit yokken nedenini söylemiyordu → `live.hint.code` → seçili dilde tek cümle
  K5  bash kurulumunda renk kodları boruya ham basılıyordu (install.sh)
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASH = shutil.which('bash')


def _fn(name):
    src = (ROOT / 'setup.sh').read_text(encoding='utf-8')
    m = re.search(r'^' + name + r'\(\) \{.*?^\}', src, re.M | re.S)
    assert m, name
    return m.group(0)


@unittest.skipIf(os.name == 'nt' or not BASH, 'bash')
class PaketAdlari(unittest.TestCase):                                         # K2
    CASES = {
        ('pyqt5', 'apt-get'): 'python3-pyqt5', ('pyqt5', 'pacman'): 'python-pyqt5',
        ('pyqt5', 'dnf'): 'python3-qt5', ('pyqt5', 'zypper'): 'python3-qt5',
        ('pyqt5', 'apk'): 'py3-qt5',
        ('python', 'apt-get'): 'python3', ('python', 'dnf'): 'python3',
        ('python', 'pacman'): 'python', ('python', 'apk'): 'python3',
        ('curl', 'apt-get'): 'curl', ('jq', 'dnf'): 'jq',
    }

    def test_each_distro_gets_its_real_name(self):
        for (logical, mgr), want in self.CASES.items():
            with self.subTest(logical=logical, mgr=mgr):
                out = subprocess.run([BASH, '-c', _fn('pkg_name') + f'\npkg_name {logical} {mgr}'],
                                     capture_output=True, text=True, timeout=10).stdout.strip()
                self.assertEqual(out, want)

    def test_no_caller_passes_a_distro_specific_name(self):
        src = (ROOT / 'setup.sh').read_text(encoding='utf-8')
        self.assertNotIn('pkg_hint python-pyqt5', src)


@unittest.skipIf(os.name == 'nt' or not BASH, 'bash')
class EskiPythonDurur(unittest.TestCase):                                     # K3
    def test_too_old_python_stops_with_exit_1(self):
        with tempfile.TemporaryDirectory() as td:
            stub = Path(td)
            py = stub / 'python3'
            py.write_text('#!/bin/sh\n'
                          'case "$*" in *exit*) exit 1;; *version_info*) echo 3.8;; esac\n',
                          encoding='utf-8')
            py.chmod(0o755)
            for tool in ('bash', 'sh', 'dirname', 'readlink', 'sed', 'cat', 'mktemp', 'rm',
                         'grep', 'tr', 'printf'):
                w = shutil.which(tool)
                if w:
                    (stub / tool).symlink_to(w)
            env = {'PATH': str(stub), 'HOME': td, 'XDG_CONFIG_HOME': td + '/c'}
            p = subprocess.run([str(stub / 'bash'), str(ROOT / 'setup.sh'), '--auto'],
                               capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn('needs Python 3.9 or newer', p.stdout + p.stderr)
        self.assertNotIn('setup verified', p.stdout + p.stderr)
        self.assertNotIn('Continue anyway', p.stdout + p.stderr)   # durdu: devam sorusu yok
        self.assertNotIn('install.sh', p.stdout + p.stderr)        # taban kurulum koşmadı


@unittest.skipIf(os.name == 'nt' or not BASH, 'bash')
class RozetEksikArac(unittest.TestCase):                                      # K1
    def _run(self, keep):
        with tempfile.TemporaryDirectory() as td:
            stub = Path(td)
            for tool in keep:
                w = shutil.which(tool)
                if w:
                    (stub / tool).symlink_to(w)
            env = {'PATH': str(stub), 'HOME': td, 'LANG': 'C.UTF-8',
                   'USAGE_URL': 'http://127.0.0.1:9'}
            p = subprocess.run([str(stub / 'bash'), str(ROOT / 'surface' / 'waybar-usage.sh')],
                               capture_output=True, text=True, env=env, timeout=30)
        return json.loads(p.stdout)

    BASE = ('bash', 'dirname', 'readlink', 'date', 'stat', 'tail', 'head', 'printf', 'mktemp')

    def test_missing_jq_is_named_not_offline(self):
        out = self._run(self.BASE + ('curl',))
        self.assertEqual(out['text'], '⚠ jq')
        self.assertIn('jq is not installed', out['tooltip'])
        self.assertNotIn('offline', out['tooltip'])

    def test_missing_curl_is_named(self):
        out = self._run(self.BASE + ('jq',))
        self.assertEqual(out['text'], '⚠ curl')

    def test_turkish_only_when_chosen(self):
        with tempfile.TemporaryDirectory() as td:
            stub = Path(td)
            for tool in self.BASE:
                w = shutil.which(tool)
                if w:
                    (stub / tool).symlink_to(w)
            env = {'PATH': str(stub), 'HOME': td, 'UT_LANG': 'tr'}
            p = subprocess.run([str(stub / 'bash'), str(ROOT / 'surface' / 'waybar-usage.sh')],
                               capture_output=True, text=True, env=env, timeout=30)
        self.assertIn('kurulu değil', json.loads(p.stdout)['tooltip'])


@unittest.skipUnless(shutil.which('node'), 'node')
class PanelIpucu(unittest.TestCase):                                          # K4
    APP = (ROOT / 'web' / 'app.js').read_text(encoding='utf-8')

    def _hint(self, live, lang='en', now=1_000_000):
        fn = re.search(r'^function limitHint\(.*?^\}', self.APP, re.M | re.S).group(0)
        i18n = re.search(r'^const I18N = \{.*?^\};', self.APP, re.M | re.S).group(0)
        js = (i18n.replace('const I18N', 'var I18N') + f"\nvar LANG='{lang}';"
              "\nvar t=(k)=>I18N[LANG]?.[k]??I18N.en?.[k]??k;\n" + fn
              + f"\nconsole.log(JSON.stringify(limitHint({{live:{json.dumps(live)}}}, {now})));")
        out = subprocess.run(['node', '-e', js], capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_no_hint_when_live_is_fine(self):
        self.assertEqual(self._hint({'ok': True, 'hint': {'code': None, 'text': None}}), '')

    def test_missing_step_says_what_to_do(self):
        self.assertIn('setup', self._hint({'hint': {'code': 'sl_missing'}}))

    def test_429_adds_the_wait_not_only_the_wait(self):
        h = self._hint({'rateLimited': True, 'retryAtMs': 1_000_000 + 45 * 60_000,
                        'hint': {'code': 'sl_missing'}})
        self.assertIn('~45 min', h)
        self.assertIn('setup', h)                    # çözüm kurulum adımı, beklemek değil

    def test_turkish_follows_the_panel_language(self):
        h = self._hint({'hint': {'code': 'sl_waiting'}}, lang='tr')
        self.assertIn('Durum satırı kurulu', h)


class MotorIpucu(unittest.TestCase):                                          # K4 (sunucu)
    def test_codes(self):
        from unittest import mock
        from usage import engine
        self.assertEqual(engine.live_hint({'ok': True})['code'], None)
        self.assertEqual(engine.live_hint({'ok': False, 'statusline': 'absent'})['code'],
                         'sl_missing')
        self.assertEqual(engine.live_hint({'ok': False, 'statusline': 'present'})['code'],
                         'sl_waiting')
        self.assertEqual(engine.live_hint({'ok': True, 'stale': True,
                                           'statusline': 'no-claude'})['code'], 'no_claude')
        with mock.patch('time.time', return_value=1000.0):
            h = engine.live_hint({'ok': False, 'statusline': 'absent', 'rateLimited': True,
                                  'retryAtMs': (1000 + 2700) * 1000})
        self.assertIn('~45 min', h['text'])


@unittest.skipIf(os.name == 'nt' or not BASH, 'bash')
class RenkYalnizTerminalde(unittest.TestCase):                                # K5
    def test_install_sh_prints_no_escape_codes_into_a_pipe(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / 'r'
            shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(
                '.git', '__pycache__', 'tests', 'docs', 'surface.conf'))
            env = dict(os.environ, HOME=td, XDG_CONFIG_HOME=td + '/c')
            env.pop('NO_COLOR', None)
            p = subprocess.run([BASH, str(repo / 'install.sh')], capture_output=True, text=True,
                               env=env, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('✓', p.stdout)
        self.assertNotIn('\x1b[', p.stdout)


if __name__ == '__main__':
    unittest.main()


class SihirbazDogrulamasi(unittest.TestCase):
    """Sihirbazın `verify` adımı doctor'u sahte bir argüman nesnesiyle çağırıyor; o nesnede
    `timeout` yoktu → sunucu ayaktayken bile "unreachable (AttributeError)"."""

    def test_verify_reports_a_real_reason(self):
        from unittest import mock
        from usage import wizard, cli
        with mock.patch.object(cli, 'fetch_http', side_effect=ConnectionRefusedError()):
            res = wizard._do_verify({})
        text = ' '.join(res['messages'])
        self.assertNotIn('AttributeError', text)
        self.assertIn('ConnectionRefusedError', text)
