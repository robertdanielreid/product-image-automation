#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from pathlib import Path

REJECTED='REJECTED_WRONG_OR_UNCERTAIN'
CLEAR_FIELDS=[
 'brandExact','productNameExact','sizeQuantityExact','strengthExactOrNotApplicable',
 'formExactOrNotApplicable','flavourAudienceBundleExactOrNotApplicable',
 'officialProductImageOrBottle','noLogoPlaceholderLifestyle','reviewedBrand',
 'reviewedProductName','reviewedSizeQuantity'
]

def read(path):
 if not path.exists(): return []
 with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(path,rows,fields=None):
 if not rows: path.write_text('',encoding='utf-8');return
 fields=fields or list(rows[0])
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def main():
 p=argparse.ArgumentParser();p.add_argument('--package-root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--store-root',type=Path,required=True);p.add_argument('--include-review',action='store_true');a=p.parse_args()
 root=a.package_root.resolve();store=a.store_root.resolve();out=root/'output'
 rp=out/'all_20076_acquisition_results.csv';vp=out/'manual_visual_review.csv'
 results=read(rp);reviews=read(vp);review={r['immutableKey']:r for r in reviews}
 changed=deleted=0
 for r in results:
  rev=review.get(r.get('immutableKey',''),{})
  decision=rev.get('manualVisualDecision')
  if decision!=REJECTED and not (a.include_review and decision=='REVIEW_REQUIRED'):continue
  staged=r.get('stagingPath','')
  if staged:
   path=store/staged
   if path.exists(): path.unlink();deleted+=1
  r['status']='RETRY_REQUIRED_PREVIOUS_CANDIDATE_REJECTED';r['stagingPath']='';r['sha256']='';r['perceptualHash']='';r['bytes']='';r['width']='';r['height']=''
  rev['manualVisualDecision']='PENDING';rev['reviewer']='';
  for f in CLEAR_FIELDS:rev[f]=''
  changed+=1
 write(rp,results,list(results[0]) if results else None)
 write(vp,reviews,list(reviews[0]) if reviews else None)
 summary={'rowsPreparedForRetry':changed,'stagedFilesDeleted':deleted}
 (out/'retry_preparation_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2))
 return 0
if __name__=='__main__':raise SystemExit(main())
