$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendRoot = Join-Path $ProjectRoot "backend"
$LogFile = Join-Path $ProjectRoot "backend-live.log"

Set-Location $BackendRoot
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 *> $LogFile
