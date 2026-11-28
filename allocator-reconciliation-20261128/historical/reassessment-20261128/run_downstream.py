"""Sequential wgpu factorial and selected alternative-policy comparisons."""
import pathlib,subprocess,json,hashlib,time,datetime,re
from process_metrics import run_process
H=pathlib.Path(__file__).resolve().parent
OUT=H/"results-downstream";OUT.mkdir(exist_ok=True)
cases=[
("performance","idle"),
("performance","repeated_uploads"),
("performance","sustained_render"),
("performance","sustained_compute"),
("memory_usage","churn"),
("memory_usage","large_textures"),
("manual-8-256","large_textures"),
("manual-8-256","large_alloc"),
]
def busy():
    p=subprocess.run(["powershell","-NoProfile","-Command",
        "Get-Process -Name cargo,rustc,r1bench-final -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessName"],
        capture_output=True,text=True)
    return p.stdout.strip()
def gate():
    while names:=busy():
        print("Waiting for exclusive measurement interval:",names.replace("\n",", "),flush=True)
        time.sleep(15)
def run(name,backend,hints,workload,trial):
    exe=H/"bin-wgpu"/f"{name}.exe"
    digest=hashlib.sha256(exe.read_bytes()).hexdigest()
    stem=f"{name}__{backend}__{hints}__{workload}__t{trial}"
    path=OUT/f"{stem}.json";receipt=OUT/f"{stem}.receipt.json"
    if path.exists():
        old=json.loads(receipt.read_text())
        assert old["rc"]==0 and old["exe_sha256"]==digest
        json.loads(path.read_text())
        return
    start=time.perf_counter()
    cmd=[str(exe),"--backend",backend,"--hints",hints,"--workload",workload,"--json",str(path)]
    p=run_process(cmd,timeout=600)
    (OUT/f"{stem}.stdout.txt").write_text(p.stdout,encoding="utf-8")
    (OUT/f"{stem}.stderr.txt").write_text(p.stderr,encoding="utf-8")
    validation_error=bool(re.search(r"VUID-|Validation Error|panicked",p.stdout+p.stderr,re.I))
    receipt.write_text(json.dumps({"rc":p.returncode,"command":cmd,"exe_sha256":digest,"validation_error":validation_error,
        "utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"wall_s":p.wall_s,"cpu_times":p.cpu_times,"settle_after_s":2},indent=2))
    if p.returncode or validation_error:raise RuntimeError(f"Failed {stem}: {p.stdout[-1000:]} {p.stderr[-2000:]}")
    json.loads(path.read_text())
    time.sleep(2)
assert (H/"DIRECT_COMPLETE").exists(),"Complete direct suite before downstream timings"
gate();time.sleep(10)
start=time.perf_counter()
for trial in range(1,6):
    for backend in ["dx12","vulkan"]:
        # The transient-pool PR changes DX12 only. Avoid repeating source-identical Vulkan states.
        states=["trunk","lazy","transient","both"] if backend=="dx12" else ["trunk","lazy"]
        variants=[f"{allocator}-{state}" for state in states for allocator in ["pr323","cache2"]]
        variants=variants[trial-1:]+variants[:trial-1]
        if trial%2==0:variants.reverse()
        for hints,workload in cases:
            gate()
            for name in variants:run(name,backend,hints,workload,trial)
            if hints=="manual-8-256" and workload=="large_textures":
                alternatives=["retain2-trunk","demand2-trunk","retain2-both","demand2-both"]
                if trial%2==0:alternatives.reverse()
                for name in alternatives:run(name,backend,hints,workload,trial)
            print(f"trial={trial} {backend}/{hints}/{workload} complete elapsed={time.perf_counter()-start:.1f}s",flush=True)
(H/"DOWNSTREAM_COMPLETE").write_text(datetime.datetime.now(datetime.timezone.utc).isoformat())
print("Downstream suite complete",flush=True)

