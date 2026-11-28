import pathlib,json,xml.etree.ElementTree as ET
H=pathlib.Path(__file__).resolve().parent;P=H.parent/'reassessment-20261128'
def parse(path):
    rows={}
    root=ET.parse(path).getroot()
    for case in root.iter('testcase'):
        failure=case.find('failure')
        if failure is None:failure=case.find('error')
        rows[(case.attrib['classname'],case.attrib['name'])]={'outcome':'pass' if failure is None else failure.attrib.get('type','failure'),'message':None if failure is None else failure.attrib.get('message'),'details':None if failure is None else failure.text,'time_s':float(case.attrib.get('time',0))}
    return rows
old=json.loads((P/'failure-triage.json').read_text())['rows']
upstream=parse(H/'sources/upstream-failure-junit.xml')
rows=[]
for row in old:
    key=(row['binary'],row['name']);assert key in upstream,key
    rows.append({**row,'clean_upstream':upstream[key]})
result={'tests':len(rows),'clean_upstream_passed':sum(r['clean_upstream']['outcome']=='pass' for r in rows),'clean_upstream_failed':sum(r['clean_upstream']['outcome']!='pass' for r in rows),'rows':rows}
(H/'control-comparison.json').write_text(json.dumps(result,indent=2))
print('Clean upstream:',result['clean_upstream_passed'],'passed,',result['clean_upstream_failed'],'failed')
for row in rows:
    if row['clean_upstream']['outcome']=='pass':print('PASS',row['name'])
