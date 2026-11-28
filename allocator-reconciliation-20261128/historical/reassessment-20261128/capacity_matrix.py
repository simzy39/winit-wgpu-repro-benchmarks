"""Independent table and boundary simulation, without invoking a GPU driver."""
import pathlib,json
H=pathlib.Path(__file__).resolve().parent
MIB=1024*1024
tables=json.loads((H.parent/"data/gpuinfo/memtables.json").read_text())["reports"]
configs={"default":(256,256,64,64),"performance":(128,256,64,128),
         "memory_usage":(8,64,4,32),"manual_large":(256,256,256,256)}
rows=[]
for table in tables:
    for heapindex,heap in table["heaps"].items():
        capacity=heap["size"]
        for index,flags in enumerate(heap["types"]):
            if any(any(excluded in f for excluded in ["LAZILY","PROTECTED","DEVICE_COHERENT","DEVICE_UNCACHED"]) for f in flags):
                continue
            visible=any("HOST_VISIBLE" in f for f in flags)
            for cfg,ranges in configs.items():
                minimum,maximum=ranges[2:] if visible else ranges[:2]
                minimum*=MIB
                maximum*=MIB
                for count in [0,1,2,7]:
                    request=MIB
                    old=min(minimum << min(count,7),maximum)
                    capped_min=min(minimum,capacity)
                    capped_max=min(maximum,capacity)
                    new=min(capped_min << min(count,7),capped_max)
                    assert 0<=new<=capacity
                    assert capped_min<=new<=capped_max
                    rows.append({"device":table["gpuname"],"url":table["url"],"heap_index":heapindex,
                        "type_within_heap":index,"flags":flags,"capacity":capacity,"config":cfg,
                        "active_blocks":count,"old_block":old,"new_block":new,"old_violation":old>capacity})
boundaries=[]
for capacity in [0,1,MIB,4*MIB-1,4*MIB,214*MIB+123,8*1024*MIB]:
    minimum=min(256*MIB,capacity)
    maximum=minimum
    # A cap does not round away the final bytes of a heap.
    assert maximum==min(capacity,256*MIB)
    for request in {0,1,max(0,capacity-1),capacity,capacity+1,2**64-1}:
        result="reject_before_driver" if request>capacity else "invalid_zero_request" if request==0 else "fits_capacity"
        boundaries.append({"capacity":capacity,"request":request,"result":result})
# Two memory types share a physical heap; independent per-type headroom would overcount it.
shared_heap={"heap_capacity":64*MIB,"budget":48*MIB,"type0_reserved":24*MIB,"type1_reserved":16*MIB,
             "aggregate_reserved":40*MIB,"remaining_budget":8*MIB,"next_block":16*MIB}
assert shared_heap["aggregate_reserved"]+shared_heap["remaining_budget"]==shared_heap["budget"]
shared_heap["next_block_exceeds_budget"]=shared_heap["next_block"]>shared_heap["remaining_budget"]
growth_case={"heap_bytes":214*MIB,"request_bytes":192*MIB,"configured_min":4*MIB,"configured_max":256*MIB,
    "upstream_main_block":192*MIB,"pr323_shared_block":256*MIB,"candidate_shared_block":214*MIB}
assert growth_case["upstream_main_block"]<=growth_case["heap_bytes"]<growth_case["pr323_shared_block"]
assert growth_case["request_bytes"]<=growth_case["candidate_shared_block"]<=growth_case["heap_bytes"]
out={"published_tables":len(tables),"comparisons":len(rows),"old_violations":sum(r["old_violation"] for r in rows),
     "growth_induced_violation":growth_case,
     "new_violations":sum(r["new_block"]>r["capacity"] for r in rows),"rows":rows,"boundaries":boundaries,
     "shared_heap_budget_fixture":shared_heap,
     "interpretation":"Synthetic static-capacity and aggregate-budget checks, not physical GPU measurements or a complete driver model."}
(H/"capacity-matrix.json").write_text(json.dumps(out,indent=2))
print({k:out[k] for k in ["published_tables","comparisons","old_violations","new_violations"]})

