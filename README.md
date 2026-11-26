# Reproducible Benchmarks & Evidence for Upstream `winit`, `gpu-allocator`, and `wgpu` PRs

Standalone, self-contained reproduction harnesses and raw isolated per-PR A/B benchmark results for four upstream contributions:

| Upstream PR / Issue | Harness | Isolated Raw Results & Summary |
|---|---|---|
| `rust-windowing/winit` [#4860](https://github.com/rust-windowing/winit/issues/4860) / PR [#4861](https://github.com/rust-windowing/winit/pull/4861) | [`winit-win32-stranding-repro/`](winit-win32-stranding-repro/) | [`results/winit-4861/summary.md`](results/winit-4861/summary.md) |
| `Traverse-Research/gpu-allocator` [#322](https://github.com/Traverse-Research/gpu-allocator/issues/322) / PR [#323](https://github.com/Traverse-Research/gpu-allocator/pull/323) | [`wgpu-mem-bench/`](wgpu-mem-bench/) | [`results/gpu-allocator-323/summary.md`](results/gpu-allocator-323/summary.md) |
| `gfx-rs/wgpu` PR [#11129](https://github.com/gfx-rs/wgpu/pull/11129) | [`wgpu-mem-bench/`](wgpu-mem-bench/) | [`results/wgpu-11129/summary.md`](results/wgpu-11129/summary.md) |
| `gfx-rs/wgpu` PR [#11130](https://github.com/gfx-rs/wgpu/pull/11130) | [`wgpu-mem-bench/`](wgpu-mem-bench/) | [`results/wgpu-11130/summary.md`](results/wgpu-11130/summary.md) |
| `gfx-rs/wgpu` [#9818](https://github.com/gfx-rs/wgpu/issues/9818) (`Performance` 32/16 experiment) | [`wgpu-mem-bench/`](wgpu-mem-bench/) | [`results/wgpu-9818/`](results/wgpu-9818/) |

## Test Environment

- **OS**: Windows 11 (`Microsoft Windows [Version 10.0.26300.10075]`)
- **CPU**: Intel Core Ultra 7 155H
- **GPU**: Intel Arc Integrated GPU (UMA; `DXGI_MEMORY_SEGMENT_GROUP_LOCAL` budget ~7.21 GiB, `NON_LOCAL` = 0; DX12 driver `31.0.101.5328`, Vulkan)
- **Toolchain**: `rustc 1.100.0`, `--release` builds
- **Methodology**: Every PR is benchmarked in complete isolation against its exact unmodified upstream base commit (no combined-patch attribution), executing one process at a time in alternating / reverse-interleaved `AB/BA` order (`N=5` or `N=10` trials per configuration).

## Hardware & Platform Limitations

- All local GPU measurements were collected on an Intel Arc **integrated (UMA)** GPU on Windows 11 and are not extrapolated to discrete GPUs (separate VRAM vs host BAR/ReBAR memory pools) or non-Intel drivers.
- The Metal code path in `Traverse-Research/gpu-allocator#323` was kept symmetric with D3D12/Vulkan and code-reviewed, but not compiled or benchmarked on macOS hardware locally.
