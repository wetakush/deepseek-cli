@echo off
setlocal enableextensions

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
if not defined DEEPAPI_MODEL set "DEEPAPI_MODEL=deepseek-chat-web"
set "PYTHONUTF8=1"

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

echo [deepapi] startuyu claude s deepseek proxy
call claude %*
set "EXIT_CODE=%ERRORLEVEL%"
exit /b %EXIT_CODE%
