# Re-publishes the BetterModel resource pack to GitHub and updates
# server.properties so the server points at the new file + hash.
# Run this any time models are added/changed and you rebuild the pack
# (e.g. after "/bm reload" or a server restart regenerates build.zip).
#
# Also runs merge_items.py first, which injects the real 3D held-item
# models (keys etc.) into build.zip via a custom_model_data override on
# minecraft:paper -- BetterModel regenerates build.zip from scratch on
# every reload/restart, wiping that injection, so it must be re-applied
# every time before publishing.
#
# Usage: powershell -ExecutionPolicy Bypass -File update_pack.ps1

$ErrorActionPreference = "Stop"

$serverRoot = "C:\Users\PC_User\AppData\Roaming\FastServer\servers\93f24aeb"
$source     = Join-Path $serverRoot "plugins\BetterModel\build.zip"
$repoDir    = "C:\Users\PC_User\Downloads\mc-resourcepack"
$propsFile  = Join-Path $serverRoot "server.properties"

if (-not (Test-Path $source)) {
    Write-Error "build.zip not found at $source -- start the server once (or /bm reload) so BetterModel regenerates it."
}

py -3.14 (Join-Path $repoDir "merge_items.py")
if ($LASTEXITCODE -ne 0) { Write-Error "merge_items.py failed -- server.properties was NOT touched." }

Copy-Item $source (Join-Path $repoDir "build.zip") -Force

Push-Location $repoDir
git add build.zip
$diff = git diff --cached --stat
if (-not $diff) {
    Write-Host "build.zip is unchanged -- nothing to publish."
    Pop-Location
    exit 0
}
git commit -m "Update resource pack"
if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Error "git commit failed -- server.properties was NOT touched." }
git push
if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Error "git push failed -- server.properties was NOT touched." }
Pop-Location

$hash = (Get-FileHash (Join-Path $repoDir "build.zip") -Algorithm SHA1).Hash.ToLower()

$content = Get-Content $propsFile -Raw
$content = $content -replace 'resource-pack-sha1=.*', "resource-pack-sha1=$hash"
Set-Content -Path $propsFile -Value $content -NoNewline

Write-Host "Published. New SHA1: $hash"
Write-Host "Restart the server (FastServer GUI) for the change to take effect."
