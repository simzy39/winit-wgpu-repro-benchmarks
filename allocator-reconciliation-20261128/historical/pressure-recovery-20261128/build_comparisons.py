import pathlib,subprocess,shutil,os,json,hashlib,sys
H=pathlib.Path(__file__).resolve().parent
names=sys.argv[1:] or ['main','pr323','cache2','recovery','smallcache','heapcap','packed']
(H/'bin').mkdir(exist_ok=True)
env=os.environ.copy();env['CARGO_BUILD_JOBS']='2'
# Identical resolved dependency graph. Paths differ, package versions do not.
lock=(H/'work/recovery/Cargo.lock').read_bytes()
for name in names:
    folder=H/'work'/name
    env['BENCH_VARIANT']=name
    (folder/'Cargo.lock').write_bytes(lock)
    clean=['cargo','clean','-p','gpu-allocator','-p','gpua-policy-bench','--target-dir',str(H/'target-comparisons')]
    p=subprocess.run(clean,cwd=folder,env=env,capture_output=True,text=True)
    (H/'logs'/('clean-'+name+'.log')).write_text(p.stdout+p.stderr)
    assert not p.returncode,name
    command=['cargo','build','--release','--locked','--offline','-p','gpua-policy-bench','--target-dir',str(H/'target-comparisons')]
    with (H/'logs'/('build-'+name+'.log')).open('w') as log:
        p=subprocess.run(command,cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT)
    assert not p.returncode,name
    exe=H/'bin'/('bench-'+name+'.exe');shutil.copyfile(H/'target-comparisons/release/gpua-policy-bench.exe',exe)
    diff=subprocess.check_output(['git','-C',str(folder/'gpu-allocator'),'diff','--binary'])
    record={'name':name,'command':command,'clean':clean,'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'source_diff_sha256':hashlib.sha256(diff).hexdigest(),'lock_sha256':hashlib.sha256(lock).hexdigest()}
    (H/'bin'/(name+'.json')).write_text(json.dumps(record,indent=2))
    print('Built '+name,flush=True)
(H/'BUILDS_COMPLETE').write_text('complete')
