# Reproduce the review candidate

All work in this bundle is local. No commits, pushes, published PRs or RustyGUI vendored
dependency changes are part of this continuation. The previous reassessment and its
parent remain the historical evidence sources.

## Source and patches

`patches/manifest.json` pins bases and SHA-256 digests. The allocator patches apply to
PR323 `179ea43f05332c2809addd7922cd056220efc36b` and main
`fc22df05140b15ed6d764beabd12a1b807011bc5`. Both were replayed onto clean archived
trees and compared across all 36 tracked files using Git's canonical blob hashes.
This accounts for Windows line-ending conversion without ignoring content changes.

Create a fresh detached checkout outside RustyGUI's workspace, apply the corresponding
patch, and run these checks from the allocator package:

```powershell
cargo test --no-default-features --features std,vulkan,d3d12 --lib
cargo test --no-default-features --features hashbrown,vulkan,d3d12 --lib
cargo clippy --no-default-features --features std,vulkan,d3d12 --all-targets -- -D warnings
cargo clippy --no-default-features --features hashbrown,vulkan,d3d12 --lib -- -D warnings
cargo fmt -- --check
```

`handoff-source-checks.json` records the final 43 std / 10 no_std tests and actual
commands for current compilers, Apple cross targets, rustdoc and Rust 1.71. The driver
`finish_handoff_source.py` records adoption/checks/export of the last convenience-API
fix; it is a historical generation step, not an idempotent reproduction command.
`check_final_source.py` supplies the shared check list; copy it and adjust paths/output
names rather than rerunning destructive generation scripts over preserved results.
`handoff-visualizer-clippy.json` records the final optional-feature check. Earlier
source-stage checks remain separately archived. Pressure tests intercept native
calls and require no GPU. Running the examples requires the corresponding device/runtime.
The pre-existing removed-Clippy-lint warning is nonfatal even with `-D warnings`.

## Rust 1.71

The declared core MSRV was tested using an independently installed Rust 1.71.0 toolchain,
without changing the default toolchain. Standalone consumer manifests and compatible
locks are retained under `msrv-final/`; the Metal consumer is under `msrv-extra/metal/`.
They refer to the isolated recovery source. Copy these fixtures and replace the local
path if reproducing elsewhere.

```powershell
cargo +1.71.0 check --locked --manifest-path <consumer>/Cargo.toml --lib
```

Compatible graphs pin thiserror 2.0.20 and resolve the allocator's Windows dependency
to windows 0.58. A direct windows pin alone does not prevent a second, newer version
from satisfying the allocator's broad range; the recorded `cargo update --precise`
step removes that ambiguity. Keep the supplied version-3 locks when using old Cargo.
The optional visualizer fails Rust 1.71 because the permitted egui family declares
Rust 1.72. Initial missing-cache/offline failures and the authoritative online retries
are both preserved. These findings are documented in the candidate README.

## Accepted direct measurements

The accepted seven-policy experiment is `results/direct-isolated/`: 210 processes,
two backends, three configurations, ten workloads, five trials. `direct-summary.json`
and `.csv` keep every cell. `results/final-pair/` adds 60 processes comparing the
pre-geometric Windows implementation with the prior candidate; its summary is `final-pair-summary`.
Do not pool old absolute timings with these new runs.

`measurement-sources/` preserves the exact seven implementations used in the policy
comparison. `bin-isolated/*.json` records complete allocator source-file hashes, lock
hashes, binary hashes and compilation commands. `bin-final/` identifies the final A/B
binaries. The dedicated pNext regression changed tests only after that build. Later
geometric reduction changes cold failure behavior. `results/backoff-plans/` and
`backoff-plan-verification.json` verify all 60 normal plan cells with six processes from
that source; these single runs do not establish final-source statistical latency.
The exact fallback source and patches remain in `measurement-sources/exact-final/`
and `patches-exact-stage/`. The full native-suite source before the final D3D12
convenience-API fix is in `measurement-sources/backoff-final/` and `patches-backoff-stage/`.
`handoff-source-delta.json` verifies that only `create_resource` and its tests changed;
the benchmark/wgpu allocation paths remain identical. Four identical-driver regression
controls fail old source and pass the fix; `lifetime-comparison.json` records the result.

To rebuild in a fresh experiment directory, create detached allocator checkouts at the
pinned bases, restore each measured `src`, README and Cargo.toml over the checkout,
and use the common bench source/manifest/lock from `repro-inputs/` (also retained in
`work/<variant>/bench` and its parent workspace). Recreate the small two-member workspace
described in `work/recovery/Cargo.toml`, adjusting only local paths. Keep a different
Cargo target directory for **every** source combination.
`build_isolated.py` documents the dependency-cache seeding procedure; its logs verify
that the allocator and benchmark were actually recompiled. Unchanged third-party
artifacts may be seeded, but local allocator/benchmark artifacts and fingerprints must
be excluded. Windows copies use extended paths to avoid MAX_PATH failures.

Run `run_comparisons.py` only after all build/check/control stages finish. It interleaves
variant order, waits for compilers, settles between processes, and preserves existing
result/receipt pairs. It expects the original bundle's stage markers; use a fresh output
root for a new experiment. `final_pair.py` documents the final matched A/B procedure.
The hardware, driver and runtime provenance from the previous bundle remains applicable;
`reuse-audit.json` verifies all 180 repeated historical main/PR/candidate plan cells.

**Rejected setup:** `results/direct/`, `bin/` and `bin-wgpu/` came from a shared Cargo target.
Cargo reused another variant's allocator artifact despite package-specific clean commands.
Those data/binaries are explicitly invalid and retained for audit. They are excluded
from accepted summaries. Neither historical evidence nor the isolated replacement runs
were overwritten.

## wgpu controls and followup

The HAL-only followup applies to PR11130
`22827ee25285b56c4056fe6bb1de27917caf45a9`; it requires the new allocator APIs. The combined
patch applies to base `60cef2be828e03ba54e2e1598001b4625c0c2163` and includes PR11129, PR11130
and the earlier regression checks. Local Cargo path overrides and lock changes are
excluded from exported patches. The test override belongs in the **workspace root**
`Cargo.toml` patch table. A worktree-local `.cargo/config.toml` override is insufficient
for trybuild's generated workspace outside the source tree; this caused the initial
`compile_fail` setup failure. The corrected full-suite compile-test executable passes.
The HAL files in the previous combined source exactly
match PR11130's head, so the followup has no lazy-allocation source prerequisite.
The combined export is replayed against a complete clean source archive and compared
across all 2,757 tracked files excluding those three local test files.
`wgpu-source-changes/` also contains all seven final changed source files.

`run_clean_wgpu.py` tested the exact historical failure set on pristine upstream with
the registry allocator and no wgpu patches. Its receipt pins the clean source status
and unchanged lock. Current trunk differs from this base only in CI dependency updates.
The clean GPU executable and nextest metadata are archived for replay. The 26-case
comparison is in `control-comparison.json`, with full JUnit and logs.

`build_isolated.py wgpu` and `run_downstream_comparisons.py` document the focused four-way
DX12 comparison. All combinations use their own Cargo targets. The same five workloads
are run five times; Vulkan is not repeated for the DX12-only pool-routing alternative.
The old factorial remains separate evidence. `run_candidate_wgpu.py` runs the HAL
rollback unit tests and the required full `cargo xtask test` after measurements finish.
`rerun_backoff_wgpu.py` repeats the full suite after the final pressure policy change
and corrected override. `CARGO_TARGET_DIR` controls build artifacts, but nextest's JUnit
store is workspace-relative: `wgpu/candidate/target/nextest/default/junit.xml`. Always
check its suite count and timestamp; a two-case control report was initially copied
from the wrong store and is explicitly preserved as a rejected pilot.
It uses the repository's pinned Rust 1.97.1, the recorded Vulkan SDK and local verified
ATL library, WARP and Agility SDK support. Test thread count is two. No CTS run is included.

`recheck_path_controls.py` replays historical binaries at a common new path. Package IDs
and working directories in saved metadata are remapped to the new clean worktree so
nextest cannot write into the historical bundle. Its JUnit destination comes from the
current Cargo graph, not merely the metadata target-directory field. Setup failures and
the successful 18-case matrix are retained. `recheck_executable_identity.py` further
separates original path, basename and directory effects after the full suite.
`recheck_gpuav.py` attempts clean-source per-process GPU-assisted-validation controls;
both documented environment-setting forms left GPUAV enabled in captured output. These
attempts are **inconclusive**, not evidence for a successfully disabled-GPUAV run. The
tests explicitly request GPU-based validation. No global SDK settings were changed.
These focused diagnostics are separate from the
default full-suite result and cannot make that suite count as passing.

The authoritative final geometric run executes 2,207 tests: 2,184 pass, 23 fail/abort,
and 18 more are excluded by the default profile. `compile_fail` passes. Its JUnit is
`sources/backoff-full-junit.xml`; every failure/control is in `VALIDATION_FAILURES.md`
and `backoff-failure-triage.json`. The final convenience resource API is separately
regression-tested; it is not used by wgpu's `allocate`/`free` integration.

## Integrity and limits

The source patches and exported experimental implementations are sufficient to review
the code. Raw measurements, compiler logs, full failure output and source receipts
support the claims. Generated target directories are caches, not portable evidence.
The final evidence manifest covers review artifacts and sources while excluding caches
and Git administrative files. The final audit rechecks both prior manifests and original
repository HEAD/status/ref snapshots. Apple runtime pressure recovery remains unverified
on hardware; cross-compilation and MSRV checks do not replace that validation.


## Verified validation diagnostics

`run_core_validation_control.py` builds a pristine-base checkout with only test
initialization changed, using a fresh target that excludes every local wgpu/naga/
allocator artifact from its seed. Registry dependencies and Cargo.lock remain upstream.
Its three-process off-only pilot and first TLAS timeout remain archived.

`run_matched_gpuav_control.py` then adds a private diagnostic environment switch and
rebuilds the same test package. One frozen binary/path executes ten Vulkan test cases
in both modes, interleaved over three trials. `GPUA_DIAGNOSTIC_CORE_ONLY=1` removes
GPUAV after the tests request it; leaving it absent retains their request. Assertions,
flag markers and native layer warnings verify the modes. Both retain core validation.

`run_layer_control.py` makes the final paired experiment for the eight mesh cases:
set `GPUA_DIAGNOSTIC_CORE_ONLY=1` in both modes, and set
`GPUA_DIAGNOSTIC_NO_LAYER=1` only in the no-layer mode. The harness records native
validation-DLL presence after instance creation; VK_LOADER_DEBUG=layer captures loader
messages. No-layer DLL absence is verified in all 24 executions. A different frozen
binary is used for this experiment, with identical bytes/path within its two modes.

The exact harness-only patches, full files, nextest metadata, commands, six logs/JUnit
files per matched comparison, binary hashes and summaries are archived. The pilot's
frozen replay metadata is `sources/core-validation-frozen-binaries.json`; the original
build metadata points to a mutable target. The two later metadata files already point
to their frozen binaries. Apply each diagnostic patch to a separate fresh base when
rebuilding; these generation scripts intentionally assert fresh output directories.

These are private research switches, not new wgpu interfaces. Removing a test's
required validation changes its meaning, so diagnostic passes do not satisfy the
original test configuration. The standard suite remains 2,184/2,207 passed, 23 failed
and 18 profile exclusions. [GPUAV_CONTROL.md](GPUAV_CONTROL.md) explains all results,
the pilot timeout and the limits of causal attribution. No global SDK settings changed.
