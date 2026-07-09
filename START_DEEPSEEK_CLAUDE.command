#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
set -a; [ -f .env ] && source .env; set +a
if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
 export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
 export ANTHROPIC_AUTH_TOKEN="$DEEPSEEK_API_KEY"
 export ANTHROPIC_MODEL='deepseek-v4-pro[1m]'
 export ANTHROPIC_DEFAULT_OPUS_MODEL='deepseek-v4-pro[1m]'
 export ANTHROPIC_DEFAULT_SONNET_MODEL='deepseek-v4-pro[1m]'
 export ANTHROPIC_DEFAULT_HAIKU_MODEL='deepseek-v4-flash'
 export CLAUDE_CODE_SUBAGENT_MODEL='deepseek-v4-flash'
 export CLAUDE_CODE_EFFORT_LEVEL=max
fi
exec claude
