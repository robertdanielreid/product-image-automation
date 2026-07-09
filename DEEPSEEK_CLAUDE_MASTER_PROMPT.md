# Prompt for DeepSeek-Claude Code

You are responsible for completing the exact product-image catalogue in this repository.

Run and maintain the included V33 pipeline until the strict final validator passes for all 20,076 catalogue rows. Begin by reading `README_FIRST.md`, `.env.example`, `scripts/master_pipeline.py`, `scripts/acquire_all_20076_real_images.py`, `scripts/verify_staged_images_gemini.py`, and `scripts/validate_all_20076_real_images.py`.

Primary command:

`./RUN_ALL.command`

Requirements:

1. Preserve all 20,076 immutable product keys and target JPG paths.
2. Never use a brand logo, generic placeholder, category graphic or lifestyle image as a product image.
3. Require exact brand, product name and quantity/size. Also require exact strength, form, flavour, audience and bundle when applicable.
4. Prefer official manufacturer pages, then authorized distributors, then reputable retailers.
5. Do not accept a page-level size dropdown as evidence that the selected image depicts that size.
6. Do not reuse identical or perceptually identical image bytes across incompatible products.
7. Keep all processing resumable. Do not delete approved images or completed audit records.
8. When a candidate is rejected, retain its URL in `output/rejected_candidates.csv` so it is not selected again.
9. Repair site-specific extraction code when a manufacturer uses JavaScript, Shopify, WooCommerce, JSON-LD or unusual image galleries.
10. Use Gemini only for vision verification; DeepSeek's Anthropic-compatible image blocks are unsupported.
11. Do not weaken `VISION_APPROVAL_THRESHOLD`, exact size checks or final validation to force a passing count.
12. Produce a clear list of genuinely unresolved products if a real exact image cannot be found.

Work autonomously. Inspect `logs/master_pipeline.log`, `STATUS_REPORT.json`, `output/acquisition_summary.json`, `output/gemini_verification_summary.json`, and `output/final_validation_summary.json`. Fix errors, rerun only failed work, and continue until the validator passes or only irreducible manual-review cases remain.
