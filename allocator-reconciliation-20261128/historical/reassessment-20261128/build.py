import pathlib, subprocess, os, shutil, hashlib, json, sys
HERE=pathlib.Path(__file__).resolve().parent
variants=sys.argv[1:] or ["main","pr323","proposal","retain2","demand2","request","vma-policy"]
(HERE/"bin-verified").mkdir(exist_ok=True)
(HERE/"logs").mkdir(exist_ok=True)
records=[]
for name in variants:
    folder=HERE/"work"/name
    env=os.environ.copy()
    env["BENCH_VARIANT"]=name
    cmd=["cargo","build","--release","--offline","-p","gpua-policy-bench","--target-dir",str(HERE/("target-"+name))]
    p=subprocess.run(cmd,cwd=folder,env=env,capture_output=True,text=True)
    (HERE/"logs"/f"build-verified-{name}.log").write_text(p.stdout+p.stderr,encoding="utf-8")
    if p.returncode:
        print(p.stderr[-7000:],flush=True)
        raise SystemExit(p.returncode)
    exe=HERE/"bin-verified"/f"bench-{name}.exe"
    shutil.copyfile(HERE/("target-"+name)/"release/gpua-policy-bench.exe",exe)
    diff=subprocess.check_output(["git","-C",str(folder/"gpu-allocator"),"diff","--binary"])
    record={"name":name,"exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),
            "source_diff_sha256":hashlib.sha256(diff).hexdigest(),
            "lock_sha256":hashlib.sha256((folder/"Cargo.lock").read_bytes()).hexdigest(),"command":cmd}
    records.append(record)
    (HERE/"bin-verified"/f"{name}.json").write_text(json.dumps(record,indent=2))
    print(f"built {name}",flush=True)

