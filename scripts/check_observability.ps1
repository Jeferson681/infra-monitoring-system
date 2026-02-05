# Start the app in background (one short cycle) and validate /health and /metrics
$log = Join-Path $env:TEMP "ims_obs_test.log"
$proc = Start-Process -FilePath "python" -ArgumentList "-m src.main -i 1 -c 0" -NoNewWindow -PassThru -RedirectStandardOutput $log -RedirectStandardError $log
Start-Sleep -Seconds 1
try {
    Invoke-RestMethod -Uri http://127.0.0.1:8000/health -UseBasicParsing | Out-Null
} catch {
    $proc | Stop-Process -ErrorAction SilentlyContinue
    Remove-Item -Path $log -ErrorAction SilentlyContinue
    exit 2
}
try {
    $m = Invoke-RestMethod -Uri http://127.0.0.1:8000/metrics -UseBasicParsing
    if (-not $m) { throw "empty" }
} catch {
    $proc | Stop-Process -ErrorAction SilentlyContinue
    Remove-Item -Path $log -ErrorAction SilentlyContinue
    exit 2
}

Write-Output 'OK'
