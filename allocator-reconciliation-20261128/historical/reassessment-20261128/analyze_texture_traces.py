"""Compare allocation inputs and identify deliberately changed free order."""
import pathlib, re, json
H = pathlib.Path(__file__).resolve().parent
root = H / "texture-api-traces"
def events(path):
    result = []
    handles = {}
    serial = 0
    for block in re.split(r"(?m)^Thread \d+, Frame \d+:\n", path.read_text()):
        match = re.match(r"(vkAllocateMemory|vkFreeMemory|vkMapMemory|vkUnmapMemory)\(", block)
        if not match: continue
        name = match[1]
        def value(key):
            m = re.search(r"(?m)^\s*" + key + r":.*?=\s*(\S+)", block)
            assert m, (key, block)
            return m[1]
        event = {"api": name}
        if name == "vkAllocateMemory":
            handle = value("pMemory")
            handles[handle] = serial
            event.update(allocation_id=serial, bytes=int(value("allocationSize")), memory_type=int(value("memoryTypeIndex")), pNext=value("pNext"))
            serial += 1
        else:
            event["allocation_id"] = handles[value("memory")]
            if name == "vkMapMemory":
                event.update(offset=value("offset"), size=value("size"), flags=value("flags"))
        result.append(event)
    return result
data = {}
for mode in ["alone", "original_order"]:
    for variant in ["pr323", "cache2"]:
        data[variant + "-" + mode] = events(root / (variant + "-" + mode + ".txt"))
allocation_inputs = {}
for key, sequence in data.items():
    relevant = [event for event in sequence if event["api"] == "vkAllocateMemory" and event["memory_type"] == 0 and event["bytes"] == 256 * 1048576][:2]
    allocation_inputs[key] = [{k:v for k,v in event.items() if k != "allocation_id"} for event in relevant]
assert all(len(v) == 2 for v in allocation_inputs.values())
assert len({json.dumps(v, sort_keys=True) for v in allocation_inputs.values()}) == 1
out = {"matching_texture_allocation_inputs": True, "allocation_inputs": allocation_inputs,
    "events": data, "interpretation": "Texture allocations request two 256 MiB blocks from type zero with null pNext in all four traces. Cache retention intentionally changes which empty handle is freed first. Trace timings are excluded."}
(H / "texture-api-comparison.json").write_text(json.dumps(out, indent=2))
print({"matching_texture_allocation_inputs": True, "alone_events": {k:v for k,v in data.items() if k.endswith("-alone")}})
