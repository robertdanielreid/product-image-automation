#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,html,json,time
from collections import Counter
from pathlib import Path

def read(path):
 if not path.exists():return []
 with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 p=argparse.ArgumentParser();p.add_argument('--package-root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--store-root',type=Path,required=True);a=p.parse_args()
 root=a.package_root.resolve();store=a.store_root.resolve();out=root/'output'
 audit=read(root/'data/all_20076_strict_image_audit.csv');results=read(out/'all_20076_acquisition_results.csv');reviews=read(out/'manual_visual_review.csv')
 rc=Counter(r.get('status') or 'MISSING' for r in results);dc=Counter(r.get('manualVisualDecision') or 'PENDING' for r in reviews)
 final={}
 fp=out/'final_validation_summary.json'
 if fp.exists():
  try:final=json.loads(fp.read_text())
  except Exception:pass
 report={'generatedAt':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'catalogueRows':len(audit),'acquisitionRows':len(results),'acquisitionStatusCounts':dict(rc),'reviewDecisionCounts':dict(dc),'approved':dc.get('APPROVED_EXACT_PRODUCT_PACKAGE',0),'manualReviewNeeded':dc.get('REVIEW_REQUIRED',0)+dc.get('PENDING',0),'rejectedPendingRetry':dc.get('REJECTED_WRONG_OR_UNCERTAIN',0),'finalValidatorPass':bool(final.get('pass')),'finalImagesPresent':sum(1 for r in audit if (store/r.get('targetJpgPath','')).exists()),'storeRoot':str(store)}
 (root/'STATUS_REPORT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 md='# Product image automation status\n\n'+ '\n'.join(f'- **{k}:** {v}' for k,v in report.items())+'\n'
 (root/'STATUS_REPORT.md').write_text(md,encoding='utf-8')
 h='<h1>Product image automation status</h1><table>'+''.join(f'<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>' for k,v in report.items())+'</table><p><a href="output/review_dashboard_v33/index.html">Open review dashboard</a></p><style>body{font-family:system-ui;margin:40px;max-width:1000px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:8px;text-align:left}th{width:35%;background:#f2f4f7}</style>'
 (root/'STATUS_REPORT.html').write_text('<!doctype html><meta charset="utf-8">'+h,encoding='utf-8')
 print(json.dumps(report,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
