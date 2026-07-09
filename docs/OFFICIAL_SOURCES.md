# Official sources checked July 2026

- DeepSeek Claude Code integration: https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code
- DeepSeek Anthropic API compatibility: https://api-docs.deepseek.com/guides/anthropic_api
- DeepSeek models and pricing: https://api-docs.deepseek.com/quick_start/pricing
- DeepSeek-VL2 official repository: https://github.com/deepseek-ai/DeepSeek-VL2
- Gemini image understanding: https://ai.google.dev/gemini-api/docs/image-understanding
- Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing

Key design facts:

- DeepSeek officially documents Claude Code integration through its Anthropic-compatible endpoint.
- DeepSeek's Anthropic compatibility table marks image content blocks as unsupported.
- DeepSeek-VL2 supports OCR and multimodal understanding, but its official repository describes substantial GPU-memory requirements for VL2-Small.
- Gemini supports inline image input and structured JSON output.
- Gemini 2.5 Flash-Lite is the low-cost vision model used by default in this package.
