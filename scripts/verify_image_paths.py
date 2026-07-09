#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,re
from pathlib import Path, PurePosixPath

def read_csv(path: Path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--package-root', type=Path, required=True)
    ap.add_argument('--artifact-root', type=Path)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--limit', type=int, default=20076)
    args=ap.parse_args()
    root=args.package_root.resolve()
    rows=read_csv(root/'data/all_20076_unique_image_manifest.csv')[args.start:args.start+args.limit]
    problems=[]; seen={}
    pattern=re.compile(r'^assets/product-images/catalogue-v28/[0-9a-f]{24}\.jpg$')
    for i,r in enumerate(rows,args.start+1):
        raw=r.get('targetJpgPath','')
        p=PurePosixPath(raw)
        if not raw: problems.append([i,r.get('immutableKey',''),'EMPTY_PATH',raw])
        if '\\' in raw: problems.append([i,r.get('immutableKey',''),'BACKSLASH',raw])
        if raw.startswith('/') or p.is_absolute(): problems.append([i,r.get('immutableKey',''),'ABSOLUTE_PATH',raw])
        if '..' in p.parts: problems.append([i,r.get('immutableKey',''),'TRAVERSAL',raw])
        if not pattern.fullmatch(raw): problems.append([i,r.get('immutableKey',''),'SCHEMA_MISMATCH',raw])
        asset=r.get('assetId','')
        if p.stem!=asset: problems.append([i,r.get('immutableKey',''),'ASSET_ID_FILENAME_MISMATCH',raw])
        if raw in seen: problems.append([i,r.get('immutableKey',''),f'DUPLICATE_PATH_WITH_{seen[raw]}',raw])
        seen[raw]=r.get('immutableKey','')
    artifact_checks={}
    if args.artifact_root:
        a=args.artifact_root.resolve(); meta=a/'chunk-metadata'/'all_20076_acquisition_results.csv'
        artifact_checks['artifactRoot']=str(a)
        artifact_checks['resultsFileExists']=meta.exists()
        artifact_checks['stagingDirectoryExists']=(a/'staging').exists()
        if meta.exists():
            rr=read_csv(meta); missing=[]
            for x in rr:
                sp=x.get('stagingPath','')
                if x.get('status','').startswith('STAGED') and (not sp or not (a/sp).exists()): missing.append(x.get('immutableKey',''))
            artifact_checks['stagedRowsMissingFiles']=len(missing)
    report={'rowsChecked':len(rows),'start':args.start,'pathProblems':len(problems),'uniquePaths':len(seen),'pass':not problems,'problemsPreview':problems[:100],'artifactChecks':artifact_checks}
    out=(args.artifact_root/'chunk-metadata/path_verification.json') if args.artifact_root else (root/'reports/ALL_20076_IMAGE_PATH_VERIFICATION.json')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2));return 0 if report['pass'] else 2
if __name__=='__main__': raise SystemExit(main())
