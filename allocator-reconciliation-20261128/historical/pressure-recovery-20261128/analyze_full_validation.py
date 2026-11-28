import pathlib,json,xml.etree.ElementTree as ET,argparse
H=pathlib.Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--junit',default='sources/candidate-full-junit.xml')
parser.add_argument('--output',default='final-failure-triage.json')
args=parser.parse_args()
root=ET.parse(H/args.junit).getroot()
known={(r['binary'],r['name']):r for r in json.loads((H/'control-comparison.json').read_text())['rows']}
rows=[];passed=failed=skipped=0
for case in root.iter('testcase'):
    if case.find('skipped') is not None:skipped+=1;continue
    failure=case.find('failure')
    if failure is None:failure=case.find('error')
    if failure is None:passed+=1;continue
    failed+=1;key=(case.attrib['classname'],case.attrib['name']);prior=known.get(key)
    rows.append({'binary':key[0],'name':key[1],'failure':dict(failure.attrib),'details':failure.text,'time_s':float(case.attrib.get('time',0)),'historical':prior is not None,'clean_upstream':None if prior is None else prior['clean_upstream']})
result={'tests':passed+failed,'passed':passed,'failed':failed,'skipped':skipped,'new_failure_names':[r for r in rows if not r['historical']],'rows':rows}
(H/args.output).write_text(json.dumps(result,indent=2))
print({k:result[k] for k in ['tests','passed','failed','skipped','new_failure_names']})
for row in rows:
    if row['clean_upstream'] and row['clean_upstream']['outcome']=='pass':print('NEEDS_FOCUSED_CONTROL',row['name'],row['failure'])
