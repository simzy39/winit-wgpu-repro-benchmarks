"""One final-source plan check per API/configuration, not a latency claim."""
import pathlib,subprocess,shutil,os,json,hashlib,time
H=pathlib.Path(__file__).resolve().parent
assert (H/'BACKOFF_SOURCE_CHECKS_COMPLETE').exists()
target=H/'target-backoff-final';assert not target.exists()
ignore=lambda directory,names:[n for n in names if any(x in n for x in ['gpu_allocator','gpu-allocator','gpua_policy_bench','gpua-policy-bench'])]
prefix=lambda p:'\\\\?\\'+str(p.resolve()) if os.name=='nt' else str(p)
shutil.copytree(prefix(H/'target-final-recovery'),prefix(target),ignore=ignore)
env=os.environ.copy();env.update(CARGO_BUILD_JOBS='2',BENCH_VARIANT='recovery')
command=['cargo','build','--release','--locked','--offline','-p','gpua-policy-bench','--target-dir',str(target)]
with (H/'logs/backoff-final-build.log').open('w') as log:p=subprocess.run(command,cwd=H/'work/recovery',env=env,stdout=log,stderr=subprocess.STDOUT)
assert not p.returncode
out=H/'results/backoff-plans';out.mkdir(parents=True)
exe=target/'release/gpua-policy-bench.exe';digest=hashlib.sha256(exe.read_bytes()).hexdigest()
fields=['blocks_created','blocks_destroyed','peak_capacity_mib','peak_allocated_mib','retained_after_release_mib','block_events','marks']
checks=[];time.sleep(10)
for backend in ['vulkan','d3d12']:
    for config in ['memory_usage','performance','manual']:
        name=f'recovery__{backend}__{config}__t1'
        command=[str(exe),backend,config,'1','recovery']
        p=subprocess.run(command,capture_output=True,text=True,timeout=300)
        (out/(name+'.json')).write_text(p.stdout);(out/(name+'.stderr.txt')).write_text(p.stderr);assert not p.returncode
        current=json.loads(p.stdout)['result']['workloads'];before=json.loads((H/'results/final-pair'/(name+'.json')).read_text())['result']['workloads']
        for workload in current:
            changes=[f for f in fields if current[workload][f]!=before[workload][f]]
            checks.append({'backend':backend,'config':config,'workload':workload,'changes':changes})
        time.sleep(2)
record={'exe_sha256':digest,'source_files':{str(p.relative_to(H/'work/recovery/gpu-allocator')):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((H/'work/recovery/gpu-allocator/src').rglob('*.rs'))},'cells':len(checks),'mismatches':[r for r in checks if r['changes']],'checks':checks,'timings':'One verification run per API/configuration; no statistical latency claim.'}
(H/'backoff-plan-verification.json').write_text(json.dumps(record,indent=2));assert not record['mismatches']
(H/'BACKOFF_PLANS_COMPLETE').write_text('complete');print('Final backoff plans match all',len(checks),'cells',flush=True)
