import pathlib,subprocess,shutil
H=pathlib.Path(__file__).resolve().parent;P=H.parent/'reassessment-20261128'
repo=H/'wgpu/both'
if not repo.exists():
    subprocess.run(['git','-C',str(H/'wgpu/upstream'),'worktree','add','--detach',str(repo),'60cef2be828e03ba54e2e1598001b4625c0c2163'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run(['git','-C',str(repo),'apply',str(H/'sources/wgpu-prior-both.patch')],check=True)
for name,allocator,state in [('cache2-both','cache2','both'),('recovery-both','recovery','both'),('recovery-candidate','recovery','candidate'),('recovery-singlepool','recovery','singlepool')]:
    folder=H/'downstream'/name
    (folder/'src').mkdir(parents=True,exist_ok=True)
    old=P/'downstream/bench/cache2-both'
    manifest=(old/'Cargo.toml').read_text()
    manifest=manifest.replace(str(P/'downstream/trees/both').replace('\\','/'),str(H/'wgpu'/state).replace('\\','/'))
    manifest=manifest.replace(str(P/'work/cache2/gpu-allocator').replace('\\','/'),str(H/'work'/allocator/'gpu-allocator').replace('\\','/'))
    assert str(P).replace('\\','/') not in manifest
    (folder/'Cargo.toml').write_text(manifest)
    shutil.copyfile(old/'Cargo.lock',folder/'Cargo.lock')
    shutil.copyfile(old/'src/main.rs',folder/'src/main.rs')
config=H/'wgpu/candidate/.cargo/config.toml'
s=config.read_text();assert '[patch.crates-io.gpu-allocator]' not in s
s+='\n[patch.crates-io.gpu-allocator]\npath = "'+str(H/'work/recovery/gpu-allocator').replace('\\','/')+'"\n'
config.write_text(s)
print('Prepared four paired downstream builds and isolated test path override')
