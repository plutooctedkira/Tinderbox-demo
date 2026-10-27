# Push E:\... to GitHub (ASCII only: PowerShell 5.1 reads BOM-less UTF-8 as ANSI)
param([string]$Msg = "update")

$root = 'E:\记忆库'
$git  = 'D:\Git\cmd\git.exe'
$ca   = 'D:\Git\ucrt64\etc\ssl\certs\ca-bundle.crt'
$px   = 'http://127.0.0.1:7897'

if (-not (Test-Path "$root\.github_token")) { throw "missing .github_token" }
$tok = (Get-Content "$root\.github_token" -Encoding ASCII) -replace '.*:([^@]+)@.*', '$1'
$b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("x-access-token:$tok"))

& $git -C $root add -A
if ((& $git -C $root status --porcelain)) {
    & $git -C $root commit -q -m $Msg
    Write-Output "committed: $Msg"
}

$flags = @('-c', "http.proxy=$px", '-c', "https.proxy=$px",
           '-c', 'http.sslBackend=openssl', '-c', "http.sslCAInfo=$ca",
           '-c', "http.extraheader=AUTHORIZATION: basic $b64")

$env:GIT_TERMINAL_PROMPT = '0'
$out = & $git -C $root @flags push origin main 2>&1
$code = $LASTEXITCODE
($out | Where-Object { $_ -match '->|error|fatal|rejected|up-to-date|To https' }) | ForEach-Object { "  $_" }

if ($code -ne 0) { Write-Output "FAILED ($code)"; exit 1 }

& $git -C $root @flags fetch origin 2>&1 | Out-Null
$local  = (& $git -C $root rev-parse HEAD).Trim().Substring(0,8)
$remote = (& $git -C $root rev-parse origin/main).Trim().Substring(0,8)
if ($local -eq $remote) {
    Write-Output "SYNCED  local $local / remote $remote"
    Write-Output "  https://github.com/plutooctedkira/Tinderbox-demo"
} else {
    Write-Output "MISMATCH  local $local / remote $remote"
    exit 1
}
