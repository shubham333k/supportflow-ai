@echo off
cd /d "C:\Users\shubh\Automation Pro"
mkdir eval\results 2>nul
".\.venv\Scripts\python.exe" -m pytest api\tests\unit\ -v --tb=short 1>eval\results\pytest_out.txt 2>eval\results\pytest_err.txt
echo "=== EXIT CODE: %ERRORLEVEL% ===" >> eval\results\pytest_out.txt
