# Full wgpu validation and failure controls

The full combined run executes 2,205 tests: 2,179 pass, 23 fail or abort, and three time out. Eighteen additional tests are excluded by the repository profile. The first build prerequisite failure is preserved separately. Every failing/timed-out case is listed below.

Both wgpu PRs remain applied in both controls. This isolates the gpu-allocator candidate; it does not establish that failures are independent of the wgpu patches.

| Binary | Test | Full result | PR 323 control | Candidate focused control | Assessment |
|---|---|---|---|---|---|
| wgpu-test::wgpu-gpu | [Executed] [Dx12/Intel(R) Arc(TM) Graphics/1] wgpu_gpu::binding_array::samplers::binding_array_samplers | test failure with exit code 101 | test failure with exit code 101 | test failure with exit code 101 | reproduces without candidate allocator |
| wgpu-test::wgpu-gpu | [Executed] [Dx12/Intel(R) Arc(TM) Graphics/1] wgpu_gpu::binding_array::samplers::partial_binding_array_samplers | test failure with exit code 101 | test failure with exit code 101 | test failure with exit code 101 | reproduces without candidate allocator |
| wgpu-test::wgpu-gpu | [Executed] [Dx12/Intel(R) Arc(TM) Graphics/1] wgpu_gpu::multiview::draw_multiview_single | test failure with exit code 101 | pass | test failure with exit code 101 | executable-path sensitive with identical candidate bytes |
| wgpu-test::wgpu-gpu | [Executed] [Dx12/Intel(R) Arc(TM) Graphics/1] wgpu_gpu::ray_tracing::as_aabb::aabb_flags_mismatch | test timeout | test timeout | pass | reproduces without candidate allocator |
| wgpu-test::wgpu-gpu | [Executed] [Dx12/Intel(R) Arc(TM) Graphics/1] wgpu_gpu::shader::zero_init_workgroup_mem::zero_init_workgroup_memory_parallel_f16 | test failure with exit code 101 | test failure with exit code 101 | test failure with exit code 101 | reproduces without candidate allocator |
| wgpu-test::wgpu-gpu | [Executed] [Dx12/Intel(R) Arc(TM) Graphics/1] wgpu_gpu::subgroup_operations::subgroup_operations | test failure with exit code 101 | test failure with exit code 101 | test failure with exit code 101 | reproduces without candidate allocator |
| wgpu-test::wgpu-gpu | [Executed] [Dx12/Intel(R) Arc(TM) Graphics/1] wgpu_gpu::transfer::copy_unaligned_rows | test failure with exit code 101 | test failure with exit code 101 | test failure with exit code 101 | reproduces without candidate allocator |
| wgpu-test::wgpu-gpu | [Executed] [Dx12/Microsoft Basic Render Driver/2] wgpu_gpu::device::request_device_error_message_native | test abort | test abort | pass | reproduces without candidate allocator |
| wgpu-test::wgpu-gpu | [Executed] [Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::binding_array::tlas::binding_array_tlas | test abort | test abort | test abort | reproduces without candidate allocator |
| wgpu-test::wgpu-gpu | [Executed] [Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_draw | test abort | test abort | test abort | reproduces without candidate allocator |
| wgpu-test::wgpu-gpu | [Executed] [Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_draw_indirect | test abort | test abort | test abort | reproduces without candidate allocator |
| wgpu-test::wgpu-gpu | [Executed] [Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_multi_draw_indirect | test abort | test abort | test abort | reproduces without candidate allocator |
| wgpu-test::wgpu-gpu | [Executed] [Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_multi_draw_indirect_color_readback | test abort | test abort | test abort | reproduces without candidate allocator |
| wgpu-test::wgpu-gpu | [Executed] [Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_multi_draw_indirect_count | test abort | test abort | test abort | reproduces without candidate allocator |
| wgpu-test::wgpu-gpu | [Executed] [Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_pipeline_basic_task_mesh | test abort | test abort | test abort | reproduces without candidate allocator |
| wgpu-test::wgpu-gpu | [Executed] [Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_pipeline_basic_task_mesh_frag | test abort | test abort | test abort | reproduces without candidate allocator |
| wgpu-test::wgpu-gpu | [Executed] [Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::mesh_shader::mesh_pipeline_basic_task_mesh_frag_no_draw | test abort | test abort | test abort | reproduces without candidate allocator |
| wgpu-test::wgpu-gpu | [Executed] [Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::multiview::draw_multiview_multisample | test failure with exit code 101 | test failure with exit code 101 | test failure with exit code 101 | reproduces without candidate allocator |
| wgpu-test::wgpu-gpu | [Executed] [Vulkan/Intel(R) Arc(TM) Graphics/0] wgpu_gpu::ray_tracing::shader::prevent_invalid_ray_query_calls | test abort | test abort | test abort | reproduces without candidate allocator |
| naga::naga | wgsl_errors::recursion_depth_template | test abort | test abort | test abort | reproduces without candidate allocator |
| wgpu-benchmark::bench/wgpu-benchmark | Computepass Encoding | test abort | test abort | test abort | reproduces without candidate allocator |
| wgpu-examples | [Executed] [Dx12/Intel(R) Arc(TM) Graphics/1] mesh_shader | test failure with exit code 101 | test failure with exit code 101 | test failure with exit code 101 | reproduces without candidate allocator |
| wgpu-examples | [Executed] [Dx12/Intel(R) Arc(TM) Graphics/1] ray_cube_compute | test timeout | test failure with exit code 101 | test failure with exit code 101 | reproduces without candidate allocator |
| wgpu-examples | [Executed] [Vulkan/Intel(R) Arc(TM) Graphics/0] mesh_shader | test abort | test abort | test abort | reproduces without candidate allocator |
| wgpu-examples | [Executed] [Vulkan/Intel(R) Arc(TM) Graphics/0] ray_cube_compute | test timeout | pass | pass | not reproduced in either focused control |
| wgpu-test::wgpu_surface | surface_configure | test failure with exit code 101 | test failure with exit code 101 | test failure with exit code 101 | reproduces without candidate allocator |

Raw output, JUnit, filters, frozen executables and hashes are under wgpu-failure-controls. Allocation correctness checks and the benchmark success counts are separate from this broader suite. Reproduction without the candidate proves a failure can occur on the unchanged allocator PR; it does not identify a driver root cause.

## Multiview path control

The first focused DX12 single-view multiview comparison is asymmetric: five unchanged-PR passes versus five candidate failures. Moving the exact archived executables to one common path yields three passes per version. An eight-run candidate-only factorial then varies path and log setting over two rounds: the original path fails four times and the common path passes four times, with both warn and debug logging. Candidate SHA-256 is unchanged in every run. The staged WARP DLL hashes also match.

This establishes executable-path sensitivity without changing allocator code or recompiling. It does not identify whether an application profile, driver cache, loader context or another path-dependent mechanism is responsible. The original failure remains in the full-suite count. The case is an unresolved environmental/backend compatibility risk, rather than a demonstrated allocator-policy regression. See multiview-control-repeats.json, multiview-common-path.json, multiview-path-matrix.json and multiview-runtime-dll-hashes.json.
