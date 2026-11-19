@ECHO off
REM Abvorn journal site sync - harvest runtime signals, rebuild docs/journal, publish.
REM Idempotent: unchanged journal produces no commit. Builds from the local
REM checkout and publishes through the GitHub API: git-over-HTTPS to github.com
REM times out on this host (300s), while api.github.com is reachable.
REM Uses absolute paths: the Task Scheduler runs this with a minimal PATH.
set "PY=C:\Users\Jean Mare\AppData\Local\Python\pythoncore-3.14-64\python.exe"
set "REPO=%~dp0.."

set "ABVORN_SYNC_REPO_DIR=%REPO%"
set "ABVORN_SYNC_DATA_DIR=%REPO%\data"
set "SITE_URL=https://abvorn.com"

"%PY%" "%~dp0sync_journal_site.py" --publish-api
exit /b %errorlevel%
