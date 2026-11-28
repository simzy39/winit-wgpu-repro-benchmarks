"""Archive the failed full-suite results and record an exact nextest failure filter."""
import pathlib,json,shutil,xml.etree.ElementTree as ET,subprocess,os
H=pathlib.Path(__file__).resolve().parent
repo=H/"downstream/validation"
target=H/"wgpu-failure-controls";target.mkdir(exist_ok=True)
for source,name in [(repo/"target/nextest/default/junit.xml","candidate-full-junit.xml"),(H/"logs/wgpu-full-tests.log","candidate-full.log"),(H/"wgpu-full-tests.json","candidate-full.json"),(repo/".gpuconfig","gpuconfig.json")]:
    if (target/name).exists():
        assert (target/name).read_bytes() == source.read_bytes()
    else:
        shutil.copyfile(source,target/name)
root=ET.parse(target/"candidate-full-junit.xml").getroot()
failures=[]
for case in root.iter("testcase"):
    fail=case.find("failure")
    if fail is None:fail=case.find("error")
    if fail is not None:
        failures.append({"binary_id":case.attrib["classname"],"name":case.attrib["name"],"failure":dict(fail.attrib),"text":fail.text})
assert len(failures)==26
# Nextest exact matchers use escaped strings, with no embedded quotation marks.
def escape(value):
    return value.replace("\\","\\\\").replace(")","\\)").replace(",","\\,").replace("/","\\/")
expression=" | ".join("(binary_id(="+escape(r["binary_id"])+") & test(="+escape(r["name"])+"))" for r in failures)
(target/"failures.json").write_text(json.dumps({"full_tests":2205,"passed":2179,"failed_or_timed_out":26,"failures":failures,"filter":expression},indent=2))
env=os.environ.copy();env["PATH"]=str(H/"tools")+";"+env["PATH"]
env["LIB"]=str(H/"tools/atl")+";"+env.get("LIB","")
cmd=["cargo","nextest","list","--benches","--tests","--all-features","--list-type","binaries-only","--message-format","json"]
p=subprocess.run(cmd,cwd=repo,env=env,capture_output=True,text=True)
(target/"candidate-binaries.stderr.txt").write_text(p.stderr)
assert p.returncode==0,p.stderr
(target/"candidate-binaries.json").write_text(p.stdout)
data=json.loads(p.stdout)
print("Failure filter saved; binaries metadata keys:",list(data),flush=True)
