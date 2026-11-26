# winit-win32 Buffered-Event Stranding Reproduction & Stress Suite

Standalone Windows reproduction and stress benchmark for:
- Issue: https://github.com/rust-windowing/winit/issues/4860
- PR: https://github.com/rust-windowing/winit/pull/4861

## Running

Build in release mode on Windows:

```powershell
cargo build --release --bins
```

Run any of the 10 stranding scenarios (600 ms startup settle + 600 ms watchdog `WM_NULL`):

```powershell
foreach ($s in @(
  "redraw_window_event", "redraw_pump_all", "redraw_pump_wakeup_only",
  "about_to_wait_window_event", "about_to_wait_pump_all", "pump_events_redraw",
  "redraw_burst", "multi_window_redraw", "wait_until_redraw", "exit_during_redraw"
)) {
  .\target\release\winit-win32-stranding-repro.exe $s
}
```

Run the stress, idle-CPU, and edge-case modes:

```powershell
foreach ($m in @("stress", "idle_cpu", "exit_in_about_to_wait", "destroy_in_redraw", "redraw_in_buffered")) {
  .\target\release\stress.exe $m
}
```

Switch the `winit` / `winit-core` dependency in `Cargo.toml` between baseline (`b1a0534`) and PR #4861 (`fb3ee36`) to reproduce before/after behavior.
