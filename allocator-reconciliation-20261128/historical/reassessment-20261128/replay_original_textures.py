"""Repeat exact archived binaries after correctness checks, with no compiler overlap."""
import pathlib, subprocess, json, hashlib, time, statistics
H=pathlib.Path(__file__).resolve().parent
while not (H/"FINAL_CHECKS_COMPLETE").exists():time.sleep(2)
def busy():
    p=subprocess.run(["powershell","-NoProfile","-Command","Get-Process -Name cargo,rustc,r1bench-final -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessName"],capture_output=True,text=True)
    return p.stdout.strip()
while busy():time.sleep(3)
out=H/"results-texture-original-replay";out.mkdir(exist_ok=True)
time.sleep(10)
rows=[]
for trial in range(1,6):
    for variant in (["pr323","cache2"] if trial%2 else ["cache2","pr323"]):
        assert not busy()
        exe=H/"bin-verified"/f"bench-{variant}.exe"
        stem=f"{variant}__t{trial}"
        assert not (out/(stem+".json")).exists()
        digest=hashlib.sha256(exe.read_bytes()).hexdigest()
        assert digest==json.loads((H/"bin-verified"/(variant+".json")).read_text())["exe_sha256"]
        p=subprocess.run([str(exe),"vulkan","default",str(trial),variant+"-original-replay"],capture_output=True,text=True,timeout=600)
        (out/(stem+".json")).write_text(p.stdout)
        (out/(stem+".receipt.json")).write_text(json.dumps({"rc":p.returncode,"stderr":p.stderr,"exe_sha256":digest},indent=2))
        assert p.returncode==0,p.stderr
        w=json.loads(p.stdout)["result"]["workloads"]["textures"]
        rows.append({"variant":variant,"trial":trial,"allocation_ms":w["alloc_us"]["sum_ms"],"heap_p99_us":w["heap_creation_us"]["p99"],"reuse_p99_us":w["reuse_us"]["p99"]})
        time.sleep(2)
    print("Original binary replay trial",trial,flush=True)
summary=[]
for variant in ["pr323","cache2"]:
    values=[r["allocation_ms"] for r in rows if r["variant"]==variant]
    summary.append({"variant":variant,"median_ms":statistics.median(values),"min_ms":min(values),"max_ms":max(values)})
(H/"texture-original-replay-summary.json").write_text(json.dumps({"summary":summary,"trials":rows,"note":"Exact archived executables, original workload order, after full correctness checks with no compiler overlap"},indent=2))
(H/"ORIGINAL_REPLAY_COMPLETE").write_text("complete")
print(summary,flush=True)
