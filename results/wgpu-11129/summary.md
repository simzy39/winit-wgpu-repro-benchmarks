# `gfx-rs/wgpu#11129` Isolated A/B Results

- **Hardware/OS**: Windows 11 (`10.0.26300.10075`), Intel Core Ultra 7 155H, Intel Arc Integrated GPU (UMA, DX12 driver `31.0.101.5328`, Vulkan), `rustc 1.100.0`, `--release`
- **Baseline**: Unmodified `gfx-rs/wgpu` `trunk` @ `60cef2be` + unmodified `gpu-allocator 0.28.0`
- **PR #11129**: `simzy39:feat/lazy-default-external-texture-params` @ `793698d8` alone (no `#11130` or `#323`)
- **Methodology**: Strictly sequential, alternating single-process runs, `N=5` trials per cell.
- **Raw data**: [`raw/`](raw/) (100 JSON files)

| Backend / Hint / Workload (Stage) | Baseline Allocator (MiB) | #11129 Allocator (MiB) | Δ Allocator / DXGI Local | Baseline PrivWS (MiB) | #11129 PrivWS (MiB) | Δ PrivWS | Δ Process Commit |
|---|---:|---:|---:|---:|---:|---:|---:|
| `dx12` / `memory_usage` / `idle` (@dev) | 12.0 `[8, 4]` | 8.0 `[8]` | -4.0 / -4.0 MiB | 87.0 (86.8–87.1) | 83.0 (82.7–83.2) | -4.0 MiB | -4.5 MiB |
| `dx12` / `memory_usage` / `multi_surface` (@dev) | 12.0 `[8, 4]` | 8.0 `[8]` | -4.0 / -4.0 MiB | 87.6 (87.5–88.1) | 83.5 (83.2–83.8) | -4.1 MiB | -4.2 MiB |
| `dx12` / `memory_usage` / `multi_surface` (@peak) | 12.0 `[8, 4]` | 8.0 `[8]` | -4.0 / -0.5 MiB | 88.4 (88.3–88.8) | 88.9 (87.9–89.0) | +0.5 MiB | +0.9 MiB |
| `dx12` / `performance` / `idle` (@dev) | 192.0 `[128, 64]` | 128.0 `[128]` | -64.0 / -64.0 MiB | 267.9 (267.7–268.5) | 204.0 (203.8–204.3) | -63.9 MiB | -64.3 MiB |
| `dx12` / `performance` / `multi_surface` (@dev) | 192.0 `[128, 64]` | 128.0 `[128]` | -64.0 / -64.0 MiB | 268.5 (268.4–268.7) | 204.5 (204.3–204.7) | -64.0 MiB | -63.8 MiB |
| `dx12` / `performance` / `multi_surface` (@peak) | 192.0 `[128, 64]` | 128.0 `[128]` | -64.0 / -60.5 MiB | 269.4 (269.2–269.6) | 210.0 (209.7–210.0) | -59.4 MiB | -59.4 MiB |
| `dx12` / `performance` / `small_gui` (@dev) | 192.0 `[128, 64]` | 128.0 `[128]` | -64.0 / -64.0 MiB | 267.8 (267.8–268.2) | 203.9 (203.8–204.5) | -63.8 MiB | -63.4 MiB |
| `dx12` / `performance` / `small_gui` (@peak) | 192.0 `[128, 64]` | 192.0 `[128, 64]` | +0.0 / +0.0 MiB | 270.5 (270.4–271.2) | 270.4 (270.3–271.5) | -0.1 MiB | +0.2 MiB |
| `vulkan` / `memory_usage` / `idle` (@dev) | 12.0 `[8, 4]` | 8.0 `[8]` | -4.0 / -4.0 MiB | 18.8 (18.6–19.6) | 18.5 (18.5–18.6) | -0.2 MiB | -4.0 MiB |
| `vulkan` / `memory_usage` / `multi_surface` (@dev) | 12.0 `[8, 4]` | 8.0 `[8]` | -4.0 / -4.0 MiB | 20.2 (19.2–23.2) | 19.2 (19.1–19.2) | -1.1 MiB | -4.1 MiB |
| `vulkan` / `memory_usage` / `multi_surface` (@peak) | 12.0 `[8, 4]` | 8.0 `[8]` | -4.0 / -3.9 MiB | 45.7 (45.7–45.9) | 47.4 (47.3–47.5) | +1.7 MiB | +1.7 MiB |
| `vulkan` / `performance` / `idle` (@dev) | 144.0 `[128, 16]` | 128.0 `[128]` | -16.0 / -16.0 MiB | 139.5 (138.7–155.3) | 138.5 (138.5–139.2) | -1.0 MiB | -16.1 MiB |
| `vulkan` / `performance` / `multi_surface` (@dev) | 144.0 `[128, 16]` | 128.0 `[128]` | -16.0 / -16.0 MiB | 139.6 (139.2–141.1) | 139.1 (139.1–139.5) | -0.4 MiB | -16.3 MiB |
| `vulkan` / `performance` / `multi_surface` (@peak) | 144.0 `[128, 16]` | 128.0 `[128]` | -16.0 / -15.9 MiB | 177.8 (177.7–178.0) | 167.3 (167.3–167.6) | -10.4 MiB | -10.5 MiB |
| `vulkan` / `performance` / `small_gui` (@dev) | 144.0 `[128, 16]` | 128.0 `[128]` | -16.0 / -16.0 MiB | 138.7 (138.6–140.3) | 138.5 (138.4–138.6) | -0.1 MiB | -16.1 MiB |
| `vulkan` / `performance` / `small_gui` (@peak) | 144.0 `[128, 16]` | 144.0 `[128, 16]` | +0.0 / +0.0 MiB | 161.5 (161.5–162.0) | 161.5 (161.4–162.0) | +0.0 MiB | +0.1 MiB |
