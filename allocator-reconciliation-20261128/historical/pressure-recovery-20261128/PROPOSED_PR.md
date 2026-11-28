# Resolve block sizing and recover empty cached memory under pressure

Shared-block growth and empty caches can cause a GPU allocation to fail even when
the resource itself would fit. Resolve block sizes once per memory type using explicit
CPU accessibility, cap Vulkan blocks to their physical heap, and retain at most one
bounded empty block per type. Growth counts occupied shared blocks; an idle cache does
not advance the next step.

On recoverable native failure, reuse compatible Vulkan blocks, reclaim empty caches,
retry, and reduce shared-block sizes geometrically if preferred growth still fails. Native
fatal and allocation-count errors stop size retries immediately. Vulkan guards its owned allocation count before calling
the driver; Metal commits pending residency removals during reclamation. New blocks are
published only after their first suballocation succeeds, with rollback on failure.
Also return D3D12 convenience-API suballocations on placed-resource creation/option
errors, dropping any partial native resource first. Treat null-success output as an
internal error for placed and committed resources instead of panicking.

Add `cached_capacity()`, `trim()` and `trim_to(bytes)` on each backend. These use cached
indices, preserve live allocation indices, and report logical allocator capacity removed.
Vulkan also bounds combined empty retention by the physical heap size. External heap
references can delay native deallocation; these APIs do not wait for GPU work or enforce
an OS memory budget.

Validation: 43 std library tests and 10 no_std tests; strict Clippy including visualizer; current
compiler checks for both Apple architectures; actual Rust 1.71 consumer builds with
compatible dependency locks, including Metal cross-compilation. The README clarifies
the optional visualizer's higher dependency MSRV. The new direct comparison covers
210 processes across seven policies, two APIs and five trials, followed by 60 processes
comparing the pre-backoff Windows implementation with the prior candidate. Allocation plans
match the prior candidate in all 60 normal workload/configuration/API cells. Controlled
driver tests demonstrate recovery for cache pressure and oversized preferred growth.
The final backoff implementation matches the same 60 normal plan cells. Under a synthetic
48 MiB/two-block limit it serves all 48 one-MiB requests, while direct exact-size fallback
serves two. Backoff makes more native calls when no size can succeed; each step strictly
decreases size toward the aligned resource floor, with no arbitrary retry-count constant.
Metal keeps conservative exact-floor recovery because its failure result is untyped.

The geometric-policy full wgpu run passes 2,184 of 2,207 tests, with 23 failures/aborts
and 18 profile exclusions. Twenty-two failures reproduce on pristine upstream; the
remaining historical DX12 multiview failure depends on the executable basename, with
its native cause unresolved. The separately tested final convenience-API fix leaves
wgpu's allocator paths identical. These are review limitations, not a green native suite.
Full measurements, every failure and controls belong with the accompanying review report.
Metal pressure recovery has been typechecked
and reviewed against the native contracts; it still needs runtime validation on Apple
hardware before describing that backend as empirically verified.

This is proposed text for human review, not a submitted PR. The consolidated allocator
patch includes the approved-in-principle sizing/cache architecture; the pressure and
lifetime fixes can be reviewed as a followup series if that better fits upstream scope.
