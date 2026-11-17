"""The program answers to its current name, `usagelens`, and the old one keeps working.

0.6.3 printed `usage-tracker 0.6.3` for `usagelens --version`, and `--help` told a pipx
user to run `python3 server.py` — a file they do not have. The old command name stays a
working entry point; the wizard reads the version as the last word of `--version`, so an
installed 0.6.3 (`usage-tracker 0.6.3`) and a newer one (`usagelens 0.6.4`) both parse.
"""
import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import server
from usage import cli, wizard

ROOT = Path(__file__).resolve().parent.parent


def _run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = server.main(argv)
    return code, out.getvalue(), err.getvalue()


class VersionNameTest(unittest.TestCase):
    def test_version_line_uses_the_new_name(self):
        code, out, _ = _run_main(['--version'])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), f'usagelens {server.VERSION}')

    def test_short_flag_matches(self):
        self.assertEqual(_run_main(['-V'])[1], _run_main(['--version'])[1])

    def test_cli_parser_version_uses_the_new_name(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            cli.build_parser().parse_args(['--version'])
        self.assertEqual(out.getvalue().strip(), f'usagelens {cli.version()}')

    def test_cli_help_names_the_new_command(self):
        self.assertTrue(cli.build_parser().format_usage().startswith('usage: usagelens'))


class HelpTextTest(unittest.TestCase):
    def setUp(self):
        code, self.out, _ = _run_main(['--help'])
        self.assertEqual(code, 0)

    def test_help_leads_with_usagelens(self):
        self.assertTrue(self.out.startswith(f'usagelens {server.VERSION}'))
        for cmd in ('usagelens ', 'usagelens --no-open', 'usagelens setup', 'usagelens --version'):
            self.assertIn(cmd, self.out)

    def test_help_still_mentions_the_old_name_and_the_clone_form(self):
        self.assertIn('usage-tracker', self.out)
        self.assertIn('python3 server.py', self.out)



class StandaloneHelpTest(unittest.TestCase):
    """The Linux release file and the .exe have no `usagelens` on PATH (the wizard installs
    them as `usage-tracker`, wizard.py:installed_binary) — `--help` must not offer it."""

    def _help(self, argv0, windows):
        with mock.patch.object(server._paths, 'is_frozen', return_value=True), \
             mock.patch.object(server._paths, 'is_windows', return_value=windows), \
             mock.patch.object(server.sys, 'argv', [argv0, '--help']):
            code, out, _ = _run_main(['--help'])
        self.assertEqual(code, 0)
        return out

    def _command_lines(self, out):
        return [l for l in out.splitlines()[1:] if l.startswith('  ') and not l.startswith('  `')
                and 'USAGE_' not in l and l.strip()
                and not l.lstrip().startswith(('This is', 'command is'))]

    def test_linux_download_shows_the_file_itself(self):
        out = self._help('/home/u/Downloads/usage-tracker-0.6.4-linux-x64', windows=False)
        cmds = self._command_lines(out)
        self.assertEqual(len(cmds), 5, out)
        for line in cmds:
            self.assertTrue(line.startswith('  ./usage-tracker-0.6.4-linux-x64'), line)
        self.assertIn('./usage-tracker-0.6.4-linux-x64 setup', out)
        self.assertIn('installed\n  command is `usage-tracker`', out)

    def test_installed_linux_binary_shows_usage_tracker(self):
        out = self._help('/home/u/.local/bin/usage-tracker', windows=False)
        for line in self._command_lines(out):
            self.assertTrue(line.startswith('  usage-tracker'), line)

    def test_windows_exe_shows_its_name_without_exe(self):
        out = self._help(r'C:\Users\u\Downloads\usage-tracker-0.6.4-windows-x64.exe',
                         windows=True)
        self.assertIn('usage-tracker-0.6.4-windows-x64 setup', out)
        for line in self._command_lines(out):
            self.assertTrue(line.startswith('  usage-tracker-0.6.4-windows-x64'), line)
        self.assertNotIn('./', out)

    def test_no_standalone_help_line_offers_usagelens(self):
        for argv0, win in (('/tmp/usage-tracker-0.6.4-linux-x64', False),
                           ('/home/u/.local/bin/usage-tracker', False),
                           (r'C:\x\usage-tracker.exe', True)):
            with self.subTest(argv0=argv0):
                for line in self._command_lines(self._help(argv0, win)):
                    self.assertNotIn('usagelens', line)

    def test_pip_install_still_leads_with_usagelens(self):
        with mock.patch.object(server._paths, 'is_frozen', return_value=False):
            self.assertEqual(server.help_command('/x/bin/usage-tracker'), 'usagelens')

class OldNameStillWorksTest(unittest.TestCase):
    def test_both_console_scripts_point_at_the_same_entry(self):
        text = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
        self.assertIn('usagelens = "server:main"', text)
        self.assertIn('usage-tracker = "server:main"', text)

    def test_unknown_command_names_the_program(self):
        code, _, err = _run_main(['gaurd'])
        self.assertEqual(code, 64)
        self.assertTrue(err.startswith('usagelens: unknown command'))


class WizardParsesBothVersionLinesTest(unittest.TestCase):
    """An installed 0.6.3 answers `usage-tracker 0.6.3`; a newer one `usagelens x.y.z`."""

    def _installed_version(self, stdout):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / 'usage-tracker'
            target.write_text('binary', encoding='utf-8')
            done = subprocess.CompletedProcess(args=[str(target), '--version'], returncode=0,
                                               stdout=stdout, stderr='')
            with mock.patch.object(wizard, 'installed_binary', return_value=target), \
                 mock.patch.object(wizard.subprocess, 'run', return_value=done):
                return wizard.installed_version()

    def test_old_line(self):
        self.assertEqual(self._installed_version('usage-tracker 0.6.3\n'), '0.6.3')

    def test_new_line(self):
        self.assertEqual(self._installed_version(f'usagelens {server.VERSION}\n'),
                         server.VERSION)


if __name__ == '__main__':
    unittest.main()
