# Cheapest practical route

## Recommended configuration

- Run locally on the existing Mac instead of renting a GPU.
- Use DeepSeek-Claude Code for terminal work, repairs and monitoring.
- Use the included browser and existing catalogue source pages for image discovery.
- Use Gemini 2.5 Flash-Lite only once per staged candidate for visual verification.
- Use the free manual review page only for the remaining uncertain products.

## Why not self-host DeepSeek-VL2?

DeepSeek-VL2 is open source and supports OCR and visual reasoning, but the official repository notes that VL2-Small may require about 80 GB of GPU memory, or about 40 GB using incremental prefilling. Renting that hardware for a large catalogue is usually more expensive and more complicated than using a low-cost vision API.

## Expected variable cost

Gemini 2.5 Flash-Lite is priced for low-cost image input. A single strict pass over roughly 20,000 images should usually cost only a few dollars. Multiple rejected candidates and retries can raise the total. A conservative working budget is approximately USD $5–$30 for vision verification, excluding unusual search or bandwidth costs.

No paid search API is required. The browser fallback uses public search results and official product pages.

## Cost controls

Edit `.env`:

- `GEMINI_MODEL=gemini-2.5-flash-lite`
- `VISION_APPROVAL_THRESHOLD=98`
- `GEMINI_WORKERS=2`
- `GEMINI_RPS=1`
- `MAX_RETRY_PASSES=3`

Lower concurrency does not reduce token cost, but it reduces rate-limit errors. Do not lower the approval threshold merely to increase completion percentage.
