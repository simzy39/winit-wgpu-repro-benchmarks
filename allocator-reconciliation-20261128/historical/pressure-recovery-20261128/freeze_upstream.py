import pathlib,subprocess,os,json,shutil,hashlib
H=pathlib.Path(__file__).resolve().parent;R=H/'wgpu/upstream'
env=os.environ.copy();env['PATH']=str(H/'tools')+';'+env['PATH'];env['LIB']=str(H/'tools/atl')+';'+env.get('LIB','');env['CARGO_NET_OFFLINE']='true';env['CARGO_BUILD_JOBS']='2'
command=['cargo','nextest','list','--benches','--tests','--all-features','--list-type','binaries-only','--message-format','json']
p=subprocess.run(command,cwd=R,env=env,capture_output=True,text=True)
(H/'logs/upstream-binaries.log').write_text(p.stderr);assert not p.returncode,p.stderr
meta=json.loads(p.stdout);(H/'sources/upstream-binaries.json').write_text(p.stdout)
folder=H/'upstream-control-bin';folder.mkdir(exist_ok=True)
key='wgpu-test::wgpu-gpu';source=pathlib.Path(meta['rust-binaries'][key]['binary-path']);destination=folder/source.name
shutil.copyfile(source,destination);meta['rust-binaries'][key]['binary-path']=str(destination)
(H/'sources/upstream-frozen-binaries.json').write_text(json.dumps(meta,indent=2))
(H/'sources/upstream-executable.json').write_text(json.dumps({'original':str(source),'frozen':str(destination),'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'size':destination.stat().st_size},indent=2))
print('Archived clean upstream GPU test executable')
