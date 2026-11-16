# Changelog

Release notes for 0.6.2 and earlier live on the
[GitHub releases page](https://github.com/ihsandeniz/usagelens/releases).

## 0.6.3

### Fixed

- **A manual limit reset now shows up.** When Anthropic lowers your usage inside the same
  week (for example after a limit reset) but keeps the same reset time, the status line
  record used to treat the lower number as stale and kept showing the old one (e.g. 98%
  instead of 14%). A large drop inside the same window (at least 10 points and to half or less,
  or down to 0) that is newer than what is stored is now accepted as a reset; readings taken
  before the reset can no longer bring the old number back that week. Small drops are still
  ignored as noise.
- **A stuck window no longer looks fresh.** The status line record's age is now taken from its
  oldest window, not the newest. If one window stops updating, the panel falls back to the
  usage endpoint instead of showing an old % as live.
- **Hidden provider cards send no requests.** A provider you hid in the panel is no longer
  polled in the background. It is queried only when you ask for everything explicitly
  (`usagelens providers --all`, `/v1/usage?all=1`). The settings screen still lists hidden
  providers so you can turn them back on.
- **`guard` no longer reports an expired window as OK.** If a window has expired and has no
  value, `guard` returns `unknown` (exit 3) instead of `ok` (exit 0), as the docs say. A known
  window over its threshold still wins (exit 1/2). Side effect: the waybar badge for Codex
  shows grey ("unknown") instead of green while Codex's 5-hour window is expired.
- **`setup --uninstall` leaves your own status line alone.** It removes only the command
  this install added; a status line script of your own that happens to be called
  `statusline.py` is no longer matched.
- **`start.sh` no longer runs the key file as shell code.** The env file is read line by
  line as `NAME=value` (optional `export `, one layer of quotes stripped); nothing in it is
  expanded or executed.
- **Floating widget toggle finds the window again.** `usage-widget toggle/close` recognise
  the 0.6.2 page title (`usagelens …`) as well as the older `usage-tracker` one.

### Build

- The package workflow compares the wizard steps in the built binaries with the source
  (`usage.wizard.steps()`) instead of a fixed count, and fails if a base step goes missing.
