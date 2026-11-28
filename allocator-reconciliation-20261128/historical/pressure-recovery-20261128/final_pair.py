"""Exact final Windows source versus the frozen prior candidate, with isolated builds."""
import pathlib,subprocess,shutil,hashlib,json,os,time,datetime,ctypes
H=pathlib.Path(__file__).resolve().parent
while not (H/'FINAL_SOURCE_CHECKS_COMPLETE').exists():time.sleep(10)
env=os.environ.copy();env.update(CARGO_BUILD_JOBS='2',BENCH_VARIANT='recovery')
target=H/'target-final-recovery';out=H/'bin-final';out.mkdir(exist_ok=True)
assert target.resolve().parent==H.resolve() and not target.exists()
exclude=lambda directory,names:[name for name in names if any(part in name for part in ['gpu_allocator','gpu-allocator','gpua_policy_bench','gpua-policy-bench'])]
prefix=lambda path:'\\\\?\\'+str(path.resolve()) if os.name=='nt' else str(path)
shutil.copytree(prefix(H/'target-isolated-direct-recovery'),prefix(target),ignore=exclude)
command=['cargo','build','--release','--locked','--offline','-p','gpua-policy-bench','--target-dir',str(target)]
with (H/'logs/final-pair-build.log').open('w') as stream:p=subprocess.run(command,cwd=H/'work/recovery',env=env,stdout=stream,stderr=subprocess.STDOUT)
assert not p.returncode
assert 'Compiling gpu-allocator ' in (H/'logs/final-pair-build.log').read_text()
shutil.copyfile(target/'release/gpua-policy-bench.exe',out/'bench-recovery.exe')
shutil.copyfile(H/'bin-isolated/bench-cache2.exe',out/'bench-cache2.exe')
for name in ['cache2','recovery']:
    source=H/'work'/name/'gpu-allocator'
    files={str(path.relative_to(source)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted((source/'src').rglob('*.rs'))}
    exe=out/('bench-'+name+'.exe')
    (out/(name+'.json')).write_text(json.dumps({'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'source_files':files,'lock_sha256':hashlib.sha256((H/'work'/name/'Cargo.lock').read_bytes()).hexdigest()},indent=2))
results=H/'results/final-pair';results.mkdir(parents=True,exist_ok=True)
kernel=ctypes.windll.kernel32;kernel.SetThreadExecutionState(0x80000001)
try:
    time.sleep(10)
    for trial in range(1,6):
        names=['cache2','recovery'] if trial%2 else ['recovery','cache2']
        for backend in ['vulkan','d3d12']:
            for config in ['memory_usage','performance','manual']:
                for name in names:
                    stem=f'{name}__{backend}__{config}__t{trial}';path=results/(stem+'.json');assert not path.exists()
                    exe=out/('bench-'+name+'.exe');command=[str(exe),backend,config,str(trial),name]
                    start=time.perf_counter();p=subprocess.run(command,capture_output=True,text=True,timeout=300)
                    path.write_text(p.stdout);(results/(stem+'.stderr.txt')).write_text(p.stderr)
                    (results/(stem+'.receipt.json')).write_text(json.dumps({'rc':p.returncode,'command':command,'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'wall_s':time.perf_counter()-start,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'settle_s':2},indent=2))
                    assert not p.returncode;json.loads(p.stdout);time.sleep(2)
        print('Final pair trial',trial,flush=True)
finally:kernel.SetThreadExecutionState(0x80000000)
(H/'FINAL_PAIR_COMPLETE').write_text('complete')
