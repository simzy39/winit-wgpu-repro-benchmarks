"""Report every full-suite failure and its matched allocator control outcomes."""
import pathlib,json,xml.etree.ElementTree as ET,collections
H=pathlib.Path(__file__).resolve().parent
O=H/"wgpu-failure-controls"
def read(path):
    root=ET.parse(path).getroot();cases={}
    for case in root.iter("testcase"):
        fail=case.find("failure")
        if fail is None:fail=case.find("error")
        cases[case.attrib["classname"],case.attrib["name"]]={"outcome":"pass" if fail is None else fail.attrib.get("type","failure"),"time_s":float(case.attrib["time"]),"message":None if fail is None else fail.attrib.get("message"),"details":None if fail is None else fail.text}
    return cases
full=read(O/"candidate-full-junit.xml")
baseline=read(O/"pr323-filtered-junit.xml")
candidate=read(O/"candidate-filtered-junit.xml")
assert len(baseline)==len(candidate)==26
matrix=json.loads((H/"multiview-path-matrix.json").read_text()) if (H/"multiview-path-matrix.json").exists() else []
path_proven=(len(matrix)==8 and len({r["exe_sha256"] for r in matrix})==1
    and all(r["failed"]==(r["path_mode"]=="original") for r in matrix))
rows=[]
for key,record in full.items():
    if record["outcome"]=="pass":continue
    a=baseline[key];b=candidate[key]
    if a["outcome"]!="pass":classification="reproduces without candidate allocator"
    elif b["outcome"]=="pass":classification="not reproduced in either focused control"
    else:classification="candidate-only in focused control: investigate"
    if classification=="candidate-only in focused control: investigate" and path_proven and key[1].endswith("wgpu_gpu::multiview::draw_multiview_single"):
        classification="executable-path sensitive with identical candidate bytes"
    rows.append({"binary":key[0],"name":key[1],"full":record,"pr323":a,"candidate":b,"classification":classification})
counts=collections.Counter(r["classification"] for r in rows)
out={"full_tests":2205,"full_passed":2179,"full_failed":23,"full_timed_out":3,"full_skipped":18,
    "rows":rows,"classifications":counts,"controls_scope":"Both wgpu PRs remain applied in both controls. This isolates the gpu-allocator candidate; it does not establish that failures are independent of the wgpu patches."}
(H/"failure-triage.json").write_text(json.dumps(out,indent=2))
lines=["# Full wgpu validation and failure controls","","The full combined run executes 2,205 tests: 2,179 pass, 23 fail or abort, and three time out. Eighteen additional tests are excluded by the repository profile. The first build prerequisite failure is preserved separately. Every failing/timed-out case is listed below.","",out["controls_scope"],"","| Binary | Test | Full result | PR 323 control | Candidate focused control | Assessment |","|---|---|---|---|---|---|"]
for r in rows:
    lines.append("| "+" | ".join([r["binary"],r["name"],r["full"]["outcome"],r["pr323"]["outcome"],r["candidate"]["outcome"],r["classification"]])+" |")
lines += ["","Raw output, JUnit, filters, frozen executables and hashes are under wgpu-failure-controls. Allocation correctness checks and the benchmark success counts are separate from this broader suite. Reproduction without the candidate proves a failure can occur on the unchanged allocator PR; it does not identify a driver root cause.",""]
if path_proven:
    lines += ["## Multiview path control","","The first focused DX12 single-view multiview comparison is asymmetric: five unchanged-PR passes versus five candidate failures. Moving the exact archived executables to one common path yields three passes per version. An eight-run candidate-only factorial then varies path and log setting over two rounds: the original path fails four times and the common path passes four times, with both warn and debug logging. Candidate SHA-256 is unchanged in every run. The staged WARP DLL hashes also match.","","This establishes executable-path sensitivity without changing allocator code or recompiling. It does not identify whether an application profile, driver cache, loader context or another path-dependent mechanism is responsible. The original failure remains in the full-suite count. The case is an unresolved environmental/backend compatibility risk, rather than a demonstrated allocator-policy regression. See multiview-control-repeats.json, multiview-common-path.json, multiview-path-matrix.json and multiview-runtime-dll-hashes.json.",""]
(H/"FAILURE_TRIAGE.md").write_text("\n".join(lines),encoding="utf-8")
print(dict(counts),flush=True)
