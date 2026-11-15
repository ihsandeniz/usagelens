"""Kurulum adımı `statusline` — Claude Code durum satırı → canlı limit ilk açılışta.

v0.6.2 değerlendirmesinin 1 numaralı kusuru: temiz kurulumda limit çubukları `—` kalıyordu,
çünkü sihirbaz limiti sağlayan durum satırını kurmuyordu ve yedek yol (`oauth/usage`) 429 +
~45 dk Retry-After veriyordu. Bu dosya adımın üç vaadini ölçer:

  S1  yazmadan önce gerçek diff (`preview` hiçbir şey yazmaz)
  S2  yazarken yedek; kullanıcının kendi statusLine'ı silinmez, SARILIR ve görünmeye devam eder
  S3  `undo` orijinali bayt-bayt geri getirir; bizden sonra değişmiş bir satıra dokunmaz

ve uçtan uca zinciri: settings.json'a yazılan komut, Claude Code'un verdiği stdin ile koşunca
panelin okuduğu kayıt oluşur ve `live.fetch()` ağa çıkmadan yüzdeyi verir.
"""
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from usage import claude_statusline as cs
from usage import wizard

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAYLOAD = {'rate_limits': {'five_hour': {'used_percentage': 12, 'resets_at': 4102444800},
                           'seven_day': {'used_percentage': 34, 'resets_at': 4102444800}}}


class _Sandbox(unittest.TestCase):
    def setUp(self):
        self.home = pathlib.Path(tempfile.mkdtemp(prefix='ut-sl-'))
        self.env = {'HOME': str(self.home), 'USERPROFILE': str(self.home),
                    'XDG_CONFIG_HOME': str(self.home / '.config'),
                    'XDG_STATE_HOME': str(self.home / '.state'),
                    'XDG_CACHE_HOME': str(self.home / '.cache'),
                    'APPDATA': str(self.home / 'AppData' / 'Roaming'),
                    'LOCALAPPDATA': str(self.home / 'AppData' / 'Local')}
        p = mock.patch.dict(os.environ, self.env)
        p.start()
        self.addCleanup(p.stop)
        os.environ.pop('CLAUDE_CONFIG_DIR', None)
        self.addCleanup(shutil.rmtree, self.home, True)
        self.claude = self.home / '.claude'
        self.settings = self.claude / 'settings.json'

    def write_settings(self, text):
        self.claude.mkdir(parents=True, exist_ok=True)
        self.settings.write_text(text, encoding='utf-8')

    def run_hook(self, payload, cmd=None):
        """settings.json'daki komutu Claude Code gibi koştur: stdin = JSON, kabuksuz."""
        cmd = cmd or json.loads(self.settings.read_text(encoding='utf-8'))['statusLine']['command']
        argv = [a.strip('"') for a in shlex.split(cmd, posix=os.name != 'nt')]
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        return subprocess.run(argv, input=json.dumps(payload), capture_output=True, text=True,
                              env=env, timeout=30)


class Probe(_Sandbox):
    def test_states(self):
        self.assertEqual(cs.probe()['state'], 'no-claude')
        self.claude.mkdir()
        self.assertEqual(cs.probe()['state'], 'absent')
        self.write_settings('{"statusLine": {"type": "command", "command": "echo hi"}}')
        self.assertEqual(cs.probe()['state'], 'other')
        self.write_settings('{ broken')
        self.assertEqual(cs.probe()['state'], 'invalid')

    def test_claude_config_dir_is_honoured(self):
        alt = self.home / 'alt'
        alt.mkdir()
        with mock.patch.dict(os.environ, {'CLAUDE_CONFIG_DIR': str(alt)}):
            self.assertEqual(cs.settings_path(), alt / 'settings.json')


class PreviewWritesNothing(_Sandbox):                                        # S1
    def test_preview_is_a_real_diff_and_writes_nothing(self):
        original = '{\n    "model": "opus"\n}\n'
        self.write_settings(original)
        out = cs.preview()
        self.assertEqual(out['state'], 'absent')
        self.assertTrue(any(l.startswith('+') and 'statusLine' in l for l in out['diff']),
                        out['diff'])
        self.assertEqual(self.settings.read_text(encoding='utf-8'), original)
        self.assertFalse(cs.record_path().exists())
        self.assertEqual(list(self.claude.iterdir()), [self.settings])

    def test_invalid_json_shows_snippet_never_writes(self):
        self.write_settings('{ "model": "opus", }')
        before = self.settings.read_bytes()
        self.assertIn('snippet', cs.preview())
        res = cs.do()
        self.assertFalse(res['ok'])
        self.assertEqual(self.settings.read_bytes(), before)

    def test_no_claude_dir_refuses_with_plain_reason(self):
        res = cs.do()
        self.assertFalse(res['ok'])
        self.assertIn('install Claude Code first', ' '.join(res['messages']))
        self.assertFalse(self.claude.exists())


class DoBacksUpAndWraps(_Sandbox):                                           # S2
    def test_fresh_settings_gets_hook_and_backup(self):
        original = '{\n    "model": "opus",\n    "env": {"A": "1"}\n}\n'
        self.write_settings(original)
        res = cs.do()
        self.assertTrue(res['ok'] and res['changed'], res)
        data = json.loads(self.settings.read_text(encoding='utf-8'))
        self.assertEqual(data['model'], 'opus')
        self.assertEqual(data['env'], {'A': '1'})
        self.assertEqual(data['statusLine']['type'], 'command')
        self.assertFalse(data['statusLine']['command'].endswith('--wrap'))
        self.assertIn('\n    "model"', self.settings.read_text(encoding='utf-8'))     # girinti korunur
        bak = self.settings.with_name('settings.json' + cs.BAK_SUFFIX)
        self.assertEqual(bak.read_text(encoding='utf-8'), original)
        self.assertEqual(cs.probe()['state'], 'present')

    def test_second_do_is_a_no_op(self):
        self.write_settings('{}')
        cs.do()
        after = self.settings.read_bytes()
        res = cs.do()
        self.assertFalse(res['changed'])
        self.assertEqual(self.settings.read_bytes(), after)
        self.assertEqual(len(list(self.claude.glob('settings.json.bak*'))), 1)

    def test_users_own_line_is_wrapped_and_still_shows(self):
        self.write_settings(json.dumps({'statusLine': {
            'type': 'command', 'command': 'echo MY-OWN-LINE', 'padding': 0}}))
        cs.do()
        sl = json.loads(self.settings.read_text(encoding='utf-8'))['statusLine']
        self.assertTrue(sl['command'].endswith('--wrap'))
        self.assertEqual(sl['padding'], 0)                            # diğer alanlar kalır
        proc = self.run_hook(PAYLOAD)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), 'MY-OWN-LINE')
        rec = json.loads((self.home / '.state' / 'usage-tracker' /
                          'statusline-limits.json').read_text(encoding='utf-8'))
        self.assertEqual(rec['windows']['five_hour']['used_percentage'], 12.0)

    def test_wrapped_command_failing_falls_back_to_our_line(self):
        self.write_settings(json.dumps({'statusLine': {'type': 'command', 'command': 'exit 3'}}))
        cs.do()
        proc = self.run_hook(PAYLOAD)
        self.assertEqual(proc.returncode, 0)
        self.assertIn('12', proc.stdout)


class UndoRestores(_Sandbox):                                                # S3
    def test_undo_restores_original_bytes(self):
        original = '{\n  "statusLine": {\n    "type": "command",\n    "command": "echo X"\n  }\n}\n'
        self.write_settings(original)
        cs.do()
        self.assertNotEqual(self.settings.read_text(encoding='utf-8'), original)
        res = cs.undo()
        self.assertTrue(res['changed'], res)
        self.assertEqual(self.settings.read_text(encoding='utf-8'), original)
        self.assertFalse(cs.record_path().exists())

    def test_undo_without_original_removes_only_our_key(self):
        self.write_settings('{\n  "model": "opus"\n}\n')
        cs.do()
        cs.undo()
        self.assertEqual(json.loads(self.settings.read_text(encoding='utf-8')), {'model': 'opus'})

    def test_undo_leaves_a_line_changed_after_us(self):
        self.write_settings('{}')
        cs.do()
        data = json.loads(self.settings.read_text(encoding='utf-8'))
        # hâlâ bizimki gibi görünüyor (aynı betik) ama yorumlayıcı değişmiş: kayıtla uyuşmaz
        data['statusLine']['command'] = data['statusLine']['command'].replace(
            json.dumps(sys.executable), '"/opt/other/python3"', 1)
        self.assertNotEqual(data['statusLine']['command'], cs.hook_command())
        self.assertTrue(cs._OURS_RE.search(data['statusLine']['command']))
        self.settings.write_text(json.dumps(data), encoding='utf-8')
        before = self.settings.read_bytes()
        res = cs.undo()
        self.assertFalse(res['changed'])
        self.assertEqual(self.settings.read_bytes(), before)

    def test_undo_never_touches_foreign_line(self):
        self.write_settings('{"statusLine": {"type": "command", "command": "echo mine"}}')
        before = self.settings.read_bytes()
        self.assertFalse(cs.undo()['changed'])
        self.assertEqual(self.settings.read_bytes(), before)

    def test_redo_after_undo_keeps_first_backup(self):
        original = '{"model": "first"}'
        self.write_settings(original)
        cs.do()
        cs.undo()
        cs.do()
        bak = self.settings.with_name('settings.json' + cs.BAK_SUFFIX)
        self.assertEqual(bak.read_text(encoding='utf-8'), original)


class FirstOpenShowsLimit(_Sandbox):
    """Uçtan uca: adım → Claude Code komutu koşar → panel ağsız yüzdeyi görür."""

    def test_live_fetch_uses_hook_record_without_network(self):
        from usage import live
        self.write_settings('{}')
        cs.do()
        proc = self.run_hook(PAYLOAD)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with mock.patch.object(live, '_fetch_raw', side_effect=AssertionError('network')), \
                mock.patch.object(live, '_CACHE', None):
            res = live.fetch()
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['source'], 'statusline')
        self.assertEqual(res['windows']['five_hour']['utilization'], 12.0)
        self.assertEqual(res['windows']['seven_day']['utilization'], 34.0)

    def test_cli_subcommand_is_the_same_hook(self):
        proc = subprocess.run([sys.executable, str(ROOT / 'server.py'), 'statusline'],
                              input=json.dumps(PAYLOAD), capture_output=True, text=True,
                              timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('12', proc.stdout)
        proc_en = subprocess.run([sys.executable, str(ROOT / 'server.py'), 'statusline'],
                                 input=json.dumps(PAYLOAD), capture_output=True, text=True,
                                 timeout=30, env=dict(os.environ, UT_LANG='en'))
        self.assertIn('5h 12%', proc_en.stdout)              # İngilizce: sayı önce, % sonra
        self.assertTrue((self.home / '.state' / 'usage-tracker' /
                         'statusline-limits.json').exists())


class WizardWiring(_Sandbox):
    def test_step_is_listed_and_auto_runs_it(self):
        self.assertIn('statusline', [s['id'] for s in wizard.steps()])
        self.assertIn('statusline', wizard.AUTO_STEPS)
        self.write_settings('{}')
        res = wizard.do('statusline')
        self.assertTrue(res['ok'], res)
        self.assertEqual(wizard.probe()['statusline']['state'], 'present')
        self.assertTrue(wizard.undo('statusline')['changed'])

    def test_setup_sh_machine_interface(self):
        if os.name == 'nt' or not shutil.which('bash'):
            self.skipTest('setup.sh is bash')
        self.write_settings('{}')
        env = dict(os.environ)

        def sh(*a):
            p = subprocess.run(['bash', str(ROOT / 'setup.sh'), *a], capture_output=True,
                               text=True, env=env, timeout=60)
            return json.loads(p.stdout)
        self.assertIn('statusline', sh('probe'))
        prev = sh('preview', 'statusline')
        self.assertTrue(any('statusLine' in l for l in prev['diff']))
        self.assertEqual(self.settings.read_text(encoding='utf-8'), '{}')
        self.assertTrue(sh('do', 'statusline')['changed'])
        self.assertEqual(sh('probe')['statusline']['state'], 'present')
        self.assertTrue(sh('undo', 'statusline')['changed'])
        self.assertEqual(json.loads(self.settings.read_text(encoding='utf-8')), {})


if __name__ == '__main__':
    unittest.main()


class ExperimentalProviders(unittest.TestCase):
    """v0.6.2: doğrulanmamış adaptörler `experimental` taşır; doğrulanmış olanlar taşımaz."""

    def test_only_the_unverified_cards_are_flagged(self):
        from usage import providers

        def fake(pid):
            m = mock.Mock()
            m.PROVIDER_ID = pid
            m.collect = lambda days: {'id': pid, 'name': pid, 'available': True, 'status': 'ok'}
            return m
        mods = tuple(fake(p) for p in ('openrouter', 'together', 'deepseek', 'ollama'))
        with mock.patch.object(providers, '_ADAPTERS', mods), \
                mock.patch.object(providers, '_collect_single',
                                  side_effect=lambda mod, days: mod.collect(days)):
            cards = {c['id']: c for c in providers.collect(1)}
        self.assertTrue(cards['together'].get('experimental'))
        self.assertTrue(cards['deepseek'].get('experimental'))
        self.assertNotIn('experimental', cards['openrouter'])
        self.assertNotIn('experimental', cards['ollama'])
