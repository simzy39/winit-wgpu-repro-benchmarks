"""Download a verified nextest release into the isolated research tools directory."""
import pathlib,json,urllib.request,hashlib,zipfile,io,subprocess
H=pathlib.Path(__file__).resolve().parent
out=H/"tools";out.mkdir(exist_ok=True)
def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"gpu-allocator-research","Accept":"application/vnd.github+json"} if "api.github.com" in url else {"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=60) as response:return response.read()
meta=json.loads(get("https://api.github.com/repos/nextest-rs/nextest/releases/latest"))
(out/"nextest-release.json").write_text(json.dumps(meta,indent=2))
candidates=[a for a in meta["assets"] if "x86_64-pc-windows-msvc" in a["name"] and a["name"].endswith(".zip")]
assert len(candidates)==1,[a["name"] for a in meta["assets"]]
asset=candidates[0]
data=get(asset["browser_download_url"])
actual=hashlib.sha256(data).hexdigest()
digest=asset.get("digest","")
if digest.startswith("sha256:"):assert actual==digest.removeprefix("sha256:")
else:
    checksum=next(a for a in meta["assets"] if a["name"]==asset["name"]+".sha256")
    assert actual==get(checksum["browser_download_url"]).decode().split()[0]
(out/asset["name"]).write_bytes(data)
archive=zipfile.ZipFile(io.BytesIO(data))
names=[n for n in archive.namelist() if pathlib.PurePosixPath(n).name=="cargo-nextest.exe"]
assert len(names)==1
exe=out/"cargo-nextest.exe"
exe.write_bytes(archive.read(names[0]))
receipt={"version":meta["tag_name"],"asset":asset["browser_download_url"],"zip_sha256":actual,
         "exe_sha256":hashlib.sha256(exe.read_bytes()).hexdigest()}
(out/"nextest-install.json").write_text(json.dumps(receipt,indent=2))
print(receipt)
subprocess.run([str(exe),"nextest","--version"],check=True)

