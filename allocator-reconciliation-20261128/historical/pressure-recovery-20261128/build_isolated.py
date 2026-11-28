"""Unique targets, seeded only with unchanged third-party artifacts."""
import pathlib,subprocess,shutil,os,json,hashlib,sys,time
H=pathlib.Path(__file__).resolve().parent
mode=sys.argv[1];env=os.environ.copy();env['CARGO_BUILD_JOBS']='2'
if mode=='wgpu':
    while not (H/'ARCHITECTURE_SELECTED.json').exists():time.sleep(10)
names=['main','pr323','cache2','recovery','smallcache','heapcap','packed'] if mode=='direct' else ['cache2-both','recovery-both','recovery-candidate','recovery-singlepool']
seed=H/('target-comparisons' if mode=='direct' else 'target-wgpu-bench')
out=H/('bin-isolated' if mode=='direct' else 'bin-wgpu-isolated');out.mkdir(exist_ok=True)
exclude=['gpu_allocator','gpu-allocator','gpua_policy_bench','gpua-policy-bench']
if mode!='direct':exclude+=['wgpu','naga']
def ignore(directory,names):return [name for name in names if any(part in name.lower() for part in exclude)]
for name in names:
    folder=H/('work' if mode=='direct' else 'downstream')/name
    target=H/('target-isolated-'+mode+'-'+name)
    assert target.resolve().parent==H.resolve()
    existing=out/(name+'.json')
    if existing.exists():
        record=json.loads(existing.read_text())
        exe=out/(('bench-' if mode=='direct' else '')+name+'.exe')
        assert hashlib.sha256(exe.read_bytes()).hexdigest()==record['exe_sha256']
        print('Preserved isolated '+name,flush=True);continue
    # Extended Windows paths avoid MAX_PATH failures when seeding proc-macro outputs.
    prefix=lambda path: ('\\\\?\\'+str(path.resolve())) if os.name=='nt' else str(path)
    shutil.copytree(prefix(seed),prefix(target),ignore=ignore,dirs_exist_ok=True)
    env['BENCH_VARIANT']=name
    command=['cargo','build','--release','--locked','--offline','--target-dir',str(target)]
    if mode=='direct':command+=['-p','gpua-policy-bench']
    log=H/'logs'/('build-isolated-'+mode+'-'+name+'.log');assert not log.exists()
    with log.open('w') as stream:p=subprocess.run(command,cwd=folder,env=env,stdout=stream,stderr=subprocess.STDOUT)
    assert not p.returncode,(name,log.read_text()[-4000:])
    output=log.read_text()
    assert 'Compiling gpu-allocator ' in output,(name,'allocator was not rebuilt')
    if mode!='direct':
        for package in ['wgpu-hal','wgpu-core','wgpu']:assert 'Compiling '+package+' ' in output,(name,package)
    binary='gpua-policy-bench.exe' if mode=='direct' else 'wgpu-mem-bench.exe'
    exe=out/(('bench-' if mode=='direct' else '')+name+'.exe');shutil.copyfile(target/'release'/binary,exe)
    sources={}
    allocator=name if mode=='direct' else name.split('-')[0]
    for path in sorted((H/'work'/allocator/'gpu-allocator/src').rglob('*.rs')):
        sources[str(path.relative_to(H/'work'/allocator/'gpu-allocator'))]=hashlib.sha256(path.read_bytes()).hexdigest()
    record={'name':name,'command':command,'target':str(target),'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'lock_sha256':hashlib.sha256((folder/'Cargo.lock').read_bytes()).hexdigest(),'allocator_source_files':sources,'excluded_seed_patterns':exclude,'verified_recompiled':True}
    (out/(name+'.json')).write_text(json.dumps(record,indent=2));print('Isolated '+mode+' '+name,flush=True)
(H/('BUILDS_ISOLATED_COMPLETE' if mode=='direct' else 'WG_BUILDS_ISOLATED_COMPLETE')).write_text('complete')
