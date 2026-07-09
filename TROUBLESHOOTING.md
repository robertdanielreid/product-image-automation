# Troubleshooting

## The terminal says the Gemini key is missing

Run `ONE_CLICK_SETUP.command` again or open `.env` and place the key after `GEMINI_API_KEY=`.

## The Mac went to sleep or restarted

Run `RESUME.command`. Completed images and decisions are preserved.

## A website blocks the downloader

Run `START_DEEPSEEK_CLAUDE.command` and use the master prompt. The browser fallback can be adjusted for the affected brand without changing approved rows.

## Gemini rate-limit errors

Set `GEMINI_RPS=0.5` and `GEMINI_WORKERS=1` in `.env`, then resume.

## Too many manual reviews

Do not lower the 98% threshold. Ask DeepSeek-Claude Code to improve image discovery for the affected brands or to search exact SKU/UPC and size-specific official pages.

## Disk space warning

Move the entire extracted folder to a drive with at least 20 GB free, then resume from that location.

## Final validator fails

Open `output/final_validation_summary.json`. The validator identifies missing approvals, missing JPGs, invalid image formats, hash changes and duplicate-image conflicts.
