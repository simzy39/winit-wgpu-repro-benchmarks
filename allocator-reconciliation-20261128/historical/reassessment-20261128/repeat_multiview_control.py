"""Resolve the single asymmetric focused outcome using alternating frozen executables."""
import pathlib,json,os,subprocess,shutil,xml.etree.ElementTree as ET,time
H=pathlib.Path(__file__).resolve().parent;R=H/"downstream/validation";O=H/"wgpu-failure-controls"
rows=json.loads((H/"failure-triage.json").read_text())["rows"]
case=next(r for r in rows if r["classification"]=="candidate-only in focused control: investigate")
assert case["name"].endswith("wgpu_gpu::multiview::draw_multiview_single")
escape=lambda s:s.replace("\\","\\\\").replace(")","\\)").replace(",","\\,").replace("/","\\/")
expression="binary_id(="+escape(case["binary"])+") & test(="+escape(case["name"])+")"
env=os.environ.copy();env["PATH"]=str(H/"tools")+";"+r"<drive>/VulkanSDK\1.4.363.0\Bin"+";"+str(R/"target/debug/deps")+";"+env["PATH"]
env.update(WGPU_BACKEND="dx12,vulkan",NEXTEST_TEST_THREADS="2",WGPU_DX12_AGILITY_SDK_PATH=str(next((R/"target/agility-sdk").rglob("D3D12Core.dll")).parent),WGPU_DX12_AGILITY_SDK_VERSION="619",WGPU_DX12_AGILITY_SDK_REQUIRE="1")
out=[]
for trial in range(1,6):
    for label in (["pr323","candidate"] if trial%2 else ["candidate","pr323"]):
        log=O/f"multiview-{label}-{trial}.log";assert not log.exists()
        command=["cargo","nextest","run","--binaries-metadata",str(O/(label+"-frozen-binaries.json")),"-E",expression,"--no-fail-fast"]
        with log.open("w") as stream:p=subprocess.run(command,cwd=R,env=env,stdout=stream,stderr=subprocess.STDOUT)
        target=O/f"multiview-{label}-{trial}.xml";shutil.copyfile(R/"target/nextest/default/junit.xml",target)
        root=ET.parse(target).getroot();assert root.attrib["tests"]=="1",root.attrib
        out.append({"trial":trial,"label":label,"rc":p.returncode,"failed":root.attrib["failures"]!="0","log":str(log.relative_to(H)),"junit":str(target.relative_to(H))})
        print(out[-1],flush=True)
    if trial>=3 and any(r["failed"] and r["label"]=="pr323" for r in out):break
(H/"multiview-control-repeats.json").write_text(json.dumps({"binary":case["binary"],"name":case["name"],"runs":out},indent=2))
