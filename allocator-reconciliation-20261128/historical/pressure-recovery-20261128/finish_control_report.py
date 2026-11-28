from pathlib import Path
import json,collections,hashlib
H=Path(__file__).resolve().parent
g=json.loads((H/'gpuav-flag-control.json').read_text());l=json.loads((H/'layer-control.json').read_text())
assert len(g['rows'])==6 and len(l['rows'])==6
for row in l['rows']:
    assert len(row['outcomes'])==8 and all(c['type']=='test abort' for c in row['outcomes'])
    assert row['validation_dll_loaded']==[('true' if row['mode']=='core' else 'false')]*8
counts={mode:dict(collections.Counter('pass' if not c['failed'] else c['type'] for row in l['rows'] if row['mode']==mode for c in row['outcomes'])) for mode in ['core','none']}
(H/'layer-control-summary.json').write_text(json.dumps({'outcomes':counts,'executions':48,'same_binary_per_mode':l['binary'],'exe_sha256':l['exe_sha256'],'validation_dll_absent_in_all_24_none_executions':True,'root_cause_limit':'These native mesh aborts do not require the SDK validation DLL. Driver/upstream shader path remains unresolved; no specific component blamed.'},indent=2))
p=H/'GPUAV_CONTROL.md';s=p.read_text()
s+='''
## Followup: core validation versus no backend validation

The eight mesh tests receive a separate same-binary comparison with GPUAV disabled
in both modes. Three trials retain core validation; three remove the backend validation
request. The harness checks the native `VkLayer_khronos_validation.dll` module after
instance creation: it is present in all 24 core-mode executions and absent in all
24 no-layer executions. Loader diagnostics and per-test flags are retained too.

**All eight tests abort in all three trials in both modes** (24/24 aborts each), with
the native fast-fail code 0xc0000409. Thus these aborts do not require GPUAV or the SDK
validation DLL. The result narrows the problem to upstream's remaining native mesh
execution path; it does not prove whether shader input, driver behavior or another
component is responsible. No validation-disabling workaround is proposed for shipping.

[Structured layer comparison](layer-control.json), [summary](layer-control-summary.json),
[six logs/JUnit files](layer-controls/), [harness patch](sources/layer-control-harness.patch)
and [frozen binary](layer-control-bin/) preserve the followup. This binary differs from
the GPUAV comparison binary; each pair of modes uses the same bytes and path within
its own experiment. Both are based on pristine upstream runtime code and the registry
allocator, with only test initialization modified.

The earlier off-only pilot includes one initial 90-second TLAS timeout, then two TLAS
passes; the later matched matrix has three TLAS passes with GPUAV off. That timeout's
origin remains unresolved and is retained in `core-validation-controls/trial1.*`.
The pilot has 30 executions; the matched GPUAV matrix 60; the layer matrix 48. These
138 diagnostic test executions are separate from the 376 benchmark/plan processes.
'''
p.write_text(s)
pilot=H/'core-validation-control.json';j=json.loads(pilot.read_text())
meta=json.loads((H/'sources/core-validation-binaries.json').read_text())
binary=next((H/'core-validation-bin').glob('*.exe'))
assert hashlib.sha256(binary.read_bytes()).hexdigest()==j['binary_sha256']
meta['rust-binaries']['wgpu-test::wgpu-gpu']['binary-path']=str(binary)
(H/'sources/core-validation-frozen-binaries.json').write_text(json.dumps(meta,indent=2))
j.update(frozen_binary=str(binary),replay_metadata='sources/core-validation-frozen-binaries.json',source_snapshot='sources/core-validation-init.rs')
pilot.write_text(json.dumps(j,indent=2))
paragraph='''
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
'''
p=H/'REPORT.md';s=p.read_text();needle='No global SDK/driver settings were changed. Raw native diagnostics, snapshots and\nfailure text remain preserved; no unsupported root-cause attribution is made.'
assert needle in s;s=s.replace(needle,needle+'\n'+paragraph);p.write_text(s)
p=H/'VALIDATION_FAILURES.md';s=p.read_text();s+='\n## Verified flag and layer controls\n'+paragraph;p.write_text(s)
p=H/'REPRODUCE.md';s=p.read_text();s+='''

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
''';p.write_text(s)
p=H/'EVIDENCE_SCOPE.md';s=p.read_text();s+='''

The final validation investigations additionally preserve `core-validation-bin/`,
`gpuav-flag-control-bin/` and `layer-control-bin/`, all three harness source/patches,
metadata, flags/module/loader receipts, logs and JUnit. The 30-execution off-only pilot,
60-execution same-binary GPUAV matrix and 48-execution core/no-layer matrix are
diagnostics, separate from the default full suite and benchmark process totals.
''';p.write_text(s)
triage=H/'backoff-failure-triage.json';d=json.loads(triage.read_text())
for row in d['rows']:
    if any(c['name']==row['name'] for c in g['rows'][0]['outcomes']):row['additional_diagnostic_evidence']='GPUAV_CONTROL.md; gpuav-flag-control.json'
    if any(c['name']==row['name'] for c in l['rows'][0]['outcomes']):row['validation_dll_absent_control']='All three matched no-layer trials abort; SDK validation DLL absent. layer-control.json'
triage.write_text(json.dumps(d,indent=2))
print('Final diagnostic reports: GPUAV on30 aborts/off6 pass24 aborts; no-layer mesh24 aborts, DLL absent; default suite23 failures unchanged')
