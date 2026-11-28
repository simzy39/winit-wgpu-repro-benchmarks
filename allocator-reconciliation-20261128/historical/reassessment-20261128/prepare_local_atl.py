"""Extract the matching Microsoft ATL library locally without modifying Visual Studio."""
import pathlib, json, hashlib, urllib.request, zipfile
H=pathlib.Path(__file__).resolve().parent
catalog=pathlib.Path(r"<drive>/ProgramData\Microsoft\VisualStudio\Packages\_Instances\f908c9b4\catalog.json")
data=json.loads(catalog.read_text(encoding="utf-8-sig"))
package=next(p for p in data["packages"] if p["id"]=="Microsoft.VC.14.44.17.14.ATL.X64.base")
payload=package["payloads"][0]
assert payload["url"].startswith("https://download.visualstudio.microsoft.com/")
archive=H/"sources/atl-x64.vsix"
if not archive.exists():
    archive.write_bytes(urllib.request.urlopen(payload["url"],timeout=120).read())
assert hashlib.sha256(archive.read_bytes()).hexdigest()==payload["sha256"]
out=H/"tools/atl";out.mkdir(parents=True,exist_ok=True)
libraries={}
with zipfile.ZipFile(archive) as z:
    for name in z.namelist():
        if name.lower().endswith(".lib"):
            target=out/pathlib.PurePosixPath(name).name
            content=z.read(name)
            target.write_bytes(content)
            libraries[target.name]={"member":name,"sha256":hashlib.sha256(content).hexdigest()}
assert (out/"atls.lib").exists()
(H/"local-atl.json").write_text(json.dumps({"package":package,"catalog_sha256":hashlib.sha256(catalog.read_bytes()).hexdigest(),
    "libraries":libraries,"scope":"Extracted inside this experiment only; no Visual Studio or global environment change"},indent=2))
print("Prepared local ATL:",libraries)
