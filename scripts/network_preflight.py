#!/usr/bin/env python3
from __future__ import annotations
import json, socket, sys, urllib.request
from pathlib import Path
HOSTS=['example.com','www.lifeextension.com','www.yourhealthbasket.co.uk']
results=[]
ok=False
for host in HOSTS:
    item={'host':host,'dns':False,'http':False,'error':''}
    try:
        item['address']=socket.gethostbyname(host); item['dns']=True
        req=urllib.request.Request('https://'+host+'/',headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req,timeout=12) as r:
            item['http']=200 <= getattr(r,'status',200) < 500
        ok = ok or item['http']
    except Exception as e:
        item['error']=repr(e)
    results.append(item)
out={'networkAvailable':ok,'tests':results}
root=Path(__file__).resolve().parents[1]
(root/'output').mkdir(exist_ok=True)
(root/'output/network_preflight.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
if not ok:
    print('NETWORK_PREFLIGHT_FAILED: external product pages and image hosts are unreachable.',file=sys.stderr)
    raise SystemExit(10)
