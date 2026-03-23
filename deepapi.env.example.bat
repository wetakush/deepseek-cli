@echo off
rem zapolni eti peremennye odin raz i pereimenuy fayl v deepapi.env.bat

set "DEEPSEEK_TOKEN="
set "DEEPSEEK_COOKIE="
set "DEEPAPI_API_KEY=deepapi-local"
set "DEEPAPI_HOST=127.0.0.1"
set "DEEPAPI_PORT=8080"
set "DEEPAPI_MODEL=deepseek-reasoner"

rem dostupnye modeli:
rem deepseek-chat
rem deepseek-reasoner
rem deepseek-chat-search
rem deepseek-reasoner-search

rem opcionalno
rem set "DEEPAPI_THINKING_ENABLED=true"
rem set "DEEPAPI_SEARCH_ENABLED=false"
rem set "DEEPAPI_ALLOW_CLIENT_THINKING_OVERRIDE=false"
rem set "DEEPAPI_ALLOW_CLIENT_SEARCH_OVERRIDE=false"
rem set "DEEPAPI_STREAM_CHUNK_SIZE=96"
rem set "DEEPAPI_NODE_COMMAND=node"
