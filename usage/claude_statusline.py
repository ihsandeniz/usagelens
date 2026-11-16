"""Claude Code status line step — the one setup step that makes live limits appear.

Claude Code hands every status line command the current limit percentages on stdin
(`rate_limits.five_hour` / `seven_day`). `surface/statusline.py` saves them, and the panel,
badge and CLI read them **without any network request**. Without this step the only other
source is `api/oauth/usage`, which rate-limits hard (a 429 can carry a ~45 min Retry-After),
so a fresh install showed `—` for the limit bars. This module installs that hook into
Claude Code's own `settings.json`.

Rules, same as every other setup step:
  · `preview` → the exact diff, before anything is written
  · `do`      → back up `settings.json`, then write; an existing `statusLine` is **wrapped**,
                not replaced: our hook records the limits, then runs the user's own command
                and prints *its* line, so the user's status line looks the same as before
  · `undo`    → restore the user's own `statusLine` (or remove ours). Refuses to touch a
                `statusLine` someone changed after us.

Never writes when `settings.json` is not valid JSON — it shows the snippet instead.
One body, two faces: `setup.sh` calls `python3 -m usage.claude_statusline <verb>` (stdout is
JSON only) and `usage/wizard.py` imports it.
"""
from __future__ import annotations

import difflib
import json
import os
import re
import sys
import time
from pathlib import Path

from . import platform as _paths

BAK_SUFFIX = '.bak-usage-tracker'
RECORD_NAME = 'statusline-original.json'
# Our command, whichever way it was installed. Used only when the record file is gone.
# Narrow on purpose (SEC-F002): our script always sits in `surface/`, our binary is named
# usagelens / usage-tracker. A personal `python3 ~/.claude/statusline.py` must NOT match.
_OURS_RE = re.compile(r'([\\/]surface[\\/]statusline\.py"?|'
                      r'(usage-tracker|usagelens)(\.exe)?"? statusline)( --wrap)?\s*$')
# Characters we refuse to put inside double quotes — they would change the command's meaning.
_UNSAFE = set('"$`\\\n') if os.name != 'nt' else set('"\n')


def claude_dir() -> Path:
    env = os.environ.get('CLAUDE_CONFIG_DIR')
    return Path(env).expanduser() if env else Path.home() / '.claude'


def settings_path() -> Path:
    return claude_dir() / 'settings.json'


def record_path() -> Path:
    return _paths.config_dir() / RECORD_NAME


def _quote(s: str) -> str | None:
    s = str(s)
    if any(c in _UNSAFE for c in s):
        return None
    return f'"{s}"'


def hook_command(wrap: bool = False) -> str | None:
    """The command Claude Code will run. None = the path can't be quoted safely."""
    if _paths.is_frozen():
        exe = _quote(sys.executable)
        base = f'{exe} statusline' if exe else None
    else:
        script = _paths.resource_dir() / 'surface' / 'statusline.py'
        if not script.is_file():  # source tree: surface/ sits next to usage/
            script = Path(__file__).resolve().parent.parent / 'surface' / 'statusline.py'
        py, sc = _quote(sys.executable or 'python3'), _quote(script)
        base = f'{py} {sc}' if py and sc else None
    if base is None:
        return None
    return base + (' --wrap' if wrap else '')


def _load_record() -> dict:
    try:
        d = json.loads(record_path().read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _indent_of(text: str) -> int:
    for line in text.splitlines()[1:]:
        stripped = line.lstrip(' ')
        if stripped and len(stripped) < len(line):
            return len(line) - len(stripped)
    return 2


def _dump(data: dict, indent: int) -> str:
    return json.dumps(data, indent=indent, ensure_ascii=False) + '\n'


def _read_settings():
    """→ (text or None, data or None, error or None)."""
    p = settings_path()
    if not p.exists():
        return None, {}, None
    try:
        text = p.read_text(encoding='utf-8')
    except OSError as exc:
        return None, None, f'cannot read {p}: {exc}'
    if not text.strip():
        return text, {}, None
    try:
        data = json.loads(text)
    except ValueError as exc:
        return text, None, f'{p} is not valid JSON ({exc}) — not touching it'
    if not isinstance(data, dict):
        return text, None, f'{p} is not a JSON object — not touching it'
    return text, data, None


def is_ours(command) -> bool:
    if not isinstance(command, str):
        return False
    rec = _load_record()
    if rec.get('ours') and command == rec['ours']:
        return True
    return bool(_OURS_RE.search(command)) and 'statusline' in command


def _current(data: dict):
    sl = (data or {}).get('statusLine')
    return sl if isinstance(sl, dict) else None


def probe() -> dict:
    text, data, err = _read_settings()
    sl = _current(data) if data is not None else None
    cmd = (sl or {}).get('command')
    if err:
        state = 'invalid'
    elif not claude_dir().is_dir():
        state = 'no-claude'
    elif sl is None:
        state = 'absent'
    elif is_ours(cmd):
        state = 'present'
    elif isinstance(cmd, str) and cmd.strip():
        state = 'other'            # the user's own status line — we will wrap it
    else:
        state = 'manual'
    return {'settings': str(settings_path()), 'state': state, 'installed': state == 'present',
            'wrapped': state == 'present' and (cmd or '').endswith('--wrap'),
            'current': cmd if isinstance(cmd, str) else None, 'error': err}


def _plan():
    """What `do` would write → dict with before/after text, or an error/state."""
    text, data, err = _read_settings()
    if err:
        return {'state': 'invalid', 'error': err}
    if not claude_dir().is_dir():
        return {'state': 'no-claude',
                'error': f'{claude_dir()} not found — install Claude Code first '
                         '(spend still works without it; live limits need it)'}
    sl = _current(data)
    if sl is not None and is_ours(sl.get('command')):
        return {'state': 'present'}
    wrap = sl is not None
    if wrap and not (isinstance(sl.get('command'), str) and sl['command'].strip()):
        return {'state': 'manual', 'error': 'your statusLine has no command to wrap — '
                                            'add ours by hand (see snippet)'}
    cmd = hook_command(wrap=wrap)
    if cmd is None:
        return {'state': 'manual', 'error': 'install path contains characters that cannot be '
                                            'quoted safely — add the command by hand'}
    new = dict(data)
    entry = dict(sl) if wrap else {'type': 'command'}
    entry['type'] = 'command'
    entry['command'] = cmd
    new['statusLine'] = entry
    indent = _indent_of(text or '')
    before = text if text is not None else ''
    return {'state': 'other' if wrap else 'absent', 'wrap': wrap, 'command': cmd,
            'original': sl, 'before': before, 'after': _dump(new, indent)}


def snippet() -> list:
    cmd = hook_command() or 'python3 /path/to/usage-tracker/surface/statusline.py'
    return ['"statusLine": ' + json.dumps({'type': 'command', 'command': cmd}, ensure_ascii=False)]


def preview() -> dict:
    plan = _plan()
    out = {'target': str(settings_path()), 'state': plan['state']}
    if plan.get('error'):
        out['note'] = plan['error']
        out['snippet'] = snippet()
        out['lines'] = [plan['error'], ''] + out['snippet']
        return out
    if plan['state'] == 'present':
        out['note'] = 'already installed'
        out['lines'] = ['Already installed in ' + str(settings_path())]
        return out
    path = str(settings_path())
    out['diff'] = list(difflib.unified_diff(
        plan['before'].splitlines(), plan['after'].splitlines(),
        fromfile=path, tofile=path + ' (after)', lineterm=''))[2:]
    out['lines'] = [out['diff'] and f'{path}:' or path] + out['diff']
    out['wrap'] = plan['wrap']
    out['note'] = ('your own status line keeps working — ours records the limits, then runs '
                   'yours and shows its output' if plan['wrap'] else
                   'adds a status line that shows 5h/7d limit % and saves them for the panel')
    return out


def _backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    bak = path.with_name(path.name + BAK_SUFFIX)
    if bak.exists():
        bak = path.with_name(f'{path.name}{BAK_SUFFIX}.{int(time.time())}')
    bak.write_bytes(path.read_bytes())
    return bak


def do() -> dict:
    plan = _plan()
    if plan.get('error'):
        return {'ok': False, 'changed': False, 'state': plan['state'],
                'messages': [f'warn|{plan["error"]}'], 'snippet': snippet()}
    if plan['state'] == 'present':
        return {'ok': True, 'changed': False, 'state': 'present',
                'messages': ['ok|Claude Code status line already installed']}
    path = settings_path()
    bak = _backup(path)
    _paths.atomic_write_text(record_path(), json.dumps(
        {'settings': str(path), 'original': plan['original'], 'ours': plan['command'],
         'backup': str(bak) if bak else None, 'at': time.time()}, ensure_ascii=False, indent=2))
    _paths.atomic_write_text(path, plan['after'])
    msgs = [f'ok|status line added to {path}']
    if bak:
        msgs.append(f'info|backup: {bak}')
    if plan['wrap']:
        msgs.append('info|your previous status line is wrapped and keeps showing')
    msgs.append('info|live limit % appears after your next message in Claude Code')
    return {'ok': True, 'changed': True, 'state': 'present', 'messages': msgs,
            'backup': str(bak) if bak else None}


def undo() -> dict:
    text, data, err = _read_settings()
    if err:
        return {'ok': False, 'changed': False, 'messages': [f'warn|{err}']}
    sl = _current(data)
    if sl is None or not is_ours(sl.get('command')):
        return {'ok': True, 'changed': False,
                'messages': ['info|no usage-tracker status line in settings.json — nothing to undo']}
    rec = _load_record()
    rec_ours = rec.get('ours')
    if not rec_ours and sl.get('command') not in (hook_command(), hook_command(wrap=True)):
        # No record of what we wrote: the pattern alone is not proof enough to delete a line
        # (SEC-F002). Only this install's exact command is removed; anything else is left alone.
        return {'ok': False, 'changed': False,
                'messages': ['warn|no setup record and the status line is not this install\'s '
                             'exact command — not touching it; remove "statusLine" from '
                             f'{settings_path()} by hand if it is ours']}
    if rec_ours and sl.get('command') != rec_ours:
        return {'ok': False, 'changed': False,
                'messages': ['warn|the status line changed since setup wrote it — not touching it']}
    new = dict(data)
    original = rec.get('original')
    if isinstance(original, dict):
        new['statusLine'] = original
    else:
        new.pop('statusLine', None)
    path = settings_path()
    _backup(path)
    _paths.atomic_write_text(path, _dump(new, _indent_of(text or '')))
    try:
        record_path().unlink()
    except OSError:
        pass
    restored = 'your previous status line is back' if isinstance(original, dict) \
        else 'status line removed'
    return {'ok': True, 'changed': True, 'messages': [f'ok|{restored} ({path})']}


def wrapped_command() -> str | None:
    """The user's own status line command we wrapped (for `statusline.py --wrap`)."""
    orig = _load_record().get('original')
    cmd = orig.get('command') if isinstance(orig, dict) else None
    return cmd if isinstance(cmd, str) and cmd.strip() else None


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    verb = argv[0] if argv else 'probe'
    fn = {'probe': probe, 'preview': preview, 'do': do, 'undo': undo}.get(verb)
    if fn is None:
        print(json.dumps({'ok': False, 'error': f'unknown verb: {verb}'}))
        return 2
    out = fn()
    out.setdefault('ok', True)
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
