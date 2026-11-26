# wgpu & gpu-allocator DX12/Vulkan Memory & Performance Benchmark

Standalone Windows DX12/Vulkan harness measuring:
- **Allocator-allocated & allocator-reserved bytes** (`Device::generate_allocator_report()`)
- **GPU video memory** (`IDXGIAdapter3::QueryVideoMemoryInfo` Local / Non-Local)
- **OS process memory** (`GetProcessMemoryInfo` `PrivateWorkingSetSize` and `PrivateUsage` commit charge)
- **Per-operation CPU latency & throughput** (`Instant`, warmup excluded)
- **Hardware GPU pass timestamps** (`Features::TIMESTAMP_QUERY` on `sustained_render` and `sustained_compute`)

Supports isolated A/B reproduction for:
- https://github.com/Traverse-Research/gpu-allocator/issues/322 & https://github.com/Traverse-Research/gpu-allocator/pull/323
- https://github.com/gfx-rs/wgpu/pull/11129
- https://github.com/gfx-rs/wgpu/pull/11130
- https://github.com/gfx-rs/wgpu/issues/9818

## Running

```powershell
cargo build --release
.\target
elease\wgpu-mem-bench.exe --backend dx12 --hints performance --workload idle --json out.json
```

Supported flags:
- `--backend`: `dx12` | `vulkan`
- `--hints`: `performance` | `memory_usage` | `manual-4-256` | `manual-8-256` | `manual-16-256` | `manual-32-256` | `manual-4-64`
- `--workload`: `idle` | `small_gui` | `repeated_uploads` | `multi_surface` | `churn` | `sustained_render` | `sustained_compute` | `large_textures` | `large_alloc`
