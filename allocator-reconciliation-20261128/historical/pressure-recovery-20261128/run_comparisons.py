"""Interleaved comparisons, serialized after compilation and GPU validation."""
import pathlib,subprocess,hashlib,json,time,datetime,ctypes
H=pathlib.Path(__file__).resolve().parent
out=H/'results/direct-isolated';out.mkdir(parents=True,exist_ok=True)
names=['main','pr323','cache2','recovery','smallcache','heapcap','packed']
def busy():
    p=subprocess.run(['powershell','-NoProfile','-Command','Get-Process -Name cargo,rustc,wgpu-gpu,wgpu-examples -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessName'],capture_output=True,text=True)
    return p.stdout.strip()
def gate():
    while busy():time.sleep(10)
def run(name,backend,config,trial):
    stem=f'{name}__{backend}__{config}__t{trial}'
    path=out/(stem+'.json');receipt=out/(stem+'.receipt.json')
    exe=H/'bin-isolated'/('bench-'+name+'.exe');digest=hashlib.sha256(exe.read_bytes()).hexdigest()
    if path.exists():
        old=json.loads(receipt.read_text());assert old['rc']==0 and old['exe_sha256']==digest;return
    command=[str(exe),backend,config,str(trial),name]
    start=time.perf_counter();p=subprocess.run(command,capture_output=True,text=True,timeout=300)
    path.write_text(p.stdout);(out/(stem+'.stderr.txt')).write_text(p.stderr)
    receipt.write_text(json.dumps({'rc':p.returncode,'command':command,'exe_sha256':digest,'wall_s':time.perf_counter()-start,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'settle_s':2},indent=2))
    assert not p.returncode,stem
    json.loads(p.stdout);time.sleep(2)
while not (H/'BUILDS_ISOLATED_COMPLETE').exists():time.sleep(10)
# Both complete suites must finish; a compiler-free gap between builds is insufficient.
while not all((H/marker).exists() for marker in ['VALIDATION_COMPLETE','REVALIDATION_COMPLETE','MSRV_FINAL_COMPLETE','UPSTREAM_CONTROL_COMPLETE','PATH_CONTROLS_COMPLETE']):time.sleep(10)
kernel=ctypes.windll.kernel32;kernel.SetThreadExecutionState(0x80000001)
try:
    gate();time.sleep(10)
    for trial in range(1,6):
        order=names[trial-1:]+names[:trial-1]
        if trial%2==0:order.reverse()
        for backend in ['vulkan','d3d12']:
            for config in ['memory_usage','performance','manual']:
                gate()
                for name in order:run(name,backend,config,trial)
                print(trial,backend,config,flush=True)
finally:kernel.SetThreadExecutionState(0x80000000)
(H/'DIRECT_COMPLETE').write_text('complete')
