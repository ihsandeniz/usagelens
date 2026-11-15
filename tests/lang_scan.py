"""English-mode text scan — "a stranger on an English desktop sees no Turkish".

Runs every user-facing surface for real, in a throwaway HOME with a synthetic transcript and
`LANG=C.UTF-8` / no `UT_LANG`, and scans what a person would read:

  · CLI: usage · providers · guard · doctor · config · setup --help · --help
  · server start banner (what start.sh prints) and the HTTP JSON the panel renders
  · waybar feeder (server up, server down, curl/jq missing)
  · setup.sh: --help, probe messages, preview of each step

A hit is either a Turkish-only letter (ç ğ ı ö ş ü İ …) or a common Turkish word from a
short list. `python3 tests/lang_scan.py` prints hits; exit 1 if any. `tests/test_lang_scan.py`
runs it as a gate. Comments and docstrings are not scanned — only output.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TR_CHARS = re.compile(r'[çğıöşüÇĞİÖŞÜ]')
# Words that are Turkish and never English. Kept to whole-word, lowercase matches.
TR_WORDS = re.compile(r'\b(sunucu|yanıt|yanit|geçerli|gecerli|değil|degil|tahmini|canlı|canli|'
                      r'bugün|bugun|haftalık|haftalik|oturum|kalibrasyon|ayarlar|kaydet|hata|'
                      r'yok|var|ile|için|icin|olarak|veya|gömülü|gomulu|okunamadı|okunamadi|'
                      r'süresi|suresi|dolmuş|dolmus|kurulum|yedek|kaynak|harcama|limitler)\b',
                      re.IGNORECASE)
# Proper nouns / identifiers that may legitimately appear and contain a hit.
ALLOW = re.compile(r'(UT_LANG=tr|README\.tr\.md|Türkçe|lang=tr|"tr"|\btr\b)')


def free_port() -> int:
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def make_home() -> Path:
    home = Path(tempfile.mkdtemp(prefix='ut-lang-'))
    proj = home / '.claude' / 'projects' / 'demo'
    proj.mkdir(parents=True)
    now = time.time()
    with open(proj / 's1.jsonl', 'w', encoding='utf-8') as f:
        for i in range(20):
            ts = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(now - 300 * i))
            f.write(json.dumps({
                'type': 'assistant', 'sessionId': 's1', 'isSidechain': False,
                'requestId': f'r{i}', 'version': '2.1.300', 'timestamp': ts,
                'message': {'id': f'm{i}', 'model': 'claude-opus-5-5', 'role': 'assistant',
                            'usage': {'input_tokens': 100, 'output_tokens': 500,
                                      'cache_creation_input_tokens': 2000,
                                      'cache_read_input_tokens': 20000}}}) + '\n')
    return home


def env_for(home: Path, port: int, path=None) -> dict:
    """A clean environment built from scratch — never a copy of os.environ.

    Copying os.environ let other tests' leftovers in (a stub PATH, CLAUDE_CONFIG_DIR) and
    let the CLI find the developer's own server on :8770 — the scan then read a different
    program's output. USAGE_URL points at this run's port, which is dead until the scan
    starts its own server.
    """
    env = {'PATH': path or os.pathsep.join([os.path.dirname(sys.executable),
                                            '/usr/local/bin', '/usr/bin', '/bin']),
           'HOME': str(home), 'LANG': 'C.UTF-8', 'USAGE_PORT': str(port),
           'USAGE_URL': f'http://127.0.0.1:{port}',
           'XDG_CONFIG_HOME': str(home / '.config'), 'XDG_STATE_HOME': str(home / '.state'),
           'XDG_CACHE_HOME': str(home / '.cache'), 'XDG_DATA_HOME': str(home / '.data'),
           'XDG_RUNTIME_DIR': str(home / '.run'),
           'USAGE_CONTEXT_BREAKDOWN': '0', 'PYTHONUTF8': '1'}
    (home / '.run').mkdir(exist_ok=True)
    return env


def run(cmd, env, stdin=None, timeout=60) -> str:
    try:
        p = subprocess.run(cmd, cwd=ROOT, env=env, input=stdin, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=timeout)
        return (p.stdout or '') + (p.stderr or '')
    except subprocess.TimeoutExpired as exc:
        return f'TIMEOUT {exc}'


def strings_in(obj, path=''):
    """Every string a JSON response carries, with where it came from. Keys are skipped
    (identifiers), and so is raw provider data (`raw`)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ('raw',):
                continue
            yield from strings_in(v, f'{path}.{k}')
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from strings_in(v, f'{path}[{i}]')
    elif isinstance(obj, str):
        # Machine codes (`gozlem-yok`, `yerel-log`) are identifiers the panel maps to text,
        # not text: lowercase, no spaces. They stay as they are on purpose.
        if not re.fullmatch(r'[a-z0-9_.:-]+', obj):
            yield path, obj


def hits_in(label: str, text: str) -> list:
    out = []
    for line in text.splitlines():
        clean = ALLOW.sub('', line)
        if TR_CHARS.search(clean) or TR_WORDS.search(clean) or 'SCAN BROKEN' in clean:
            out.append(f'{label}: {line.strip()[:160]}')
    return out


def collect(home: Path) -> list:
    port = free_port()
    env = env_for(home, port)
    py = sys.executable
    srv = [py, str(ROOT / 'server.py')]
    hits = []

    for args in (['--help'], ['usage'], ['providers'], ['guard'], ['doctor'], ['config'],
                 ['setup', '--help'], ['usage', '--format', 'waybar']):
        hits += hits_in('cli ' + ' '.join(args), run(srv + args, env))

    # feeder with the server DOWN. USAGE_URL always set: without it the feeder reads
    # surface/surface.conf and would ask whatever runs on the developer's :8770.
    feeder = ['sh', str(ROOT / 'surface' / 'waybar-usage.sh')]
    down = dict(env, USAGE_URL=f'http://127.0.0.1:{free_port()}')
    out = run(feeder, down)
    if '"off"' not in out:
        out += '\nSCAN BROKEN: feeder did not take the offline path'
    hits += hits_in('waybar (server down)', out)

    # start the server the way start.sh does, capture its banner
    log = home / 'server.log'
    with open(log, 'w', encoding='utf-8') as fh:
        proc = subprocess.Popen(['bash', str(ROOT / 'start.sh')], cwd=ROOT, env=env,
                                stdout=fh, stderr=subprocess.STDOUT)
    try:
        base = f'http://127.0.0.1:{port}'
        for _ in range(100):
            try:
                urllib.request.urlopen(base + '/', timeout=1).read()
                break
            except Exception:
                time.sleep(0.2)
        time.sleep(0.5)
        hits += hits_in('start.sh banner', log.read_text(encoding='utf-8', errors='replace'))
        for ep in ('/api/usage', '/api/spend?days=30', '/api/providers', '/v1/usage',
                   '/api/limit-kutu', '/api/settings', '/api/view-config'):
            try:
                body = json.loads(urllib.request.urlopen(base + ep, timeout=30).read())
            except Exception as exc:
                hits.append(f'http {ep}: request failed: {exc}')
                continue
            for where, s in strings_in(body):
                for h in hits_in(f'http {ep}{where}', s):
                    hits.append(h)
        env['USAGE_URL'] = base
        hits += hits_in('waybar (server up)', run(feeder, env))
        # curl/jq missing: a PATH with only the basics
        stub = home / 'bin'
        stub.mkdir(exist_ok=True)
        for tool in ('sh', 'cat', 'date', 'printf', 'sed', 'awk', 'grep', 'tr', 'head',
                     'python3', 'dirname', 'readlink', 'basename', 'cut', 'mktemp', 'rm'):
            w = shutil.which(tool)
            if w and not (stub / tool).exists():
                (stub / tool).symlink_to(w)
        hits += hits_in('waybar (no curl/jq)', run(feeder, dict(env_for(home, port, str(stub)),
                                                                 USAGE_URL=base)))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    sh = ['bash', str(ROOT / 'setup.sh')]
    hits += hits_in('setup.sh --help', run(sh + ['--help'], env))
    probe = run(sh + ['probe'], env)
    try:
        for where, s in strings_in(json.loads(probe.split('\n{', 1)[-1] if not probe.startswith('{')
                                              else probe)):
            hits += hits_in(f'setup.sh probe{where}', s)
    except ValueError:
        hits += hits_in('setup.sh probe', probe)
    for step in ('server', 'waybar', 'widget', 'tray', 'keys', 'statusline'):
        hits += hits_in(f'setup.sh preview {step}', run(sh + ['preview', step], env))
    # The interactive install flow is NOT run here: it starts systemd --user units, and a
    # fake HOME does not isolate `systemctl --user`. It is scanned inside the containers.
    return hits


def main() -> int:
    home = make_home()
    try:
        hits = collect(home)
    finally:
        shutil.rmtree(home, ignore_errors=True)
    for h in hits:
        print(h)
    print(f'{len(hits)} Turkish hit(s) in English mode')
    return 1 if hits else 0


if __name__ == '__main__':
    sys.exit(main())
