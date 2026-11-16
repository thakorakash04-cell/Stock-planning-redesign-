"""Schema and row-change summaries without changing saved calculations."""
from collections import Counter
import json

def compare(old,new):
    previous={s['name']:s for s in (old or {}).get('sheets',[])};report=[]
    for sheet in new.get('sheets',[]):
        before=previous.pop(sheet['name'],{'headers':[],'rows':[]})
        a=Counter(json.dumps(r,sort_keys=True,default=str) for r in before['rows']);b=Counter(json.dumps(r,sort_keys=True,default=str) for r in sheet['rows'])
        report.append({'Section':sheet['name'],'Previous rows':len(before['rows']),'New rows':len(sheet['rows']),'Added or changed rows':sum((b-a).values()),'Removed or replaced rows':sum((a-b).values()),'Added columns':', '.join(h for h in sheet['headers'] if h not in before['headers']),'Removed columns':', '.join(h for h in before['headers'] if h not in sheet['headers'])})
    for name,sheet in previous.items():report.append({'Section':name,'Previous rows':len(sheet['rows']),'New rows':0,'Removed or replaced rows':len(sheet['rows']),'Removed columns':', '.join(sheet['headers'])})
    return report
