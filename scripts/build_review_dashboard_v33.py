#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,html,json,math,shutil
from collections import Counter
from pathlib import Path
from PIL import Image,ImageOps

def read(path):
 if not path.exists():return []
 with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def esc(v):return html.escape(str(v or ''))
def main():
 p=argparse.ArgumentParser();p.add_argument('--package-root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--store-root',type=Path,required=True);p.add_argument('--page-size',type=int,default=250);a=p.parse_args()
 root=a.package_root.resolve();store=a.store_root.resolve();out=root/'output/review_dashboard_v33';imgs=out/'images';imgs.mkdir(parents=True,exist_ok=True)
 audit=read(root/'data/all_20076_strict_image_audit.csv');results={r['immutableKey']:r for r in read(root/'output/all_20076_acquisition_results.csv')};reviews={r['immutableKey']:r for r in read(root/'output/manual_visual_review.csv')}
 pending=[]
 for row in audit:
  key=row['immutableKey'];rev=reviews.get(key,{});decision=rev.get('manualVisualDecision') or 'PENDING'
  if decision=='APPROVED_EXACT_PRODUCT_PACKAGE':continue
  res=results.get(key,{})
  thumb=''
  staged=res.get('stagingPath','')
  if staged and (store/staged).exists():
   thumb=f"{key.replace(':','_')}.jpg";dest=imgs/thumb
   if not dest.exists():
    try:
     with Image.open(store/staged) as im:
      im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((600,600));im.save(dest,'JPEG',quality=82,optimize=True)
    except Exception:thumb=''
  pending.append((row,res,rev,decision,thumb))
 css='''body{font-family:system-ui;margin:0;background:#f4f6f8;color:#17202a}header{position:sticky;top:0;background:white;padding:12px 18px;border-bottom:1px solid #ccd2d8;z-index:2}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:14px;padding:18px}.card{background:white;border:1px solid #d9dee5;border-radius:10px;padding:12px}.card img{width:100%;height:280px;object-fit:contain;background:#fafafa}.meta{font-size:13px;line-height:1.4}.decision{font-weight:700}.small{font-size:11px;color:#586069;word-break:break-all}.nav a{display:inline-block;padding:5px 8px;margin:2px;background:#e9eef5;border-radius:5px;text-decoration:none}.warn{color:#9c2f00}.summary{margin:20px;padding:20px;background:white;border-radius:10px}'''
 pages=max(1,math.ceil(len(pending)/a.page_size));links=' '.join(f'<a href="page-{i:03d}.html">{i}</a>' for i in range(1,pages+1))
 for i in range(pages):
  cards=[]
  for row,res,rev,decision,thumb in pending[i*a.page_size:(i+1)*a.page_size]:
   image=f'<img loading="lazy" src="images/{esc(thumb)}">' if thumb else '<div style="height:280px;display:grid;place-items:center;background:#fee">No staged image</div>'
   cards.append(f'''<article class="card">{image}<div class="meta"><b>#{esc(row.get('batchIndex'))} {esc(row.get('brand'))}</b><div>{esc(row.get('productName'))}</div><div><b>Expected size:</b> {esc(row.get('size'))}</div><div class="decision warn">{esc(decision)}</div><div><b>AI:</b> {esc(rev.get('aiDecision'))} {esc(rev.get('aiConfidence'))}</div><div>{esc(rev.get('aiReason') or res.get('reason'))}</div><div><a target="_blank" href="{esc(res.get('evidencePage'))}">Evidence page</a> · <a target="_blank" href="{esc(res.get('resolvedImageUrl'))}">Original image</a></div><div class="small">{esc(row.get('immutableKey'))}</div></div></article>''')
  (out/f'page-{i+1:03d}.html').write_text(f'<!doctype html><meta charset="utf-8"><title>Review queue {i+1}/{pages}</title><style>{css}</style><header><h1>Exact product-image review {i+1}/{pages}</h1><div class="nav">{links}</div><p>Use OPEN_REVIEW_QUEUE.command to approve or reject interactively.</p></header><main class="grid">{"".join(cards)}</main>',encoding='utf-8')
 counts=Counter((reviews.get(r['immutableKey'],{}).get('manualVisualDecision') or 'PENDING') for r in audit)
 (out/'index.html').write_text(f'<!doctype html><meta charset="utf-8"><title>Product image review</title><style>{css}</style><div class="summary"><h1>Product-image review status</h1><pre>{esc(json.dumps(dict(counts),indent=2))}</pre><p>Rows requiring attention: {len(pending)}</p><div class="nav">{links}</div></div>',encoding='utf-8')
 print(out/'index.html');return 0
if __name__=='__main__':raise SystemExit(main())
