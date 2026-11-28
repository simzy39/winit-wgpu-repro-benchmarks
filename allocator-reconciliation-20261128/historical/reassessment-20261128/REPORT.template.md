# gpu-allocator PR 323 architecture and implementation recommendation

28 November 2026 Australia Sydney.

Adopt the resolved sizing policy, exact Vulkan heap cap, bounded cache of one empty block per memory type, and explicit trimming in an expanded PR 323. Keep the corrected maximum dedicated threshold and geometric growth. Interpret the existing host/device configuration through CPU accessibility; make capacity, placement, budgets and lifetime independent concerns.

The proposed cache keeps the largest eligible empty block through one growth step, bounded by min(2 × minimum, maximum). It can retain that block while other blocks remain live. This restores useful hysteresis without retaining every large burst. The larger-cache and demand-based alternatives below show why neither zero retention nor fewer heap calls alone determines the best policy.

{{FULL_VALIDATION_STATUS}}

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

{{GROWTH_TABLE}}

## 9 Retention and reclamation

The cache owns one index per memory type. Reusing that block clears the index. When a shared block becomes empty, the policy retains it if it is within the limit and larger than the existing cached block; otherwise it releases it. Replacing a cache releases the old empty block without moving live block slots.

The one-step limit follows the existing size configuration. Performance ranges allow a larger cache; MemoryUsage ranges retain a small one. It is a practical bound, not a claim about every application's working set. Explicit trim releases cached blocks and preserves live allocations and indices. Returned bytes describe allocator capacity removed; driver or resource references can affect physical release timing.

The local hardware check releases 8 MiB while a live allocation remains in a 4 MiB block, then reaches zero after that allocation is freed. Vulkan's mapped byte survives trimming. Larger-cache results quantify the alternative:

{{CACHE_LIMIT_TABLE}}

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

{{DIRECT_COUNTS}}

{{DIRECT_TABLE}}

Latency columns are process-level medians with complete trial ranges in [the full tables](DIRECT_RESULTS.md). Heap-creation latency remains variable. Identical block decisions do not establish identical driver timing; gains against main with overlapping ranges should not be read as proven algorithmic speedups.

{{OUTLIER_NOTE}}

Unused bytes include headroom and fragmentation. Free-gap dispersion is useful for the single-type fragmentation workload but is not an interchangeable cross-pool fragmentation percentage. The candidate preserves the free-list algorithm and does not relocate live resources.

{{NATIVE_REFERENCE_TABLE}}

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

{{PRACTICAL_DECISION}}

## 15 Public API and compatibility

Existing AllocationSizes constructors, private fields and the public get_memblock_size behavior remain compatible. The helper returns the configured growth step before hardware limits. Host means CPU-accessible, including accessible device-local types; device means CPU-inaccessible.

The additive trim method is the only public API addition. Configuration remains immutable. The per-type range removes configuration parameters and repeated classification from allocation and free paths.

Fixed block sizes remain fixed, but retention changes when another block is live: an empty block can now be cached alongside it. Explicitly configured growth and placement remain predictable. On small Vulkan heaps the resolved range can be smaller than the configured minimum to satisfy the API limit.

{{METADATA_TABLE}}

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

{{DOWNSTREAM_COUNTS}}

{{DOWNSTREAM_TABLE}}

{{DOWNSTREAM_INTERPRETATION}}

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

{{VALIDATION_SUMMARY}}

Only Intel Arc UMA was used for physical Vulkan and D3D12 measurements. WARP was a supplementary property/correctness source. Published tables and synthetic tests cover other architectures; Metal compilation is not runtime validation.

The experiments do not establish performance under real discrete-GPU eviction pressure, WDDM residency churn, Android workloads or Apple hardware. Synthetic fault injection covers capacity and fallback correctness; it is not a measured real-OOM latency result. No claim of a universal optimum follows from five trials on one GPU.

Driver latency, desktop activity and unrecorded thermal state remain sources of variation. The measured cache ceiling is a compromise tied to existing application settings. Large recurring workloads may prefer a larger cache, while memory-constrained applications should use smaller settings and explicit trimming at known boundaries.

The recommendation is a coherent practical upstream contribution, with a clear route toward heap-aware pressure and application lifetime policy. The final review boundary preserves all existing branches and evidence.

