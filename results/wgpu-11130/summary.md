# `gfx-rs/wgpu#11130` Isolated A/B Results

- **Hardware/OS**: Windows 11 (`10.0.26300.10075`), Intel Core Ultra 7 155H, Intel Arc Integrated GPU (UMA, DX12 driver `31.0.101.5328`), `rustc 1.100.0`, `--release`
- **Baseline**: Unmodified `gfx-rs/wgpu` `trunk` @ `60cef2be` + unmodified `gpu-allocator 0.28.0`
- **PR #11130**: `simzy39:feat/dx12-transient-memory-pool` @ `22827ee2` alone (no `#11129` or `#323`)
- **Methodology**: Strictly sequential, alternating single-process runs (`N=5` across all 11 DX12 cells, plus `N=10` reverse-interleaved `AB/BA` on `repeated_uploads` and `small_gui` to average out Intel iGPU DVFS clock-state flips).
- **Raw data**: [`raw/`](raw/) (110 JSON files), [`raw-abba10/`](raw-abba10/) (40 JSON files)

## DX12 `Performance` & `MemoryUsage` Isolated A/B (`N=5`, except `*` = `AB/BA N=10`)

| Hint / Workload | Samples/Run | Baseline Allocator / PrivWS (MiB) | #11130 Allocator / PrivWS (MiB) | Δ Memory | Baseline CPU `p50` (min–max) | #11130 CPU `p50` (min–max) | GPU Pass `p50` Base vs #11130 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `memory_usage` / `idle` | — | 12.0 `[8, 4]` / 86.9 (86.8–87.3) | 12.0 `[8, 4]` / 87.1 (86.9–87.6) | +0.0 / +0.1 MiB | — | — | — |
| `memory_usage` / `small_gui` | 180 | 28.0 `[16, 8, 4]` / 105.7 (105.6–105.8) | 28.0 `[16, 8, 4]` / 105.6 (105.6–105.8) | +0.0 / -0.0 MiB | 628.5 (527.9–638.1) us | 463.8 (444.8–601.9) us | — |
| `performance` / `churn` | 225 | 192.0 `[128, 64]` / 270.2 (270.1–270.2) | 144.0 `[128, 16]` / 222.1 (222.0–222.1) | -48.0 / -48.1 MiB | 4.6 (3.4–10.4) us | 4.5 (4.2–8.9) us | — |
| `performance` / `idle` | — | 192.0 `[128, 64]` / 268.1 (267.8–268.3) | 144.0 `[128, 16]` / 219.9 (219.7–220.5) | -48.0 / -48.2 MiB | — | — | — |
| `performance` / `large_alloc` | 5 | 1004.0 `[300, 256×2, 128, 64]` / 1088.4 (1088.3–1088.5) | 956.0 `[300, 256×2, 128, 16]` / 1040.5 (1040.4–1040.7) | -48.0 / -47.9 MiB | 36.89 (20.44–55.76) ms | 21.67 (19.34–34.73) ms | — |
| `performance` / `large_textures` | 20 | 448.0 `[256, 128, 64]` / 544.5 (544.4–544.6) | 400.0 `[256, 128, 16]` / 496.6 (496.5–496.6) | -48.0 / -47.9 MiB | 1.96 (1.89–2.14) ms | 2.05 (1.81–2.91) ms | — |
| `performance` / `multi_surface` | 30 | 192.0 `[128, 64]` / 269.4 (269.3–269.5) | 144.0 `[128, 16]` / 221.2 (221.1–221.5) | -48.0 / -48.2 MiB | 11.07 (11.04–11.13) ms | 11.13 (11.04–11.15) ms | — |
| `performance` / `repeated_uploads`* | 360 | 192.0 `[128, 64]` / 270.7 (270.6–270.9) | 144.0 `[128, 16]` / 222.7 (222.6–222.8) | -48.0 / -48.0 MiB | 256.3 (236.5–443.5) us | 257.5 (229.9–444.9) us | — |
| `performance` / `small_gui`* | 180 | 192.0 `[128, 64]` / 270.4 (270.3–270.5) | 144.0 `[128, 16]` / 222.4 (222.3–222.6) | -48.0 / -48.0 MiB | 479.5 (452.9–522.0) us | 469.6 (451.0–582.6) us | — |
| `performance` / `sustained_compute` | 105 | 256.0 `[128, 64×2]` / 334.9 (334.8–336.0) | 208.0 `[128, 64, 16]` / 286.9 (286.9–288.2) | -48.0 / -48.0 MiB | 853.3 (834.6–925.3) us | 837.9 (816.3–853.4) us | 527.3 (519.2–530.9) vs 522.9 (520.4–527.3) us |
| `performance` / `sustained_render` | 225 | 256.0 `[128, 64×2]` / 334.2 (334.2–334.3) | 208.0 `[128, 64, 16]` / 286.4 (286.2–286.6) | -48.0 / -47.8 MiB | 3.93 (3.90–4.01) ms | 3.96 (3.90–4.02) ms | 3563.1 (3493.4–3615.4) vs 3567.0 (3493.9–3608.4) us |
