"""Policy model only; actual allocator fault-stream tests follow if warranted."""
import json,pathlib
H=pathlib.Path(__file__).resolve().parent
def run(policy,budget,count_limit,requests):
    blocks=[];calls=[];succeeded=0
    for request in requests:
        for block in blocks:
            if block['free']>=request:block['free']-=request;break
        else:
            if len(blocks)>=count_limit:break
            size=64
            while True:
                calls.append(size)
                if sum(b['size'] for b in blocks)+size<=budget:
                    blocks.append({'size':size,'free':size-request});break
                if size==request:return {'successes':succeeded,'calls':calls,'blocks':blocks}
                size=request if policy=='exact' else max(request,size//2)
            succeeded+=1;continue
        succeeded+=1
    return {'successes':succeeded,'calls':calls,'blocks':blocks}
rows=[]
for scenario,budget,count,requests in [('count_limited',48,2,[1]*48),('no_memory',0,4096,[1]),('large_resource',12,4096,[9])]:
    for policy in ['exact','geometric']:
        rows.append({'scenario':scenario,'policy':policy,'unit':'MiB','budget':budget,'count_limit':count,**run(policy,budget,count,requests)})
(H/'reduction-model.json').write_text(json.dumps(rows,indent=2))
for row in rows:print(row)
