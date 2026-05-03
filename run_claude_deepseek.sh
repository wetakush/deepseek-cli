#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -f "$SCRIPT_DIR/deepapi.env.sh" ]]; then
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/deepapi.env.sh"
fi

if [[ -z "${DEEPSEEK_TOKEN:-}" ]]; then
  echo "[deepapi] DEEPSEEK_TOKEN not found"
  echo "create deepapi.env.sh next to this script"
  echo "example is in deepapi.env.example.sh"
  exit 1
fi

export DEEPAPI_HOST="${DEEPAPI_HOST:-127.0.0.1}"
export DEEPAPI_PORT="${DEEPAPI_PORT:-8080}"
export DEEPAPI_API_KEY="${DEEPAPI_API_KEY:-deepapi-local}"
export ANTHROPIC_AUTH_TOKEN="$DEEPAPI_API_KEY"
export DEEPAPI_MODEL="${DEEPAPI_MODEL:-deepseek-v4}"
export DEEPAPI_ALLOW_CLIENT_THINKING_OVERRIDE="${DEEPAPI_ALLOW_CLIENT_THINKING_OVERRIDE:-false}"
export DEEPAPI_ALLOW_CLIENT_SEARCH_OVERRIDE="${DEEPAPI_ALLOW_CLIENT_SEARCH_OVERRIDE:-false}"
export DEEPAPI_STREAM_CHUNK_SIZE="${DEEPAPI_STREAM_CHUNK_SIZE:-96}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

if [[ "${DEEPAPI_HOST}" == "127.0.0.1" || "${DEEPAPI_HOST}" == "localhost" ]]; then
  if command -v hostname >/dev/null 2>&1; then
    resolved_host="$(hostname -I 2>/dev/null | awk '{print $1}')"
    if [[ -n "${resolved_host:-}" ]]; then
      export DEEPAPI_HOST="$resolved_host"
    fi
  fi
fi

export ANTHROPIC_BASE_URL="http://${DEEPAPI_HOST}:${DEEPAPI_PORT}"

choose_model() {
  echo
  echo "[deepapi] choose model"
  echo "  1. deepseek-v4 (thinking + search)"
  echo "  2. deepseek-chat"
  echo "  3. deepseek-reasoner-search (thinking + search)"
  echo "  4. deepseek-chat-search (search)"
  echo "  enter. keep ${DEEPAPI_MODEL}"
  echo "  or type any custom model id manually"
  read -r -p "model> " model_choice || true
  case "${model_choice:-}" in
    "") ;;
    1) export DEEPAPI_MODEL="deepseek-v4" ;;
    2) export DEEPAPI_MODEL="deepseek-chat" ;;
    3) export DEEPAPI_MODEL="deepseek-reasoner-search" ;;
    4) export DEEPAPI_MODEL="deepseek-chat-search" ;;
    *) export DEEPAPI_MODEL="${model_choice}" ;;
  esac
}

apply_model_defaults() {
  case "${DEEPAPI_MODEL}" in
    deepseek-reasoner)
      export DEEPAPI_THINKING_ENABLED=true
      export DEEPAPI_SEARCH_ENABLED=false
      ;;
    deepseek-chat)
      export DEEPAPI_THINKING_ENABLED=false
      export DEEPAPI_SEARCH_ENABLED=false
      ;;
    deepseek-reasoner-search|deepseek-v4|expert|deepseek-chat-web)
      export DEEPAPI_THINKING_ENABLED=true
      export DEEPAPI_SEARCH_ENABLED=true
      if [[ "${DEEPAPI_MODEL}" == "deepseek-chat-web" ]]; then
        export DEEPAPI_MODEL="deepseek-v4"
      fi
      ;;
    deepseek-chat-search)
      export DEEPAPI_THINKING_ENABLED=false
      export DEEPAPI_SEARCH_ENABLED=true
      ;;
    *)
      export DEEPAPI_THINKING_ENABLED="${DEEPAPI_THINKING_ENABLED:-true}"
      export DEEPAPI_SEARCH_ENABLED="${DEEPAPI_SEARCH_ENABLED:-true}"
      ;;
  esac
}

choose_thinking() {
  echo
  echo "[deepapi] choose thinking mode"
  echo "  1. auto by model, current ${DEEPAPI_THINKING_ENABLED}"
  echo "  2. enable thinking"
  echo "  3. disable thinking"
  echo "  enter. keep current"
  read -r -p "thinking> " thinking_choice || true
  case "${thinking_choice:-}" in
    2) export DEEPAPI_THINKING_ENABLED=true ;;
    3) export DEEPAPI_THINKING_ENABLED=false ;;
  esac
}

choose_model
apply_model_defaults
choose_thinking

PYTHON_CMD=""
if command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD="python"
fi

if [[ -z "$PYTHON_CMD" ]]; then
  echo "[deepapi] python not found in PATH"
  exit 1
fi

if ! "$PYTHON_CMD" -c "import fastapi,uvicorn,httpx" >/dev/null 2>&1; then
  echo "[deepapi] installing dependencies"
  "$PYTHON_CMD" -m pip install -r "$SCRIPT_DIR/requirements.txt"
fi

if ! curl -fsS "$ANTHROPIC_BASE_URL/health" >/dev/null 2>&1; then
  echo "[deepapi] starting local proxy on $ANTHROPIC_BASE_URL"
  nohup env \
    DEEPSEEK_TOKEN="$DEEPSEEK_TOKEN" \
    DEEPSEEK_COOKIE="${DEEPSEEK_COOKIE:-}" \
    DEEPAPI_API_KEY="$DEEPAPI_API_KEY" \
    DEEPAPI_HOST="$DEEPAPI_HOST" \
    DEEPAPI_PORT="$DEEPAPI_PORT" \
    DEEPAPI_MODEL="$DEEPAPI_MODEL" \
    DEEPAPI_THINKING_ENABLED="${DEEPAPI_THINKING_ENABLED:-false}" \
    DEEPAPI_SEARCH_ENABLED="${DEEPAPI_SEARCH_ENABLED:-true}" \
    DEEPAPI_ALLOW_CLIENT_THINKING_OVERRIDE="$DEEPAPI_ALLOW_CLIENT_THINKING_OVERRIDE" \
    DEEPAPI_ALLOW_CLIENT_SEARCH_OVERRIDE="$DEEPAPI_ALLOW_CLIENT_SEARCH_OVERRIDE" \
    DEEPAPI_STREAM_CHUNK_SIZE="$DEEPAPI_STREAM_CHUNK_SIZE" \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    "$PYTHON_CMD" -m deepapi >"$SCRIPT_DIR/deepapi.log" 2>&1 &
else
  echo "[deepapi] proxy already running"
fi

ready=""
for _ in $(seq 1 40); do
  if curl -fsS "$ANTHROPIC_BASE_URL/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done

if [[ -z "$ready" ]]; then
  echo "[deepapi] proxy did not start, check deepapi.log"
  exit 1
fi

claude_model_arg=(--model "$DEEPAPI_MODEL")
for arg in "$@"; do
  if [[ "$arg" == --model || "$arg" == --model=* ]]; then
    claude_model_arg=()
    break
  fi
done

echo "[deepapi] starting claude with model $DEEPAPI_MODEL, thinking=${DEEPAPI_THINKING_ENABLED:-false}, search=${DEEPAPI_SEARCH_ENABLED:-true}"
exec claude "${claude_model_arg[@]}" "$@"
