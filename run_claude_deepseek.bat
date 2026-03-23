@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

if exist "%SCRIPT_DIR%deepapi.env.bat" call "%SCRIPT_DIR%deepapi.env.bat"

if not defined DEEPSEEK_TOKEN (
  echo [deepapi] ne naiden DEEPSEEK_TOKEN
  echo sozday fayl deepapi.env.bat ryadom s etim batnikom
  echo primer est v deepapi.env.example.bat
  pause
  exit /b 1
)

if not defined DEEPAPI_HOST set "DEEPAPI_HOST=127.0.0.1"
if not defined DEEPAPI_PORT set "DEEPAPI_PORT=8080"
if not defined DEEPAPI_API_KEY set "DEEPAPI_API_KEY=deepapi-local"
if not defined ANTHROPIC_BASE_URL set "ANTHROPIC_BASE_URL=http://%DEEPAPI_HOST%:%DEEPAPI_PORT%"
if not defined ANTHROPIC_AUTH_TOKEN set "ANTHROPIC_AUTH_TOKEN=%DEEPAPI_API_KEY%"
if not defined DEEPAPI_MODEL set "DEEPAPI_MODEL=deepseek-reasoner"
if not defined DEEPAPI_ALLOW_CLIENT_THINKING_OVERRIDE set "DEEPAPI_ALLOW_CLIENT_THINKING_OVERRIDE=false"
if not defined DEEPAPI_ALLOW_CLIENT_SEARCH_OVERRIDE set "DEEPAPI_ALLOW_CLIENT_SEARCH_OVERRIDE=false"
if not defined DEEPAPI_STREAM_CHUNK_SIZE set "DEEPAPI_STREAM_CHUNK_SIZE=96"
set "PYTHONUTF8=1"

call :choose_model
call :apply_model_defaults
call :choose_thinking

set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
  echo [deepapi] python ne naiden v path
  pause
  exit /b 1
)

call %PYTHON_CMD% -c "import fastapi,uvicorn,httpx" 1>nul 2>nul
if errorlevel 1 (
  echo [deepapi] ustanavlivayu zavisimosti
  call %PYTHON_CMD% -m pip install -r "%SCRIPT_DIR%requirements.txt"
  if errorlevel 1 (
    echo [deepapi] ne udalos ustanovit zavisimosti
    pause
    exit /b 1
  )
)

powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -UseBasicParsing -Uri '%ANTHROPIC_BASE_URL%/health' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  echo [deepapi] zapusk local proxy na %ANTHROPIC_BASE_URL%
  start "deepapi" /min cmd /c "cd /d "%SCRIPT_DIR%" && call %PYTHON_CMD% -m deepapi"
) else (
  echo [deepapi] proxy uzhe zapushen
)

set "READY="
for /l %%N in (1,1,40) do (
  powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; try { $r = Invoke-WebRequest -UseBasicParsing -Uri '%ANTHROPIC_BASE_URL%/health' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
  if not errorlevel 1 (
    set "READY=1"
    goto :health_ok
  )
  timeout /t 1 /nobreak >nul
)

:health_ok
if not defined READY (
  echo [deepapi] proxy ne podnyalsya, prover okno deepapi
  pause
  exit /b 1
)

set "RAW_ARGS=%*"
set "CLAUDE_MODEL_ARG=--model %DEEPAPI_MODEL%"
echo(%RAW_ARGS% | findstr /i /c:"--model " /c:"--model=" >nul && set "CLAUDE_MODEL_ARG="

echo [deepapi] startuyu claude s model %DEEPAPI_MODEL%, thinking=%DEEPAPI_THINKING_ENABLED%, search=%DEEPAPI_SEARCH_ENABLED%
call claude %CLAUDE_MODEL_ARG% %*
set "EXIT_CODE=%ERRORLEVEL%"
exit /b %EXIT_CODE%

:choose_model
echo.
echo [deepapi] vyberi model
 echo   1. deepseek-reasoner (thinking)
 echo   2. deepseek-chat
 echo   3. deepseek-reasoner-search (thinking + search)
 echo   4. deepseek-chat-search (search)
 echo   enter. ostavit %DEEPAPI_MODEL%
 echo   ili vvedi lyuboy drugoy model id vruchnuyu
set "MODEL_CHOICE="
set /p MODEL_CHOICE="model^> "
if not defined MODEL_CHOICE exit /b 0
if /i "%MODEL_CHOICE%"=="1" set "DEEPAPI_MODEL=deepseek-reasoner" & exit /b 0
if /i "%MODEL_CHOICE%"=="2" set "DEEPAPI_MODEL=deepseek-chat" & exit /b 0
if /i "%MODEL_CHOICE%"=="3" set "DEEPAPI_MODEL=deepseek-reasoner-search" & exit /b 0
if /i "%MODEL_CHOICE%"=="4" set "DEEPAPI_MODEL=deepseek-chat-search" & exit /b 0
set "DEEPAPI_MODEL=%MODEL_CHOICE%"
exit /b 0

:apply_model_defaults
if /i "%DEEPAPI_MODEL%"=="deepseek-reasoner" (
  set "DEEPAPI_THINKING_ENABLED=true"
  set "DEEPAPI_SEARCH_ENABLED=false"
  exit /b 0
)
if /i "%DEEPAPI_MODEL%"=="deepseek-chat" (
  set "DEEPAPI_THINKING_ENABLED=false"
  set "DEEPAPI_SEARCH_ENABLED=false"
  exit /b 0
)
if /i "%DEEPAPI_MODEL%"=="deepseek-reasoner-search" (
  set "DEEPAPI_THINKING_ENABLED=true"
  set "DEEPAPI_SEARCH_ENABLED=true"
  exit /b 0
)
if /i "%DEEPAPI_MODEL%"=="deepseek-chat-search" (
  set "DEEPAPI_THINKING_ENABLED=false"
  set "DEEPAPI_SEARCH_ENABLED=true"
  exit /b 0
)
if not defined DEEPAPI_THINKING_ENABLED set "DEEPAPI_THINKING_ENABLED=true"
if not defined DEEPAPI_SEARCH_ENABLED set "DEEPAPI_SEARCH_ENABLED=true"
exit /b 0

:choose_thinking
echo.
echo [deepapi] vyberi thinking mode
 echo   1. auto po modeli, seichas %DEEPAPI_THINKING_ENABLED%
 echo   2. vklyuchit thinking
 echo   3. vyklyuchit thinking
 echo   enter. ostavit kak est
set "THINKING_CHOICE="
set /p THINKING_CHOICE="thinking^> "
if not defined THINKING_CHOICE exit /b 0
if /i "%THINKING_CHOICE%"=="1" exit /b 0
if /i "%THINKING_CHOICE%"=="2" set "DEEPAPI_THINKING_ENABLED=true" & exit /b 0
if /i "%THINKING_CHOICE%"=="3" set "DEEPAPI_THINKING_ENABLED=false" & exit /b 0
exit /b 0
