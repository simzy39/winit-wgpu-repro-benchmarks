"""Windows native plan/benchmark runner. Requires Python 3.12+, Git and Rust.

python reproduce_allocator.py --source /path/to/gpu-allocator --output /path/to/run
Use separate output directories for every source variant. Never mix Cargo targets.
"""
from pathlib import Path
import argparse, subprocess, tarfile, io, json, shutil, hashlib, os

p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--trials',type=int,default=1);p.add_argument('--backend',choices=['d3d12','vulkan','both'],default='both')
a=p.parse_args();assert os.name=='nt','The supplied native harness targets Windows'
source=a.source.resolve();output=a.output.resolve();assert not output.exists(),'Use a fresh output directory'
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=source),'Commit tracked source changes before measuring'
output.mkdir(parents=True);library=output/'gpu-allocator';library.mkdir()
archive=subprocess.check_output(['git','archive','HEAD'],cwd=source)
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(library,filter='data')
bundle=Path(__file__).resolve().parent;inputs=bundle/'historical/pressure-recovery-20261128/repro-inputs'
bench=output/'bench';(bench/'src').mkdir(parents=True)
shutil.copyfile(inputs/'bench.rs',bench/'src/main.rs');shutil.copyfile(inputs/'bench.Cargo.toml',bench/'Cargo.toml')
shutil.copyfile(inputs/'bench.Cargo.lock',output/'Cargo.lock')
(output/'Cargo.toml').write_text('[workspace]\nresolver="2"\nmembers=["gpu-allocator","bench"]\n')
target=output/'target';env=os.environ.copy();env.update(CARGO_BUILD_JOBS='2',CARGO_INCREMENTAL='0',BENCH_VARIANT=revision)
command=['cargo','build','--release','--locked','-p','gpua-policy-bench','--target-dir',str(target)]
with (output/'build.log').open('w') as log:subprocess.run(command,cwd=output,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
exe=target/'release/gpua-policy-bench.exe';record={'allocator_revision':revision,'binary_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'build_command':command,'runs':[]}
for trial in range(1,a.trials+1):
    for api in (['d3d12','vulkan'] if a.backend=='both' else [a.backend]):
        for config in ['memory_usage','performance','manual']:
            name=f'{api}__{config}__t{trial}'
            result=subprocess.run([str(exe),api,config,str(trial),revision],cwd=output,capture_output=True,text=True,timeout=300)
            (output/(name+'.json')).write_text(result.stdout);(output/(name+'.stderr.txt')).write_text(result.stderr)
            record['runs'].append({'name':name,'returncode':result.returncode});(output/'receipt.json').write_text(json.dumps(record,indent=2))
            assert result.returncode==0;print(name,flush=True)
