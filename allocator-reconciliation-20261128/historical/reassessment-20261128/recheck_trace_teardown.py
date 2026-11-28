"""Check whether the same api_dump teardown crash occurs on the unchanged allocator PR."""
import pathlib,os,subprocess,json
H=pathlib.Path(__file__).resolve().parent
out=H/"texture-api-traces"
rows=[]
for trial in range(1,9):
    env=os.environ.copy()
    env.pop("TEXTURES_ONLY",None)
    path=out/f"pr323-teardown-repeat-{trial}.txt"
    assert not path.exists()
    env.update(VK_INSTANCE_LAYERS="VK_LAYER_LUNARG_api_dump",VK_LAYER_PATH=r"<drive>/VulkanSDK\1.4.363.0\Bin",
        VK_APIDUMP_LOG_FILENAME=str(path),VK_APIDUMP_OUTPUT_FORMAT="text",VK_APIDUMP_FILE="true",VK_APIDUMP_FLUSH="true")
    p=subprocess.run([str(H/"diagnostics/pr323/bench.exe"),"vulkan","default",str(trial),"pr323-trace-repeat"],env=env,capture_output=True,text=True,timeout=300)
    (out/f"pr323-teardown-repeat-{trial}.stdout.txt").write_text(p.stdout)
    (out/f"pr323-teardown-repeat-{trial}.stderr.txt").write_text(p.stderr)
    tail=path.read_text().splitlines()[-8:]
    row={"trial":trial,"rc":p.returncode,"tail":tail,"timings_excluded":True}
    rows.append(row)
    print(row,flush=True)
    if p.returncode:break
(H/"trace-teardown-recheck.json").write_text(json.dumps(rows,indent=2))
