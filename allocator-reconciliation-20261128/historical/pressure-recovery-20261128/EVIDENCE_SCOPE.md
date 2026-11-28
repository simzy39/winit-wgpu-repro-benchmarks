# Evidence manifest scope

`EVIDENCE.sha256` covers the portable review bundle: complete final allocator source,
all final and archived patches, measured source snapshots, standalone pressure/lifetime
controls, benchmark inputs, MSRV manifests/locks, accepted and rejected raw measurements,
summaries, full compiler/native-test logs, frozen canonical binaries, documentation,
source/binary receipts and final audits. Paths are relative to this directory.

The two earlier bundles have their own unchanged manifests. `prior-integrity-final.json`
records a fresh streaming hash check of all 438 and 4,317 historical entries. The new
manifest does not recursively include either historical bundle; pinned paths/digests
and the prior manifests preserve that chain.

Excluded items remain on disk; none are deleted:

- Cargo `target`/`target-*` directories, `.git`, Python bytecode and build caches.
- Mutable `work/` and `wgpu/` checkout trees and clean patch replay scratch trees.
  Final source, complete patches, exact bases, benchmark inputs and measured snapshots
  provide portable reconstruction. Relevant logs/JUnit are copied outside those trees.
- Duplicate binaries staged under path/identity/GPUAV control `bin` folders. Their
  receipts identify the historical canonical bytes or the frozen clean-upstream binary.
- Executables from the explicitly rejected shared-target `bin/` and `bin-wgpu/` setup.
  The invalidation flags, build receipts and raw rejected data remain covered.
- `EVIDENCE.sha256` itself and `evidence-integrity.json`, which records the manifest's
  digest, file/byte counts and successful read-back verification without a hash cycle.

Canonical accepted binaries in `bin-isolated/`, `bin-final/`, `bin-wgpu-isolated/` and
`upstream-control-bin/` are covered. Installed helper/ATL evidence is covered too.
`candidate-control-bin/` freezes the GPU binary from the geometric full suite, while
`bin-final/backoff-plan-only.exe` freezes the six-process plan-verification binary.
`sources/final-frozen-binaries.json` records both. All seven complete changed wgpu
files are included in `wgpu-source-changes/` alongside the complete patches.
Source-generation scripts are historical records, often intentionally non-idempotent;
use `REPRODUCE.md` when reconstructing a fresh experiment.

`final-boundary-audit.json` compares original repository HEAD/status/diff/refs with the
initial snapshot and verifies exported source bytes and patch digests. Vendor hashes
and timestamps are inventoried read-only; no pre-continuation vendor hash snapshot
exists, and the audit does not claim one. All allocator/wgpu source edits and review
artifacts reside in this new research bundle and its detached experimental worktrees.
Ordinary compiler, toolchain and driver caches are outside the evidence scope.


The final validation investigations additionally preserve `core-validation-bin/`,
`gpuav-flag-control-bin/` and `layer-control-bin/`, all three harness source/patches,
metadata, flags/module/loader receipts, logs and JUnit. The 30-execution off-only pilot,
60-execution same-binary GPUAV matrix and 48-execution core/no-layer matrix are
diagnostics, separate from the default full suite and benchmark process totals.
