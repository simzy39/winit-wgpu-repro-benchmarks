"""Sequential interleaved hardware measurements; existing output is immutable."""
import pathlib,subprocess,time,json,hashlib,sys,datetime
H=pathlib.Path(__file__).resolve().parent
OUT=H/"results-direct-verified"
OUT.mkdir(exist_ok=True)
variants=["main","pr323","proposal","retain2","demand2","request","vma-policy","cache2"]
configs=["memory_usage","performance","manual","default","tiny_fixed"]
trials=int(sys.argv[1]) if len(sys.argv)>1 else 5
def busy():
    p=subprocess.run(["powershell","-NoProfile","-Command",
      "Get-Process -Name cargo,rustc,r1bench-final -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessName"],
      capture_output=True,text=True)
    return p.stdout.strip()
def gate():
    while (names:=busy()):
        print("Waiting for exclusive measurement interval:",names.replace("\n",", "),flush=True)
        time.sleep(15)
def run(name,backend,config,trial):
    if (H/"STOP_VERIFIED").exists():
        print("Stopped at a completed-run boundary",flush=True)
        raise SystemExit(0)
    stem=f"{name}__{backend}__{config}__t{trial}"
    path=OUT/f"{stem}.json"
    exe=H/"bin-verified"/f"bench-{name}.exe"
    digest=hashlib.sha256(exe.read_bytes()).hexdigest()
    receipt=OUT/f"{stem}.receipt.json"
    if path.exists():
        meta=json.loads(receipt.read_text())
        assert meta["exe_sha256"]==digest and meta["rc"]==0
        json.loads(path.read_text())
        return
    start=time.perf_counter()
    p=subprocess.run([str(exe),backend,config,str(trial),name],capture_output=True,text=True,timeout=600)
    path.write_text(p.stdout,encoding="utf-8")
    (OUT/f"{stem}.stderr.txt").write_text(p.stderr,encoding="utf-8")
    receipt.write_text(json.dumps({"rc":p.returncode,"exe_sha256":digest,"wall_s":time.perf_counter()-start,
        "settle_after_s":2,"utc":datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2))
    if p.returncode:
        print(p.stdout[-2000:],p.stderr[-4000:],flush=True)
        raise SystemExit(p.returncode)
    json.loads(p.stdout)
    time.sleep(2)
gate()
time.sleep(10)
start=time.perf_counter()
for t in range(1,trials+1):
    gate()
    order=variants[t-1:]+variants[:t-1]
    if t%2==0: order=order[::-1]
    for backend in ["vulkan","d3d12"]:
        for cfg in configs:
            gate()
            for name in order: run(name,backend,cfg,t)
            print(f"trial={t} {backend}/{cfg} complete elapsed={time.perf_counter()-start:.1f}s",flush=True)
    run("vma","vulkan","default",t)
(H/"DIRECT_COMPLETE").write_text(datetime.datetime.now(datetime.timezone.utc).isoformat())
print("Direct suite complete",flush=True)

