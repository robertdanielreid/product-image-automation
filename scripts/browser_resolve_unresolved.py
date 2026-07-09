#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,importlib.util,json,re,time,urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


def read(path):
 if not path.exists():return []
 with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(path,rows,fields):
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def load_acquire(root):
 p=root/'scripts/acquire_all_20076_real_images.py';spec=importlib.util.spec_from_file_location('acq',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def search_links(page,query,preferred):
 url='https://www.bing.com/search?'+urllib.parse.urlencode({'q':query,'count':'8'})
 try:
  page.goto(url,wait_until='domcontentloaded',timeout=35000);page.wait_for_timeout(1000)
 except Exception:return []
 links=page.eval_on_selector_all('li.b_algo h2 a','els => els.map(a => a.href)') or []
 clean=[]
 for u in links:
  if not isinstance(u,str) or not u.startswith('http'):continue
  d=urllib.parse.urlparse(u).netloc.lower().removeprefix('www.')
  if any(x in d for x in ['bing.com','microsoft.com','amazon.','ebay.','pinterest.','facebook.','instagram.']):continue
  clean.append(u)
 return sorted(dict.fromkeys(clean),key=lambda u:0 if any(urllib.parse.urlparse(u).netloc.lower().endswith(d) for d in preferred) else 1)[:6]

def rendered_candidates(page,url,acq):
 try:
  page.goto(url,wait_until='domcontentloaded',timeout=40000);page.wait_for_timeout(1400)
 except Exception:return []
 title=page.title()
 items=[]
 try:
  og=page.locator('meta[property="og:image"]').get_attribute('content')
  if og:items.append({'url':urllib.parse.urljoin(page.url,og),'alt':'','origin':'browser-og'})
 except Exception:pass
 try:
  raw=page.eval_on_selector_all('img','''els => els.map(img => ({src: img.currentSrc || img.src || '', alt: [img.alt,img.title,img.getAttribute('data-caption')].filter(Boolean).join(' '), w: img.naturalWidth||img.width||0, h: img.naturalHeight||img.height||0}))''')
 except Exception:raw=[]
 for x in raw:
  u=urllib.parse.urljoin(page.url,x.get('src',''))
  if not u.startswith('http') or acq.is_bad_image_url(u):continue
  if x.get('w',0) and x.get('h',0) and min(x['w'],x['h'])<180:continue
  items.append({'url':u,'alt':x.get('alt',''),'origin':'browser-rendered-img'})
 out=[];seen=set()
 for x in items:
  if x['url'] in seen:continue
  seen.add(x['url']);out.append(acq.Candidate(x['url'],page.url,x['origin'],x['alt'],title,''))
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--package-root',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--max-rows',type=int,default=0);ap.add_argument('--headful',action='store_true');a=ap.parse_args()
 root=a.package_root.resolve();out=root/'output';acq=load_acquire(root)
 audit=read(root/'data/all_20076_strict_image_audit.csv');results={r['immutableKey']:r for r in read(out/'all_20076_acquisition_results.csv')}
 domain_map=acq.load_official_domains(root/'data/brand_official_domain_map.csv')
 target=[]
 for r in audit:
  res=results.get(r['immutableKey'],{})
  if not res.get('status','').startswith('STAGED'):target.append(r)
 if a.max_rows>0:target=target[:a.max_rows]
 overrides_path=out/'manual_overrides.csv';old=read(overrides_path);bykey={r.get('immutableKey',''):r for r in old if r.get('immutableKey')}
 found=0;failed=0
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=not a.headful)
  context=browser.new_context(user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36',locale='en-CA')
  page=context.new_page()
  for i,row in enumerate(target,1):
   official=domain_map.get(acq.norm(row['brand']),set())
   q=f'"{row["brand"]}" "{row["productName"]}" "{row["size"]}" official product image'
   if official:q='site:'+next(iter(official))+' '+q
   links=search_links(page,q,official)
   ranked=[]
   for link in links[:4]:
    for c in rendered_candidates(page,link,acq):
     score,match=acq.candidate_score(row,c,official);ranked.append((score,c,match))
   ranked.sort(key=lambda x:x[0],reverse=True)
   if ranked and ranked[0][0]>=55:
    score,c,match=ranked[0]
    bykey[row['immutableKey']]={'immutableKey':row['immutableKey'],'approvedDirectImageUrl':c.url,'approvedSourcePageUrl':c.page_url,'exactVariantConfirmed':'false','reviewer':'browser-discovery','evidenceNote':f'{c.alt} | {c.page_title}'[:500]}
    found+=1
   else:failed+=1
   if i%25==0:print(f'Browser discovery {i}/{len(target)} found={found} unresolved={failed}',flush=True)
   time.sleep(0.4)
  browser.close()
 fields=['immutableKey','approvedDirectImageUrl','approvedSourcePageUrl','exactVariantConfirmed','reviewer','evidenceNote']
 write(overrides_path,list(bykey.values()) or [{f:'' for f in fields}],fields)
 summary={'processed':len(target),'candidateOverridesFound':found,'stillUnresolved':failed}
 (out/'browser_resolution_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
