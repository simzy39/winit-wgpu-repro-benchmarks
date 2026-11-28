# Reclaim the other DX12 pool on OOM and roll back failed resource creation

Keep the general and transient pools, and release the active pool lock before trimming
the other pool on allocator OOM. Retry only when that reclamation removes cached
capacity. Before the existing budget preflight rejects a request, trim both pools and
requery process usage.

Return a placed allocation to its pool when native resource creation fails or returns
no resource, and drop any partial resource first. Apply the same cleanup when naming a
new resource fails. Two unit tests cover the resource-before-allocation destruction
order, null success and successful ownership transfer without requiring hardware.

This followup requires the new gpu-allocator cache/recovery APIs. It applies to PR11130's
head without requiring the lazy-allocation PR; combined validation also includes PR11129.
Publication requires an allocator release containing those APIs and the corresponding
wgpu dependency update; validation here uses the documented local workspace override.
The existing budget estimate remains approximate: it can reject reuse that requires no
new backing memory, and it does not predict the next growth step exactly. This patch
does not claim to solve budget-aware allocation planning.

Validation: both new HAL unit tests pass; 100 focused downstream processes complete
without workload failures. Separate pools save 48 MiB in two Performance workloads
against single-pool routing. The full suite passes 2,184 of 2,207 tests, with 23
failures/aborts and 18 profile exclusions. Twenty-two failures reproduce on clean
upstream; the historical DX12 multiview failure is basename-sensitive with an unresolved
native cause. The review report includes every failure, controls and measurement scope.
This is local proposed text for human review, not a submitted PR.
