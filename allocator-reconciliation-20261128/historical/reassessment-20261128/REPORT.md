# gpu-allocator PR 323 architecture and implementation recommendation

28 November 2026 Australia Sydney.

Adopt the resolved sizing policy, exact Vulkan heap cap, bounded cache of one empty block per memory type, and explicit trimming in an expanded PR 323. Keep the corrected maximum dedicated threshold and geometric growth. Interpret the existing host/device configuration through CPU accessibility; make capacity, placement, budgets and lifetime independent concerns.

The proposed cache keeps the largest eligible empty block through one growth step, bounded by min(2 × minimum, maximum). It can retain that block while other blocks remain live. This restores useful hysteresis without retaining every large burst. The larger-cache and demand-based alternatives below show why neither zero retention nor fewer heap calls alone determines the best policy.

Allocator-specific checks and the benchmark processes pass. The broader wgpu matrix is not clean: 2,179 of 2,205 tests pass, 23 fail and three time out. Matched controls reproduce 24 of the 26 unsuccessful cases with unchanged allocator PR 323; 1 case remains unreproduced in both focused controls, and 1 case depends on executable path with identical candidate bytes. Both wgpu patches remain applied in these controls, so this comparison isolates the allocator candidate only. The recommendation is for review with these validation limits, not a claim of a fully passing wgpu matrix. [Every failure and control result](FAILURE_TRIAGE.md).

The complete candidate is [against PR 323](patches/candidate-on-pr323-179ea43.patch) and [against upstream main](patches/candidate-on-main-fc22df0.patch). These patches are local review artifacts. Actual PR branches and application dependencies remain untouched.

## 1 Recovered project state

| Repository or contribution | Verified state |
|---|---|
| gpu-allocator upstream main and PR base | fc22df05140b15ed6d764beabd12a1b807011bc5 |
| gpu-allocator PR 323 and fork branch | 179ea43f05332c2809addd7922cd056220efc36b |
| wgpu base | 60cef2be828e03ba54e2e1598001b4625c0c2163 |
| wgpu PR 11129 | 793698d89332250d5abe92e61769625233be9ac9 |
| wgpu PR 11130 | 22827ee25285b56c4056fe6bb1de27917caf45a9 |

GitHub and remote-ref snapshots are in [sources](sources). All three PRs were drafts when inspected. The allocator discussion contains the contributor's later decision to expand scope; no subsequent maintainer response changes the technical requirements. Older wgpu progress notes reference intermediate heads, so experiments use the verified final heads above.

The full clone and historical main, PR, proposal and prototype worktrees were recovered. The proposal and prototype already had uncommitted changes; those remain intact. No additional allocator work later than the recovered report was found. [Recovery audit](recovery-audit.json).

## 2 Existing evidence and independent assessment

All 438 entries in the original SHA-256 manifest matched. Re-running the historical analyzer into a new destination reproduced its complete JSON summary. Its 1,500 comparisons are cross-products of trials, not 1,500 independent runs. The normalized allocate, free, map and unmap streams match over 3,910 calls, including allocation sizes and type indices. [Reanalysis](historical-reanalysis/verification.json), [API comparison](historical-api-equivalence.json).

The historical conclusions about reachable CPU-accessible types, the dedicated-threshold bug, the reclamation regression and texture over-reservation are supported. Two qualifications matter. Historical allocation timings include Vulkan requirement-query cache misses and every D3D12 requirements query. The new harness prepares requirements before timing, so old and new absolute timings are separate experiments. Also, historical intent explains the public settings; it does not establish an optimal allocation policy.

The exact texture workload is 24 RGBA8 images of 2048 × 2056 pixels: 385.5 MiB payload. Driver requirements are larger. The old evidence reports approximately 409.5 MiB live requirements and 544 MiB reservation on PR 323. The burst is forty 6.25 MiB upload buffers, allocated and freed over four rounds. All original reports, patches, raw files and binaries remain preserved.

The published historical wgpu reproduction repository also remains clean: all 353 checked tracked artifacts match their Git blobs. Of 330 JSON comparisons with the local isolated logs, 310 match exactly. Twenty wgpu 11130 files have different timing and OS accounting observations under reused trial names; their adapter/workload identity and all allocator metrics agree. Treat these as distinct observations rather than duplicate copies, and do not merge their trial labels. [Historical wgpu integrity](historical-wgpu-integrity.json), [field differences](historical-wgpu-json-differences.json).

## 3 Modern allocator research

[The research appendix](RESEARCH.md) examines current VMA 3.5.0 and D3D12MA sources, Dawn, ANGLE, Mesa, API specifications and relevant papers. Source snapshots include Git blob identities.

VMA and D3D12MA combine preferred blocks, large-allocation decisions, caching, fallback and budgets. Dawn separates buddy suballocation from heap recycling and GPU lifetime tracking. ANGLE delegates substantial Vulkan allocation policy to VMA. Mesa's driver-level caches also know fences and placement domains. Their surrounding capabilities matter as much as their block formulas.

Device-side CUDA allocation research and virtual-memory stitching solve different problems from this CPU-side, resource-binding allocator. Their throughput or fragmentation results cannot be transferred to these graphics API calls.

The measured native reference is VMA 3.3.0 bundled by vk-mem 0.5.0. It uses native defaults, matching memory types and persistent CPU mappings. It is separate from both current VMA source research and the simplified policy inspired by VMA.

## 4 The role of CPU visibility

CPU visibility should interpret the existing configuration, rather than serve as the complete architectural foundation. It does not identify a small heap, a transient resource or available process memory. ReBAR exposes CPU-accessible device memory; UMA can expose different accessibility properties over the same physical RAM.

HOST_VISIBLE describes mapping; DEVICE_LOCAL describes device access and heap membership. Substituting one for the other silently changes configured policies on UMA and ReBAR. Eleven downloaded published tables match the recovered data; together with the local probe they cover discrete NVIDIA with and without ReBAR, AMD SAM, Intel discrete and integrated GPUs, Apple Silicon, Adreno and Mali. These are table-based conclusions outside the local Intel hardware. [Vulkan properties](https://docs.vulkan.org/refpages/latest/refpages/source/VkMemoryPropertyFlagBits.html), [table verification](sources/gpuinfo/verification.json).

The original 18-of-36 classification difference is reproducible. It is evidence against silently changing configuration semantics, rather than evidence that visibility alone is optimal.

PR 161 explicitly documented the ranges as CPU-visible and GPU-only; PR 263 later replaced that wording with host/device terminology. That history explains the compatibility contract. It does not determine an optimal future policy. [PR 161 implementation](https://github.com/Traverse-Research/gpu-allocator/commit/23d97047885100859650f66c5e34e75660157eaf), [PR 263 documentation change](https://github.com/Traverse-Research/gpu-allocator/commit/955b13a45bff8308b48d553032f9d6216c0e57e6).

## 5 Alternative architectures

| Alternative | Result or architectural assessment |
|---|---|
| Resolve the existing ranges once | Removes duplicated classification and allocation/free disagreement without a public constructor change |
| Replace visibility with locality | Reinterprets application settings and can choose blocks larger than small BAR heaps |
| Capacity-derived defaults | Useful hardware input; explicit application settings still need precedence |
| Dynamic budget-aware planning | Appropriate long-term direction; requires current per-heap or per-segment state |
| Geometric growth | Retains amortization and the documented practical behavior; can increase peak reservation |
| Demand-limited or request-sized blocks | Texture savings can accompany worse packing and more heap calls in other workloads |
| Retain only the final block | Misses reuse while another block remains live |
| One bounded empty cache | Reuses a useful block across bursts with a predictable retention ceiling |
| Cache through the maximum | More reuse at the cost of retaining the largest historical shared block |
| Timers or adaptive retention | Insufficient evidence to justify additional state and tuning |
| Explicit trim | Gives applications a deterministic release boundary |

The implemented variants and full results retain unfavorable cells as well as improvements. No single scalar benchmark defines a universal optimum.

## 6 Backend correctness

Vulkan resolves the host range from the existing mappable property, which currently means exactly HOST_VISIBLE. The same value drives CPU mapping. Static heap capacity limits the resolved shared range, and a guard inside MemoryType protects resource allocations through both initial and fallback paths. Explicit dedicated schemes remain separate from allocator-personal blocks.

D3D12 recognizes UPLOAD, READBACK and GPU_UPLOAD explicitly. CUSTOM is CPU-accessible only for WRITE_COMBINE or WRITE_BACK. Unknown values are not assumed mappable. The supported Windows bindings provide the named GPU_UPLOAD constant. The allocator still constructs DEFAULT and the two existing CUSTOM types; this change does not introduce GPU upload placement. [Microsoft heap specification](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/D3D12GPUUploadHeaps.md).

Standard READBACK heaps are CPU-visible, but this shared path currently implements readback through CUSTOM plus WRITE_BACK. The old Type != DEFAULT rule therefore worked for reachable heaps while remaining too permissive as a general predicate. This distinction answers the review concern without changing placement.

Metal resolves Shared and Private placement heaps. Managed is a resource storage mode, not a supported heap mode. Cache removal and trimming preserve residency-set removal. Apple type checks cover both architectures; runtime behavior needs Apple hardware. [Apple heap modes](https://developer.apple.com/documentation/metal/mtlheapdescriptor/storagemode.md).

Arithmetic remains bounded by the configured 256 MiB maximum before a Vulkan cap lowers it. Count shifts are clamped; cache-limit multiplication saturates. A fresh block begins at offset zero, so reducing its end to an exact Vulkan heap capacity does not violate resource alignment. Shared/personal boundaries, non-power-of-two settings, tiny heaps, non-quantized capacities, free ordering, cache replacement, trimming and regrowth are tested.

## 7 Heap capacity and memory budget

The capacity fix belongs with growth. With a 214 MiB heap, a 4–256 MiB host range and a 192 MiB request, upstream main chooses a valid 192 MiB personal block. PR 323 advances to a 256 MiB shared block, violating the per-allocation heap limit. The candidate creates a 214 MiB shared block. The new regression test records the API allocation size through a mock Vulkan device.

This also fixes the older case where an application directly configures a minimum larger than the heap. The exact cap retains the last partial 4 MiB quantum and supports heaps below 4 MiB. A 4 MiB floor is unnecessary for Vulkan allocation size. [Vulkan allocation rule 01713](https://docs.vulkan.org/refpages/latest/refpages/source/vkAllocateMemory.html), [static matrix](capacity-matrix.json).

The published-table matrix contains 928 static checks: four exceed a heap before capping, and none do afterward. The separate growth example demonstrates a reachable change introduced by geometric request advancement.

A budget is a changing process guideline, shared by types using the same heap. It must not be frozen into the immutable range at construction. D3D12 video-memory capacity on UMA and Metal's recommended working set are not equivalent to Vulkan's individual-allocation limit. This candidate adds trimming rather than pretending those quantities are interchangeable. [Vulkan budgets](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceMemoryBudgetPropertiesEXT.html), [Metal working-set recommendation](https://developer.apple.com/documentation/metal/mtldevice/recommendedmaxworkingsetsize.md).

The capacity guard bounds individual allocations. Aggregate pressure across types, separate allocators and other processes still requires dynamic handling. An allocation can fail while smaller empty cached blocks reserve memory. The caller can trim and retry; this patch provides no automatic cache eviction or smaller-block retry on allocation failure. That pressure integration remains a material limitation, especially for the larger Performance cache ceilings.

## 8 Growth and dedicated selection

Keep the configured maximum as the allocator-personal threshold. A request above the current step but below the maximum must not permanently stall shared growth. Keep geometric advancement for the practical patch; it has predictable bounds and amortizes heap creation.

The workload results reject a general rule that smaller request-sized blocks reduce total reservation. Repeated 6.25 MiB requests pack efficiently into larger shared blocks. A smaller rounded block can leave a larger fraction unusable for the next request. Conversely, textures just above a geometric step expose substantial rounding headroom.

“Dedicated” in these tables means a one-allocation block. Vulkan resource-dedicated allocation metadata is a separate API concern; the direct harness requests allocator-managed allocations.

| Vulkan MemoryUsage workload | Policy | Heaps created | Peak MiB | Retained MiB |
|---|---|---|---|---|
| textures | pr323 | 10 | 544 | 0 |
| textures | cache2 | 10 | 544 | 0 |
| textures | demand2 | 14 | 468 | 0 |
| textures | request | 24 | 480 | 0 |
| burst_release | pr323 | 44 | 288 | 0 |
| burst_release | cache2 | 41 | 288 | 8 |
| burst_release | demand2 | 84 | 320 | 0 |
| burst_release | request | 157 | 320 | 8 |
| mixed_frames | pr323 | 115 | 148 | 4 |
| mixed_frames | cache2 | 7 | 136 | 28 |
| mixed_frames | demand2 | 321 | 136 | 20 |
| mixed_frames | request | 631 | 168 | 16 |
| sporadic_long_lived | pr323 | 41 | 156 | 4 |
| sporadic_long_lived | cache2 | 30 | 156 | 8 |
| sporadic_long_lived | demand2 | 69 | 156 | 4 |
| sporadic_long_lived | request | 113 | 196 | 4 |

## 9 Retention and reclamation

The cache owns one index per memory type. Reusing that block clears the index. When a shared block becomes empty, the policy retains it if it is within the limit and larger than the existing cached block; otherwise it releases it. Replacing a cache releases the old empty block without moving live block slots.

The one-step limit follows the existing size configuration. Performance ranges allow a larger cache; MemoryUsage ranges retain a small one. It is a practical bound, not a claim about every application's working set. Explicit trim releases cached blocks and preserves live allocations and indices. Returned bytes describe allocator capacity removed; driver or resource references can affect physical release timing.

The local hardware check releases 8 MiB while a live allocation remains in a 4 MiB block, then reaches zero after that allocation is freed. Vulkan's mapped byte survives trimming. Larger-cache results quantify the alternative:

| Backend | Config | Workload | Cache | Heaps | Peak MiB | Retained MiB | Alloc ms median (range) |
|---|---|---|---|---|---|---|---|
| vulkan | memory_usage | burst_release | cache2 | 41 | 288 | 8 | 35.79 (27.51–55.27) |
| vulkan | memory_usage | burst_release | cachemax | 38 | 288 | 32 | 31.00 (25.17–46.17) |
| vulkan | memory_usage | mixed_frames | cache2 | 7 | 136 | 28 | 6.18 (2.68–8.64) |
| vulkan | memory_usage | mixed_frames | cachemax | 7 | 136 | 76 | 3.70 (2.81–4.09) |
| vulkan | memory_usage | textures | cache2 | 10 | 544 | 0 | 36.44 (13.25–47.30) |
| vulkan | memory_usage | textures | cachemax | 10 | 544 | 64 | 40.92 (34.99–77.36) |
| vulkan | manual | burst_release | cache2 | 25 | 384 | 8 | 61.89 (42.35–74.07) |
| vulkan | manual | burst_release | cachemax | 22 | 384 | 128 | 32.18 (23.82–34.96) |
| vulkan | manual | mixed_frames | cache2 | 7 | 136 | 28 | 5.84 (3.97–11.31) |
| vulkan | manual | mixed_frames | cachemax | 7 | 136 | 76 | 6.27 (5.61–12.79) |
| vulkan | manual | textures | cache2 | 6 | 544 | 0 | 13.24 (10.31–24.55) |
| vulkan | manual | textures | cachemax | 6 | 544 | 256 | 10.95 (10.54–21.89) |
| d3d12 | memory_usage | burst_release | cache2 | 41 | 288 | 8 | 130.19 (107.98–248.14) |
| d3d12 | memory_usage | burst_release | cachemax | 38 | 288 | 32 | 104.08 (89.92–143.26) |
| d3d12 | memory_usage | mixed_frames | cache2 | 7 | 136 | 28 | 17.11 (14.33–22.94) |
| d3d12 | memory_usage | mixed_frames | cachemax | 7 | 136 | 76 | 15.78 (10.42–27.41) |
| d3d12 | memory_usage | textures | cache2 | 10 | 544 | 0 | 91.35 (77.01–103.35) |
| d3d12 | memory_usage | textures | cachemax | 10 | 544 | 64 | 99.51 (81.50–162.07) |
| d3d12 | manual | burst_release | cache2 | 25 | 384 | 8 | 217.16 (194.23–315.64) |
| d3d12 | manual | burst_release | cachemax | 22 | 384 | 128 | 160.93 (143.33–252.64) |
| d3d12 | manual | mixed_frames | cache2 | 7 | 136 | 28 | 18.46 (12.72–23.06) |
| d3d12 | manual | mixed_frames | cachemax | 7 | 136 | 76 | 16.85 (13.92–58.74) |
| d3d12 | manual | textures | cache2 | 6 | 544 | 0 | 76.73 (66.95–132.23) |
| d3d12 | manual | textures | cachemax | 6 | 544 | 256 | 83.20 (64.10–111.75) |

The Manual burst saves three heap creations with the larger cache, while retention rises from 8 to 128 MiB. Mixed frames retain 76 rather than 28 MiB with identical heap counts. The selected bound favors memory efficiency in that trade-off. Performance permits caching a whole 256 MiB GPU block or 128 MiB CPU-visible block; its single texture burst retains 256 MiB versus zero on PR 323, without reducing creations for that first burst. This is a per-type limit, not an allocator-wide budget. Multiple types and separate allocator instances multiply it. Applications needing immediate release must call trim.

## 10 Implemented candidates

| Variant | Change |
|---|---|
| main | Exact upstream base |
| pr323 | Exact existing PR |
| proposal | Historical behavior-preserving refactor |
| retain2 | Last-block retention through one growth step, plus capacity and classification fixes |
| demand2 | Growth constrained by roughly twice the current request, with 4 MiB rounding |
| request | Rounded request-sized shared blocks |
| vma-policy | Simplified preferred-size ramp and half-max threshold; not VMA |
| cache2 | Resolved ranges, capacity guard, largest eligible empty cache and trim |
| cachemax | Same cache mechanism with the configured maximum as the retention limit |
| vma | Native VMA reference |

All implementations are in detached worktrees. The native VMA counter check uses AllocationInfo2. The simplified VMA policy can create shared blocks equal to request size, so its block-kind counts are reconstructed from its explicit threshold rather than the raw size-equality heuristic.

## 11 Comparative measurements

The primary machine is Windows 11 build 26300, Core Ultra 7 155H, Intel Arc integrated graphics, driver 31.0.101.5328, Rust 1.100.0. The recorded power plan is the existing Acer plan. Hardware and toolchain settings were recorded, not changed. [Environment](sources/runtime-environment.json).

Both benchmark families and allocator-specific checks use Rust 1.100.0. The full wgpu test worktree follows its checked-in Rust 1.97.1 toolchain pin; its matched failure controls use the same pin. [Toolchains by workspace](sources/toolchains-by-workspace.json).

The main direct suite uses equivalent release builds and an identical harness across eight variants, two backends and five configurations, with five trials. Native VMA is a separate default-policy reference. Processes run sequentially with interleaved variant order and two-second settle intervals. Compilation is excluded from timing periods. The direct harness measures allocator calls; resource requirements, reporting and driver queries are outside those intervals.

The suite completed 405 processes and 4,050 workload measurements, with no harness failures. All 500 paired PR/proposal decision comparisons match; all block-decision cells are stable across five trials. This verifies successful allocation behavior, not the absence of untraced driver-level failed attempts.

| Backend | Case | Policy | Heaps | Peak MiB | Retained MiB | Alloc ms median (range) | Alloc p99 µs | Free total ms |
|---|---|---|---|---|---|---|---|---|
| vulkan | performance burst_release | main | 6 | 320 | 128 | 16.17 (9.25–34.12) | 1920.6 | 28.37 |
| vulkan | performance burst_release | pr323 | 12 | 320 | 0 | 57.48 (32.97–74.78) | 7594.2 | 255.77 |
| vulkan | performance burst_release | cache2 | 6 | 320 | 128 | 8.26 (5.06–19.17) | 1766 | 23.92 |
| d3d12 | performance burst_release | main | 6 | 320 | 128 | 73.38 (54.38–94.32) | 13204.9 | 7.11 |
| d3d12 | performance burst_release | pr323 | 12 | 320 | 0 | 150.12 (126.12–247.01) | 14919.1 | 190.85 |
| d3d12 | performance burst_release | cache2 | 6 | 320 | 128 | 74.90 (51.86–81.21) | 13284.4 | 4.05 |
| vulkan | memory_usage mixed_frames | main | 115 | 148 | 76 | 46.45 (20.98–82.66) | 630.7 | 29.87 |
| vulkan | memory_usage mixed_frames | pr323 | 115 | 148 | 4 | 26.44 (23.41–33.76) | 412.6 | 32.62 |
| vulkan | memory_usage mixed_frames | cache2 | 7 | 136 | 28 | 3.93 (3.37–25.84) | 2.1 | 4.1 |
| d3d12 | memory_usage mixed_frames | main | 115 | 148 | 76 | 140.91 (134.92–214.59) | 2608.2 | 20.69 |
| d3d12 | memory_usage mixed_frames | pr323 | 115 | 148 | 4 | 170.28 (97.82–314.42) | 2889.6 | 26.34 |
| d3d12 | memory_usage mixed_frames | cache2 | 7 | 136 | 28 | 17.31 (9.08–18.08) | 2.2 | 1.42 |

Across all 100 direct configuration/backend/workload cells, cache2 lowers peak reservation in four, matches it in 96 and raises it in none. It reduces heap creations in 28 and matches them in 72. Retention is higher in 38 and equal in 62. These cell counts are descriptive, not a weighted application score. The integrated churn regression below shows why these direct workloads alone are insufficient.

| Backend | Ten-workload process config | Policy | Whole-process CPU ms median (range) |
|---|---|---|---|
| vulkan | memory_usage | pr323 | 218.75 (187.50–281.25) |
| vulkan | memory_usage | cache2 | 265.62 (187.50–281.25) |
| vulkan | performance | pr323 | 625.00 (578.12–625.00) |
| vulkan | performance | cache2 | 531.25 (484.38–593.75) |
| d3d12 | memory_usage | pr323 | 328.12 (218.75–375.00) |
| d3d12 | memory_usage | cache2 | 296.88 (218.75–328.12) |
| d3d12 | performance | pr323 | 578.12 (531.25–734.38) |
| d3d12 | performance | cache2 | 546.88 (500.00–609.38) |

CPU time includes setup, reporting, driver threads and all ten workloads. Observed values are quantized in 15.625 ms steps. It does not establish an overall CPU improvement: Vulkan MemoryUsage is higher for cache2 in this sample and ranges overlap. The elapsed-call reductions in a specific mixed workload must not be presented as equivalent whole-process CPU savings.

Latency columns are process-level medians with complete trial ranges in [the full tables](DIRECT_RESULTS.md). Heap-creation latency remains variable. Identical block decisions do not establish identical driver timing; gains against main with overlapping ranges should not be read as proven algorithmic speedups.

One cache2 Vulkan MemoryUsage mixed trial takes 25.84 ms versus a 3.93 ms median. Its longest allocation, 14.34 ms, is also the heap-creation p99; reuse p99 stays at 2 µs and all seven block decisions match other trials. This localizes the outlier to a heap-creating call, but does not identify whether the driver, OS scheduling or page commitment caused it. The outlier remains in every summary. Identical fixed-policy texture decisions also show large timing variation across variants. [Outlier review](outlier-review.json).

The main fixed-size Vulkan texture cell has a consistent unfavorable gap: PR 1.49 ms versus cache2 27.70 ms despite the same two heaps. A separate 20-process diagnostic compares textures alone and in the original workload sequence. Ten further processes replay the exact original executables after correctness checks, with compiler activity excluded. Those follow-ups are retained separately and do not replace any main-suite value.

| Fixed texture follow-up | Policy | Alloc ms median (range) |
|---|---|---|
| Filtered diagnostic alone | pr323 | 0.70 (0.65–109.58) |
| Filtered diagnostic original_order | pr323 | 41.20 (0.79–50.93) |
| Filtered diagnostic alone | cache2 | 1.94 (0.82–47.13) |
| Filtered diagnostic original_order | cache2 | 1.23 (0.97–42.87) |
| Exact archived binary replay | pr323 | 2.42 (2.04–70.73) |
| Exact archived binary replay | cache2 | 2.08 (1.72–29.35) |

API traces confirm identical texture allocation inputs: two 256 MiB requests on memory type zero, with null pNext. Cache retention intentionally reverses which empty handle is freed first. Follow-up timing rankings vary, so the original gap cannot be treated as a stable intrinsic algorithm cost or silently discarded as noise. Driver history and environmental state are plausible influences; the exact cause remains unresolved. The filtered follow-up also changes the harness binary, while the replay retains the original executable hashes. Both occur after wake and the recorded power-source event. [Diagnostic results](texture-diagnostic-summary.json), [original executable replay](texture-original-replay-summary.json), [API inputs and free order](texture-api-comparison.json).

Unused bytes include headroom and fragmentation. Free-gap dispersion is useful for the single-type fragmentation workload but is not an interchangeable cross-pool fragmentation percentage. The candidate preserves the free-list algorithm and does not relocate live resources.

| Vulkan default case | Implementation | Heaps | Shared | Personal/dedicated | Peak MiB | Retained MiB | Alloc ms median (range) |
|---|---|---|---|---|---|---|---|
| burst_release | pr323 | 13 | 13 | 0 | 256 | 64 | 33.84 (23.91–47.00) |
| burst_release | cache2 | 13 | 13 | 0 | 256 | 64 | 23.74 (10.18–46.72) |
| burst_release | vma | 13 | 13 | 0 | 480 | 32 | 67.73 (56.01–401.28) |
| mixed_frames | pr323 | 3 | 3 | 0 | 384 | 384 | 33.01 (20.34–37.40) |
| mixed_frames | cache2 | 3 | 3 | 0 | 384 | 384 | 27.80 (1.61–45.31) |
| mixed_frames | vma | 14 | 14 | 0 | 288 | 128 | 13.22 (11.75–36.20) |
| textures | pr323 | 2 | 2 | 0 | 512 | 256 | 1.49 (1.20–2.77) |
| textures | cache2 | 2 | 2 | 0 | 512 | 256 | 27.70 (23.72–28.41) |
| textures | vma | 3 | 3 | 0 | 448 | 256 | 16.69 (2.73–43.21) |

Native VMA reduces texture reservation from 512 to 448 MiB here, but raises burst peak reservation from 256 to 480 MiB. It makes different packing and retention choices and supplies a broader budget/fallback system. These data justify learning from its combined policy, not claiming that gpu-allocator or VMA wins generally. The differing default block ranges prevent attributing every difference to one heuristic.

## 12 Raw evidence and reproducibility

[Reproduction instructions](REPRODUCE.md) describe isolated preparation, builds, correctness checks and measurement. [The evidence manifest](EVIDENCE.sha256) covers sources, scripts, binaries, reports, patches and raw outputs. [Direct CSV](direct-summary.csv), [direct JSON](direct-summary.json), [downstream CSV](downstream-summary.csv) and [downstream JSON](downstream-summary.json) retain every cell and paired comparison.

An initial pilot reused a stale Cargo artifact through a shared target directory. It was stopped and is explicitly invalid in results-direct/INVALID.txt. Those outputs and binaries are preserved and excluded. Verified direct builds use separate target directories. Downstream builds explicitly clean each changed crate before rebuilding; receipts record source-diff, lockfile and executable hashes. Seeded dependency caches are followed by explicit allocator-artifact removal.

The final growth regression was added to the cfg(test) module after benchmark binaries were built. Runtime source stayed frozen. The additional test was run separately; [source freeze records](source-freeze-mtimes.json) document file hashes and timestamps. Adding that test and including previously untracked test code in exported diffs explains why final patch hashes differ from earlier build-diff receipts.

The old evidence manifest is independently verified again at the review boundary. The new dataset does not overwrite any historical benchmark output.

One downstream DX12 Manual large-allocation process spans Modern Standby from 07:47:56 to 09:39:30 Sydney time on 28 November. Its 6,696.76-second wall time and raw output are preserved under results-downstream-suspended. An identical-binary replacement finishes in 2.27 seconds and supplies the valid cell. Thus the downstream suite has 520 valid processes from 521 attempts. The event log also records a power-source change after wake. The power plan was unchanged; timing comparisons remain interleaved desktop observations with this additional environmental limitation. [Exclusion and replacement](measurement-exclusions.json), [power events](sources/kernel-power-recent.json).

## 13 Recommended long term architecture

Separate application lifetime intent, memory-type compatibility and physical-heap pressure. A memory type owns free ranges and static resolved preferences. A physical heap or D3D12 memory segment owns aggregate budget and reservation information. Applications supply meaningful lifetime boundaries that the allocator cannot infer from CPU accessibility.

A future planning/pressure interface should account for existing-block reuse and the actual proposed new reservation, with smaller or personal-allocation fallback on pressure where the backend supports it. Budgets remain advisory and allocation failures remain necessary to handle. A configurable cache budget can follow measurements on discrete hardware. There is no present justification for a policy-trait hierarchy, background threads or timers.

~~~mermaid
flowchart TD
    A[Resource requirements and placement] --> B[Compatible memory type]
    C[Application size configuration] --> D[Resolved static sizing]
    B --> D
    H[Vulkan heap capacity] --> D
    B --> E[Existing compatible free ranges]
    E -->|fits| R[Reuse]
    E -->|miss| G[Grow or allocate personal block]
    D --> G
    F[Shared block becomes empty] --> K[Keep one eligible empty block]
    K --> E
    T[Application trim boundary] --> X[Release empty blocks]
~~~

Dedicated resource requirements are checked before ordinary shared reuse. The diagram separates concerns rather than changing that ordering.

## 14 Recommended practical implementation

Use cache2 for the upstream candidate. It fixes the growth/retention interaction, resolves classification once, protects the shared-block size and provides an application release mechanism. It changes no placement preferences and requires no new dependency.

Keep request-sized and demand-limited policies experimental. Keep a larger maximum cache as a documented trade-off rather than the default. The decisive result is the combination of bounded retention, substantially reduced churn, and preserved application control; it is not zero retained memory.

Compared with the current PR, the candidate adds resolved policy ownership, explicit classification, capacity checks, bounded caching and trim. Compared with Claude's proposal, it intentionally changes allocation/reclamation behavior; the original proposal remains the measured behavior-preserving control. The small additional dynamic state addresses the live-anchor churn that last-block-only retention cannot fix. The cost is retained memory and, in integrated churn, additional peak headroom. Keep that cost explicit in review.

## 15 Public API and compatibility

Existing AllocationSizes constructors, private fields and the public get_memblock_size behavior remain compatible. The helper returns the configured growth step before hardware limits. Host means CPU-accessible, including accessible device-local types; device means CPU-inaccessible.

The additive trim method is the only public API addition. Configuration remains immutable. The per-type range removes configuration parameters and repeated classification from allocation and free paths.

Fixed block sizes remain fixed, but retention changes when another block is live: an empty block can now be cached alongside it. Explicitly configured growth and placement remain predictable. On small Vulkan heaps the resolved range can be smaller than the configured minimum to satisfy the API limit.

| Backend | MemoryUsage case | Policy | Peak tracked Rust bytes | After release bytes | After allocator drop bytes |
|---|---|---|---|---|---|
| vulkan | burst_release | pr323 | 13023 | 824 | 0 |
| vulkan | burst_release | cache2 | 13143 | 1552 | 0 |
| vulkan | mixed_frames | pr323 | 10311 | 1628 | 0 |
| vulkan | mixed_frames | cache2 | 10975 | 3676 | 0 |
| vulkan | fragmentation | pr323 | 335383 | 824 | 0 |
| vulkan | fragmentation | cache2 | 335503 | 7144 | 0 |
| d3d12 | burst_release | pr323 | 12951 | 752 | 0 |
| d3d12 | burst_release | cache2 | 13047 | 1456 | 0 |
| d3d12 | mixed_frames | pr323 | 10271 | 1588 | 0 |
| d3d12 | mixed_frames | cache2 | 10911 | 3612 | 0 |
| d3d12 | fragmentation | pr323 | 335311 | 752 | 0 |
| d3d12 | fragmentation | cache2 | 335407 | 7048 | 0 |

Rust metadata measurements are separate instrumented runs, with timings excluded. They include allocator-owned dynamic allocations and temporaries within its calls, exclude inline storage and driver/C++ allocations, and return to zero after allocator destruction.

## 16 Effects on wgpu PR 11129 and PR 11130

Keep lazy external-texture initialization. Eliminating unused resources is independent of block growth and caching; avoiding the first tiny staging allocation can avoid creating a whole CPU-visible block. Its concurrency and queue-drop behavior still matter.

Keep distinct DX12 transient sizing for now. Core caching cannot infer which resources are transient. A smaller pool still establishes smaller initial blocks and a smaller cache ceiling. The general pool and transient pool serve different lifetime distributions. Removing the second pool without a replacement workload input would change that control.

The combined unmodified correctness fixture passes. D3D12 exercises external textures, concurrent initialization, the expected RGBA pixel and queue-drop safety. This adapter's Vulkan path lacks the external-texture feature, so Vulkan covers applicable initialization and burst release instead. The 64 MiB temporary burst leaves only the 128 MiB GPU block on both backends.

wgpu's DX12 budget check estimates a minimum block rather than actual growth or reuse. Its Manual clamps can also differ from gpu-allocator's 4 MiB rounding. These assumptions deserve a later shared planning/pressure interface. Current wgpu code does not call the new trim method, so it does not yet reclaim this cache automatically under pressure. wgpu's Metal backend does not use gpu-allocator.

## 17 Combined patch measurements

The factorial compares PR 323 and cache2 against unchanged wgpu, lazy-only, transient-only and both patches. Vulkan omits source-identical transient-only duplicates. Selected demand2 and retain2 combinations test whether a different growth policy changes the integrated texture result.

These are real resource creation, upload, render and compute workloads, with allocator snapshots, DXGI usage, process working set, private commit, CPU-operation latency and whole-process CPU time. Process CPU time includes all child threads and differs from elapsed allocator-call latency. [Windows CPU accounting](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes).

Benchmark processes are serialized and compilation does not overlap measurement. Evidence reads, report editing and source-only reproduction checks continued during the downstream phase; this was an interactive desktop rather than a dedicated idle laboratory system. Interleaving, five trials and reported ranges reduce the risk of mistaking incidental latency for a policy effect.

The integrated “peak” memory columns are sampled at harness stages. Reserved memory after user resources drop includes live wgpu internal resources as well as spare blocks. Device destruction is reported separately.

The integrated texture workload uses twenty 2048 × 2048 RGBA8 textures with uploads and common initialization resources. It differs from the direct twenty-four-image 2048 × 2056 allocation-only workload. Churn creates 250 mixed-size buffers from 64 KiB to 16 MiB; repeated uploads issue 400 writes. Render and compute workloads execute actual offscreen GPU passes. These are focused graphics workloads rather than traces of an entire production application.

All 520 integrated processes completed across 104 five-trial cells, with no captured panic or validation-error output. The driver records OS/GPU metrics and whole-process CPU time for every run. The full table includes each independent patch state and unfavorable cells.

| Backend | Case | Variant | Initial MiB | Sampled peak MiB | After resources MiB | Create p50 µs | Create p99 µs | Process CPU ms |
|---|---|---|---|---|---|---|---|---|
| dx12 | performance idle | pr323-trunk | 192 | 192 | 192 | — | — | 281.25 |
| dx12 | performance idle | pr323-lazy | 128 | 128 | 128 | — | — | 250 |
| dx12 | performance idle | pr323-transient | 144 | 144 | 144 | — | — | 250 |
| dx12 | performance idle | pr323-both | 128 | 128 | 128 | — | — | 250 |
| dx12 | performance idle | cache2-trunk | 192 | 192 | 192 | — | — | 250 |
| dx12 | performance idle | cache2-both | 128 | 128 | 128 | — | — | 265.62 |
| vulkan | performance idle | pr323-trunk | 144 | 144 | 144 | — | — | 187.5 |
| vulkan | performance idle | pr323-lazy | 128 | 128 | 128 | — | — | 218.75 |
| vulkan | performance idle | cache2-trunk | 144 | 144 | 144 | — | — | 203.12 |
| vulkan | performance idle | cache2-lazy | 128 | 128 | 128 | — | — | 203.12 |
| dx12 | performance repeated_uploads | pr323-trunk | 192 | 192 | 192 | 375.6 | 1260.1 | 390.62 |
| dx12 | performance repeated_uploads | pr323-both | 128 | 144 | 144 | 540.7 | 2606.7 | 343.75 |
| dx12 | performance repeated_uploads | cache2-trunk | 192 | 192 | 192 | 424.6 | 1685.1 | 390.62 |
| dx12 | performance repeated_uploads | cache2-both | 128 | 144 | 144 | 393.4 | 1658.1 | 359.38 |
| dx12 | memory_usage churn | pr323-trunk | 12 | 76 | 12 | 10.2 | 13 | 265.62 |
| dx12 | memory_usage churn | pr323-both | 8 | 76 | 12 | 11.5 | 106.7 | 281.25 |
| dx12 | memory_usage churn | cache2-trunk | 12 | 92 | 28 | 14.6 | 130.2 | 312.5 |
| dx12 | memory_usage churn | cache2-both | 8 | 92 | 28 | 13.5 | 118.4 | 281.25 |
| vulkan | memory_usage churn | pr323-trunk | 12 | 76 | 12 | 4.4 | 25.2 | 171.88 |
| vulkan | memory_usage churn | pr323-lazy | 8 | 76 | 12 | 3.7 | 30.3 | 218.75 |
| vulkan | memory_usage churn | cache2-trunk | 12 | 92 | 28 | 4.3 | 30.7 | 203.12 |
| vulkan | memory_usage churn | cache2-lazy | 8 | 92 | 28 | 5.2 | 65.4 | 171.88 |
| dx12 | manual-8-256 large_textures | pr323-trunk | 12 | 524 | 12 | 6041.4 | 54943.4 | 421.88 |
| dx12 | manual-8-256 large_textures | cache2-trunk | 12 | 524 | 12 | 5801.7 | 64584.2 | 375 |
| dx12 | manual-8-256 large_textures | demand2-trunk | 12 | 388 | 12 | 9602.6 | 29071.4 | 468.75 |
| dx12 | manual-8-256 large_textures | pr323-both | 8 | 524 | 12 | 6879.3 | 59502.9 | 406.25 |
| dx12 | manual-8-256 large_textures | cache2-both | 8 | 524 | 12 | 6974.3 | 62563.7 | 421.88 |
| dx12 | manual-8-256 large_textures | demand2-both | 8 | 388 | 12 | 9880.9 | 39838.3 | 406.25 |

| Backend | Performance workload | Variant | GPU pass p50 µs | GPU pass p99 µs | Sampled reserved MiB |
|---|---|---|---|---|---|
| dx12 | sustained_render | pr323-trunk | 4341.87 | 4517.76 | 256 |
| dx12 | sustained_render | cache2-trunk | 4345 | 4504.58 | 256 |
| dx12 | sustained_render | cache2-both | 4421.35 | 4547.92 | 208 |
| dx12 | sustained_compute | pr323-trunk | 532.19 | 576.15 | 256 |
| dx12 | sustained_compute | cache2-trunk | 533.49 | 577.08 | 256 |
| dx12 | sustained_compute | cache2-both | 532.5 | 566.61 | 208 |
| vulkan | sustained_render | pr323-trunk | 3758.23 | 3927.76 | 208 |
| vulkan | sustained_render | cache2-trunk | 3801.09 | 3917.29 | 208 |
| vulkan | sustained_render | cache2-lazy | 3866.61 | 3973.28 | 208 |
| vulkan | sustained_compute | pr323-trunk | 659.58 | 730.62 | 208 |
| vulkan | sustained_compute | cache2-trunk | 602.03 | 690.47 | 208 |
| vulkan | sustained_compute | cache2-lazy | 663.18 | 712.55 | 208 |

| Backend | Case | Variant | Sampled DXGI local peak MiB | Sampled private commit peak MiB | Private working set after resources MiB |
|---|---|---|---|---|---|
| dx12 | performance idle | pr323-trunk | 260.74 | 291.97 | 267.83 |
| dx12 | performance idle | cache2-trunk | 260.74 | 291.68 | 267.86 |
| dx12 | performance idle | cache2-both | 196.74 | 227.73 | 204.01 |
| dx12 | memory_usage churn | pr323-trunk | 144.82 | 225.71 | 202.03 |
| dx12 | memory_usage churn | cache2-trunk | 160.94 | 225.74 | 202.07 |
| dx12 | memory_usage churn | cache2-both | 160.94 | 226.1 | 202.08 |
| vulkan | performance idle | pr323-trunk | 145.36 | 189.35 | 154.56 |
| vulkan | performance idle | cache2-trunk | 145.36 | 189.41 | 154.61 |
| vulkan | performance idle | cache2-lazy | 129.36 | 173.29 | 138.52 |
| vulkan | memory_usage churn | pr323-trunk | 129.37 | 175.6 | 140.75 |
| vulkan | memory_usage churn | cache2-trunk | 129.37 | 175.67 | 87.01 |
| vulkan | memory_usage churn | cache2-lazy | 129.37 | 175.61 | 76.75 |

The idle DX12 savings overlap. Lazy initialization removes the first CPU-visible block: 192 to 128 MiB with Performance settings. Transient separation alone changes 192 to 144 MiB. Together they reach 128 MiB, not the sum of both independent savings. Cache2 leaves these initial reservations unchanged. On Vulkan, lazy initialization changes 144 to 128 MiB; transient separation has no Vulkan implementation.

Once uploads actually occur, a staging pool is needed. The combined DX12 path peaks and remains at 144 MiB in the repeated-upload case versus 192 MiB without the patches. This supports smaller lifetime-specific sizing even with the revised cache. Lazy allocation avoids unused resources; it cannot eliminate resources a workload uses.

The cache has an unfavorable integrated churn cell: with MemoryUsage settings, sampled peak reservation rises from 76 to 92 MiB and resource-drop reservation from 12 to 28 MiB. Retaining a reusable empty block alongside live internal resources costs 16 MiB here. This direct counterexample limits the claim of memory improvement and is a reason to keep explicit trimming and application sizing.

Demand-limited growth reduces the Manual integrated texture peak from 524 to 388 MiB. That confirms the direct geometric-headroom concern using real resources. It does not outweigh demand2's much greater mixed and burst heap churn in the direct suite. A future opt-in texture/lifetime policy could use this result; a universal default change would trade away substantial amortization.

Rendering and compute pass timings, DXGI local usage, private commit, working set, CPU-call ranges and full factorial states are retained in downstream-summary.csv. Paired allocator deltas and patch interactions are in downstream-interactions.csv and downstream-interactions.json. The harness samples GPU timestamps when supported. Changes in process commit and DXGI accounting are not interchangeable with allocator capacity. Identical reservations with variable creation latency do not demonstrate a stable GPU performance gain. No throughput improvement is required for the two wgpu patches' resource-avoidance and lifetime-sizing rationale.

## 18 Proposed scope of PR 323

Include resolved per-type ranges, explicit supported-value classification, restored CPU-accessibility documentation, the maximum personal threshold, geometric advancement, exact Vulkan capacity protection on all allocation paths, bounded empty caching and trim.

These changes are interdependent. Advancing a shared block makes the capacity guard necessary. Reclaiming every grown block causes the measured burst regression. Retention needs one authoritative range and a deterministic release mechanism.

Keep broad placement changes, new default sizing heuristics, dynamic budget APIs, relocation/defragmentation and independent Metal resource fixes separate. Proposed title and description are [local draft text](PROPOSED_PR.md).

## 19 Independent issues

| Issue | Assessment and separation |
|---|---|
| Vulkan fallback can retry the same type | Still present; guarded capacity is now consistent. A broader compatible-type search is a separate placement/fallback change |
| Vulkan fallback can mask the original error | Preserve current behavior here; error selection should accompany fallback redesign |
| Metal Shared texture helper can select Private through Unknown | Code/spec-supported finding; needs runtime reproduction and a resource-selection fix |
| Shared heaps on Intel Macs | Apple documents Private-only heap support there; fixing CPU-visible resources needs a backend strategy |
| Dynamic pressure recovery | Explicit trim is available, but automatic per-heap pressure and smaller-block retry remain future work |
| wgpu block-size mirror | A future allocation plan should replace minimum-based reservation estimates and duplicated rounding |
| Mapping accessible memory for GPU-only use | Accessibility and mapping intent could be separated in a later API; keep current getter behavior compatible here |

## 20 Validation limits and remaining uncertainty

The candidate passes formatting; 17 std unit tests; nine no_std tests; seven doctests (five intentionally ignored); strict Clippy for std, no_std and visualizer features; strict rustdoc; Apple ARM/Intel and Linux no_std checks; and physical Vulkan/D3D12 examples. The Apple ARM Metal no_std check also passes. The upstream Clippy configuration prints a pre-existing removed-lint warning; successful checks do not mean every tool emitted no warning.

Capacity/fallback, cache replacement, free-order invariants, trimming and regrowth are covered by behavioral tests. Hardware trimming and the unmodified downstream external-texture fixture pass. The complete combined wgpu cargo xtask test result is recorded in wgpu-full-tests.json and logs/wgpu-full-tests.log. Exact commands and exit codes accompany the validation logs. The declared Rust 1.71 minimum was not retested. Allocator checks use Rust 1.100.0; the full wgpu suite and its controls use the repository's Rust 1.97.1 pin.

The first full wgpu build stops before GPU tests because the optional Visual C++ ATL library is absent. Its failed result and log are preserved separately. A hash-verified Microsoft package supplies atls.lib inside this experiment, with a process-local LIB search path; the Visual Studio installation and global configuration are unchanged. Microsoft identifies ATL as an optional component. The recheck emits nonfatal missing-debug-PDB linker warnings for the supplied ATL objects. [Microsoft component list](https://learn.microsoft.com/en-us/visualstudio/install/workload-component-id-vs-community?view=visualstudio), [package verification](local-atl.json).

The api_dump follow-up has one access violation at vkDestroyDevice with cache2. Repeating the same layered run on unchanged PR 323 reproduces that teardown access violation on its second attempt. All ordinary diagnostic processes pass. This validates that the failure also occurs without the candidate changes; its precise layer/driver cause is not established. Trace timings are excluded, and the captured allocation inputs remain available. See trace-teardown-recheck.json and texture-api-traces/receipts.json.

Both exported candidate patches pass git apply --check against their exact bases. A fresh reconstruction verifies all nine allocator source trees after line-ending normalization. The final audit verifies original evidence and branch state again; no commits, pushes, PR updates or upstream comments were made.

The full wgpu run completes with 2,179 passes, 23 failures/aborts and three timeouts out of 2,205 tests, plus 18 profile exclusions. The 26-case matched control reproduces 24 with the unchanged allocator PR, leaves 1 unreproduced in both focused runs, and identifies 1 executable-path-sensitive case. The original full-run results are preserved; focused results do not replace them. Controls retain both wgpu patches and therefore do not prove independence from those patches. The precise root causes remain unestablished and need further backend/driver investigation. [Failure table](FAILURE_TRIAGE.md), [full structured comparison](failure-triage.json).

The asymmetric DX12 multiview result receives additional controls: five original-path PR passes versus five candidate failures; three passes per version at a common path; then eight candidate runs crossing path and logging. Identical candidate bytes fail four times at the original path and pass four times at the common path. Logging does not change that outcome, and staged WARP DLL hashes match. This establishes path sensitivity while leaving the underlying application-profile, cache, loader or driver cause unresolved. The full failure remains recorded; the experiment does not certify that every deployed executable path will work. [Path matrix](multiview-path-matrix.json).

Only Intel Arc UMA was used for physical Vulkan and D3D12 measurements. WARP was a supplementary property/correctness source. Published tables and synthetic tests cover other architectures; Metal compilation is not runtime validation.

The experiments do not establish performance under real discrete-GPU eviction pressure, WDDM residency churn, Android workloads or Apple hardware. Synthetic fault injection covers capacity and fallback correctness; it is not a measured real-OOM latency result. No claim of a universal optimum follows from five trials on one GPU.

Driver latency, desktop activity and unrecorded thermal state remain sources of variation. The measured cache ceiling is a compromise tied to existing application settings. Large recurring workloads may prefer a larger cache, while memory-constrained applications should use smaller settings and explicit trimming at known boundaries.

The recommendation is a coherent practical upstream contribution, with a clear route toward heap-aware pressure and application lifetime policy. The final review boundary preserves all existing branches and evidence.

