# run.ps1 — set up and launch the CSV Data Analyst (Windows / PowerShell).
#
# Creates a Python virtualenv, installs backend requirements + frontend packages,
# ensures data_analyst/.env exists, then starts the FastAPI backend and the Vite
# frontend together.
#
#   powershell -ExecutionPolicy Bypass -File run.ps1
#
$ErrorActionPreference = "Stop"
$root     = $PSScriptRoot
$venv     = Join-Path $root ".venv"
$backend  = Join-Path $root "data_analyst"
$frontend = Join-Path $root "app"

# 1) Python virtualenv
if (-not (Test-Path $venv)) {
    Write-Host "==> Creating virtualenv (.venv)" -ForegroundColor Cyan
    python -m venv $venv
}
$py = Join-Path $venv "Scripts\python.exe"

# 2) Python requirements
Write-Host "==> Installing Python requirements" -ForegroundColor Cyan
& $py -m pip install --upgrade pip --quiet
& $py -m pip install -r (Join-Path $backend "requirements.txt") --quiet

# 3) .env (holds OPENAI_API_KEY; gitignored)
$envFile    = Join-Path $backend ".env"
$envExample = Join-Path $backend ".env.example"
if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
    Write-Host "==> Created data_analyst/.env from .env.example" -ForegroundColor Yellow
    Write-Host "    EDIT IT and set OPENAI_API_KEY before chatting." -ForegroundColor Yellow
}

# 4) Frontend packages
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "==> Installing frontend packages (npm install)" -ForegroundColor Cyan
    Push-Location $frontend; npm install; Pop-Location
}

# 5) Launch backend (new window) + frontend (this window)
Write-Host "==> Starting backend  -> http://127.0.0.1:8000  (/docs)" -ForegroundColor Green
Write-Host "==> Starting frontend -> http://localhost:5173" -ForegroundColor Green
Start-Process -FilePath $py `
    -ArgumentList @("-m", "uvicorn", "src.api:app", "--reload") `
    -WorkingDirectory $backend
Push-Location $frontend
npm run dev
Pop-Location
