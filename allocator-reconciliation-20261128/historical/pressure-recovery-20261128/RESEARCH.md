# Pressure-recovery design evidence

This continuation reuses the frozen VMA 3.5, D3D12MA, Dawn, ANGLE and Mesa sources in
the [previous source archive](../reassessment-20261128/sources/). Previous measurements
remain separate. New experiments compare the previous candidate with implementations
of smallest-cache selection, aggregate heap limits and occupied-block-first placement.

## Native failure contracts

[Vulkan's allocation specification](https://docs.vulkan.org/refpages/latest/refpages/source/vkAllocateMemory.html)
distinguishes host/device memory exhaustion from other failures. A block may not exceed
its heap's declared size. The allocation-count limit is a valid-usage requirement;
historical `ERROR_TOO_MANY_OBJECTS` behavior is not a reliable way to enforce it. The
candidate therefore guards its own allocation count before new native allocations,
reclaims empty blocks, and never treats a count failure as a reason to retry a smaller
block. Other users of the same device remain responsible for their own allocations.

The frozen VMA source, `VmaBlockVector::AllocatePage`, retries smaller blocks with a
bounded sequence of halvings and has budget-dependent allocation decisions. It is useful
precedent for bounded recovery, but its shift limit is not copied into this allocator.
The exact-floor alternative was implemented first, then compared with geometric
reduction using the actual library and identical intercepted native calls. With a
48 MiB budget and two-block limit, 48 requests of 1 MiB produced only two successful
allocations with exact-floor fallback; geometric reduction served all 48 using
32 MiB and 16 MiB blocks. Conversely, zero available memory needed two failed calls
with exact fallback and seven with geometric reduction. A 9 MiB request within a
12 MiB budget needed two versus four calls. [Actual driver streams](reduction-actual.json)
are distinct from the illustrative [pure model](reduction-model.json).

The candidate therefore halves typed Vulkan/D3D12 memory failures toward the aligned
resource floor. Each attempt is strictly smaller; termination follows from the size
domain rather than an arbitrary attempt limit. This favors useful sharing when native
block count is constrained, at the cost of more failed calls when memory is exhausted.
Metal retains one exact-floor attempt because its `nil` result does not identify a
typed memory failure. Neither choice predicts the driver's available budget.

[Microsoft's heap descriptor documentation](https://learn.microsoft.com/en-us/windows/win32/api/d3d12/ns-d3d12-d3d12_heap_desc)
permits non-aligned `SizeInBytes`, while recommending multiples of the effective
alignment to avoid wasted memory. The existing backend uses 4 MiB heap alignment;
its pressure fallback therefore rounds the requested resource size up to that alignment.
Normal successful sizing is preserved. Only `E_OUTOFMEMORY` triggers D3D12 recovery;
other native errors remain diagnostic failures.

[Apple's heap creation contract](https://developer.apple.com/documentation/metal/mtldevice/makeheap%28descriptor%3A%29.md)
provides a heap on success and `nil` on failure, without a reason code. The candidate
allows bounded reclamation/retry for this result while preserving the public creation
failure diagnostic. It does not claim that every `nil` means memory exhaustion.

Metal residency sets require additional handling. [`removeAllocation`](https://developer.apple.com/documentation/metal/mtlresidencyset/removeallocation%28_%3A%29.md)
stages membership removal, and [`commit`](https://developer.apple.com/documentation/metal/mtlresidencyset/commit%28%29.md)
applies pending membership changes. Merely dropping the allocator's heap reference is
therefore insufficient evidence that a residency-managed heap has become reclaimable.
The implementation tracks pending removals from earlier ordinary frees as well as caches
released during the current failure, and batches a commit in `trim`/`trim_to`. Recovery
can retry after that commit even when no logical cache bytes were removed by the current
call. Committing this allocator's residency set also applies any other pending changes
to that set; this side effect is documented. External references can still delay release.

## Cache control and budgets

An empty cache is not reusable across incompatible memory types. A fixed aggregate
allowance derived from one type's cache size can evict another useful type's cache,
even when there is abundant physical capacity. The `heapcap` experiment implements
that alternative rather than assuming the effect. The candidate also enforces an
intrinsic Vulkan bound: empty caches sharing a heap cannot exceed the entire heap size.
This is distinct from a changing process budget or an arbitrary fraction of VRAM.

`cached_capacity`, `trim` and `trim_to` distinguish empty retained blocks from unused
space inside live blocks. The partial operation removes whole blocks largest first,
making a byte target predictable without allocating a sorting buffer on a pressure
path. Indices remain stable, and selection visits memory types rather than historical
block slots. Releasing allocator ownership does not promise immediate physical release
when a client or Metal residency machinery holds another native reference.

The candidate reclaims all its empty caches after a recoverable native failure. That
can evict a cache on an unrelated heap; it is a deliberately conservative pressure path,
not a heap-budget prediction system. Vulkan host-memory exhaustion and mapped-address
pressure can have broader scope than a single device heap. Normal successful allocation
does not perform reclamation or a budget query.

## Rust compatibility

[Cargo's Rust-version guidance](https://doc.rust-lang.org/stable/cargo/reference/rust-version.html)
and [resolver documentation](https://doc.rust-lang.org/stable/cargo/reference/resolver.html)
separate package compatibility from dependency resolution. Rust 1.71 builds in this
bundle use explicit compatible locks rather than assuming that every newer dependency
allowed by a broad range supports the same compiler. The newer Rust-aware resolver is
not available in Cargo 1.71. Both initial resolution failures and successful locked
builds are retained.

The oldest permitted [egui release's workspace manifest](https://raw.githubusercontent.com/emilk/egui/0.24.1/Cargo.toml)
declares Rust 1.72; the current permitted egui 0.27.2 build rejects Rust 1.71 too. The
optional visualizer therefore needs a separate compatibility qualification. Source and
dependency manifests, actual Rust 1.71 compiler logs and the README correction provide
the evidence; no compiler-version bump is used to conceal an existing optional-feature
or dependency-selection issue.
