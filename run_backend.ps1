# Start the Backend
Write-Host "Starting Backend API..." -ForegroundColor Cyan
Set-Location d:\project\project\backend
d:\project\project\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
