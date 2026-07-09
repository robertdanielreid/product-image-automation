#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,html,json,math
from collections import Counter
from pathlib import Path
CSS='''body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#f5f6f8;color:#17202a}header{position:sticky;top:0;background:#fff;border-bottom:1px solid #ccd2d8;padding:12px 18px;z-index:2}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;padding:18px}.card{background:#fff;border:1px solid #dfe3e8;border-radius:10px;padding:12px;box-shadow:0 1px 2px #0001}.card img{width:100%;height:250px;object-fit:contain;background:#fafafa;border-radius:6px}.bad{border-color:#d93025}.good{border-color:#188038}.meta{font-size:13px;line-height:1.35}.status{font-weight:700}.small{font-size:12px;color:#5f6368;word-break:break-all}.nav a{display:inline-block;margin:3px;padding:5px 8px;background:#eef2f7;border-radius:5px;text-decoration:none}.summary{padding:20px;background:#fff;margin:20px;border-radius:10px}'''

def esc(v): return html.escape(str(v or ''))
def main():
 p=argparse.ArgumentParser();p.add_argument('--package-root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--store-root',type=Path,required=True);p.add_argument('--page-size',type=int,default=400);a=p.parse_args()
 root=a.package_root.resolve(); result_path=root/'output/all_20076_acquisition_results.csv'
 if not result_path.exists(): raise SystemExit(f'Missing {result_path}')
 rows=list(csv.DictReader(result_path.open(encoding='utf-8-sig')))
 out=root/'output/review_dashboard';out.mkdir(parents=True,exist_ok=True)
 pages=math.ceil(len(rows)/a.page_size)
 links=' '.join(f'<a href="page-{i:03d}.html">{i}</a>' for i in range(1,pages+1))
 for i in range(pages):
  chunk=rows[i*a.page_size:(i+1)*a.page_size];cards=[]
  for r in chunk:
   staged=r.get('stagingPath',''); img='../'+staged.replace('output/','') if staged else ''
   kind='staged' if r.get('status','').startswith('STAGED') else 'unresolved'; cls='good' if kind=='staged' else 'bad'
   image=f'<img loading="lazy" src="{esc(img)}" alt="">' if img else '<div style="height:250px;display:grid;place-items:center;background:#fee">No image downloaded</div>'
   cards.append(f'''<article class="card {cls}">{image}<div class="meta"><div><b>#{esc(r['batchIndex'])} {esc(r['brand'])}</b></div><div>{esc(r['productName'])}</div><div><b>Package:</b> {esc(r['size'])}</div><div class="status">{esc(r['status'])}</div><div><b>Origin:</b> {esc(r.get('origin',''))}</div><div><b>Evidence:</b> <a href="{esc(r.get('evidencePage',''))}">page</a></div><div><b>Image:</b> <a href="{esc(r.get('resolvedImageUrl',''))}">source</a></div><div class="small">{esc(r.get('reason',''))}</div><div class="small">{esc(r['immutableKey'])}</div></div></article>''')
  doc=f'''<!doctype html><meta charset="utf-8"><title>All 20,076 product images — review {i+1}/{pages}</title><style>{CSS}</style><header><h1>Strict product-image review — page {i+1}/{pages}</h1><div class="nav">{links}</div><p>Approval requires exact brand, product, package size/count/volume, strength, flavour, format, audience and bundle.</p></header><main class="grid">{''.join(cards)}</main>'''
  (out/f'page-{i+1:03d}.html').write_text(doc,encoding='utf-8')
 counts=Counter(r.get('status','') for r in rows)
 index=f'''<!doctype html><meta charset="utf-8"><title>20,076 product-image review index</title><style>{CSS}</style><div class="summary"><h1>20,076 strict product-image review</h1><pre>{esc(json.dumps(dict(counts),indent=2))}</pre><div class="nav">{links}</div></div>'''
 (out/'index.html').write_text(index,encoding='utf-8');print(out/'index.html')
if __name__=='__main__':main()
