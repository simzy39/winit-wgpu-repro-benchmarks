"""Export the complete candidate, including new tests, without creating a commit."""
import pathlib,subprocess,json,hashlib
H=pathlib.Path(__file__).resolve().parent
R=H/"work/cache2/gpu-allocator"
out=H/"patches";out.mkdir(exist_ok=True)
subprocess.run(["git","-C",str(R),"add","--intent-to-add","src/vulkan/capacity_tests.rs"],check=True)
records={}
for base,name,control in [
("179ea43f05332c2809addd7922cd056220efc36b","candidate-on-pr323-179ea43.patch",H.parent/"ws/pr323/gpu-allocator"),
("fc22df05140b15ed6d764beabd12a1b807011bc5","candidate-on-main-fc22df0.patch",H.parent/"ws/main/gpu-allocator")]:
    diff=subprocess.check_output(["git","-C",str(R),"diff","--binary",base])
    assert diff
    path=out/name
    path.write_bytes(diff)
    p=subprocess.run(["git","-C",str(control),"apply","--check",str(path)],capture_output=True,text=True)
    records[name]={"base":base,"sha256":hashlib.sha256(diff).hexdigest(),"apply_check_rc":p.returncode,"stderr":p.stderr}
    assert p.returncode==0,p.stderr
(out/"manifest.json").write_text(json.dumps(records,indent=2))
print(subprocess.check_output(["git","-C",str(R),"diff","--stat"],text=True))
print(records)

