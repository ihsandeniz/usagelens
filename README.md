# usagelens

**Your Claude Code limits, spend and "what ate my limit" — on your own desktop, from files
already on your disk.** Formerly *usage-tracker* — the old GitHub address redirects here.

![badge → panel → Limit Black Box (demo data)](docs/demo.gif)

```bash
pipx install git+https://github.com/ihsandeniz/usagelens.git && usagelens setup
```

Needs Python 3.9+ (`python3 --version`); on older Pythons pipx stops with an unclear
"cannot determine package name" error.

`setup` walks you through each step and shows exactly what it will write before writing it
(every file is backed up; `usagelens setup --uninstall` undoes it). Then `usagelens panel`
opens the panel at `http://127.0.0.1:8770`. No account, no telemetry, loopback only,
stdlib Python — nothing to compile.

- **Live limits from your next Claude Code reply.** One setup step adds a Claude Code status line hook
  (yours keeps showing if you have one). Claude Code already receives your 5-hour and weekly
  % with every reply; the hook saves it, so while you use Claude Code no request is made.
  When the saved % is older than 10 minutes (Claude Code idle, or the hook not installed),
  usagelens asks Anthropic's usage endpoint itself: one GET to
  `api.anthropic.com/api/oauth/usage` with your local Claude Code login token, at most every
  2 minutes, waiting out any 429. The request identifies itself as Claude Code (`User-Agent: claude-cli/2.1.197 (external, cli)`, `anthropic-beta: oauth-2025-04-20`), not as usagelens. Nothing else is sent. There is no off switch yet; without a
  Claude Code login on the machine no request is made.
- **Real spend.** Token counts from your transcripts × real model prices: today, 30 days,
  per model. On a subscription that is the API-equivalent value, not your bill.
- **Where you look.** Web panel, waybar badge `◐ S13% W18%`, floating widget, tray icon,
  phone badge, and a CLI (`usagelens usage`, `guard`, `watch --notify`).

![the panel, limits first (demo data)](docs/screenshot.png)

## Limit Black Box — not the same as `/usage`

Claude Code's `/usage` shows how your *recent* usage splits across skills, sub-agents, MCP
servers and plugins. The Black Box records every move of the official limit % over whole
windows and tells you when one burned **about 2× faster than your usual** for the same work —
with anonymous evidence (`usagelens kanit`) you can paste into a bug report.

## Other ways to install

| | |
|---|---|
| From a clone (Linux) | `git clone https://github.com/ihsandeniz/usagelens && cd usagelens && ./setup.sh` — adds waybar, widget and tray steps; `./setup.sh --ui` for a browser window |
| Arch (AUR) | package `usagelens` — **not uploaded yet** |
| Windows | download the `.exe` from [Releases](https://github.com/ihsandeniz/usagelens/releases/latest) and double-click it → [docs/WINDOWS.md](docs/WINDOWS.md) |

`usage-tracker` still works as a command name.

To remove it, run `usagelens setup --uninstall` **before** `pipx uninstall usagelens` — it puts
your Claude Code status line back. Uninstalling first leaves Claude Code pointing at a deleted
program (your old line is still in `~/.claude/settings.json.bak-usage-tracker`).

## More

- **Full guide** — every surface, other desktops (GNOME, KDE, XFCE, polybar, i3blocks),
  provider keys, settings, HTTP endpoints, security: [docs/GUIDE.md](docs/GUIDE.md)
- CLI reference [docs/CLI.md](docs/CLI.md) · JSON contract [docs/WIRE.md](docs/WIRE.md) ·
  Türkçe [README.tr.md](README.tr.md)
- Inspired by [Pane](https://github.com/ItsJazii/pane), a Windows usage app — usagelens is a
  separate project, not affiliated.

MIT — see [LICENSE](LICENSE). The bundled price snapshot comes from
[models.dev](https://models.dev) (MIT, © 2025 models.dev) — see
[data/MODELS_DEV_LICENSE](data/MODELS_DEV_LICENSE).
