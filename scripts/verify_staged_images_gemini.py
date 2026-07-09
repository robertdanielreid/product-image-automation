#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageOps

APPROVED = "APPROVED_EXACT_PRODUCT_PACKAGE"
REJECTED = "REJECTED_WRONG_OR_UNCERTAIN"
REVIEW = "REVIEW_REQUIRED"
TRUE_FIELDS = [
    "brandExact", "productNameExact", "sizeQuantityExact",
    "strengthExactOrNotApplicable", "formExactOrNotApplicable",
    "flavourAudienceBundleExactOrNotApplicable", "officialProductImageOrBottle",
    "noLogoPlaceholderLifestyle",
]

_RATE_LOCK = threading.Lock()
_LAST_REQUEST = 0.0


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = fields or list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def rate_limit(rps: float) -> None:
    global _LAST_REQUEST
    delay = 1.0 / max(rps, 0.05)
    with _RATE_LOCK:
        wait = delay - (time.monotonic() - _LAST_REQUEST)
        if wait > 0:
            time.sleep(wait)
        _LAST_REQUEST = time.monotonic()


def prepare_image(path: Path, max_side: int = 1800, max_bytes: int = 7_000_000) -> tuple[bytes, str]:
    data = path.read_bytes()
    with Image.open(BytesIO(data)) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        if max(im.size) > max_side or len(data) > max_bytes:
            im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        out = BytesIO()
        im.save(out, "JPEG", quality=90, optimize=True)
        return out.getvalue(), "image/jpeg"


def prompt_for(row: dict[str, str], result: dict[str, str]) -> str:
    return f"""You are the final quality-control verifier for a supplement webstore.
Inspect the attached candidate product image. Fail closed. Do not infer a match merely because the webpage or brand is related.

EXPECTED CATALOGUE IDENTITY
Brand: {row.get('brand','')}
Product name: {row.get('productName','')}
Quantity/size: {row.get('size','')}
Format/form: {row.get('format','')}
Strength: {row.get('strength','')}
SKU: {row.get('sku','')}
Region: {row.get('region','')}
Candidate source page: {result.get('evidencePage','')}
Candidate image URL: {result.get('resolvedImageUrl','')}

APPROVE only when the image is a real official product/bottle/package image and the visible package or image-specific evidence matches the exact brand, product name, and quantity/size. Also verify strength, dosage form, flavour, audience, and bundle configuration when applicable.
REJECT logos, badges, placeholders, category graphics, ingredient panels without the product, lifestyle images, generic family images, wrong packaging, wrong size/count/volume, wrong flavour, wrong strength, or another product from the same brand.
If the exact quantity/size cannot be read or unambiguously confirmed from this image, choose REVIEW or REJECT, never APPROVE.
Return only the required JSON."""


SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["APPROVE", "REVIEW", "REJECT"]},
        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        "real_product_image": {"type": "boolean"},
        "brand_exact": {"type": "boolean"},
        "product_name_exact": {"type": "boolean"},
        "size_quantity_exact": {"type": "boolean"},
        "strength_exact_or_not_applicable": {"type": "boolean"},
        "form_exact_or_not_applicable": {"type": "boolean"},
        "flavour_audience_bundle_exact_or_not_applicable": {"type": "boolean"},
        "no_logo_placeholder_lifestyle": {"type": "boolean"},
        "visible_brand": {"type": "string"},
        "visible_product_name": {"type": "string"},
        "visible_size_quantity": {"type": "string"},
        "visible_strength": {"type": "string"},
        "visible_form": {"type": "string"},
        "evidence": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": [
        "decision", "confidence", "real_product_image", "brand_exact",
        "product_name_exact", "size_quantity_exact",
        "strength_exact_or_not_applicable", "form_exact_or_not_applicable",
        "flavour_audience_bundle_exact_or_not_applicable",
        "no_logo_placeholder_lifestyle", "visible_brand", "visible_product_name",
        "visible_size_quantity", "visible_strength", "visible_form", "evidence", "reason",
    ],
}


@dataclass
class Verification:
    immutableKey: str
    status: str
    payload: dict[str, Any] | None = None
    error: str = ""


def call_gemini(api_key: str, model: str, prompt: str, image_bytes: bytes, mime: str, rps: float, retries: int) -> dict[str, Any]:
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "contents": [{"role": "user", "parts": [
            {"text": prompt},
            {"inlineData": {"mimeType": mime, "data": base64.b64encode(image_bytes).decode("ascii")}},
        ]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 650,
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
        },
    }
    last_error = ""
    for attempt in range(retries + 1):
        rate_limit(rps)
        try:
            resp = requests.post(endpoint, params={"key": api_key}, json=body, timeout=120)
            if resp.status_code in {429, 500, 502, 503, 504}:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except Exception as exc:
            last_error = str(exc)
            if attempt >= retries:
                break
            time.sleep(min(60, 2 ** attempt * 3))
    raise RuntimeError(last_error)


def verify_one(row: dict[str, str], result: dict[str, str], store: Path, api_key: str, model: str, rps: float, retries: int, mock: bool) -> Verification:
    key = row["immutableKey"]
    staged_rel = result.get("stagingPath", "")
    image_path = store / staged_rel
    if not staged_rel or not image_path.exists():
        return Verification(key, "NO_IMAGE", error="staged image missing")
    if mock:
        payload = {
            "decision": "REVIEW", "confidence": 50, "real_product_image": True,
            "brand_exact": False, "product_name_exact": False, "size_quantity_exact": False,
            "strength_exact_or_not_applicable": True, "form_exact_or_not_applicable": True,
            "flavour_audience_bundle_exact_or_not_applicable": True,
            "no_logo_placeholder_lifestyle": True, "visible_brand": "", "visible_product_name": "",
            "visible_size_quantity": "", "visible_strength": "", "visible_form": "",
            "evidence": "mock run", "reason": "mock run",
        }
        return Verification(key, "OK", payload)
    try:
        image_bytes, mime = prepare_image(image_path)
        payload = call_gemini(api_key, model, prompt_for(row, result), image_bytes, mime, rps, retries)
        return Verification(key, "OK", payload)
    except Exception as exc:
        return Verification(key, "ERROR", error=str(exc))


def is_strict_approval(payload: dict[str, Any], threshold: int) -> bool:
    required = [
        payload.get("real_product_image"), payload.get("brand_exact"),
        payload.get("product_name_exact"), payload.get("size_quantity_exact"),
        payload.get("strength_exact_or_not_applicable"), payload.get("form_exact_or_not_applicable"),
        payload.get("flavour_audience_bundle_exact_or_not_applicable"),
        payload.get("no_logo_placeholder_lifestyle"),
    ]
    return payload.get("decision") == "APPROVE" and int(payload.get("confidence", 0)) >= threshold and all(v is True for v in required)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--store-root", type=Path, required=True)
    ap.add_argument("--model", default=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"))
    ap.add_argument("--threshold", type=int, default=int(os.getenv("VISION_APPROVAL_THRESHOLD", "98")))
    ap.add_argument("--workers", type=int, default=int(os.getenv("GEMINI_WORKERS", "2")))
    ap.add_argument("--rps", type=float, default=float(os.getenv("GEMINI_RPS", "1")))
    ap.add_argument("--retries", type=int, default=5)
    ap.add_argument("--max-requests", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--mock", action="store_true")
    args = ap.parse_args()

    root = args.package_root.resolve()
    store = args.store_root.resolve()
    out = root / "output"
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key and not args.mock:
        raise SystemExit("GEMINI_API_KEY is missing. Add it to .env or export it before running.")

    audit = read_csv(root / "data/all_20076_strict_image_audit.csv")
    results = {r["immutableKey"]: r for r in read_csv(out / "all_20076_acquisition_results.csv")}
    review_path = out / "manual_visual_review.csv"
    review_rows = read_csv(review_path)
    review = {r["immutableKey"]: r for r in review_rows}
    audit_by_key = {r["immutableKey"]: r for r in audit}

    pending: list[tuple[dict[str, str], dict[str, str]]] = []
    for row in audit:
        key = row["immutableKey"]
        res = results.get(key)
        rev = review.get(key, {})
        if not res or not res.get("status", "").startswith("STAGED"):
            continue
        if args.resume and rev.get("manualVisualDecision") in {APPROVED, REJECTED, REVIEW}:
            continue
        pending.append((row, res))
    if args.max_requests > 0:
        pending = pending[:args.max_requests]

    print(f"Gemini verification pending: {len(pending)}; model={args.model}; threshold={args.threshold}", flush=True)
    completed: dict[str, Verification] = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {
            ex.submit(verify_one, row, res, store, api_key, args.model, args.rps, args.retries, args.mock): row["immutableKey"]
            for row, res in pending
        }
        for i, fut in enumerate(as_completed(futs), 1):
            key = futs[fut]
            try:
                completed[key] = fut.result()
            except Exception as exc:
                completed[key] = Verification(key, "ERROR", error=str(exc))
            if i % 25 == 0:
                print(f"Verified {i}/{len(pending)}", flush=True)

    # Preserve existing fields and append AI audit columns.
    fields = list(review_rows[0]) if review_rows else [
        "batchIndex", "immutableKey", "brand", "productName", "size", "targetJpgPath",
        "resolvedImageUrl", "evidencePage", "origin", "width", "height", "sha256",
        "perceptualHash", "pageBrandCoverage", "pageProductCoverage", "exactSizeEvidence",
        "imageCandidateScore", "status", "manualVisualDecision", "reviewer", "evidenceNote",
        *TRUE_FIELDS, "reviewedBrand", "reviewedProductName", "reviewedSizeQuantity",
    ]
    extra_fields = ["aiDecision", "aiConfidence", "aiReason", "aiEvidence", "aiVisibleBrand", "aiVisibleProductName", "aiVisibleSizeQuantity", "aiModel", "aiVerifiedAt"]
    for f in extra_fields:
        if f not in fields:
            fields.append(f)

    rejected_existing = read_csv(out / "rejected_candidates.csv")
    rejected_map = {(r.get("immutableKey", ""), r.get("resolvedImageUrl", "")): r for r in rejected_existing}

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for key, verification in completed.items():
        row = audit_by_key[key]
        res = results[key]
        rr = review.setdefault(key, {k: "" for k in fields})
        # Never overwrite a human approval.
        if rr.get("manualVisualDecision") == APPROVED and rr.get("reviewer", "").lower() not in {"gemini", "gemini-api"}:
            continue
        rr.update({
            "batchIndex": row.get("batchIndex", ""), "immutableKey": key,
            "brand": row.get("brand", ""), "productName": row.get("productName", ""),
            "size": row.get("size", ""), "targetJpgPath": row.get("targetJpgPath", ""),
            "resolvedImageUrl": res.get("resolvedImageUrl", ""), "evidencePage": res.get("evidencePage", ""),
            "origin": res.get("origin", ""), "width": res.get("width", ""), "height": res.get("height", ""),
            "sha256": res.get("sha256", ""), "perceptualHash": res.get("perceptualHash", ""),
            "pageBrandCoverage": res.get("pageBrandCoverage", ""), "pageProductCoverage": res.get("pageProductCoverage", ""),
            "exactSizeEvidence": res.get("exactSizeEvidence", ""), "imageCandidateScore": res.get("imageCandidateScore", ""),
            "status": res.get("status", ""), "aiModel": args.model, "aiVerifiedAt": now,
        })
        if verification.status != "OK" or not verification.payload:
            rr.update({"manualVisualDecision": REVIEW, "reviewer": "gemini-api", "aiDecision": "ERROR", "aiReason": verification.error})
            continue
        payload = verification.payload
        rr.update({
            "aiDecision": payload.get("decision", ""), "aiConfidence": payload.get("confidence", ""),
            "aiReason": payload.get("reason", ""), "aiEvidence": payload.get("evidence", ""),
            "aiVisibleBrand": payload.get("visible_brand", ""), "aiVisibleProductName": payload.get("visible_product_name", ""),
            "aiVisibleSizeQuantity": payload.get("visible_size_quantity", ""),
        })
        if is_strict_approval(payload, args.threshold):
            rr.update({
                "manualVisualDecision": APPROVED, "reviewer": "gemini-api",
                "evidenceNote": f"AI strict approval at {payload.get('confidence')}%: {payload.get('evidence','')}",
                "brandExact": "true", "productNameExact": "true", "sizeQuantityExact": "true",
                "strengthExactOrNotApplicable": "true", "formExactOrNotApplicable": "true",
                "flavourAudienceBundleExactOrNotApplicable": "true", "officialProductImageOrBottle": "true",
                "noLogoPlaceholderLifestyle": "true", "reviewedBrand": row.get("brand", ""),
                "reviewedProductName": row.get("productName", ""), "reviewedSizeQuantity": row.get("size", ""),
            })
        elif payload.get("decision") == "REJECT" or int(payload.get("confidence", 0)) >= 90:
            rr.update({"manualVisualDecision": REJECTED, "reviewer": "gemini-api", "evidenceNote": payload.get("reason", "")})
            rejected_map[(key, res.get("resolvedImageUrl", ""))] = {
                "immutableKey": key, "resolvedImageUrl": res.get("resolvedImageUrl", ""),
                "evidencePage": res.get("evidencePage", ""), "reason": payload.get("reason", ""),
                "aiConfidence": payload.get("confidence", ""), "rejectedAt": now,
            }
        else:
            rr.update({"manualVisualDecision": REVIEW, "reviewer": "gemini-api", "evidenceNote": payload.get("reason", "")})
            # During automatic retry passes, do not select the same uncertain candidate again.
            rejected_map[(key, res.get("resolvedImageUrl", ""))] = {
                "immutableKey": key, "resolvedImageUrl": res.get("resolvedImageUrl", ""),
                "evidencePage": res.get("evidencePage", ""), "reason": payload.get("reason", ""),
                "aiConfidence": payload.get("confidence", ""), "rejectedAt": now,
            }

    ordered_review = []
    for row in audit:
        key = row["immutableKey"]
        rr = review.get(key)
        if rr is None:
            rr = {k: "" for k in fields}
            rr.update({"batchIndex": row.get("batchIndex", ""), "immutableKey": key, "brand": row.get("brand", ""), "productName": row.get("productName", ""), "size": row.get("size", ""), "targetJpgPath": row.get("targetJpgPath", ""), "manualVisualDecision": "PENDING"})
        ordered_review.append(rr)
    write_csv(review_path, ordered_review, fields)
    rejected_fields = ["immutableKey", "resolvedImageUrl", "evidencePage", "reason", "aiConfidence", "rejectedAt"]
    write_csv(out / "rejected_candidates.csv", list(rejected_map.values()), rejected_fields)

    counts: dict[str, int] = {}
    for r in ordered_review:
        d = r.get("manualVisualDecision", "PENDING") or "PENDING"
        counts[d] = counts.get(d, 0) + 1
    summary = {"model": args.model, "approvalThreshold": args.threshold, "processedThisRun": len(completed), "decisionCounts": counts, "rejectedCandidateCount": len(rejected_map), "generatedAt": now}
    (out / "gemini_verification_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
