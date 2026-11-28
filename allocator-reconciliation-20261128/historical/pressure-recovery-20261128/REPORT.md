# gpu-allocator PR #323: pressure recovery and final upstream candidate

Review date: 28 November 2026. This continues the completed
[architectural reassessment](../reassessment-20261128/REPORT.md); it does not replace or
rewrite its research, hardware tables, measurements or failure records.

## Recommendation and review boundary

Use resolved per-type sizing, explicit CPU accessibility, exact Vulkan heap caps,
bounded empty caching and occupied-block growth. Add automatic recovery that reuses
compatible blocks, reclaims caches and retries before reducing preferred shared-block
sizes. For typed Vulkan/D3D12 memory failures, geometric reduction is preferable to a
single exact-resource-sized fallback when heap count constrains useful sharing. Keep
Metal's untyped failure handling conservative, and commit staged residency removals
when requesting reclamation.

Retain one largest eligible empty block per type and the existing placement order.
The implemented smallest-cache, aggressive aggregate-cap and packing alternatives do
not provide a better default across these measurements. Bound Vulkan's aggregate
empty retention by its physical heap size; expose application-controlled aggregate
retention through indexed `cached_capacity()`, `trim()` and `trim_to(bytes)` APIs.

Keep wgpu's general/transient split. A single-pool-routing implementation increases
reservation in two measured workloads even with the improved allocator. The proposed
followup adds cross-pool reclamation without nested locks and repairs placed-resource
rollback. The allocator's own D3D12 convenience resource API also needs rollback on
creation errors; the final lifetime audit tests this separately.

This is a source candidate for review, **not publication approval**. No commits, pushes,
PR updates or changes to RustyGUI's vendored dependencies are part of this work.
Apple runtime validation and unresolved native wgpu failures remain material limits.

## Review artifacts and provenance

| Artifact | Purpose |
|---|---|
| [Complete allocator source](candidate-source/) | All 36 tracked files, including both new backend regression modules |
| [Allocator patch on PR323](patches/candidate-on-pr323-179ea43.patch) | Consolidated review change on `179ea43f05332c2809addd7922cd056220efc36b` |
| [Allocator patch on main](patches/candidate-on-main-fc22df0.patch) | Same result on `fc22df05140b15ed6d764beabd12a1b807011bc5` |
| [wgpu HAL followup](patches/wgpu-pressure-followup-on-pr11130-22827ee.patch) | Applies to PR11130 `22827ee25285b56c4056fe6bb1de27917caf45a9`; needs the allocator APIs |
| [wgpu combined patch](patches/wgpu-combined-on-base-60cef2b.patch) | Both earlier PRs, regressions and followup on `60cef2be828e03ba54e2e1598001b4625c0c2163` |
| [Complete changed wgpu files](wgpu-source-changes/) | All seven changed source files for direct inspection |
| [Patch manifest](patches/manifest.json) | Base IDs, SHA-256 digests and replay checks |
| [Allocator PR description](PROPOSED_PR.md), [wgpu PR description](PROPOSED_WGPU_PR.md) | Proposed text, never submitted |
| [Reproduction guide](REPRODUCE.md), [native-contract research](RESEARCH.md) | Commands, locks, inputs and primary references |

Each allocator patch was applied to a clean archived base and compared against all
36 files using Git canonical blob hashes, accounting for Windows line endings.
The HAL-only followup was also replayed against its exact PR head. Local workspace
dependency overrides and lock changes are excluded from the wgpu exports. Earlier
exact-fallback source/patches and all measured policy alternatives remain available.
The combined wgpu patch also applies to a full clean archive and matches all 2,757
tracked files after excluding the three local test configuration/lock files.

## Allocation and recovery invariants

Sizing is resolved once per memory type. CPU accessibility interprets the existing
host/device settings; heap capacity, resource compatibility, placement, lifetime and
budgets remain separate inputs. Vulkan uses `HOST_VISIBLE`, D3D12 uses standard heap
types or explicit custom CPU page properties, and Metal uses storage mode. The
GPU_UPLOAD value remains compatible with older permitted Windows bindings. Explicit
Vulkan dedicated-buffer/image schemes preserve their native allocation chains.

A shared block grows according to occupied shared blocks, excluding the idle cached
block. Its maximum is also the personal-block threshold. Vulkan caps both bounds to
the exact physical heap size, including heaps below the configured minimum. Requests
that exceed every compatible heap fail without an oversized native allocation.

The failure path follows these rules:

1. Try the normal selected type, including existing blocks. On Vulkan pressure, first
   search existing blocks in the other compatible types, preserving usable caches.
2. On a recoverable cause, release this allocator's empty caches. Retry preferred
   growth if reclamation actually released capacity. Metal also retries when its own
   residency commit applies earlier removals, even if current logical bytes are zero.
3. For typed Vulkan/D3D12 memory failures, halve toward the aligned resource floor,
   requiring strict size decrease at each attempt. D3D12 rounds the floor to its
   existing 4 MiB heap alignment. Metal tries its exact resource floor once because
   `nil` does not classify the cause. Explicit dedicated allocations do not shrink.
4. Fatal native errors stop immediately. Allocation-count failures may reclaim/retry,
   but never shrink. Vulkan guards its own live native-block count before allocation;
   reuse remains possible at the limit. External users of the same device must still
   obey the device-wide limit.

Private failure categories preserve backend causes without adding public error enum
variants or matching diagnostic strings. Vulkan host/device OOM and known mapping
pressure are recoverable. Failed mapping frees memory; an anomalous success with a
null mapping unmaps/frees and stops as an internal error. D3D12 recovery requires
`E_OUTOFMEMORY`. Metal preserves the existing public internal-error diagnostic for
heap-creation failure while allowing bounded recovery privately.

New native blocks are published, counted and assigned stable slots only after their
first suballocation succeeds. Failure destroys the unpublished block and preserves
live indices/counters. An impossible first-suballocation OOM becomes a public internal
error rather than triggering pressure retries. Failed overall allocations can evict
empty caches; atomicity here means no leaked native block, live suballocation or
partially published allocator entry, not that caches remain unchanged.

## Cache policy, aggregate retention and public API

Each type retains at most one empty shared block, bounded by `min(2 * min, max)`.
The largest eligible block wins. This bound comes from the configured growth sequence;
it is a practical default, not an inferred application working set. Separate types and
allocator instances can multiply retention. Vulkan additionally ensures empty caches
sharing a physical heap do not exceed that heap's declared size. This intrinsic cap
does not establish safety against a changing OS budget or double-counting on UMA.

The aggressive experimental heap cap derives a whole-heap allowance from a single
type's cache allowance. It reduces retention in four cells but increases creation
count and peak capacity in two. There is no evidence for imposing that arbitrary
cross-type coupling by default. D3D12's backend does not own a Vulkan-like static heap
capacity or an exact current budget; no invented physical cap is added there.

`trim()` is a small, familiar explicit release operation, complemented by a measurable
`cached_capacity()` and partial `trim_to(bytes)`. The byte target applies only to empty
retained capacity. Partial trimming releases whole blocks largest first and may go
below the target. This is easier to use predictably than requiring callers to issue
per-type release operations; it does not conflate free regions inside live blocks with
reclaimable blocks or promise control of process VRAM usage.

All three APIs use cached-block indices. Full trimming visits memory types; partial
trimming makes bounded repeated type scans without a sorting allocation, at most
quadratic in the number of types (Vulkan has at most 32). They never walk the historical
block-slot vector. A regression includes 100,000 vacant historical slots. Ordinary
allocation still uses the existing reverse slot traversal, avoiding a new placement
policy or index compaction. Live allocation indices remain stable.

Returned bytes describe allocator capacity relinquished. D3D12 COM references, retained
Metal allocations/heaps/resources and pending GPU use can prevent immediate native
deallocation. Metal `trim`/`trim_to` commits pending changes to the allocator's own
residency set, including changes staged before the call. Ordinary free preserves
batching. These APIs do not wait for GPU work; clients must obey existing lifetime rules.

Automatic recovery deliberately reclaims all own empty caches, including unrelated
heaps: host-memory and mapping pressure need not be local to one device heap. Successful
allocations do not query budgets or trigger pressure reclamation. No background timer,
global cache registry, policy-trait hierarchy or arbitrary attempt-count limit is added.

## Comparative measurements

The machine and runtime match the prior bundle: Windows 11 build 26300, Core Ultra 7
155H, Intel Arc integrated graphics, driver 31.0.101.5328. Direct/downstream benchmark
builds use Rust 1.100.0; the full wgpu suite follows its Rust 1.97.1 pin. This is one
UMA system, not runtime evidence for discrete/ReBAR/mobile/Apple hardware. The previous
published memory tables and native allocator research remain applicable within their
original scope.

Accepted new data comprises **376 processes**: 210 seven-policy direct comparisons,
60 matched pre-geometric A/B processes, 100 downstream processes and six geometric
normal-plan verification processes. That is 2,760 direct workload records and 100
downstream records. Policy/timing experiments use five trials; six final verification
processes are single-run plan checks, not a new statistical timing experiment.

Every accepted comparison uses a unique Cargo target per source combination, source
hashes, binary/lock hashes and compile logs showing the changed local crates were
rebuilt. Variants run sequentially with interleaved order and settling; compilers and
GPU validation runs are excluded from timing periods. Requirement preparation/reporting
are outside direct allocator-call intervals. Complete medians and trial ranges remain
in [direct CSV](direct-summary.csv), [matched A/B CSV](final-pair-summary.csv) and
[downstream CSV](downstream-summary.csv), with raw data/receipts under `results/`.

An initial shared-target setup reused another variant's allocator artifact despite
package-specific cleaning. `results/direct/`, `bin/` and `bin-wgpu/` are explicitly
**invalid** and excluded. The rejected raw evidence remains archived. Accepted runs
were rebuilt with isolated targets and verified compile/source receipts.

### Alternatives across 60 API/configuration/workload cells

All block-decision fields are stable across the five trials.

| Compared with prior bounded candidate | Lower retained capacity | Higher heap creations | Higher peak capacity | Decision |
|---|---:|---:|---:|---|
| Recovery prototype | 0 | 0 | 0 | Preserve normal plans; improve cold failure handling |
| Smallest eligible cache | 34 | 2 | 0 | Keep as measured alternative; default retains useful sharing |
| Aggressive aggregate cap | 4 | 2 | 2 | Reject derived cross-type allowance |
| Occupied-block-first placement | 0 | 0 | 0 | Preserve simpler existing placement |

The 60-process matched A/B after rollback/Metal fixes again matches all 60 normal plan
cells. Final geometric-source verification matches all 60 cells too. These do not prove
identical latency: native allocation/commitment and scheduling vary even with identical
plans. Five-trial timings describe the **pre-geometric implementation**, not exact final
source. Later geometric changes affect failure handling; convenience resource rollback
does not change the benchmark's direct `allocate`/`free` path. No final-code statistical
speedup or whole-process CPU improvement is claimed. This continuation did not sample
whole-process CPU totals; previous CPU evidence remains separate.

For scale, the accepted seven-policy D3D12 MemoryUsage results below compare against
the actual original main/PR sources. Values are creations / peak MiB / retained MiB:

| Workload | Main | PR323 | Prior bounded candidate | Recovery prototype |
|---|---|---|---|---|
| Mixed frames | 115 / 148 / 76 | 115 / 148 / 4 | 7 / 136 / 28 | 7 / 136 / 28 |
| Upload ring | 53 / 92 / 32 | 53 / 92 / 0 | 5 / 92 / 8 | 5 / 92 / 8 |
| Sporadic long-lived | 41 / 156 / 4 | 41 / 156 / 4 | 30 / 156 / 8 | 30 / 156 / 8 |

Caching trades retained capacity for avoided creation calls; PR323's lower empty
retention in some rows remains visible. Historical main/PR/bounded-candidate plan
results were reused only after [180/180 repeated cells matched](reuse-audit.json).
Old absolute timings are never pooled with these new runs.

### Recovery and reduction experiments

Identical intercepted native-driver streams show that the prior bounded cache alone
fails when an 8 MiB empty cache in another type prevents 16 MiB preferred growth.
Recovery releases that cache and succeeds on retry under a 24 MiB live-byte limit.
The exact-fallback prototype also succeeds at a 9 MiB resource when preferred 16 MiB
growth exceeds a 12 MiB limit; the prior candidate fails. Fatal errors make one native
attempt in both implementations. [Streams](pressure-comparison.json)

The stronger alternative comparison uses the actual library, not only a sizing model:

| Driver/request constraint | Exact-floor fallback | Geometric reduction |
|---|---|---|
| 48 MiB, two blocks, 48 requests of 1 MiB | 2 successes; attempts 64,1,64,1 MiB | 48 successes; attempts 64,32,64,32,16 MiB |
| No available memory, one 1 MiB request | 2 failed calls: 64,1 | 7 failed calls: 64,32,16,8,4,2,1 |
| 12 MiB available, one 9 MiB request | Success after 64,9 | Success after 64,32,16,9 |

These are deliberate deterministic fault injections. They establish algorithm behavior
and the extra-call tradeoff; they do not measure physical OOM latency or justify inducing
device-wide OOM on this machine. Source, tests and logs are retained in
`reduction-controls/` and [reduction-actual.json](reduction-actual.json). The pure model
is separately labeled. Dedicated chain/flags, fatal errors, mapping rollback, count
limits, external COM references, first-suballocation failure and stable slots have
permanent library regressions.

### wgpu PR11130

The four-way DX12 experiment has 20 cells, five trials each and no workload failures.
It compares the prior allocator/both patches, new allocator/both patches, new allocator/
HAL followup and new allocator/single-pool routing. The latter routes requests to the
general pool; it does not pretend to be a complete mutex/architecture merger.

| Workload/settings | Existing two pools | Followup two pools | Single routing |
|---|---:|---:|---:|
| Performance idle, peak MiB | 128 | 128 | 128 |
| Performance repeated uploads, peak MiB | 144 | 144 | 192 |
| Performance sustained render, peak MiB | 208 | 208 | 256 |
| MemoryUsage churn, peak / after resources MiB | 92 / 28 | 92 / 28 | 92 / 28 |
| Manual 8–256 large textures, peak / after resources MiB | 524 / 12 | 524 / 12 | 524 / 12 |

Normal recovery-source behavior matches the old allocator in this focused comparison;
the cold geometric policy was added later. OS/private-memory and operation latency
samples remain in the [full downstream tables](DOWNSTREAM_RESULTS.md). These workload
results support keeping lifetime pools even though the allocator's cache is now bounded.
Lazy external-texture initialization remains useful independently; the prior factorial
already measures its interaction with the pool split and is not needlessly repeated.

The followup drops the active pool lock before trimming the other pool, then retries
only if capacity was released. Both pools are trimmed and usage requeried before the
existing budget preflight refuses a request. Failed/null placed creation and naming
failure drop any resource before freeing its allocation. Two hardware-independent
HAL unit tests exercise rollback order and successful ownership transfer.

The budget preflight remains approximate: it can reject a request that would reuse a
live block without new reservation and can underestimate the next growth step. Removing
that policy or introducing an exact planning API would be a separate scope decision.
The followup does not claim to solve this limitation or eliminate races in OS budgets.
The HAL followup applies directly to PR11130 without lazy-allocation source dependencies;
the combined validation includes PR11129 as well.
Publishing the wgpu followup requires an allocator release containing the new APIs and
a corresponding dependency update. Local validation uses the documented workspace
override; this review candidate does not invent a future crates.io release version.

## Validation and native failures

The final source passes **43 std library tests and 10 no_std tests**, strict project
Clippy for both modes and visualizer, rustdoc, formatting, Apple ARM Clippy/Intel
cross-checks and actual Rust 1.71 consumer builds. Commands/results are in
[handoff-source-checks.json](handoff-source-checks.json) and
[visualizer receipt](handoff-visualizer-clippy.json). The earlier geometric stage had
38 std tests; the final five exercise convenience-resource rollback/ownership. The
identical four failing control tests all reproduce with the old convenience function;
fixed source passes them and successful ownership transfer. Source/test hashes and
[comparison logs](lifetime-comparison.json) make this independent of GPU hardware.
Only `create_resource` and its regression module differ from the full native suite's
allocator source; [the exact source delta](handoff-source-delta.json) verifies that all
allocation/recovery paths and other backends remain identical.
The final wgpu source differs from its full-suite snapshot only in three documentation
comment lines explaining the bounded cache; [the comment receipt](sources/wgpu-comment-delta.json)
and saved full-suite file preserve that distinction.

The first full wgpu run executed 2,207 tests: 2,183 passed and 24 failed, with 18 tests
excluded by the default profile. Its new `compile_fail` failure came from the local
dependency override being absent in trybuild's generated external workspace. Moving
the test-only override to the root workspace patch table fixes it; the actual full-suite
compile-test executable passes. That setup failure and the initially mislocated JUnit
copy are preserved, with authoritative corrected output and explanations.

The geometric-policy rerun executes **2,207 tests: 2,184 pass and 23 fail/abort**,
with 18 profile exclusions and no new failure names. `compile_fail` passes in that full
run. Twenty-two final failures also fail pristine upstream; DX12 multiview is the
historical basename-sensitive exception discussed below. The complete individual
[failure table and controls](VALIDATION_FAILURES.md) and
[structured triage](backoff-failure-triage.json) preserve every outcome. The native suite
is not green. This full run precedes only the separately tested D3D12 convenience-API
fix; its `allocate`/`free` path is identical to final source.

Clean upstream controls contain no wgpu patches and use the registry allocator. The
exact historical 26-case failure set yields 22 failures and four passes. Current fetched
trunk differs from the pinned base only in two CI action dependency updates; no runtime
source differs. Source status and Cargo.lock were clean. [Comparison](control-comparison.json)

Three frozen binaries at a common new path pass all 18 focused multiview/WARP replays.
Further replay of the **same historical candidate bytes** isolates a basename-dependent
multiview failure: the original basename fails at both original and new directories
(six runs), while a short basename passes all three. WARP passes all nine identity
controls. This bounds the unexplained effect but does not identify its native cause;
it must not be called an allocator fix or a proven driver-profile issue.

Both attempted documented per-process GPUAV settings leave GPUAV enabled in captured
output; tests explicitly request GPU-based validation. These are inconclusive controls,
not successfully disabled-GPUAV runs. The actual SDK validation DLL was identified.
No global SDK/driver settings were changed. Raw native diagnostics, snapshots and
failure text remain preserved; no unsupported root-cause attribution is made.

A subsequent verified, **same-binary** upstream diagnostic overrides the required
GPUAV flag in test initialization, retaining core validation. With no proposed wgpu
patches and the registry allocator, TLAS and ray-query each abort in three GPUAV-on
trials and pass in three off trials. All eight mesh tests still abort in both modes.
A second matched comparison removes backend validation entirely: all eight still
abort in all three trials, with the SDK validation DLL absent in every no-layer
execution. This rules out that DLL as a requirement for these mesh aborts; it does
not identify the faulting driver/shader component. An initial off-only TLAS timeout
is also preserved. These are diagnostic configurations, **not conformance passes**;
the default suite still has 23 failures. [Complete controls and limits](GPUAV_CONTROL.md)


## Declared MSRV

The core library declares Rust **1.71** and builds with an independently installed
1.71.0 toolchain using compatible locks: std Vulkan, std D3D12, no_std Vulkan and
Metal cross-compilation. Main/PR/prior-candidate comparisons distinguish existing
dependency issues from this source change. This does not mean every latest dependency
allowed by the broad version ranges supports 1.71: windows 0.62.2 requires 1.82 and
thiserror 2.0.21 requires 1.77. Compatible fixtures use windows 0.58 and thiserror 2.0.20.
A direct windows pin alone can allow a second newer copy; recorded `cargo update
--precise` steps resolve the allocator's graph explicitly. Hashbrown 0.16.1 supports
1.65 and is not the incompatibility initially suspected.

The optional visualizer already permits egui releases whose oldest supported version
requires 1.72; actual Rust 1.71 builds reject the tested visualizer graph. The README
therefore qualifies the core MSRV and optional/development dependency requirements.
No MSRV bump or artificial source workaround hides that existing dependency constraint.
Initial offline missing-cache failures and authoritative successful online/locked
retries remain visible. [MSRV fixtures](msrv-final/), [extra checks](msrv-extra-online-results.json)

## Remaining limits and handoff

The prior report's independent Metal helper/placement issues also remain: Unknown
texture selection can choose Private for a requested Shared texture, and Intel Mac
heaps have native storage-mode restrictions. They need a backend/resource strategy and
Apple runtime validation; this pressure/cache change does not claim to resolve them.

The candidate does not implement memory compaction, fence retirement, device-wide
allocation accounting, per-heap dynamic budget enforcement or immediate physical
release in the presence of external references. Explicit trimming remains useful for
idle/background boundaries and coordination between allocator instances. The largest
bounded cache is supported by these workloads, not proven globally optimal.

Apple pressure/residency behavior is typechecked and checked against native contracts,
but still requires runtime validation on Apple hardware. Physical pressure recovery,
discrete-GPU behavior and driver-specific failure costs need broader hardware coverage.
Clients retaining Metal heaps/resources or the allocator's residency set must continue
to coordinate native residency and lifetime, including across allocator destruction;
this change does not introduce a new shutdown protocol for externally retained sets.
Unresolved native wgpu failures and basename sensitivity prevent describing the native
suite as clean. The final review boundary is a complete local source/evidence bundle,
not a publication or vendoring action.

The final integrity receipt rechecks both historical evidence manifests and original
repository HEAD/status/diff/ref snapshots, plus the exported source/replay hashes.
The vendor inventory records final hashes/timestamps for 411 files, with none newer
than this continuation's bootstrap; it is explicitly not a retroactive hash baseline.
Generated targets and duplicate staging binaries are caches; the evidence manifest
covers portable review artifacts, exact source, canonical binaries, raw measurements,
logs and receipts. No historical evidence is silently replaced by this continuation.

Final receipts: [historical hashes](prior-integrity-final.json),
[repository/source boundary](final-boundary-audit.json),
[manifest scope](EVIDENCE_SCOPE.md) and [manifest verification](evidence-integrity.json).
The full [SHA-256 manifest](EVIDENCE.sha256) seals this continuation's review evidence.
