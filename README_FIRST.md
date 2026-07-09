# Start here — exact product images for all 20,076 products

This package is designed for the cheapest practical workflow with DeepSeek-Claude Code.

## You only need to do three things

1. Get a Gemini API key from Google AI Studio.
2. Double-click `ONE_CLICK_SETUP.command` and paste the key once.
3. Double-click `RUN_ALL.command`.

The program is resumable. If the Mac restarts or the terminal closes, double-click `RESUME.command`.

## Why Gemini is included

DeepSeek-Claude Code is the coding/orchestration agent. DeepSeek's Anthropic-compatible API does not accept image message blocks, so it cannot reliably inspect bottle labels itself. Gemini 2.5 Flash-Lite is used only for the final image verification step.

## What the automation does

- Processes all 20,076 catalogue rows.
- Searches existing official product pages first.
- Uses manufacturer-first web discovery when the existing page is ambiguous.
- Downloads the best candidate image and converts it to an RGB JPG.
- Rejects logos, placeholders, lifestyle photos, wrong products and wrong sizes.
- Checks exact brand, product name, quantity/size, strength, form, flavour, audience and bundle.
- Avoids reusing one image across incompatible products.
- Retries rejected candidates with a different image.
- Produces a small manual review queue only for uncertain cases.
- Refuses to publish an image unless it passes the strict validator.

## Main files

- `ONE_CLICK_SETUP.command` — first-time setup.
- `RUN_ALL.command` — complete or resume the full process.
- `CHECK_STATUS.command` — open the current counts.
- `OPEN_REVIEW_QUEUE.command` — approve the remaining uncertain images.
- `START_DEEPSEEK_CLAUDE.command` — open DeepSeek-Claude Code in this project.
- `DEEPSEEK_CLAUDE_MASTER_PROMPT.md` — prompt for the coding agent.
- `STEP_BY_STEP_GUIDE.docx` — illustrated written instructions.

## Output

Final JPG files:

`webstore_image_output/assets/product-images/catalogue-v28/`

Final validated regional catalogues:

`output/catalogue_ca_V28_PRODUCTION_READY.csv`

`output/catalogue_eu_V28_PRODUCTION_READY.csv`

`output/catalogue_uk_V28_PRODUCTION_READY.csv`

`output/catalogue_us_V28_PRODUCTION_READY.csv`

The package is fail-closed. A missing or uncertain image remains unresolved rather than being replaced with a brand logo.
