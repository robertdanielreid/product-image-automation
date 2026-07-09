#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,html,json,mimetypes,os,threading,urllib.parse,webbrowser
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

APPROVED='APPROVED_EXACT_PRODUCT_PACKAGE';REJECTED='REJECTED_WRONG_OR_UNCERTAIN';PENDING={'PENDING','REVIEW_REQUIRED',''}
FLAGS=['brandExact','productNameExact','sizeQuantityExact','strengthExactOrNotApplicable','formExactOrNotApplicable','flavourAudienceBundleExactOrNotApplicable','officialProductImageOrBottle','noLogoPlaceholderLifestyle']
def read(path):
 if not path.exists():return []
 with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(path,rows,fields):
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--package-root',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--store-root',type=Path,required=True);ap.add_argument('--port',type=int,default=8765);a=ap.parse_args()
 root=a.package_root.resolve();store=a.store_root.resolve();out=root/'output';review_path=out/'manual_visual_review.csv';results={r['immutableKey']:r for r in read(out/'all_20076_acquisition_results.csv')};audit={r['immutableKey']:r for r in read(root/'data/all_20076_strict_image_audit.csv')};lock=threading.Lock()
 class H(BaseHTTPRequestHandler):
  def send_html(self,s,code=200):
   b=s.encode();self.send_response(code);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
  def rows(self):
   rs=read(review_path);return [r for r in rs if (r.get('manualVisualDecision') or 'PENDING') in PENDING]
  def do_GET(self):
   u=urllib.parse.urlparse(self.path);q=urllib.parse.parse_qs(u.query)
   if u.path=='/image':
    key=q.get('key',[''])[0];res=results.get(key,{});p=store/res.get('stagingPath','')
    if not p.exists():self.send_error(404);return
    data=p.read_bytes();self.send_response(200);self.send_header('Content-Type','image/jpeg');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
   rows=self.rows();idx=max(0,min(int(q.get('i',['0'])[0] or 0),max(0,len(rows)-1)))
   if not rows:self.send_html('<h1>No pending manual reviews</h1><p>Run the finalizer or close this window.</p>');return
   r=rows[idx];key=r['immutableKey'];row=audit.get(key,{});res=results.get(key,{})
   body=f'''<!doctype html><meta charset="utf-8"><title>Review {idx+1}/{len(rows)}</title><style>body{{font-family:system-ui;margin:20px;background:#f5f6f8}}main{{max-width:1100px;margin:auto;background:white;padding:20px;border-radius:12px}}img{{width:100%;height:600px;object-fit:contain;background:#fafafa}}button{{font-size:18px;padding:14px 22px;margin:8px;border:0;border-radius:8px}}.ok{{background:#188038;color:white}}.bad{{background:#d93025;color:white}}.skip{{background:#e8eaed}}.meta{{font-size:16px;line-height:1.45}}code{{word-break:break-all}}</style><main><h1>{idx+1} of {len(rows)} pending</h1><img src="/image?key={urllib.parse.quote(key)}"><div class="meta"><h2>{html.escape(row.get('brand',''))} — {html.escape(row.get('productName',''))}</h2><p><b>Expected quantity/size:</b> {html.escape(row.get('size',''))}<br><b>Format:</b> {html.escape(row.get('format',''))}</p><p><b>AI result:</b> {html.escape(r.get('aiDecision',''))} {html.escape(r.get('aiConfidence',''))}<br>{html.escape(r.get('aiReason',''))}</p><p><a target="_blank" href="{html.escape(res.get('evidencePage',''))}">Open evidence page</a> · <a target="_blank" href="{html.escape(res.get('resolvedImageUrl',''))}">Open original image</a></p><code>{html.escape(key)}</code></div><form method="post"><input type="hidden" name="key" value="{html.escape(key)}"><input type="hidden" name="i" value="{idx}"><button class="ok" name="decision" value="approve">Approve exact match</button><button class="bad" name="decision" value="reject">Reject wrong/uncertain</button><button class="skip" name="decision" value="skip">Skip</button></form></main>'''
   self.send_html(body)
  def do_POST(self):
   n=int(self.headers.get('Content-Length','0'));data=urllib.parse.parse_qs(self.rfile.read(n).decode());key=data.get('key',[''])[0];decision=data.get('decision',['skip'])[0];idx=int(data.get('i',['0'])[0]);
   with lock:
    rows=read(review_path);fields=list(rows[0]) if rows else []
    for r in rows:
     if r.get('immutableKey')!=key:continue
     row=audit.get(key,{})
     if decision=='approve':
      r['manualVisualDecision']=APPROVED;r['reviewer']='human-local-review';r['evidenceNote']='Human visually confirmed exact brand, product, and package.'
      for f in FLAGS:r[f]='true'
      r['reviewedBrand']=row.get('brand','');r['reviewedProductName']=row.get('productName','');r['reviewedSizeQuantity']=row.get('size','')
     elif decision=='reject':
      r['manualVisualDecision']=REJECTED;r['reviewer']='human-local-review';r['evidenceNote']='Human rejected candidate as wrong or uncertain.'
     break
    write(review_path,rows,fields)
    if decision=='reject':
     res=results.get(key,{})
     rp=out/'rejected_candidates.csv';rejected=read(rp);rfields=['immutableKey','resolvedImageUrl','evidencePage','reason','aiConfidence','rejectedAt']
     pair=(key,res.get('resolvedImageUrl',''))
     if pair[1] and not any((x.get('immutableKey'),x.get('resolvedImageUrl'))==pair for x in rejected):
      import time
      rejected.append({'immutableKey':key,'resolvedImageUrl':pair[1],'evidencePage':res.get('evidencePage',''),'reason':'Human rejected candidate as wrong or uncertain.','aiConfidence':'','rejectedAt':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
      write(rp,rejected,rfields)
   self.send_response(303);self.send_header('Location',f'/?i={idx}');self.end_headers()
  def log_message(self,fmt,*args):pass
 server=ThreadingHTTPServer(('127.0.0.1',a.port),H);url=f'http://127.0.0.1:{a.port}/';print(f'Review server: {url}');webbrowser.open(url)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 return 0
if __name__=='__main__':raise SystemExit(main())
