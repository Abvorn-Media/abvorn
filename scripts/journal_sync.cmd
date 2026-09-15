@ECHO off
REM Abvorn journal site sync - harvest runtime signals, rebuild docs/journal, push.
REM Idempotent: unchanged journal produces no commit. Uses a throwaway mirror
REM clone (hard reset each run) so the working repo is never touched.
REM Uses absolute paths: the Task Scheduler runs this with a minimal PATH.
set "PY=C:\Users\Jean Mare\AppData\Local\Python\pythoncore-3.14-64\python.exe"
set "GIT=C:\Program Files\Git\cmd\git.exe"
set "MIRROR=%USERPROFILE%\.abvorn\journal-mirror"
if not exist "%MIRROR%\.git" "%GIT%" clone --single-branch --branch main https://github.com/Abvorn-Media/abvorn.git "%MIRROR%"
if errorlevel 1 exit /b 1

set "ABVORN_SYNC_REPO_DIR=%MIRROR%"
set "ABVORN_SYNC_DATA_DIR=%~dp0..\data"
set "SITE_URL=https://abvorn.com"

"%PY%" "%~dp0sync_journal_site.py"