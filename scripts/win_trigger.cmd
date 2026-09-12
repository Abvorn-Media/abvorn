@ECHO off
REM Abvorn win.sh trigger - bridge GSC evidence into loop run briefs.
REM Idempotent: skips when evidence is below threshold or a run is pending.
python "%~dp0win_trigger.py" --loop seo-growth