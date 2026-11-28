# Verified GPUAV flag control

This diagnostic uses upstream `60cef2b`, its unchanged registry allocator/lock and
none of the proposed wgpu patches. The sole source change is a test-initialization
control: a private process variable removes GPU_BASED_VALIDATION after the tests'
explicit request. Both modes assert core validation is enabled and print the final
flags before creating the instance. This intentionally changes the required test
configuration; off-mode results are **not conformance passes**.

One frozen executable, with identical bytes, basename, directory, working directory,
adapter configuration and metadata, runs both modes. The three trials interleave
on/off order, one test thread at a time. The Vulkan layer warns that both core and
GPU-assisted validation are enabled in each on-mode process, and not in any off-mode
process. All 60 executions have the corresponding per-test flag marker. This corrects
the earlier environment-only attempts, which never disabled GPUAV and remain archived.

Outcomes across 30 executions per mode: GPUAV on `{'test abort': 30}`; GPUAV off `{'pass': 6, 'test abort': 24}`.


| Exact Vulkan test identity | GPUAV on (3 trials) | GPUAV off (3 trials) |
|---|---|---|
| `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::binding_array::tlas::binding_array_tlas` | 3 test abort | 3 pass |
| `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_draw` | 3 test abort | 3 test abort |
| `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_draw_indirect` | 3 test abort | 3 test abort |
| `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_multi_draw_indirect` | 3 test abort | 3 test abort |
| `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_multi_draw_indirect_color_readback` | 3 test abort | 3 test abort |
| `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_multi_draw_indirect_count` | 3 test abort | 3 test abort |
| `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_pipeline_basic_task_mesh` | 3 test abort | 3 test abort |
| `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_pipeline_basic_task_mesh_frag` | 3 test abort | 3 test abort |
| `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_pipeline_basic_task_mesh_frag_no_draw` | 3 test abort | 3 test abort |
| `[Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::ray_tracing::shader::prevent_invalid_ray_query_calls` | 3 test abort | 3 pass |

The comparison establishes dependence on the GPUAV configuration for the tested cases
where outcomes change. It does not distinguish a validation-layer defect, instrumented
shader/driver interaction or another component of that path. It does not fix the
candidate's default full suite, establish allocator causality, or cover the separate
example binary or DX12 basename-dependent case.

Authoritative [receipt](gpuav-flag-control.json), [summary](gpuav-flag-control-summary.json),
[all six logs/JUnit files](gpuav-flag-controls/),
[harness-only patch](sources/gpuav-flag-control-harness.patch),
[exact harness source](sources/gpuav-flag-control-init.rs) and
[frozen binary](gpuav-flag-control-bin/) preserve the comparison. The initial isolated
build excludes all local wgpu/naga/allocator artifacts; the final harness edit rebuilds
the same package at the same path, with per-mode runtime assertions preventing silent
reuse of the wrong control. A separate three-process off-only pilot is also retained.

The default full suite remains 2,184 passes and 23 failures/aborts among 2,207 executed
tests, with 18 profile exclusions. Do not subtract these diagnostic results from that
failure count. Original pristine-upstream controls and all historical evidence remain
unchanged. No global Vulkan SDK/driver settings were modified.

## Followup: core validation versus no backend validation

The eight mesh tests receive a separate same-binary comparison with GPUAV disabled
in both modes. Three trials retain core validation; three remove the backend validation
request. The harness checks the native `VkLayer_khronos_validation.dll` module after
instance creation: it is present in all 24 core-mode executions and absent in all
24 no-layer executions. Loader diagnostics and per-test flags are retained too.

**All eight tests abort in all three trials in both modes** (24/24 aborts each), with
the native fast-fail code 0xc0000409. Thus these aborts do not require GPUAV or the SDK
validation DLL. The result narrows the problem to upstream's remaining native mesh
execution path; it does not prove whether shader input, driver behavior or another
component is responsible. No validation-disabling workaround is proposed for shipping.

[Structured layer comparison](layer-control.json), [summary](layer-control-summary.json),
[six logs/JUnit files](layer-controls/), [harness patch](sources/layer-control-harness.patch)
and [frozen binary](layer-control-bin/) preserve the followup. This binary differs from
the GPUAV comparison binary; each pair of modes uses the same bytes and path within
its own experiment. Both are based on pristine upstream runtime code and the registry
allocator, with only test initialization modified.

The earlier off-only pilot includes one initial 90-second TLAS timeout, then two TLAS
passes; the later matched matrix has three TLAS passes with GPUAV off. That timeout's
origin remains unresolved and is retained in `core-validation-controls/trial1.*`.
The pilot has 30 executions; the matched GPUAV matrix 60; the layer matrix 48. These
138 diagnostic test executions are separate from the 376 benchmark/plan processes.
