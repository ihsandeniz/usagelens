"""usage/context.py — per-session context window breakdown.

Guards: (1) no percent before the window is measured (a 200k guess showed a 19 % session as
95 %), (2) the breakdown's drift since measurement goes to Messages / out of Free space,
(3) dead pids and <synthetic> usage lines are ignored, (4) nothing under ~/.claude is written.
"""
import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _usage_line(total, model='claude-opus-5-5', mid='m1'):
    return json.dumps({'type': 'assistant', 'timestamp': '2026-09-30T10:00:00Z',
                       'message': {'id': mid, 'model': model, 'usage': {
                           'input_tokens': 10, 'cache_read_input_tokens': total - 10,
                           'cache_creation_input_tokens': 0}}})


def _live_child(compact_pct=None):
    """A live process to stand in for the Claude Code session.

    `_compact_pct` reads the session's own environment first (/proc/<pid>/environ). Using the
    test runner's pid made the result depend on whoever runs the suite: inside Claude Code,
    CLAUDE_AUTOCOMPACT_PCT_OVERRIDE is set and wins over settings.json. The child gets an
    environment we control."""
    env = {k: v for k, v in os.environ.items() if k != 'CLAUDE_AUTOCOMPACT_PCT_OVERRIDE'}
    if compact_pct is not None:
        env['CLAUDE_AUTOCOMPACT_PCT_OVERRIDE'] = str(compact_pct)
    return subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'], env=env)


class ContextTest(unittest.TestCase):
    child_pct = None

    def setUp(self):
        self.child = _live_child(self.child_pct)
        self.addCleanup(self._stop_child)
        pid = self.child.pid
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        os.environ['CLAUDE_CONFIG_DIR'] = str(root)
        (root / 'sessions').mkdir()
        (root / 'projects' / 'proj').mkdir(parents=True)
        (root / 'settings.json').write_text(json.dumps({'env': {'CLAUDE_AUTOCOMPACT_PCT_OVERRIDE': '55'}}), encoding='utf-8')
        (root / 'sessions' / f'{pid}.json').write_text(json.dumps(
            {'pid': pid, 'sessionId': 'live', 'cwd': str(root), 'name': 'live-one', 'status': 'idle'}), encoding='utf-8')
        (root / 'sessions' / '999999.json').write_text(json.dumps(
            {'pid': 999999, 'sessionId': 'dead', 'cwd': str(root)}), encoding='utf-8')
        (root / 'projects' / 'proj' / 'live.jsonl').write_text('\n'.join([
            _usage_line(150_000, mid='a'),
            _usage_line(190_000, mid='b'),
            json.dumps({'type': 'assistant', 'message': {'model': '<synthetic>', 'usage': {'input_tokens': 0}}}),
        ]) + '\n', encoding='utf-8')
        self.root = root
        from usage import context
        self.ctx = importlib.reload(context)

    def _stop_child(self):
        self.child.kill()
        self.child.wait()

    def tearDown(self):
        os.environ.pop('CLAUDE_CONFIG_DIR', None)
        self.tmp.cleanup()

    def _drift_session(self):
        self.ctx._CACHE['live'] = {'at': 1e18, 'total': 180_000, 'error': None, 'data': {
            'model': 'claude-opus-5-5', 'window': 1_000_000, 'measured_total': 180_000,
            'categories': [{'name': 'Messages', 'tokens': 140_000, 'kind': 'used'},
                           {'name': 'Free space', 'tokens': 787_000, 'kind': 'free'}],
            'memory_files': [], 'skills': [], 'agents': [], 'mcp_tools': []}}
        return self.ctx.compute(breakdown=False)['sessions'][0]

    def test_dead_pid_skipped_and_last_real_usage_wins(self):
        r = self.ctx.compute(breakdown=False)
        self.assertEqual([s['session_id'] for s in r['sessions']], ['live'])
        self.assertEqual(r['sessions'][0]['total'], 190_000)

    def test_no_percent_before_window_is_measured(self):
        s = self.ctx.compute(breakdown=False)['sessions'][0]
        self.assertIsNone(s['window'])
        self.assertIsNone(s['percent'])
        self.assertIsNone(s['compact_at'])

    def test_drift_goes_to_messages(self):
        s = self._drift_session()
        cats = {c['name']: c['tokens'] for c in s['breakdown']['categories']}
        self.assertEqual(cats['Messages'], 150_000)
        self.assertEqual(cats['Free space'], 777_000)
        self.assertEqual(s['percent'], 19.0)
        self.assertEqual(s['compact_at'], 550_000)

    def test_read_only(self):
        before = sorted(p.name for p in self.root.rglob('*'))
        self.ctx.compute(breakdown=False)
        self.assertEqual(before, sorted(p.name for p in self.root.rglob('*')))


@unittest.skipUnless(Path('/proc/self/environ').exists(), 'session env is read from /proc')
class SessionEnvWinsTest(ContextTest):
    """The session's own CLAUDE_AUTOCOMPACT_PCT_OVERRIDE beats settings.json (55 there)."""
    child_pct = 80

    def test_drift_goes_to_messages(self):
        self.assertEqual(self._drift_session()['compact_at'], 800_000)


if __name__ == '__main__':
    unittest.main()
