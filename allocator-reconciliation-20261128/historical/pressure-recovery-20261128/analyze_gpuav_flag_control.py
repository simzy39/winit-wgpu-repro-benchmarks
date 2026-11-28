from pathlib import Path
import json,collections
H=Path(__file__).resolve().parent
d=json.loads((H/'gpuav-flag-control.json').read_text());by=collections.defaultdict(lambda:collections.defaultdict(list))
for row in d['rows']:
    for case in row['outcomes']:
        by[case['name']][row['mode']].append(case['type'] if case['failed'] else 'pass')
lines=[]
for name,modes in sorted(by.items()):
    render=lambda values:', '.join(f'{count} {outcome}' for outcome,count in collections.Counter(values).items())
    lines.append(f"| `{name.replace('[Executed] ', '')}` | {render(modes['on'])} | {render(modes['off'])} |")
counts={mode:dict(collections.Counter('pass' if not c['failed'] else c['type'] for row in d['rows'] if row['mode']==mode for c in row['outcomes'])) for mode in ['on','off']}
warnings={mode:[row['gpuav_enabled_warning_present'] for row in d['rows'] if row['mode']==mode] for mode in ['on','off']}
native_off_confirmed=all(warnings['on']) and not any(warnings['off'])
result={'mode_outcomes':counts,'native_gpuav_warning_by_trial':warnings,'verified_native_off_control':native_off_confirmed,'same_binary_and_path':d['same_binary_and_path_for_both_modes'],'exe_sha256':d['exe_sha256'],'tests':len(by),'executions':60,'ordinary_native_suite_unchanged':{'passed':2184,'failed':23,'executed':2207,'profile_exclusions':18}}
(H/'gpuav-flag-control-summary.json').write_text(json.dumps(result,indent=2))
assert native_off_confirmed,'Do not claim GPUAV was actually disabled without this check'
text='''# Verified GPUAV flag control

This diagnostic uses upstream `60cef2b`, its unchanged registry allocator/lock and
none of the proposed wgpu patches. The sole source change is a test-initialization
control: a private process variable removes GPU_BASED_VALIDATION after the tests'
explicit request. Both modes assert core validation is enabled and print the final
flags before creating the instance. This intentionally changes the required test
configuration; off-mode results are **not conformance passes**.

One frozen executable, with identical bytes, basename, directory, working directory,
adapter configuration and metadata, runs both modes. The three trials interleave
on/off order, one test thread at a time. The Vulkan layer warns that both core and
GPU-assisted validation are enabled in each on-mode process, and not in any off-mode
process. All 60 executions have the corresponding per-test flag marker. This corrects
the earlier environment-only attempts, which never disabled GPUAV and remain archived.

'''+f"Outcomes across 30 executions per mode: GPUAV on `{counts['on']}`; GPUAV off `{counts['off']}`.\n\n"+'''
| Exact Vulkan test identity | GPUAV on (3 trials) | GPUAV off (3 trials) |
|---|---|---|
'''+ '\n'.join(lines)+'''

The comparison establishes dependence on the GPUAV configuration for the tested cases
where outcomes change. It does not distinguish a validation-layer defect, instrumented
shader/driver interaction or another component of that path. It does not fix the
candidate's default full suite, establish allocator causality, or cover the separate
example binary or DX12 basename-dependent case.

Authoritative [receipt](gpuav-flag-control.json), [summary](gpuav-flag-control-summary.json),
[all six logs/JUnit files](gpuav-flag-controls/),
[harness-only patch](sources/gpuav-flag-control-harness.patch),
[exact harness source](sources/gpuav-flag-control-init.rs) and
[frozen binary](gpuav-flag-control-bin/) preserve the comparison. The initial isolated
build excludes all local wgpu/naga/allocator artifacts; the final harness edit rebuilds
the same package at the same path, with per-mode runtime assertions preventing silent
reuse of the wrong control. A separate three-process off-only pilot is also retained.

The default full suite remains 2,184 passes and 23 failures/aborts among 2,207 executed
tests, with 18 profile exclusions. Do not subtract these diagnostic results from that
failure count. Original pristine-upstream controls and all historical evidence remain
unchanged. No global Vulkan SDK/driver settings were modified.
'''
(H/'GPUAV_CONTROL.md').write_text(text)
print(result,flush=True)
