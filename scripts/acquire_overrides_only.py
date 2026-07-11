#!/usr/bin/env python3
"""Download images ONLY for products with manual overrides."""
from __future__ import annotations
import sys, csv, hashlib
from pathlib import Path
from collections import Counter

# Add scripts dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from acquire_all_20076_real_images import (
    process_row, load_official_domains, read_overrides,
    load_rejected_candidates, write_csv, ImageResult, asdict,
)

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--package-root', type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument('--store-root', type=Path, required=True)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--results-dir', type=Path, default=None)
    args = ap.parse_args()
    
    package = args.package_root.resolve()
    store = args.store_root.resolve()
    
    # Load audit
    audit = list(csv.DictReader((package / 'data/all_20076_strict_image_audit.csv').open(encoding='utf-8-sig')))
    audit_by_key = {r['immutableKey']: r for r in audit}
    
    # Load previous results
    results_dir = (args.results_dir or (package / 'output')).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    results_path = results_dir / 'all_20076_acquisition_results.csv'
    prior = {}
    if results_path.exists():
        prior = {r['immutableKey']: r for r in csv.DictReader(results_path.open(encoding='utf-8-sig', newline=''))}
    
    # Load overrides
    overrides = read_overrides(package / 'output' / 'manual_overrides.csv')
    
    # Only process products with overrides that aren't already staged
    todo = []
    results = dict(prior)
    for key, ov in overrides.items():
        if not ov.get('approvedDirectImageUrl', '').startswith('http'):
            continue
        p = prior.get(key, {})
        if p.get('status', '').startswith('STAGED') and (store / p.get('stagingPath', '')).exists():
            continue
        row = audit_by_key.get(key)
        if row:
            todo.append(row)
    
    if not todo:
        print('No override products need processing')
        return 0
    
    print(f'Processing {len(todo)} override products')
    
    domains = load_official_domains(package / 'data' / 'brand_official_domain_map.csv')
    rejected = load_rejected_candidates(results_dir / 'rejected_candidates.csv')
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(process_row, r, package, store, domains, True, overrides, rejected): r for r in todo}
        done = 0
        for fut in as_completed(futs):
            row = futs[fut]
            try:
                res = fut.result()
            except Exception as exc:
                res = ImageResult(row['batchIndex'], row['immutableKey'], row['brand'], row['productName'], row['size'], row['targetJpgPath'], 'ERROR', reason=str(exc))
            results[row['immutableKey']] = asdict(res)
            done += 1
            if done % 25 == 0:
                counts = Counter(r['status'] for r in results.values())
                print(f'{done}/{len(todo)}: {dict(counts)}', flush=True)
    
    # Write full results (merged with prior)
    ordered = []
    for row in audit:
        r = results.get(row['immutableKey'])
        if r:
            ordered.append(r)
    
    write_csv(results_path, ordered)
    
    counts = Counter(r['status'] for r in ordered)
    staged = sum(1 for r in ordered if r['status'].startswith('STAGED'))
    print(f'\nDone. {len(ordered)} total, {staged} staged: {dict(counts)}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
