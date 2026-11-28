"""Check which previous plan measurements remain comparable; never merge old timings."""
import pathlib,json,hashlib
H=pathlib.Path(__file__).resolve().parent;P=H.parent/'reassessment-20261128'
old=json.loads((P/'direct-summary.json').read_text())['cells']
new=json.loads((H/'direct-summary.json').read_text())['cells']
index={(r['variant'],r['backend'],r['config'],r['workload']):r for r in old}
fields=['blocks_created','blocks_destroyed','peak_capacity_mib','peak_allocated_mib','retained_after_release_mib']
rows=[]
for row in new:
    if row['variant'] not in ['main','pr323','cache2']:continue
    key=tuple(row[k] for k in ['variant','backend','config','workload']);prior=index[key]
    differences={f:{'old':prior[f],'new':row[f]} for f in fields if prior[f]!=row[f]}
    rows.append({'variant':key[0],'backend':key[1],'config':key[2],'workload':key[3],'differences':differences})
checks={}
for name in ['main','pr323','cache2']:
    checks[name]={'harness_matches_frozen':(H/'work'/name/'bench/src/main.rs').read_bytes()==(P/'repro-inputs/bench.rs').read_bytes(),'old_build':json.loads((P/'bin-verified'/(name+'.json')).read_text()),'new_build':json.loads((H/'bin-isolated'/(name+'.json')).read_text())}
result={'compared_cells':len(rows),'matching_cells':sum(not r['differences'] for r in rows),'rows':rows,'provenance':checks,'timings':'Old absolute timings are not pooled with new measurements.'}
(H/'reuse-audit.json').write_text(json.dumps(result,indent=2))
print('Prior direct plan cells matching:',result['matching_cells'],'/',result['compared_cells'])
for row in rows:
    if row['differences']:print(row)
