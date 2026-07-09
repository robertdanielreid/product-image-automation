# Step-by-step process

## 1. Obtain the vision key

Open Google AI Studio and create a Gemini API key. Billing can be enabled if the free quota is insufficient. Product bottle images are public catalogue assets, not patient or client data.

## 2. Extract the ZIP

Place the extracted folder somewhere permanent, such as Documents. Do not run it directly from inside the ZIP preview.

## 3. Run setup

Double-click `ONE_CLICK_SETUP.command`.

The setup script:

- creates a private Python environment;
- installs the crawler, image converter and Chromium;
- asks for the Gemini key;
- stores the key locally in `.env` with restricted permissions;
- checks external internet access.

## 4. Start the complete run

Double-click `RUN_ALL.command`.

Keep the Mac connected to power. The command uses `caffeinate` to prevent sleep. The process may run for a long time because it is intentionally rate-limited and verifies every product independently.

## 5. Resume after interruption

Double-click `RESUME.command`. The crawler preserves completed downloads, rejected URLs, AI decisions and final approvals.

## 6. Check progress

Double-click `CHECK_STATUS.command`.

The status report shows:

- candidates downloaded;
- exact matches approved;
- images requiring review;
- rejected candidates waiting for a different source;
- final JPG files materialized;
- whether the strict final validator passes.

## 7. Review only uncertain images

Double-click `OPEN_REVIEW_QUEUE.command`.

For each item, compare the image against the displayed expected brand, exact product name and quantity/size. Approve only when the package clearly matches. Reject anything unclear.

After review, run `RESUME.command` so rejected images are retried and approved images are finalized.

## 8. Let DeepSeek-Claude Code manage problems

Double-click `START_DEEPSEEK_CLAUDE.command`, then paste the contents of `DEEPSEEK_CLAUDE_MASTER_PROMPT.md`.

The agent should inspect logs, fix site-specific extraction issues, rerun failed rows and preserve all strict matching rules.

## 9. Import into the webstore

Use only files created after `STATUS_REPORT.html` says the final validator passed.

Copy the image folder into the webstore public assets directory while preserving:

`assets/product-images/catalogue-v28/<assetId>.jpg`

Import the matching regional production-ready CSV files from `output/`.
