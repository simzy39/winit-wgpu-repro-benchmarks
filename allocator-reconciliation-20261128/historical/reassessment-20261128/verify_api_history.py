import pathlib,json,re,hashlib
H=pathlib.Path(__file__).resolve().parent
D=H.parent/"results/apidump"
def stream(path):
    rows=[]
    relevant=False
    for line in path.read_text().splitlines():
        if line.startswith("vk"):
            relevant=line.startswith(("vkAllocateMemory(","vkFreeMemory(","vkMapMemory(","vkUnmapMemory("))
            if relevant: rows.append(line)
        elif relevant and re.search(r"\b(allocationSize|memoryTypeIndex|offset|size|flags):",line):
            rows.append(line.strip())
    return rows
data={}
for name in ["pr323","proto"]:
    data[name]=stream(D/f"{name}_detailed_1.txt")
payload={key:hashlib.sha256("\n".join(value).encode()).hexdigest() for key,value in data.items()}
out={"equal":data["pr323"]==data["proto"],"normalized_sha256":payload,
     "api_calls":sum(x.startswith("vk") for x in data["pr323"]),
     "method":"Keep allocate/free/map/unmap calls and allocation size, type, mapping size, offset and flags. api_dump already anonymized handle and pointer addresses."}
(H/"historical-api-equivalence.json").write_text(json.dumps(out,indent=2))
print(out)

