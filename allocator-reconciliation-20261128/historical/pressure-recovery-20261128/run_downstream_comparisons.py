"""Focused paired downstream cases, all with independent build directories."""
import pathlib,subprocess,json,hashlib,time,datetime,re,ctypes
H=pathlib.Path(__file__).resolve().parent
out=H/'results/downstream-isolated';out.mkdir(parents=True,exist_ok=True)
while not all((H/marker).exists() for marker in ['DIRECT_COMPLETE','ARCHITECTURE_SELECTED.json','WG_BUILDS_ISOLATED_COMPLETE']):time.sleep(10)
names=['cache2-both','recovery-both','recovery-candidate','recovery-singlepool']
cases=[('performance','idle'),('performance','repeated_uploads'),('performance','sustained_render'),('memory_usage','churn'),('manual-8-256','large_textures')]
kernel=ctypes.windll.kernel32;kernel.SetThreadExecutionState(0x80000001)
try:
    time.sleep(10)
    for trial in range(1,6):
        order=names[trial-1:]+names[:trial-1]
        if trial%2==0:order.reverse()
        for hints,workload in cases:
            for name in order:
                stem=f'{name}__dx12__{hints}__{workload}__t{trial}'
                path=out/(stem+'.json');receipt=out/(stem+'.receipt.json')
                exe=H/'bin-wgpu-isolated'/(name+'.exe');digest=hashlib.sha256(exe.read_bytes()).hexdigest()
                if path.exists():
                    meta=json.loads(receipt.read_text());assert meta['rc']==0 and meta['exe_sha256']==digest;continue
                command=[str(exe),'--backend','dx12','--hints',hints,'--workload',workload,'--json',str(path)]
                start=time.perf_counter();p=subprocess.run(command,capture_output=True,text=True,timeout=600)
                (out/(stem+'.stdout.txt')).write_text(p.stdout);(out/(stem+'.stderr.txt')).write_text(p.stderr)
                error=bool(re.search(r'VUID-|Validation Error|panicked',p.stdout+p.stderr,re.I))
                receipt.write_text(json.dumps({'rc':p.returncode,'command':command,'exe_sha256':digest,'wall_s':time.perf_counter()-start,'validation_error':error,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'settle_s':2},indent=2))
                assert p.returncode==0 and not error,stem
                json.loads(path.read_text());time.sleep(2)
            print(trial,hints,workload,flush=True)
finally:kernel.SetThreadExecutionState(0x80000000)
(H/'DOWNSTREAM_COMPLETE').write_text('complete')
