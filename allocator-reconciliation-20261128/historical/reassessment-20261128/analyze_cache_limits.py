import pathlib,json,collections,statistics,csv
H=pathlib.Path(__file__).resolve().parent
groups=collections.defaultdict(list)
processes=[]
for p in sorted((H/"results-cache-limits").glob("*.json")):
    if p.name.endswith(".receipt.json"):continue
    d=json.loads(p.read_text());r=json.loads(p.with_name(p.stem+".receipt.json").read_text())
    assert r["rc"]==0
    processes.append({"variant":d["variant"],"backend":d["backend"],"config":d["config"],"trial":d["trial"],**r["cpu_times"],"wall_s":r["wall_s"]})
    for name,w in d["result"]["workloads"].items():
        groups[d["variant"],d["backend"],d["config"],name].append(w)
rows=[]
for key,values in sorted(groups.items()):
    row=dict(zip(["variant","backend","config","workload"],key));row["trials"]=len(values)
    for name in ["blocks_created","peak_capacity_mib","retained_after_release_mib"]:
        row[name]=statistics.median(w[name] for w in values)
    times=[w["alloc_us"]["sum_ms"] for w in values]
    row["alloc_total_ms"]=statistics.median(times);row["alloc_total_min_ms"]=min(times);row["alloc_total_max_ms"]=max(times)
    rows.append(row)
out={"processes":len(processes),"cells":rows,"process_cpu":processes,
     "interpretation":"CPU time covers the whole ten-workload process, including setup, reporting and driver threads; it is not allocator-only CPU time."}
(H/"cache-limit-summary.json").write_text(json.dumps(out,indent=2))
with (H/"cache-limit-summary.csv").open("w",newline="") as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
for r in rows:
    if r["backend"]=="vulkan" and r["variant"] in ["cache2","cachemax"] and r["workload"] in ["mixed_frames","burst_release","textures"]:
        print(r)
print("processes",len(processes))

