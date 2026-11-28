"""Check declared Rust 1.71 with fresh and explicitly compatible consumer graphs."""
import pathlib,subprocess,json,os
H=pathlib.Path(__file__).resolve().parent
rows=[]
env=os.environ.copy();env["CARGO_BUILD_JOBS"]="2"
for variant in ["pr323","cache2","recovery"]:
    for mode,features in [("std-vulkan","std,vulkan"),("std-d3d12","std,d3d12"),("nostd-vulkan","hashbrown,vulkan")]:
        for graph in ["latest","compatible"]:
            folder=H/"msrv"/(variant+"-"+mode+"-"+graph)
            (folder/"src").mkdir(parents=True,exist_ok=True)
            manifest='[package]\nname="msrv-probe"\nversion="0.0.0"\nedition="2021"\nrust-version="1.71"\n[workspace]\n[dependencies]\n'
            path=str(H/"work"/variant/"gpu-allocator").replace("\\","/")
            manifest+='gpu-allocator={path="'+path+'",default-features=false,features=['+','.join('"'+f+'"' for f in features.split(','))+']}\n'
            if graph=="compatible":
                manifest+='thiserror={version="=2.0.20",default-features=false}\n'
                if "d3d12" in features:manifest+='windows={version="=0.58.0",features=["Win32_Graphics_Direct3D12","Win32_Graphics_Dxgi_Common"]}\n'
            (folder/"Cargo.toml").write_text(manifest)
            (folder/"src/lib.rs").write_text('#![no_std]\npub fn sizes() -> gpu_allocator::AllocationSizes { gpu_allocator::AllocationSizes::default() }\n')
            prefix=variant+"-"+mode+"-"+graph
            if graph=="compatible":
                p=subprocess.run(["cargo","+stable","generate-lockfile","--manifest-path",str(folder/"Cargo.toml")],cwd=H,env=env,capture_output=True,text=True)
                (H/"logs"/("msrv-resolve-"+prefix+".log")).write_text(p.stdout+p.stderr)
                if p.returncode:
                    rows.append({"variant":variant,"mode":mode,"graph":graph,"phase":"resolve","rc":p.returncode});continue
                lock=folder/"Cargo.lock";s=lock.read_text();lock.write_text(s.replace("version = 4\n","version = 3\n",1))
            command=["cargo","+1.71.0","check","--manifest-path",str(folder/"Cargo.toml"),"--lib"]
            if graph=="compatible":command.append("--locked")
            else:command.append("--offline")
            p=subprocess.run(command,cwd=H,env=env,capture_output=True,text=True)
            (H/"logs"/("msrv-"+prefix+".log")).write_text(p.stdout+p.stderr)
            row={"variant":variant,"mode":mode,"graph":graph,"phase":"build","rc":p.returncode,"command":command}
            rows.append(row);(H/"msrv-results.json").write_text(json.dumps(rows,indent=2))
            print(row,flush=True)
(H/"MSRV_INITIAL_COMPLETE").write_text("complete")
