param([ValidateSet('start','stop','status','logs','gpu-check')][string]$Action = 'status')
$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskCompose = Join-Path $taskRoot 'compose.yaml'
if ($Action -eq 'start') {
    foreach ($taskFolder in @('models','input','output','user','cache')) {
        New-Item -ItemType Directory -Path (Join-Path $taskRoot "data/$taskFolder") -Force | Out-Null
    }
    docker compose -f $taskCompose up -d --build
} elseif ($Action -eq 'stop') {
    docker compose -f $taskCompose stop comfy
} elseif ($Action -eq 'logs') {
    docker compose -f $taskCompose logs --tail 80 comfy
} elseif ($Action -eq 'gpu-check') {
    Get-Content -LiteralPath (Join-Path $taskRoot 'gpu_probe.py') -Raw | docker compose -f $taskCompose exec -T comfy python -
} else {
    docker compose -f $taskCompose ps
}
if ($LASTEXITCODE -ne 0) { throw "Docker action failed: $Action" }
