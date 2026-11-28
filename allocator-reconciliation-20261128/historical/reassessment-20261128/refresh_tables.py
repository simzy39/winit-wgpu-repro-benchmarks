import pathlib,json,urllib.request,gzip,hashlib,re,html
H=pathlib.Path(__file__).resolve().parent
records=json.loads((H.parent/"data/gpuinfo/memtables.json").read_text())["reports"]
out=H/"sources/gpuinfo"
out.mkdir(exist_ok=True)
summary=[]
for rep in records:
    try:
        req=urllib.request.Request(rep["url"],headers={"User-Agent":"Mozilla/5.0 (allocator research)"})
        with urllib.request.urlopen(req,timeout=20) as response:data=response.read()
        text=data.decode("utf-8")
        start=text.find("id='devicememory'")
        end=text.find("</table>",start)
        row=re.compile(r"<tr><td class='subkey'[^>]*>(.*?)</td><td>(.*?)</td><td>Memory heap (\d+)</td></tr>",re.S)
        heaps={}
        for key,value,heap in row.findall(text[start:end]):
            entry=heaps.setdefault(heap,{"size":None,"flags":[],"types":[]})
            flags=[html.unescape(x).strip() for x in re.split(r"<br>",value) if x.strip()]
            flags=[] if flags==["none"] else flags
            if key=="Flags":entry["flags"]=flags
            elif key=="Size":entry["size"]=int(re.sub(r"[^0-9]","",value))
            elif key.startswith("Memory type"):entry["types"].append(flags)
        assert heaps
        path=out/f"report-{rep['id']}.html.gz"
        with gzip.open(path,"wb") as stream:stream.write(data)
        entry={"id":rep["id"],"url":rep["url"],"sha256":hashlib.sha256(data).hexdigest(),
               "tables_equal":heaps==rep["heaps"],"heaps":heaps}
        summary.append(entry)
        print(rep["id"],entry["tables_equal"],len(data),flush=True)
    except Exception as exc:
        summary.append({"id":rep["id"],"error":str(exc)})
        print("Could not refresh report",rep["id"],str(exc),flush=True)
        # Stop on an access restriction rather than repeat it against every page.
        if isinstance(exc,urllib.error.HTTPError) and exc.code in [403,429]:break
(out/"verification.json").write_text(json.dumps(summary,indent=2))

