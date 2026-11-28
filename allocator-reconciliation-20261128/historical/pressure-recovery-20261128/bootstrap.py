"""Initialize a new isolated continuation without changing prior research."""
import pathlib,subprocess,json,shutil,hashlib,datetime
H=pathlib.Path(__file__).resolve().parent
P=H.parent/"reassessment-20261128"
def run(*args,cwd=None):return subprocess.run(args,cwd=cwd,check=True,capture_output=True,text=True).stdout
for name in ["logs","sources","patches","results","tools"]:(H/name).mkdir(exist_ok=True)
old=json.loads((P/"final-recovery-audit.json").read_text())
states={path:{field:run("git","-C",path,*command) for field,command in {
    "head":["rev-parse","HEAD"],"status":["status","--short","--branch"],"diff":["diff","--stat"],"refs":["show-ref"]}.items()} for path in old["repositories"]}
(H/"initial-repositories.json").write_text(json.dumps(states,indent=2))
for name in ["main","pr323","cache2","recovery"]:
    folder=H/"work"/name;repo=folder/"gpu-allocator"
    assert not repo.exists(),"Preserve existing new worktrees"
    folder.mkdir(parents=True)
    revision="fc22df05140b15ed6d764beabd12a1b807011bc5" if name=="main" else "179ea43f05332c2809addd7922cd056220efc36b"
    run("git","-C",str(H.parent/"repo"),"worktree","add","--detach",str(repo),revision)
    if name in {"cache2","recovery"}:run("git","-C",str(repo),"apply",str(P/"patches/candidate-on-pr323-179ea43.patch"))
    (folder/"Cargo.toml").write_text('[workspace]\nmembers=["gpu-allocator","bench"]\nresolver="2"\n')
    (folder/"bench/src").mkdir(parents=True)
    shutil.copyfile(P/"repro-inputs/bench.rs",folder/"bench/src/main.rs")
    shutil.copyfile(P/"repro-inputs/cache2.bench.toml",folder/"bench/Cargo.toml")
    shutil.copyfile(P/"repro-inputs/cache2.Cargo.lock",folder/"Cargo.lock")
for name in ["cargo-nextest.exe","nextest-install.json"]:shutil.copyfile(P/"tools"/name,H/"tools"/name)
shutil.copytree(P/"tools/atl",H/"tools/atl")
run("git","-C",str(H.parent.parent/"winit-wgpu/repos/wgpu"),"worktree","add","--detach",str(H/"wgpu/upstream"),"60cef2be828e03ba54e2e1598001b4625c0c2163")
shutil.copyfile(H/"wgpu/upstream/AGENTS.md",H/"sources/wgpu-AGENTS.md")
(H/"BOOTSTRAP_COMPLETE").write_text(datetime.datetime.now(datetime.timezone.utc).isoformat())
print("Created four allocator controls and a clean upstream wgpu worktree")
