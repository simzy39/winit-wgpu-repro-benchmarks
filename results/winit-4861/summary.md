# `rust-windowing/winit#4861` Isolated A/B Results

- **Hardware/OS**: Windows 11 (`10.0.26300.10075`), Intel Core Ultra 7 155H, `rustc 1.100.0`, `--release`
- **Baseline**: `rust-windowing/winit` `master` @ `b1a05346` (post-`v0.31.0-beta.4`)
- **PR #4861**: `simzy39:fix/win32-buffered-event-stranding` @ `fb3ee36a`
- **Methodology**: Strictly sequential, alternating Before/After single-process runs; `N=5` trials per scenario (600 ms settle + 600 ms `WM_NULL` watchdog) and `N=3` trials per stress/idle/edge mode.
- **Raw data**: [`winit_ab.json`](winit_ab.json), [`v030-before-settled.txt`](v030-before-settled.txt)

## Scenarios (`N=5` alternating trials; median and min–max)

| Scenario | Before (`b1a0534`) | After (`fb3ee36`) |
|---|---|---|
| `redraw_window_event` | Stranded **5/5**, 607.68 (600.63–610.40) ms, `atw=2` | Stranded **0/5**, 0.72 (0.45–0.86) ms, `atw=1` |
| `redraw_pump_all` | Stranded **5/5**, 608.70 (607.89–610.42) ms, `atw=2` | Stranded **0/5**, 0.87 (0.85–1.11) ms, `atw=1` |
| `redraw_pump_wakeup_only` | Stranded **0/5**, 1.03 (0.88–1.21) ms, `atw=2` | Stranded **0/5**, 0.97 (0.70–1.30) ms, `atw=1` |
| `about_to_wait_window_event` | Stranded **0/5**, 0.82 (0.54–0.91) ms, `atw=1` | Stranded **0/5**, 0.67 (0.48–0.82) ms, `atw=1` |
| `about_to_wait_pump_all` | Stranded **5/5**, 607.55 (605.87–609.12) ms, `atw=1` | Stranded **0/5**, 1.29 (0.87–1.43) ms, `atw=1` |
| `pump_events_redraw` | 1st-pump: **0/5** (2 pumps) | 1st-pump: **5/5** (1 pump, 0.56 (0.39–0.72) ms) |
| `redraw_burst` | Stranded **5/5**, 608.66 (606.01–609.49) ms, `atw=2` | Stranded **0/5**, 11.96 (10.81–12.78) ms (all 50: 12.01 (10.86–12.82) ms), `atw=1` |
| `multi_window_redraw` | Stranded **5/5**, 607.60 (606.74–608.49) ms, `atw=2` | Stranded **0/5**, 0.80 (0.66–1.04) ms, `atw=1` |
| `wait_until_redraw` | Stranded **5/5**, 606.59 (600.64–609.59) ms, `atw=2` | Stranded **0/5**, 0.61 (0.56–0.69) ms, `atw=1` |
| `exit_during_redraw` | Stranded **0/5**, 0.54 (0.45–0.63) ms, `atw=1` | Stranded **0/5**, 0.63 (0.52–0.74) ms, `atw=1` |

## Stress, Idle CPU, and Edge Modes (`N=3` alternating trials)

| Mode | Before (`b1a0534`) | After (`fb3ee36`) |
|---|---|---|
| `stress` (100 cycles) | **3/3 hung** (>3,000 ms watchdog) | **3/3 passed (300/300 cycles)**, `spurious_about_to_wait=0`, `p50=135.6 us (132.1–141.7)`, `p90=327.3 us (264.5–362.8)`, `p99=921.8 us (598.1–1416.8)` |
| `redraw_in_buffered` | **3/3 hung** (>3,000 ms watchdog) | **3/3 passed**, `0.78 ms (0.58–0.94)` |
| `idle_cpu` (2,000 ms `WaitUntil`) | **3/3**: `0.000% CPU`, `non_timer_wakeups=0` | **3/3**: `0.000% CPU`, `non_timer_wakeups=0` |
| `destroy_in_redraw` | 3/3 passed, `1.28 ms (1.26–1.30)` | 3/3 passed, `0.91 ms (0.88–1.24)` |
| `exit_in_about_to_wait` (windowless startup) | 3/3 passed, `0.004 ms` | 3/3 passed, `0.005 ms (0.004–0.005)` |
