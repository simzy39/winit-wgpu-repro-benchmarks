"""Final, locked source MSRV checks. Preserve the initial resolver experiment."""
import pathlib,subprocess,os,json,shutil
H=pathlib.Path(__file__).resolve().parent
env=os.environ.copy();env['CARGO_BUILD_JOBS']='2'
rows=[]
for variant in ['pr323','cache2','recovery']:
    for mode in ['std-vulkan','std-d3d12','nostd-vulkan']:
        source=H/'msrv'/(variant+'-'+mode+'-compatible')
        folder=H/'msrv-final'/(variant+'-'+mode)
        folder.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/'Cargo.toml',folder/'Cargo.toml')
        shutil.copyfile(source/'Cargo.lock',folder/'Cargo.lock')
        shutil.copytree(source/'src',folder/'src',dirs_exist_ok=True)
        commands=[]
        if mode=='std-d3d12':
            lock=(folder/'Cargo.lock').read_text()
            if 'name = "windows"\nversion = "0.62.2"' in lock:
                commands.append(['cargo','+stable','update','--manifest-path',str(folder/'Cargo.toml'),'-p','windows@0.62.2','--precise','0.58.0','--offline'])
        commands.append(['cargo','+1.71.0','check','--manifest-path',str(folder/'Cargo.toml'),'--lib','--locked','--offline'])
        output='';rc=0
        for command in commands:
            p=subprocess.run(command,env=env,capture_output=True,text=True)
            output+='COMMAND: '+repr(command)+'\n'+p.stdout+p.stderr
            if p.returncode:rc=p.returncode;break
            lock=folder/'Cargo.lock';lock.write_text(lock.read_text().replace('version = 4\n','version = 3\n',1))
        (H/'logs'/('msrv-final-'+variant+'-'+mode+'.log')).write_text(output)
        rows.append({'variant':variant,'mode':mode,'rc':rc,'commands':commands})
        (H/'msrv-final-results.json').write_text(json.dumps(rows,indent=2));print(rows[-1],flush=True)
(H/'MSRV_FINAL_COMPLETE').write_text('complete')
