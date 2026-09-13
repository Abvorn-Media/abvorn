@echo off
REM Start the self-hosted LanguageTool HTTP server (localhost only).
REM Uses the portable Temurin JRE under %USERPROFILE%\.abvorn\tools so no
REM system Java install is required. Checked by abvorn.core.copyguard before
REM copy is published (pages, social, email).
REM
REM   scripts\start_languagetool_server.cmd          start (blocking)
REM   scripts\start_languagetool_server.cmd spawn    start detached, log to ~\.abvorn\tools\

setlocal
set "TOOLS=%USERPROFILE%\.abvorn\tools"
set "JAVA=%TOOLS%\jre\jdk-17.0.20.1+1-jre\bin\java.exe"
set "LT=%TOOLS%\LanguageTool-6.6\languagetool-server.jar"
set "LOG=%TOOLS%\languagetool-server.log"

if not exist "%JAVA%" (
  echo ERROR: portable JRE not found at %JAVA%
  exit /b 1
)
if not exist "%LT%" (
  echo ERROR: LanguageTool not found at %LT%
  exit /b 1
)

if /I "%~1"=="spawn" (
  start "LanguageTool HTTP Server" /min cmd /c ""%JAVA%" -cp "%LT%" org.languagetool.server.HTTPServer --port 8081 --allow-origin >> "%LOG%" 2>&1"
  echo LanguageTool server starting in background. Log: %LOG%
  exit /b 0
)

"%JAVA%" -cp "%LT%" org.languagetool.server.HTTPServer --port 8081 --allow-origin