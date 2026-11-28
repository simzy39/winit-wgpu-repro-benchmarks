# Source patches and dependencies

`source-pins.json` at the bundle root records each public PR head and its upstream base. The seven repository-named patches contain complete diffs from those bases, including the prerequisite commits in allocator #323. Prefer checking out the public PR commits when reproducing final-source checks.

The additional validation-only source [1cdcc63e82fffb19572d1a2a5aed8ad416217f35](https://github.com/simzy39/wgpu/commit/1cdcc63e82fffb19572d1a2a5aed8ad416217f35) combines #11152 and #11153 with the existing registry dependency. Its complete diff is `wgpu-rollback-surface-integration.patch`; it is not an additional production PR.

The prepared wgpu follow-up is split for review:

1. Start at wgpu #11130, commit `219e80584bdf325890a7111e8dc8e07163885fe4`.
2. Apply `wgpu-pool-with-rollback-registry-base.patch`. This integrates the independent #11152 ownership changes with pool routing, using the existing registry allocator. Actual Rust 1.95 `cargo check --locked -p wgpu-hal --all-features --lib` passes; see `checks/narrow-crosspool.json` and its raw log, relative to `final-source`.
3. `wgpu-crosspool-only-api-dependent.patch` adds only coordinated peer-cache reclamation and the post-reclamation budget check. **It requires the allocator API from #323.** It is preserved for a future normal dependency update after an actual release; it is not a compiling PR against today's dependency and includes no production override or guessed release version.

The separate `wgpu-crosspool-api-dependent-prepared.patch` preserves the historical consolidated implementation, including rollback, and applies to the rebased #11130 head. Use the narrower pair for future integration. The original validated consolidated source and measurements remain under `historical/pressure-recovery-20261128`.

Allocator #327 and #328 can merge independently before #323. wgpu #11129, #11130, #11152 and #11153 do not require the new allocator API. None of these contributions has been merged by this publication work.
