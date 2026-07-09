#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,os,shutil,subprocess,sys,time
from pathlib import Path


def load_env(path:Path):
 if not path.exists():return
 for line in path.read_text(encoding='utf-8').splitlines():
  line=line.strip()
  if not line or line.startswith('#') or '=' not in line:continue
  k,v=line.split('=',1);k=k.strip();v=v.strip().strip('"').strip("'")
  os.environ.setdefault(k,v)
def read_csv(path):
 if not path.exists():return []
 with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def run(cmd:list[str],root:Path,log:Path,allow_fail=False):
 stamp=time.strftime('%Y-%m-%d %H:%M:%S')
 print(f'\n[{stamp}] RUN: {" ".join(cmd)}',flush=True)
 log.parent.mkdir(parents=True,exist_ok=True)
 with log.open('a',encoding='utf-8') as lf:
  lf.write(f'\n[{stamp}] RUN: {" ".join(cmd)}\n');lf.flush()
  proc=subprocess.Popen(cmd,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  assert proc.stdout
  for line in proc.stdout:
   print(line,end='');lf.write(line);lf.flush()
  code=proc.wait();lf.write(f'EXIT {code}\n')
 if code and not allow_fail:raise SystemExit(code)
 return code
def decision_counts(root:Path):
 rows=read_csv(root/'output/manual_visual_review.csv');out={}
 for r in rows:
  d=r.get('manualVisualDecision') or 'PENDING';out[d]=out.get(d,0)+1
 return out
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--package-root',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--store-root',type=Path,required=True);ap.add_argument('--passes',type=int,default=int(os.getenv('MAX_RETRY_PASSES','3')));ap.add_argument('--skip-browser',action='store_true');ap.add_argument('--skip-vision',action='store_true');ap.add_argument('--browser-limit',type=int,default=int(os.getenv('BROWSER_FALLBACK_LIMIT','0')));a=ap.parse_args()
 root=a.package_root.resolve();store=a.store_root.resolve();load_env(root/'.env')
 store.mkdir(parents=True,exist_ok=True);(root/'logs').mkdir(exist_ok=True)
 free=shutil.disk_usage(store).free
 if free<15*1024**3:print(f'WARNING: only {free/1024**3:.1f} GB free. 20+ GB is recommended.',flush=True)
 if not a.skip_vision and not os.getenv('GEMINI_API_KEY','').strip():raise SystemExit('Missing GEMINI_API_KEY. Run ONE_CLICK_SETUP.command or edit .env.')
 py=str(root/'.venv/bin/python') if (root/'.venv/bin/python').exists() else sys.executable
 workers=os.getenv('ACQUIRE_WORKERS','6');gworkers=os.getenv('GEMINI_WORKERS','2');rps=os.getenv('GEMINI_RPS','1')
 log=root/'logs/master_pipeline.log'
 run([py,'scripts/network_preflight.py'],root,log,allow_fail=True)
 for pass_no in range(1,max(1,a.passes)+1):
  print(f'\n========== ACQUISITION/VERIFICATION PASS {pass_no}/{a.passes} ==========',flush=True)
  if pass_no>1 and not a.skip_browser:
   cmd=[py,'scripts/browser_resolve_unresolved.py','--package-root',str(root)]
   if a.browser_limit>0:cmd += ['--max-rows',str(a.browser_limit)]
   run(cmd,root,log,allow_fail=True)
  run([py,'scripts/acquire_all_20076_real_images.py','--package-root',str(root),'--store-root',str(store),'--workers',workers,'--search-fallback','--resume'],root,log)
  if not a.skip_vision:
   run([py,'scripts/verify_staged_images_gemini.py','--package-root',str(root),'--store-root',str(store),'--workers',gworkers,'--rps',rps,'--resume'],root,log,allow_fail=True)
  counts=decision_counts(root);print('Current decisions:',json.dumps(counts,indent=2),flush=True)
  if counts.get('APPROVED_EXACT_PRODUCT_PACKAGE',0)>=20076:break
  if pass_no<a.passes and not a.skip_vision:
   run([py,'scripts/prepare_rejected_for_retry.py','--package-root',str(root),'--store-root',str(store),'--include-review'],root,log,allow_fail=True)
 run([py,'scripts/build_review_dashboard_v33.py','--package-root',str(root),'--store-root',str(store)],root,log,allow_fail=True)
 code=run([py,'scripts/validate_all_20076_real_images.py','--package-root',str(root),'--store-root',str(store),'--materialize-approved','--expected-count','20076'],root,log,allow_fail=True)
 run([py,'scripts/status_report.py','--package-root',str(root),'--store-root',str(store)],root,log,allow_fail=True)
 print('\nPipeline finished. Open STATUS_REPORT.html and output/review_dashboard_v33/index.html.',flush=True)
 return code
if __name__=='__main__':raise SystemExit(main())
