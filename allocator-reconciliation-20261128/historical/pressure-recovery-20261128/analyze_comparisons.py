import pathlib,json,statistics,collections,csv,sys
H=pathlib.Path(__file__).resolve().parent
input_folder=H/(sys.argv[1] if len(sys.argv)>1 else 'results/direct-isolated')
prefix=sys.argv[2] if len(sys.argv)>2 else 'direct'
groups=collections.defaultdict(list);runs=0
for path in input_folder.glob('*.json'):
    if path.name.endswith('.receipt.json'):continue
    receipt=json.loads(path.with_name(path.stem+'.receipt.json').read_text());assert receipt['rc']==0
    data=json.loads(path.read_text());runs+=1
    for workload,row in data['result']['workloads'].items():groups[data['variant'],data['backend'],data['config'],workload].append((data['trial'],row))
rows=[];nondeterministic=[]
metrics=['blocks_created','blocks_destroyed','peak_capacity_mib','peak_allocated_mib','retained_after_release_mib','peak_unused_mib']
for key,values in sorted(groups.items()):
    row=dict(zip(['variant','backend','config','workload'],key));row['trials']=len(values)
    for field in metrics:row[field]=statistics.median(v[field] for _,v in values)
    decisions={json.dumps({k:v[k] for k in metrics+['block_events','marks']},sort_keys=True) for _,v in values}
    if len(decisions)!=1:nondeterministic.append(key)
    for timing in ['alloc_us','free_us','reuse_us','heap_creation_us']:
        for field in (['p50','p99','max','sum_ms'] if timing in ['alloc_us','free_us'] else ['p50','p99']):
            sequence=[v[timing][field] for _,v in values]
            for suffix,fn in [('median',statistics.median),('min',min),('max',max)]:row[timing+'_'+field+'_'+suffix]=fn(sequence)
    rows.append(row)
comparisons=[]
index={(r['variant'],r['backend'],r['config'],r['workload']):r for r in rows}
for variant in ['recovery','smallcache','heapcap','packed']:
    for baseline in ['cache2','recovery']:
        if variant==baseline:continue
        pairs=[(r,index[baseline,r['backend'],r['config'],r['workload']]) for r in rows if r['variant']==variant and (baseline,r['backend'],r['config'],r['workload']) in index]
        if not pairs:continue
        counts={}
        for field in ['blocks_created','peak_capacity_mib','retained_after_release_mib']:
            counts[field]={label:sum(op(a[field],b[field]) for a,b in pairs) for label,op in [('lower',lambda a,b:a<b),('equal',lambda a,b:a==b),('higher',lambda a,b:a>b)]}
        comparisons.append({'variant':variant,'baseline':baseline,'cells':len(pairs),'counts':counts})
result={'processes':runs,'workload_measurements':sum(len(v) for v in groups.values()),'nondeterministic':nondeterministic,'comparisons':comparisons,'cells':rows}
(H/(prefix+'-summary.json')).write_text(json.dumps(result,indent=2))
if rows:
    with (H/(prefix+'-summary.csv')).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
print({k:result[k] for k in ['processes','workload_measurements','nondeterministic','comparisons']})
