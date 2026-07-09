# Codex task: acquire and validate every catalogue image

Work from this package in a terminal with unrestricted HTTPS and DNS access.

1. Read `README_FIRST.md` and `reports/COUNT_DISCREPANCY.md`.
2. Use all **20,076** rows. Do not omit nine rows merely because the request previously stated 20,067.
3. Run:

```bash
./RUN_ACQUIRE_ALL_20076.sh /absolute/path/to/webstore
```

4. Resolve every `UNRESOLVED`, duplicate conflict and package conflict. Prefer manufacturer pages. Authorized retailers are permitted only when brand, exact product and exact package are attributable and visible.
5. Review every staged image using `output/review_dashboard/index.html`. Do not approve by URL or filename alone. Approve only when the image visibly shows the exact product/package.
6. Enter `APPROVED_EXACT_PRODUCT_PACKAGE` in `output/manual_visual_review.csv` only after visual verification.
7. Run:

```bash
./RUN_FINALIZE_ALL_20076.sh /absolute/path/to/webstore
```

8. Do not declare completion unless `output/final_validation_summary.json` has `"pass": true`, `approvedAndMaterialized: 20076`, `failureCount: 0`, and all four regional production catalogues contain their full expected row counts.

Never use logos, generic placeholders, unrelated bottle images, package-size substitutions or a single shared image for incompatible variants.
