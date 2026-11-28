# Proposed allocator PR title

Resolve block sizing per memory type, bound Vulkan growth, and retain a bounded empty-block cache

# Proposed description

Growable blocks currently use the current growth step as their personal-allocation threshold. An allocation that fits the configured maximum can therefore receive a personal block instead of advancing shared growth. The existing PR corrects that threshold, but releasing every grown empty block makes recurring bursts recreate their heaps.

Resolve the immutable sizing range when each memory type is constructed. Preserve the CPU-accessibility meaning of the existing host/device settings and use that same resolved range for growth, personal allocation and reclamation. Vulkan additionally caps the range to the selected heap's exact capacity and checks individual requests on both initial and fallback paths. This prevents a 192 MiB request on a 214 MiB heap from advancing to an invalid 256 MiB shared block.

Keep geometric growth and the configured maximum threshold. Cache the largest eligible empty shared block per memory type, including while another block remains live. Limit that cache to the smaller of twice the configured minimum and the maximum. Add an explicit trim method to release empty blocks without disturbing live allocation indices. Existing constructors and placement preferences remain compatible; no dependency is added.

On Intel Arc UMA, a five-trial Performance upload burst creates six heaps with the candidate versus twelve with the current PR, while retaining 128 MiB. A MemoryUsage mixed workload creates seven heaps versus 115, with peak reservation falling from 148 to 136 MiB and retention increasing from 4 to 28 MiB. A cache through the maximum saves further creations in some bursts but can retain substantially more memory. Full results include unfavorable cells and timing ranges; these observations do not establish a universal optimum.

Validation covers unit and boundary tests, Vulkan capacity/fallback fault injection, std/no_std and feature checks, strict Clippy and rustdoc, Apple target type checks, physical Vulkan/D3D12 examples, hardware trimming checks, and wgpu integration. Metal runtime validation and physical discrete-GPU pressure testing remain open.

The broader combined wgpu matrix runs 2,205 tests: 2,179 pass, 23 fail/abort and three time out. The local failure report records matched controls with the unchanged allocator PR and frozen candidate binaries. This is an allocator recommendation with documented full-stack validation limits.

The local REPORT.md contains the exact revisions, source research, full validation results and reproducible raw evidence. This is draft text only; it has not been posted.

# Suggested downstream disposition

Keep wgpu PR 11129's lazy external-texture initialization and PR 11130's smaller DX12 transient pool. Resource avoidance and explicit lifetime sizing remain useful with bounded allocator caching. Use the factorial measurements in REPORT.md to describe combined savings, because the independent savings overlap.

Keep a future heap-aware allocation planning and pressure interface separate. It should expose actual new reservation and compatible reuse rather than mirror a minimum block size in downstream budget checks. Independent Vulkan fallback placement and Metal resource-selection issues should also remain separate.
