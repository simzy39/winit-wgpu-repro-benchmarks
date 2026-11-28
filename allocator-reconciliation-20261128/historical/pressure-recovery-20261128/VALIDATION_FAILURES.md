# Final wgpu failures and controls

The geometric-policy full `cargo xtask test` run executes 2,207 tests: **2,184 pass,
23 fail/abort**, and 18 more tests are excluded by the default profile. JUnit records
zero skipped testcases; nextest's summary separately reports the profile exclusions.
The full command exits 1 (nextest exits 100). No failure name is new relative to the
historical failure set. The test-only dependency override is corrected and `compile_fail`
passes in this full run. The two new HAL rollback unit tests pass separately.

The full run uses the geometric allocator snapshot in `measurement-sources/backoff-final`.
The final source additionally fixes only D3D12's convenience `create_resource` function
and its tests; wgpu uses `allocate`/`free` and those paths are byte-identical. That final
delta has 43 passing allocator library tests and identical-driver controls demonstrating
the old bug. It is not represented as a second full native run of the convenience fix.
The wgpu followup's only later change is three documentation comment lines; the saved
full-suite source and `sources/wgpu-comment-delta.json` record both hashes.

Authoritative artifacts: [JUnit](sources/backoff-full-junit.xml),
[complete output](logs/backoff-full-wgpu.log), [triage including failure details](backoff-failure-triage.json),
[clean upstream comparison](control-comparison.json).
Generated feature actual/difference screenshots and colocated references are archived
under [final-feature-images](sources/final-feature-images/), with hashes and original
modification times in `sources/final-feature-images.json`; this includes passing cases.

| Binary | Exact test identity (adapter/API included) | Final outcome | Clean upstream control | Disposition |
|---|---|---|---|---|
| `wgpu-test::wgpu-gpu` | `[Dx12/Intel(R) Arc(TM) Graphics/1] wgpu_gpu::binding_array::samplers::binding_array_samplers` | test failure with exit code 101 | test failure with exit code 101 | Also fails on pristine upstream |
| `wgpu-test::wgpu-gpu` | `[Dx12/Intel(R) Arc(TM) Graphics/1] wgpu_gpu::binding_array::samplers::partial_binding_array_samplers` | test failure with exit code 101 | test failure with exit code 101 | Also fails on pristine upstream |
| `wgpu-test::wgpu-gpu` | `[Dx12/Intel(R) Arc(TM) Graphics/1] wgpu_gpu::multiview::draw_multiview_single` | test failure with exit code 101 | pass | Basename-dependent historical failure; native cause unresolved |
| `wgpu-test::wgpu-gpu` | `[Dx12/Intel(R) Arc(TM) Graphics/1] wgpu_gpu::shader::zero_init_workgroup_mem::zero_init_workgroup_memory_parallel_f16` | test failure with exit code 101 | test failure with exit code 101 | Also fails on pristine upstream |
| `wgpu-test::wgpu-gpu` | `[Dx12/Intel(R) Arc(TM) Graphics/1] wgpu_gpu::subgroup_operations::subgroup_operations` | test failure with exit code 101 | test failure with exit code 101 | Also fails on pristine upstream |
| `wgpu-test::wgpu-gpu` | `[Dx12/Intel(R) Arc(TM) Graphics/1] wgpu_gpu::transfer::copy_unaligned_rows` | test failure with exit code 101 | test failure with exit code 101 | Also fails on pristine upstream |
| `wgpu-test::wgpu-gpu` | `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::binding_array::tlas::binding_array_tlas` | test abort | test abort | Also fails on pristine upstream |
| `wgpu-test::wgpu-gpu` | `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_draw` | test abort | test abort | Also fails on pristine upstream |
| `wgpu-test::wgpu-gpu` | `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_draw_indirect` | test abort | test abort | Also fails on pristine upstream |
| `wgpu-test::wgpu-gpu` | `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_multi_draw_indirect` | test abort | test abort | Also fails on pristine upstream |
| `wgpu-test::wgpu-gpu` | `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_multi_draw_indirect_color_readback` | test abort | test abort | Also fails on pristine upstream |
| `wgpu-test::wgpu-gpu` | `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_multi_draw_indirect_count` | test abort | test abort | Also fails on pristine upstream |
| `wgpu-test::wgpu-gpu` | `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_pipeline_basic_task_mesh` | test abort | test abort | Also fails on pristine upstream |
| `wgpu-test::wgpu-gpu` | `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_pipeline_basic_task_mesh_frag` | test abort | test abort | Also fails on pristine upstream |
| `wgpu-test::wgpu-gpu` | `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_pipeline_basic_task_mesh_frag_no_draw` | test abort | test abort | Also fails on pristine upstream |
| `wgpu-test::wgpu-gpu` | `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::multiview::draw_multiview_multisample` | test failure with exit code 101 | test failure with exit code 101 | Also fails on pristine upstream |
| `wgpu-test::wgpu-gpu` | `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::ray_tracing::shader::prevent_invalid_ray_query_calls` | test abort | test abort | Also fails on pristine upstream |
| `naga::naga` | `wgsl_errors::recursion_depth_template` | test abort | test abort | Also fails on pristine upstream |
| `wgpu-benchmark::bench/wgpu-benchmark` | `Computepass Encoding` | test abort | test abort | Also fails on pristine upstream |
| `wgpu-examples` | `[Dx12/Intel(R) Arc(TM) Graphics/1] mesh_shader` | test failure with exit code 101 | test failure with exit code 101 | Also fails on pristine upstream |
| `wgpu-examples` | `[Dx12/Intel(R) Arc(TM) Graphics/1] ray_cube_compute` | test failure with exit code 101 | test failure with exit code 101 | Also fails on pristine upstream |
| `wgpu-examples` | `[Vulkan/Intel(R) Arc(TM) Graphics/0] mesh_shader` | test abort | test abort | Also fails on pristine upstream |
| `wgpu-test::wgpu_surface` | `surface_configure` | test failure with exit code 101 | test failure with exit code 101 | Also fails on pristine upstream |

Twenty-two final failures reproduce on a source-clean upstream checkout with registry
gpu-allocator and no wgpu patches. Matching outcomes establish that these failures do
not require the proposed patches; they do not identify the native root causes or prove
that every internal failure mechanism is identical.

DX12 `draw_multiview_single` passes clean upstream but still fails the final candidate's
normal executable. Identical historical candidate bytes isolate basename sensitivity:
original basename at original/new directories fails all six runs; short basename passes
all three. WARP passes all nine identity controls. The common-path three-binary matrix
passes all 18 runs. These results bound the issue without certifying deployed executable
names or establishing a driver-profile/cache/loader explanation.

Both GPUAV environment-setting attempts still report GPUAV enabled. They are
inconclusive, not successful no-GPUAV controls. Tests explicitly request GPU-based
validation. See [identity receipts](identity-controls.json), [common-path receipts](path-controls.json),
[GPUAV attempts](gpuav-controls.json) and [loaded-layer diagnostics](layer-diagnostics.json).
No global driver/SDK settings were changed.

The earlier full run's extra `compile_fail` failure was local test setup: `.cargo/config`
did not supply the allocator patch to trybuild's external workspace. The root workspace
Cargo.toml patch fixes it. Initial logs and the initially mislocated two-case JUnit pilot
remain archived; neither substitutes for this final full result. The historical report
and all 26 original failures/timeouts are preserved too.

## Verified flag and layer controls

A subsequent verified, **same-binary** upstream diagnostic overrides the required
GPUAV flag in test initialization, retaining core validation. With no proposed wgpu
patches and the registry allocator, TLAS and ray-query each abort in three GPUAV-on
trials and pass in three off trials. All eight mesh tests still abort in both modes.
A second matched comparison removes backend validation entirely: all eight still
abort in all three trials, with the SDK validation DLL absent in every no-layer
execution. This rules out that DLL as a requirement for these mesh aborts; it does
not identify the faulting driver/shader component. An initial off-only TLAS timeout
is also preserved. These are diagnostic configurations, **not conformance passes**;
the default suite still has 23 failures. [Complete controls and limits](GPUAV_CONTROL.md)
