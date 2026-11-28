from pathlib import Path
import json
H=Path(__file__).resolve().parent
d=json.loads((H/'backoff-failure-triage.json').read_text())
assert (d['tests'],d['passed'],d['failed'],d['new_failure_names'])==(2207,2184,23,[])
rows=[]
for r in d['rows']:
    clean=r['clean_upstream']['outcome']
    verdict='Also fails on pristine upstream' if clean!='pass' else 'Basename-dependent historical failure; native cause unresolved'
    name=r['name'].replace('[Executed] ','')
    rows.append(f"| `{r['binary']}` | `{name}` | {r['failure']['type']} | {clean} | {verdict} |")
text='''# Final wgpu failures and controls

The geometric-policy full `cargo xtask test` run executes 2,207 tests: **2,184 pass,
23 fail/abort**, and 18 more tests are excluded by the default profile. JUnit records
zero skipped testcases; nextest's summary separately reports the profile exclusions.
The full command exits 1 (nextest exits 100). No failure name is new relative to the
historical failure set. The test-only dependency override is corrected and `compile_fail`
passes in this full run. The two new HAL rollback unit tests pass separately.

The full run uses the geometric allocator snapshot in `measurement-sources/backoff-final`.
The final source additionally fixes only D3D12's convenience `create_resource` function
and its tests; wgpu uses `allocate`/`free` and those paths are byte-identical. That final
delta has 43 passing allocator library tests and identical-driver controls demonstrating
the old bug. It is not represented as a second full native run of the convenience fix.

Authoritative artifacts: [JUnit](sources/backoff-full-junit.xml),
[complete output](logs/backoff-full-wgpu.log), [triage including failure details](backoff-failure-triage.json),
[clean upstream comparison](control-comparison.json).

| Binary | Exact test identity (adapter/API included) | Final outcome | Clean upstream control | Disposition |
|---|---|---|---|---|
'''+ '\n'.join(rows)+'''

Twenty-two final failures reproduce on a source-clean upstream checkout with registry
gpu-allocator and no wgpu patches. Matching outcomes establish that these failures do
not require the proposed patches; they do not identify the native root causes or prove
that every internal failure mechanism is identical.

DX12 `draw_multiview_single` passes clean upstream but still fails the final candidate's
normal executable. Identical historical candidate bytes isolate basename sensitivity:
original basename at original/new directories fails all six runs; short basename passes
all three. WARP passes all nine identity controls. The common-path three-binary matrix
passes all 18 runs. These results bound the issue without certifying deployed executable
names or establishing a driver-profile/cache/loader explanation.

Both GPUAV environment-setting attempts still report GPUAV enabled. They are
inconclusive, not successful no-GPUAV controls. Tests explicitly request GPU-based
validation. See [identity receipts](identity-controls.json), [common-path receipts](path-controls.json),
[GPUAV attempts](gpuav-controls.json) and [loaded-layer diagnostics](layer-diagnostics.json).
No global driver/SDK settings were changed.

The earlier full run's extra `compile_fail` failure was local test setup: `.cargo/config`
did not supply the allocator patch to trybuild's external workspace. The root workspace
Cargo.toml patch fixes it. Initial logs and the initially mislocated two-case JUnit pilot
remain archived; neither substitutes for this final full result. The historical report
and all 26 original failures/timeouts are preserved too.
'''
(H/'VALIDATION_FAILURES.md').write_text(text)
p=H/'REPORT.md';s=p.read_text().replace('''Final full-suite results and individual native-failure disposition are recorded below
after the geometric-policy rerun completes.''','''The geometric-policy rerun executes **2,207 tests: 2,184 pass and 23 fail/abort**,
with 18 profile exclusions and no new failure names. `compile_fail` passes in that full
run. Twenty-two final failures also fail pristine upstream; DX12 multiview is the
historical basename-sensitive exception discussed below. The complete individual
[failure table and controls](VALIDATION_FAILURES.md) and
[structured triage](backoff-failure-triage.json) preserve every outcome. The native suite
is not green. This full run precedes only the separately tested D3D12 convenience-API
fix; its `allocate`/`free` path is identical to final source.''')
s=s.replace('''The geometric source passes std/no_std library tests, strict project Clippy, rustdoc,
formatting, Apple ARM Clippy/Intel cross-checks and real Rust 1.71 consumer builds.
Final convenience-API changes are validated separately and their exact source delta
is recorded with the final audit. The optional visualizer is checked with the current
compiler. See machine-readable check receipts for individual commands and outcomes.''','''The final source passes **43 std library tests and 10 no_std tests**, strict project
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
allocation/recovery paths and other backends remain identical.''')
s=s.replace('''The candidate does not implement memory compaction, fence retirement, device-wide''','''The prior report's independent Metal helper/placement issues also remain: Unknown
texture selection can choose Private for a requested Shared texture, and Intel Mac
heaps have native storage-mode restrictions. They need a backend/resource strategy and
Apple runtime validation; this pressure/cache change does not claim to resolve them.

The candidate does not implement memory compaction, fence retirement, device-wide''')
p.write_text(s)
print('Updated report and all 23 individual failure dispositions')
