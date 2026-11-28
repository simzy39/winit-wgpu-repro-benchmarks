"""Paired follow-up isolating the cost of a larger empty-cache limit."""
import pathlib,subprocess,json,time,hashlib,datetime
from process_metrics import run_process
H=pathlib.Path(__file__).resolve().parent
assert (H/"DIRECT_COMPLETE").exists()
OUT=H/"results-cache-limits";OUT.mkdir(exist_ok=True)
start=time.perf_counter()
time.sleep(10)
for trial in range(1,6):
    for backend in ["vulkan","d3d12"]:
        for cfg in ["memory_usage","manual","performance"]:
            names=["pr323","cache2","cachemax"] if cfg!="performance" else ["pr323","cache2"]
            if trial%2==0:names.reverse()
            for name in names:
                path=OUT/f"{name}__{backend}__{cfg}__t{trial}.json"
                assert not path.exists()
                exe=H/"bin-verified"/f"bench-{name}.exe"
                p=run_process([str(exe),backend,cfg,str(trial),name],timeout=600)
                path.write_text(p.stdout)
                path.with_name(path.stem+".receipt.json").write_text(json.dumps({"rc":p.returncode,
                    "exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),"stderr":p.stderr,
                    "utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"cpu_times":p.cpu_times,"wall_s":p.wall_s,"settle_after_s":2},indent=2))
                if p.returncode:raise RuntimeError(p.stderr)
                json.loads(p.stdout)
                time.sleep(2)
            print(f"cache limit trial={trial} {backend}/{cfg} elapsed={time.perf_counter()-start:.1f}s",flush=True)
(H/"CACHE_LIMITS_COMPLETE").write_text("complete")

