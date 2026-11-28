"""Archive the full report from nextest's workspace-relative store directory."""
from pathlib import Path
import json,shutil,xml.etree.ElementTree as ET
H=Path(__file__).resolve().parent
source=H/'wgpu/candidate/target/nextest/default/junit.xml'
root=ET.parse(source).getroot();assert len(list(root.iter('testcase')))>=2200
dest=H/'sources/candidate-full-junit.xml'
if dest.exists():dest.rename(H/'sources/candidate-full-junit-mislocated-pilot.xml')
shutil.copyfile(source,dest)
triage=H/'final-failure-triage.json'
if triage.exists():triage.rename(H/'final-failure-triage-mislocated-pilot.json')
(H/'junit-location-recovery.json').write_text(json.dumps({'actual_full_report':str(source),'archived_as':str(dest),'reason':'Saved binary metadata and build target-directory overrides do not override nextest workspace-relative report store. Full log and actual candidate workspace report agree. Earlier two-test snapshot preserved and excluded.','testcase_nodes':len(list(root.iter('testcase')))},indent=2))
print('Recovered actual full-suite JUnit:',root.attrib)
