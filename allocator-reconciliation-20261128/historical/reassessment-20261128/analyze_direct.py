"""Summarize verified direct measurements, preserving every cell and paired trial."""
import pathlib,json,statistics,collections,csv,math
H=pathlib.Path(__file__).resolve().parent
runs=[]
for path in sorted((H/"results-direct-verified").glob("*.json")):
    if path.name.endswith(".receipt.json"):continue
    d=json.loads(path.read_text())
    receipt=json.loads(path.with_name(path.stem+".receipt.json").read_text())
    assert receipt["rc"]==0
    runs.append(d)
cells=collections.defaultdict(list)
for d in runs:
    for workload,w in d["result"]["workloads"].items():
        cells[d["variant"],d["backend"],d["config"],workload].append((d["trial"],w))
def decision(w):
    return {k:w[k] for k in ["blocks_created","blocks_destroyed","peak_capacity_mib","peak_allocated_mib",
                             "retained_after_release_mib","block_events","marks"]}
def block_kinds(variant, config, workload, w):
    if variant=="vma-policy":
        maxima={"memory_usage":(64,32),"performance":(256,128),"manual":(256,128),"default":(256,64),"tiny_fixed":(8,4)}
        shared=dedicated=0
        for event in w["block_events"]:
            properties=w["per_location"][event["location"]]["memory_type"]
            visible="HOST_VISIBLE" in properties or "WRITE_" in properties
            threshold=maxima[config][1 if visible else 0]*1024*1024//2
            if event["request_bytes"]>threshold:dedicated+=1
            else:shared+=1
        return shared,dedicated,"explicit experiment threshold; raw size-equality inference corrected"
    if variant=="vma" and (H/"vma-native-counts.json").exists():
        native=json.loads((H/"vma-native-counts.json").read_text())["result"]["workloads"][workload]
        assert native["blocks_created"]==w["blocks_created"]
        locs=native["per_location"].values()
        return sum(x["shared_blocks_created"] for x in locs),sum(x["dedicated_blocks_created"] for x in native["per_location"].values()),"native AllocationInfo2 verification"
    locs=w["per_location"].values()
    return sum(x["shared_blocks_created"] for x in locs),sum(x["dedicated_blocks_created"] for x in w["per_location"].values()),"block-size inference"
rows=[]
nondeterministic=[]
for key,values in sorted(cells.items()):
    fingerprints={json.dumps(decision(w),sort_keys=True) for _,w in values}
    if len(fingerprints)>1:nondeterministic.append(key)
    row=dict(zip(["variant","backend","config","workload"],key))
    row["trials"]=len(values)
    kinds=[block_kinds(key[0],key[2],key[3],w) for _,w in values]
    row["shared_blocks_created"]=statistics.median(x[0] for x in kinds)
    row["dedicated_blocks_created"]=statistics.median(x[1] for x in kinds)
    row["block_kind_method"]=kinds[0][2]
    for field in ["blocks_created","blocks_destroyed","peak_capacity_mib","peak_allocated_mib",
                  "retained_after_release_mib","peak_unused_mib"]:
        row[field]=statistics.median(w[field] for _,w in values)
    for obj in ["alloc_us","free_us"]:
        for field in ["p50","p99","max","sum_ms"]:
            seq=[w[obj][field] for _,w in values]
            row[f"{obj}_{field}_median"]=statistics.median(seq)
            row[f"{obj}_{field}_min"]=min(seq)
            row[f"{obj}_{field}_max"]=max(seq)
    row["reuse_p50_us"]=statistics.median(w["reuse_us"]["p50"] for _,w in values)
    row["heap_creation_p50_us"]=statistics.median(w["heap_creation_us"]["p50"] for _,w in values)
    rows.append(row)
equivalence=[]
for (v,b,c,w),values in cells.items():
    if v!="pr323":continue
    other={t:x for t,x in cells.get(("proposal",b,c,w),[])}
    for trial,x in values:
        if trial in other:
            equivalence.append({"backend":b,"config":c,"workload":w,"trial":trial,"equal":decision(x)==decision(other[trial])})
paired=[]
for (v,b,c,w),values in cells.items():
    if v not in {"retain2","cache2","demand2","request","vma-policy"}:continue
    base={t:x for t,x in cells.get(("pr323",b,c,w),[])}
    for trial,x in values:
        if trial in base:
            y=base[trial]
            paired.append({"variant":v,"backend":b,"config":c,"workload":w,"trial":trial,
                "allocation_time_ratio":x["alloc_us"]["sum_ms"]/y["alloc_us"]["sum_ms"],
                "free_time_ratio":x["free_us"]["sum_ms"]/y["free_us"]["sum_ms"],
                "reserved_ratio":x["peak_capacity_mib"]/y["peak_capacity_mib"],
                "created_delta":x["blocks_created"]-y["blocks_created"],
                "retained_delta_mib":x["retained_after_release_mib"]-y["retained_after_release_mib"]})
out={"processes":len(runs),"workload_measurements":sum(len(d["result"]["workloads"]) for d in runs),
     "cells":rows,"nondeterministic":nondeterministic,
     "proposal_equivalence_comparisons":len(equivalence),"proposal_mismatches":[x for x in equivalence if not x["equal"]],
     "paired":paired}
(H/"direct-summary.json").write_text(json.dumps(out,indent=2))
with (H/"direct-summary.csv").open("w",newline="") as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]))
    writer.writeheader();writer.writerows(rows)
lines=["# Direct hardware measurements","","All cells are retained in direct-summary.csv and direct-summary.json. Values below are medians of process-level measurements. Allocation time sums exclude prepared resource requirements. p99 is computed within each workload, then summarized across trials.","",
       f"Processes: {len(runs)}. Workload measurements: {out['workload_measurements']}. Proposal decision mismatches: {len(out['proposal_mismatches'])}/{len(equivalence)}. Nondeterministic cells: {len(nondeterministic)}.",""]
for backend in ["vulkan","d3d12"]:
    for cfg in ["memory_usage","performance","manual","default","tiny_fixed"]:
        lines += [f"## {backend} {cfg}","","| Workload | Variant | Heaps created | Peak reserved MiB | Peak live MiB | Retained MiB | Alloc total ms median and range | Alloc p99 us | Free total ms |","|---|---|---:|---:|---:|---:|---|---:|---:|"]
        for r in rows:
            if r["backend"]!=backend or r["config"]!=cfg:continue
            lines.append(f"| {r['workload']} | {r['variant']} | {r['blocks_created']:.0f} | {r['peak_capacity_mib']:.2f} | {r['peak_allocated_mib']:.2f} | {r['retained_after_release_mib']:.2f} | {r['alloc_us_sum_ms_median']:.2f} ({r['alloc_us_sum_ms_min']:.2f} to {r['alloc_us_sum_ms_max']:.2f}) | {r['alloc_us_p99_median']:.2f} | {r['free_us_sum_ms_median']:.2f} |")
        lines.append("")
(H/"DIRECT_RESULTS.md").write_text("\n".join(lines),encoding="utf-8")
print({k:out[k] for k in ["processes","workload_measurements","proposal_equivalence_comparisons","proposal_mismatches","nondeterministic"]})

