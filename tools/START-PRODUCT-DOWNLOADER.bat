@echo off
cd /d "%~dp0"
py -3 --version >nul 2>&1
if not errorlevel 1 (
 set "LM_PYTHON=py -3"
) else (
 python --version >nul 2>&1
 if errorlevel 1 (
  echo Install Python from https://www.python.org/downloads/ and enable Add Python to PATH.
  pause
  exit /b 1
 )
 set "LM_PYTHON=python"
)
%LM_PYTHON% -m pip install -r download-products-requirements.txt
if errorlevel 1 goto failed
%LM_PYTHON% -m playwright install chromium
if errorlevel 1 goto failed
%LM_PYTHON% download_products.py
pause
exit /b
:failed
echo Setup did not finish. Keep the error text and send it for help.
pause
