#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,shutil
from collections import defaultdict,Counter
from pathlib import Path
from PIL import Image
APPROVED='APPROVED_EXACT_PRODUCT_PACKAGE'
TRUE_VALUES={'true','yes','1','approved'}
REGIONS=['ca','eu','uk','us']

def read_csv(path):
 with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write_csv(path,rows,fields):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def main():
 p=argparse.ArgumentParser();p.add_argument('--package-root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--store-root',type=Path,required=True);p.add_argument('--materialize-approved',action='store_true');p.add_argument('--expected-count',type=int,default=20076);a=p.parse_args()
 root=a.package_root.resolve();store=a.store_root.resolve();out=root/'output'
 audit=read_csv(root/'data/all_20076_strict_image_audit.csv')
 result_path=out/'all_20076_acquisition_results.csv';review_path=out/'manual_visual_review.csv'
 results={r['immutableKey']:r for r in read_csv(result_path)} if result_path.exists() else {}
 review={r['immutableKey']:r for r in read_csv(review_path)} if review_path.exists() else {}
 failures=[];approved=[];hash_identities=defaultdict(set);approved_by_key={}
 for row in audit:
  key=row['immutableKey'];res=results.get(key);rev=review.get(key)
  if not res: failures.append((key,'missing acquisition result'));continue
  if not rev or rev.get('manualVisualDecision')!=APPROVED: failures.append((key,'not visually approved'));continue
  # Separate reviewer attestations prevent a generic approval from concealing a
  # wrong brand, similarly named product, or wrong quantity/package variant.
  required_flags={
   'brandExact': 'brand not explicitly confirmed',
   'productNameExact': 'product name not explicitly confirmed',
   'sizeQuantityExact': 'size/quantity not explicitly confirmed',
   'strengthExactOrNotApplicable': 'strength not confirmed or marked N/A',
   'formExactOrNotApplicable': 'dosage form not confirmed or marked N/A',
   'flavourAudienceBundleExactOrNotApplicable': 'flavour/audience/bundle not confirmed or marked N/A',
   'officialProductImageOrBottle': 'image is not confirmed as official product/bottle image',
   'noLogoPlaceholderLifestyle': 'logo/placeholder/lifestyle exclusion not confirmed',
  }
  missing=[msg for field,msg in required_flags.items() if str(rev.get(field,'')).strip().lower() not in TRUE_VALUES]
  if missing: failures.append((key,'; '.join(missing)));continue
  # The reviewed expected identity is immutable and must equal the catalogue.
  checks=[('reviewedBrand',row['brand']),('reviewedProductName',row['productName']),('reviewedSizeQuantity',row['size'])]
  mismatch=[f'{f} mismatch' for f,expected in checks if str(rev.get(f,'')).strip()!=str(expected).strip()]
  if mismatch: failures.append((key,'; '.join(mismatch)));continue
  staged_rel=res.get('stagingPath','');staging=store/staged_rel
  if not staged_rel or not staging.exists(): failures.append((key,'approved row missing staged image'));continue
  try:
   with Image.open(staging) as im: im.verify()
   with Image.open(staging) as im:
    if im.format!='JPEG':raise ValueError(f'format={im.format}')
    if im.mode!='RGB':raise ValueError(f'mode={im.mode}')
    if min(im.size)<240:raise ValueError(f'size={im.size}')
  except Exception as e: failures.append((key,f'invalid JPEG: {e}'));continue
  sha=hashlib.sha256(staging.read_bytes()).hexdigest()
  if sha!=res.get('sha256'): failures.append((key,'SHA-256 differs from acquisition record'));continue
  ident=(row['brand'].lower().strip(),row['productName'].lower().strip(),row['size'].lower().strip())
  hash_identities[sha].add(ident)
  final=store/row['targetJpgPath']
  if a.materialize_approved:
   final.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(staging,final)
  if not final.exists(): failures.append((key,'final target JPG missing; rerun with --materialize-approved'));continue
  try:
   with Image.open(final) as im: im.verify()
  except Exception as e: failures.append((key,f'final target unreadable: {e}'));continue
  rec={**row,'resolvedImageUrl':res.get('resolvedImageUrl',''),'evidencePage':res.get('evidencePage',''),'jpgSha256':sha,'imageSrc':'/'+row['targetJpgPath'].replace('\\','/')}
  approved.append(rec);approved_by_key[key]=rec
 for sha,ids in hash_identities.items():
  if len(ids)>1: failures.append((sha,f'identical bytes approved across {len(ids)} incompatible identities'))
 fields=list(approved[0]) if approved else list(audit[0])+['resolvedImageUrl','evidencePage','jpgSha256','imageSrc']
 write_csv(out/'catalogue_all_20076_PRODUCTION_READY.csv',approved,fields)
 # Rebuild original regional catalogue files with only approved local imageSrc values.
 regional_counts={}
 for reg in REGIONS:
  src=root/'data/source_catalogues'/f'catalogue_{reg}_with_product_images_v24_final_208_completion.csv';src_rows=read_csv(src);new=[]
  for r in src_rows:
   key=f"{r['region']}:{r['productId']}:{r['variantIndex']}";ap=approved_by_key.get(key)
   if ap:
    r['imageSrc']=ap['imageSrc'];r['imageKind']='product';r['imageTrusted']='True';r['imageResolutionMethod']='self-hosted-jpg-strict-exact-product-package-approved';r['imageMatchStatus']='APPROVED_EXACT_PRODUCT_PACKAGE';r['imageNotes']=(r.get('imageNotes','')+' | V28 self-hosted exact product/package JPG approved.').strip(' |')
    new.append(r)
  regional_counts[reg]=len(new)
  write_csv(out/f'catalogue_{reg}_V28_PRODUCTION_READY.csv',new,list(src_rows[0]) if src_rows else [])
 summary={'scope':len(audit),'expected':a.expected_count,'approvedAndMaterialized':len(approved),'failureCount':len(failures),'regionalApprovedCounts':regional_counts,'pass':len(approved)==a.expected_count and len(audit)==a.expected_count and not failures,'failureReasonCounts':dict(Counter(reason for _,reason in failures)),'failuresPreview':failures[:200]}
 (out/'final_validation_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2));print('PASS' if summary['pass'] else 'FAIL');return 0 if summary['pass'] else 2
if __name__=='__main__':raise SystemExit(main())
