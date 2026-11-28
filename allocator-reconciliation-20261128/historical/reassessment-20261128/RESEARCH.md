# GPU allocation architecture research

Research date 28 November 2026 Australia Sydney. Source snapshots and their Git blob identities are in [sources](sources). This analysis distinguishes application resource allocation from driver paging and from allocation performed by GPU shader or CUDA threads.

## Allocation decisions need different information

Placement selects a compatible memory type and, indirectly, a physical heap. CPU accessibility constrains mapping and cache maintenance. Locality describes the GPU's access to physical memory. Neither property determines how much memory an application will need, how long a burst will last, or how much headroom the operating system currently allows.

A resource supplies size, alignment, compatible types and sometimes a driver requirement for dedicated memory. A shared pool supplies its free ranges, fragmentation and compatible resource classes. Growth chooses a new block only after existing blocks cannot satisfy that request. Reclamation chooses whether the latency saved by a cached block justifies its reservation. These are separate decisions, even when a compact implementation expresses several through one resolved range.

Physical heap size is a hard limit on an individual Vulkan allocation. It is not a reservation for the process. Dynamic budgets are estimates and can change between query and allocation. An allocator must handle failure even when a budget check passed. Several memory types can share one heap, so budget and reserved-byte accounting belong to the heap, while resource compatibility and free lists belong to the memory type. [Vulkan allocation requirements](https://docs.vulkan.org/refpages/latest/refpages/source/vkAllocateMemory.html), [Vulkan heap budgets](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceMemoryBudgetPropertiesEXT.html).

## Vulkan Memory Allocator

Current upstream source identifies itself as VMA 3.5.0. Its preferred block size depends on heap capacity: heaps at most 1 GiB use approximately one eighth of their capacity; larger heaps use the configured large-heap preference. It starts below that preferred size and can reduce new blocks under budget constraints. Large requests can prefer dedicated allocations. Freeing keeps an empty block as hysteresis unless another empty block exists or the heap is over budget.

This policy combines capacity, demand and caching rather than using CPU visibility as its sizing foundation. VMA also has richer type selection, pools, budget integration and allocation metadata. Copying its block formula without those surrounding mechanisms would produce a different allocator. The experimental policy inspired by VMA in this investigation is therefore named separately from the actual VMA reference.

The hardware reference uses VMA 3.3.0 bundled by vk-mem 0.5.0, with its native block defaults, explicit synchronization supplied by the single-threaded harness, matching memory types, and persistent mapping for CPU-visible allocations. Its settings are not equivalent to gpu-allocator's two application ranges. [VMA source](https://github.com/GPUOpen-LibrariesAndSDKs/VulkanMemoryAllocator/blob/master/include/vk_mem_alloc.h), [budget behavior](https://gpuopen-librariesandsdks.github.io/VulkanMemoryAllocator/html/staying_within_budget.html), [Rust wrapper](https://docs.rs/vk-mem/0.5.0/vk_mem/).

## Direct3D 12 Memory Allocator

Current D3D12MA source uses preferred block sizes, a greater-than-half-block preference for committed resources, fallback, empty-block hysteresis and budget-aware decisions. A preference for committed allocation is a heuristic within a larger fallback process, not a universal requirement that every such allocation be committed.

D3D12MA can use DXGI budgets and estimate when they are unavailable. Its documentation warns that creation latency is unpredictable and that successful allocations can still trigger migration or device removal under overcommitment. This supports measuring tails and operating-system usage alongside reserved bytes. It does not establish a single best block size for gpu-allocator. [D3D12MA source](https://github.com/GPUOpen-LibrariesAndSDKs/D3D12MemoryAllocator/blob/master/src/D3D12MemAlloc.cpp), [allocation guidance](https://gpuopen-librariesandsdks.github.io/D3D12MemoryAllocator/html/optimal_allocation.html).

## Dawn

Dawn's Vulkan allocator combines a per-memory-type buddy allocator with a separate pool of reusable heaps. The inspected source defaults to 8 MiB Vulkan heap blocks, constrains a buddy block to its heap capacity, and exposes allocator control. Its D3D12 buddy allocator uses a 4 MiB minimum heap block. Buddy allocation rounds suballocation sizes to powers of two, introducing a different internal-fragmentation trade-off from gpu-allocator's free list.

The pool returns reusable heaps and provides explicit removal of recycled allocations. Dawn also tracks execution serials and GPU lifetime. gpu-allocator has no equivalent queue completion model, so it cannot safely infer when a resource is no longer in use or when frame-scoped pools should be recycled. These are reasons to keep transient lifetime policy in wgpu even if core block growth improves. [Vulkan source](https://github.com/google/dawn/blob/main/src/dawn/native/vulkan/ResourceMemoryAllocatorVk.cpp), [D3D12 source](https://github.com/google/dawn/blob/main/src/dawn/native/d3d12/ResourceAllocatorManagerD3D12.cpp), [pool source](https://github.com/google/dawn/blob/main/src/dawn/native/PooledResourceMemoryAllocator.cpp), [buddy source](https://github.com/google/dawn/blob/main/src/dawn/native/BuddyMemoryAllocator.cpp).

## ANGLE

ANGLE's inspected Vulkan wrapper delegates allocation to VMA. It passes an application-selected preferred large block size and exposes custom pools, allocation requirements and property preferences. This supports separating application workload policy from allocation mechanics. It is not independent evidence that VMA's defaults are optimal for gpu-allocator. [ANGLE wrapper](https://github.com/google/angle/blob/main/src/libANGLE/renderer/vulkan/vk_mem_alloc_wrapper.cpp).

## Mesa

The inspected amdgpu winsys source combines slab suballocation, reusable buffer-object caching, alignment to driver page sizes, placement flags and reclamation. Reclamation tests whether objects are idle; it cannot free an object merely because the CPU-side producer dropped its reference. It can release cached objects when allocation fails.

This is driver code with access to fences, kernel domains and virtual-address management that gpu-allocator does not possess. Reusing its distinction between suballocation, backing-object caching and pressure recovery is reasonable; adopting its heuristics or GPU-idle assumptions directly is not. The snapshot was obtained from an upstream-source mirror because the official GitLab page was inaccessible through the browser. [Inspected source mirror](https://github.com/chaotic-cx/mesa-mirror/blob/main/src/gallium/winsys/amdgpu/drm/amdgpu_bo.c), [official source location](https://gitlab.freedesktop.org/mesa/mesa/-/blob/main/src/gallium/winsys/amdgpu/drm/amdgpu_bo.c).

## Academic research and its applicability

GMLake addresses fragmentation in DNN frameworks using virtual memory stitching to combine non-contiguous physical allocations. Its results depend on CUDA virtual memory operations and training workloads. Applying that technique to arbitrary Vulkan, Metal and D3D12 resource allocations would require different binding and resource-lifetime machinery. The useful lesson here is that allocation demand, free-range fragmentation and physical reservation must be measured separately. [GMLake ASPLOS 2024](https://arxiv.org/abs/2401.08156).

Throughput-Oriented GPU Memory Allocation studies device-side concurrent allocation with thousands of GPU threads. Its synchronization mechanisms target a different bottleneck from this CPU-side allocator, whose API requires mutable access. Its reported throughput ratios cannot predict heap-creation latency or justify changing gpu-allocator's free list. [Gelado and Garland PPoPP 2019](https://research.nvidia.com/sites/default/files/pubs/2019-02_Throughput-oriented-GPU-memory/paper.pdf).

## CPU visibility and public configuration

CPU visibility is insufficient as the primary foundation for an ideal allocator. It says neither that a heap is small nor that the workload is transient. ReBAR can make most VRAM visible; UMA can expose distinct private and shared resource types backed by the same system memory. The same CPU-visible type can hold long-lived dynamic buffers and short-lived staging resources.

CPU visibility should continue to interpret the existing host/device configuration. Changing that interpretation silently would override explicit application choices. Resolving the selected range at type construction is appropriate because AllocationSizes is immutable after allocator construction. Store static resolved sizes per type, use the existing Vulkan mappable property as the authoritative accessibility input, and apply physical capacity independently. Runtime pressure and demand are separate policy inputs rather than reasons to reinterpret the word host.

On D3D12, recognize UPLOAD, READBACK and GPU_UPLOAD explicitly. For CUSTOM heaps, recognize WRITE_COMBINE and WRITE_BACK explicitly; UNKNOWN and undocumented integer values must not accidentally become evidence of CPU accessibility. The supported windows 0.62 bindings include D3D12_HEAP_TYPE_GPU_UPLOAD, so a numeric literal is unnecessary. DEFAULT is not mappable even on UMA. [Microsoft heap types](https://learn.microsoft.com/en-us/windows/win32/api/d3d12/ne-d3d12-d3d12_heap_type), [GPU upload specification](https://github.com/microsoft/DirectX-Specs/blob/master/d3d/D3D12GPUUploadHeaps.md).

Metal Shared and Private describe access and storage behavior, not separate physical RAM on Apple silicon. Current gpu-allocator constructs only those placement heaps. Managed is CPU-accessible as a resource storage mode but is not a supported heap storage mode. The classifier should describe reachable heap modes rather than imply Managed heaps are supported. Intel Macs require Private heaps; repairing CPU-visible allocation there needs a backend-specific resource strategy. [Apple heap storage modes](https://developer.apple.com/documentation/metal/mtlheapdescriptor/storagemode.md).

## Policy alternatives

| Policy | Strength | Cost or missing input | Appropriate use |
|---|---|---|---|
| Existing two ranges interpreted by visibility | Predictable application control and compatibility | Workload and capacity are not encoded | Configuration interpretation |
| Locality selects the two ranges | Simple | Silently changes UMA and ReBAR settings; no capacity protection | Reject as a replacement |
| Capacity-derived preferred blocks | Sensible small-heap defaults | Does not know process pressure or lifetime | Future opt-in defaults plus a hard cap now |
| Budget-aware growth | Can avoid speculative reservation under pressure | Requires extension/platform state and handles stale estimates | Backend pressure input |
| Fixed blocks | Simple and stable | Over-reserves small workloads or creates many blocks | Explicit fixed configuration |
| Geometric growth by active block count | Amortizes backing allocations | Active count is only a coarse demand signal; can over-round a request | Compatible practical default |
| Rounded request-sized blocks | Limits a new block's excess bytes | Often one heap per medium resource; little amortization | Experimental memory-focused policy |
| Demand-limited growth | Restrains geometric growth for small requests | Repeated small allocations can create many blocks and scans | Experimental workload policy |
| Dedicated threshold at configured maximum | Honors existing documented contract | Large shared blocks may contain little useful headroom | Practical compatibility |
| Dedicated preference near half a block | Avoids poorly utilized large shared blocks | Can increase repeated heap churn; changes contract | Evaluate as an explicit future policy |
| Retain only minimum-sized final block | Low retention | Recreates every larger recurring burst | Current PR trade-off |
| Retain final block through one growth step | Small bounded cache and fewer recurring creations | Still depends on free order; no full working-set cache | Practical candidate |
| Retain one empty block alongside live blocks | Stronger reuse and hysteresis | Needs cache tracking and a pressure/trim mechanism | Implemented practical candidate |
| Adaptive retention or timers | Can recognize temporal reuse | More state, tuning and unpredictable behavior | No present justification |
| Explicit trimming | Deterministic application control | Caller chooses pressure or lifetime boundary | Additive API candidate |
| Background reclamation | May hide reclamation latency | Threads, synchronization and missing lifetime knowledge | No present justification |

## Long term ownership model

Use three levels of responsibility. The application supplies workload and lifetime intent, explicit preferences, and pressure notifications. A memory type owns compatibility and its free ranges. A physical heap or D3D12 memory segment owns aggregate reservation and dynamic budget state. Metal's recommendedMaxWorkingSetSize is a process-level recommendation rather than a hard per-heap size and needs a corresponding backend policy.

Keep static resolved configuration separate from dynamic state. New-block planning can consume a size/alignment request, current reusable ranges and an optional pressure snapshot. The same plan should be observable by downstream budget checks so wgpu need not estimate a potentially 256 MiB block with a 4 MiB minimum. An estimate must account for reuse as well as new reservation and remain advisory because the OS budget can change immediately.

A practical evolution can add explicit trimming first, then a planning or pressure interface with discrete-device evidence. An internal min/max value is sufficient for the static part; introducing a public hierarchy of policy traits, timers or allocation classes now would make the API harder to maintain without establishing better behavior.

