# Final upstream reconciliation and publication

Publication snapshot: 29 November 2026 (Australia/Sydney). Measurements and source metadata retain their original recorded timestamps.

This report distinguishes confirmed source defects, reproducible native failures and unresolved component attribution. No upstream PR was merged and no repository protection was bypassed. RustyGUI's vendored dependencies were not part of any source edit.

## Contributions and exact heads

| Contribution | PR | Final commit | Status |
|---|---|---|---|
| Allocator sizing/cache/recovery | [PR](https://github.com/Traverse-Research/gpu-allocator/pull/323) | 693a9fb44e7d6effa20f988217524c61553f95fe | Updated; draft: Apple runtime/architecture review outstanding. |
| Allocator D3D12 rollback | [PR](https://github.com/Traverse-Research/gpu-allocator/pull/327) | 8b08388331e0479c965cd602557bbf8feade500c | Created; ready for review. |
| Vulkan native allocation contracts | [PR](https://github.com/Traverse-Research/gpu-allocator/pull/328) | 99e3979dae3a7c4e8300c33cea681a175f1b3747 | Created; ready for review. |
| Lazy external-texture parameters | [PR](https://github.com/gfx-rs/wgpu/pull/11129) | 19244b7c845bfcf17d57d73137a858ebef64eabb | Retained, rebased and updated; ready for review. |
| DX12 transient pool | [PR](https://github.com/gfx-rs/wgpu/pull/11130) | 219e80584bdf325890a7111e8dc8e07163885fe4 | Retained, rebased and updated; ready for review. |
| wgpu DX12 creation rollback | [PR](https://github.com/gfx-rs/wgpu/pull/11152) | 58e05c149e854c2312474182cd0a3ed08e66603f | Created; ready for review. |
| Surface reconfiguration test | [PR](https://github.com/gfx-rs/wgpu/pull/11153) | c79c064f4d3aa62382761c3cabb98cf6b1e6b56c | Independent test-only fix. |

No existing implementation PR was closed: both wgpu changes remain justified. The obsolete MSRV policy proposal [allocator#324](https://github.com/Traverse-Research/gpu-allocator/issues/324) was closed as not planned, with the compatible compiler evidence and links to the actual fixes. Historical issue/PR evidence and superseded patch snapshots remain preserved.

## Defect and issue coverage

| Confirmed source problem / requested control | Upstream issue | Contribution / disposition |
|---|---|---|
| Current growth step incorrectly becomes the dedicated threshold; oversized empty retention | [allocator#322](https://github.com/Traverse-Research/gpu-allocator/issues/322) | Updated #323 |
| Allocation fails while reclaimable caches remain; preferred block too large for current pressure | [allocator#329](https://github.com/Traverse-Research/gpu-allocator/issues/329) | #323 |
| Manual empty-cache release | Existing [allocator#96](https://github.com/Traverse-Research/gpu-allocator/issues/96) | Indexed cached_capacity/trim/trim_to in #323; comment added |
| Vulkan heap caps, duplicate/invalid fallback, fatal error masking and feature-dependent AMD selection | [allocator#326](https://github.com/Traverse-Research/gpu-allocator/issues/326) | #328 |
| Owned Vulkan allocation count can exceed the native limit | Existing [allocator#125](https://github.com/Traverse-Research/gpu-allocator/issues/125) | #328 guard; #323 reclaims caches. External allocation coordination remains caller responsibility |
| Allocator D3D12 convenience creation abandons reserved allocations on error | [allocator#325](https://github.com/Traverse-Research/gpu-allocator/issues/325) | #327 |
| wgpu placed-resource / SetName failures abandon allocations | [wgpu#11142](https://github.com/gfx-rs/wgpu/issues/11142) | Independent rollback PR |
| General/transient pools need peer-cache reclamation | [wgpu#11145](https://github.com/gfx-rs/wgpu/issues/11145) | Prepared narrow patch; actual allocator release required |
| Idle default external parameters and transient lifetime interference | Existing [wgpu#9818](https://github.com/gfx-rs/wgpu/issues/9818) | Retain #11129 and #11130 |
| Metal Shared texture descriptor becomes a Private wildcard allocation | [allocator#330](https://github.com/Traverse-Research/gpu-allocator/issues/330) | Source-confirmed; Apple runtime and a validated fix outstanding |
| Shared CPU placement heaps attempted on non-Apple macOS GPUs | [allocator#331](https://github.com/Traverse-Research/gpu-allocator/issues/331) | Native-contract finding; supported resource strategy/runtime validation outstanding |
| Surface test rejects successfully acquired Suboptimal frames | [wgpu#11150](https://github.com/gfx-rs/wgpu/issues/11150) | Independent test-only fix |

Success-with-null native output cleanup and first-suballocation rollback are defensive hardening, not separate reports of conforming native behavior. Normal failed vkMapMemory cleanup already existed upstream. CPU-accessibility classification is an explicit interpretation of existing size settings, not a claim that every old constructed heap was misclassified. No MSRV increase was needed.

Reproducible native failures have their own reports or existing coverage; a shared root cause is not inferred:

| Observation | Issue / existing coverage |
|---|---|
| Intel Vulkan ray/TLAS GPUAV-dependent aborts | [#11143](https://github.com/gfx-rs/wgpu/issues/11143) |
| Eight Intel Vulkan mesh fast-fails with validation DLL absent | [#11144](https://github.com/gfx-rs/wgpu/issues/11144) |
| DX12 f16 workgroup initialization returns ones | [#11146](https://github.com/gfx-rs/wgpu/issues/11146) |
| DX12 unaligned-row readback mismatch | [#11147](https://github.com/gfx-rs/wgpu/issues/11147) |
| Vulkan multisample multiview readback mismatch | [#11148](https://github.com/gfx-rs/wgpu/issues/11148) |
| Existing Naga deep-template test overflows its Windows debug stack | [#11149](https://github.com/gfx-rs/wgpu/issues/11149) |
| DX12 ray_cube_compute image threshold exceedance on clean upstream | [11154](https://github.com/gfx-rs/wgpu/issues/11154) |
| Clean-upstream ray-test timeouts and slow examples | [#11151](https://github.com/gfx-rs/wgpu/issues/11151) |
| Sampler rounding mismatch, same one-byte output | Existing [#8617](https://github.com/gfx-rs/wgpu/issues/8617); Windows/DX12 evidence added |
| Subgroup mask mismatch | Existing [#7163](https://github.com/gfx-rs/wgpu/issues/7163); related Windows/DX12 evidence added without claiming its Linux cause |
| Arc Computepass abort/device-loss family | Existing [#8644](https://github.com/gfx-rs/wgpu/issues/8644); controls added |
| DX12 Arc multiview, including executable-basename sensitivity | Existing [#8645](https://github.com/gfx-rs/wgpu/issues/8645); identical-byte controls added |

The intermediate-copy-buffer reset/drop leak is already covered by [#11068](https://github.com/gfx-rs/wgpu/issues/11068) and another contributor's [#11069](https://github.com/gfx-rs/wgpu/pull/11069). It was not duplicated or conflated with creation rollback or the row-content mismatch.

## Validation and comparative evidence

- Allocator D3D12 rollback: five public-constructor COM-stub regressions pass; four fail on main. Formatting, strict all-target Clippy and actual Rust 1.71 consumers with Windows 0.58 and minimum0.53 bindings pass.
- Vulkan correctness: ten public-constructor ash driver-stub regressions pass; nine fail before the fix. A stronger AMD case directly proves baseline selects the feature-dependent preferred type. Formatting, strict std/no_std Clippy and std 1.71/no_std 1.81 consumers pass.
- #323: 54 Windows std and 10 shared no_std tests pass; strict Clippy/rustdoc/formatting, actual std 1.71/no_std 1.81 consumers, minimum Windows bindings and current-compiler Apple ARM/Intel cross-compilation pass. Final strengthened tests were also linted. The b620867 plan measurement source and final 693a9fb successor differ only in a test module; production source is identical.
- #11129: independent formatting, strict core all-target/all-feature Clippy, actual Rust 1.95 and 41 focused passing harness entries. Of these,12 Vulkan entries are feature-unsupported;29 checks execute. DX12 Arc, bundled WARP and API validation cover concurrent first use, submit, zero initialization and queue drop. The first attempt's12 WARP metadata/runtime failures are preserved as rejected setup; the corrected DLL/metadata rerun passes.
- #11130: independent formatting, strict HAL Clippy, Rust 1.95, one sizing unit and three executed lifetime tests on Vulkan/Arc, DX12/Arc and WARP pass. Runtime source/Cargo.lock are unchanged by the rebase; the sole inherited upstream delta is the CI workflow.
- wgpu creation rollback: two ownership/drop-order unit tests, strict HAL Clippy, formatting and actual Rust 1.95 pass with the unchanged registry dependency.
- The private pool-plus-rollback integration base also compiles against the registry allocator on Rust 1.95. Its followup patch contains only peer reclamation and budget recheck, avoiding duplicate ownership changes.

The first fresh standalone rollback full native run has **2175 passing harness cases,22 failures/aborts and 5 timeouts among 2202**, with 18 profile exclusions. It is not green. Feature-unsupported/skipped-failure harness entries can be counted as passes by nextest; these counts are not all executed GPU workloads.

The historical integrated allocator/wgpu run has 2184/2207, 23 failures/aborts and 18 profile exclusions. Twenty-two failures reproduce on pristine upstream with registry gpu-allocator and none of our wgpu patches. Counts differ partly because branches contain different regression cases; they are not a before/after score for allocator quality.

The fresh paired ray control reuses a frozen pristine-upstream executable verified against the old seal. Three baseline test identities exceed 100 seconds. Candidate outcomes vary (DX12 TLAS passes, DX12 AABB times out, Vulkan BLAS compaction passes in the recorded trial). This bounds attribution; it is not a causal performance comparison. An isolated pristine Vulkan ray-AABB example passes with test-reported 80.15 seconds and measured whole-process wall time 104.05 seconds. These are different timing boundaries from the 90-second nextest termination; this is a slow clean control, not a matched same-mode timeout reproduction.

Historical policy evidence is reused: 210 independent processes across seven policies, 60 further direct comparison processes and 100 focused wgpu processes. Six publication-source native harness processes verify 60 normal allocation-plan cells with zero differences. Those new runs are plan checks, with no statistical latency claim. The selected cache remains one largest eligible block per type, bounded by min(2*minimum,maximum); Vulkan also caps aggregate empty retention across types sharing a heap to the physical heap size. More aggressive aggregate caps, alternative selection and packing did not universally improve the measured workloads.

| Historical comparison | Selected policy / split | Alternative |
|---|---:|---:|
| Performance repeated-upload retained reservation |144 MiB, separate pools |192 MiB, single pool |
| Performance sustained-render retained reservation |208 MiB, separate pools |256 MiB, single pool |
| Controlled Vulkan allocation path,48 MiB / two-block limit, one-MiB requests served |48, geometric fallback |2, exact-resource fallback |

The last row uses a synthetic intercepted native path, not a physical OS-budget promise. Raw trials, ranges, hashes and all rejected pilots are retained in the historical reports and final-source receipts. Release/coalescing can be delayed by external native references; trim reports logical allocator capacity.


Surface fix: formatting, strict test-target Clippy, actual Rust 1.95 compilation and six native repetitions pass (three Vulkan, three DX12). The existing regression now reaches view creation, rendering and presentation instead of rejecting the documented usable status.

Final combined validation run (standalone rollback plus surface test fix), source 1cdcc63e82fffb19572d1a2a5aed8ad416217f35: **2180 passing harness entries and 22 failures/aborts/timeouts among 2202**, plus 18 profile exclusions. This run is also not green. See the complete [failure ledger](final-source/checks/combined-native-analysis.json) and [JUnit](final-source/checks/rollback-surface-full-junit.xml.gz).
The exact combined source is [published in the contributor fork](https://github.com/simzy39/wgpu/commit/1cdcc63e82fffb19572d1a2a5aed8ad416217f35); its complete patch is included in the bundle.
The GPU-test executable hashes before and after this test-only integration match; changes in those outcomes do not establish an effect of the surface source change.
All 22 final failure identities have [upstream issue coverage](final-source/checks/final-failure-issue-map.json). No new failure identities appeared relative to the earlier standalone rollback run.

Windows native linking reports unavailable debug symbols for the supplied ATL library; linking completes, but native fault attribution remains limited. Render manifests distinguish newly written output from retained images after timeouts.
The public MSRV reproduction runner also passes against the final allocator head with the preserved std/Vulkan lock and actual Rust 1.71.

## Dependencies, merge order and blockers

1. Allocator #327 and #328 are independent correctness PRs on main. Merge them before #323, then rebase #323 to remove prerequisite commits from its review diff.
2. wgpu #11129, #11130, the creation rollback and surface test fix have no new allocator API dependency. Creation rollback and pool routing have a prepared, typechecked integration; resolve their small overlap when merging.
3. Merge/release the allocator APIs before submitting the normal dependency update plus cross-pool recovery. No future release number is guessed, and no production path/git override is introduced.
4. Apple runtime validation remains a material limit for new Metal cache/recovery/residency behavior. The outstanding Metal storage-selection/platform defects remain separately documented and unfixed.

DX12 multiview basename behavior, native ray/mesh failures and other reported output mismatches remain unresolved. Disabling GPUAV/validation in diagnostics is not a conformance pass or shipping workaround. The full native suite has never been represented as green.

## Changes beyond the reviewed candidate

- Split allocator D3D12 rollback and Vulkan native-contract fixes into independently reviewable PRs; keep sizing/cache/recovery together so a threshold change does not introduce oversized idle retention.
- Exclude feature-dependent AMD coherent types from automatic selection, with a direct preference-selection regression. No device-feature enablement is assumed.
- Replace standalone internal-field fixtures with public constructors; import size_of explicitly for old-compiler compatibility; preserve minimum Windows binding support.
- Rebase existing wgpu contributions onto current upstream, retain their meaningful regression tests and replace superseded descriptions with precise final-source/historical evidence.
- Prepare a registry-compatible pool/rollback integration and a narrow API-dependent recovery patch, retaining the historical consolidated patch as evidence.
- Correct the independently confirmed surface test expectation for a documented successful acquisition status.
- Close the unnecessary MSRV policy proposal; distinguish defensive hardening from confirmed public defects; add precise native reports without unsupported component blame.
- Publish reproducible source/harnesses, raw sanitized evidence, compatible consumer locks, source pins and integrity manifests. No executables, SDK libraries or vendored application dependencies are published.

All new commits use the contributor's public GitHub noreply identity. PRs disclose agent-created code/descriptions and leave human self-review unasserted. Publication authorization did not authorize merging.


The allocator classification concerns are answered in the original [D3D12](https://github.com/Traverse-Research/gpu-allocator/pull/323#discussion_r4726539855), [Metal](https://github.com/Traverse-Research/gpu-allocator/pull/323#discussion_r4726539979) and [Vulkan](https://github.com/Traverse-Research/gpu-allocator/pull/323#discussion_r4726540121) review threads. Maintainer approval is still outstanding.

## CI and review snapshot

- [Traverse-Research/gpu-allocator#323](https://github.com/Traverse-Research/gpu-allocator/pull/323): OPEN, draft=True, review=REVIEW_REQUIRED; No check results reported.
- [gfx-rs/wgpu#11129](https://github.com/gfx-rs/wgpu/pull/11129): OPEN, draft=False, review=REVIEW_REQUIRED; 2 neutral, 2 skipped, 65 success.
- [gfx-rs/wgpu#11130](https://github.com/gfx-rs/wgpu/pull/11130): OPEN, draft=False, review=REVIEW_REQUIRED; 2 neutral, 2 skipped, 65 success.
- [Traverse-Research/gpu-allocator#327](https://github.com/Traverse-Research/gpu-allocator/pull/327): OPEN, draft=False, review=REVIEW_REQUIRED; No check results reported.
- [Traverse-Research/gpu-allocator#328](https://github.com/Traverse-Research/gpu-allocator/pull/328): OPEN, draft=False, review=REVIEW_REQUIRED; No check results reported.
- [gfx-rs/wgpu#11152](https://github.com/gfx-rs/wgpu/pull/11152): OPEN, draft=False, review=REVIEW_REQUIRED; 2 neutral, 2 skipped, 65 success.
- [gfx-rs/wgpu#11153](https://github.com/gfx-rs/wgpu/pull/11153): OPEN, draft=False, review=REVIEW_REQUIRED; 2 neutral, 2 skipped, 65 success.

Review/CI states are a snapshot, not approval or a guarantee of future CI. Required maintainer review and repository protections remain in force. Complete raw snapshots are in final-source/checks/final-ci-review.json.

Preserved evidence: 438 entries (0 mismatches), 4317 entries (0 mismatches), 2691 entries (0 mismatches). Only explicitly excluded build caches were reclaimed.

Vendor audit: 411 files checked against the preserved inventory; 0 hash mismatches, 0 added files. No RustyGUI vendor edit was made.
