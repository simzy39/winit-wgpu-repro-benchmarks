import pathlib,json,subprocess,os,time
H=pathlib.Path(__file__).resolve().parent
old=json.loads((H/"validation.json").read_text())
checks=[r for r in old if r["rc"]!=0]
checks += [next(r for r in old if r["name"]==n) for n in ["fmt","unit-std","rustdoc"]]
nostd=next(r for r in old if r["name"]=="unit-std").copy()
nostd["name"]="unit-nostd"
nostd["command"]=[x.replace("std,vulkan,d3d12","hashbrown,vulkan,d3d12") for x in nostd["command"]]
checks.append(nostd)
out=[]
env=os.environ.copy();env["RUSTDOCFLAGS"]="-D warnings"
for r in checks:
    start=time.perf_counter()
    p=subprocess.run(r["command"],cwd=H/"work/cache2/gpu-allocator",env=env,capture_output=True,text=True)
    (H/"logs"/f"validation-recheck-{r['name']}.log").write_text(p.stdout+p.stderr,encoding="utf-8")
    out.append({"name":r["name"],"command":r["command"],"rc":p.returncode,"wall_s":time.perf_counter()-start})
    (H/"validation-recheck.json").write_text(json.dumps(out,indent=2))
    print(r["name"],p.returncode,flush=True)
    if p.returncode:print(p.stderr[-4000:],flush=True)

