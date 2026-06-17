$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = "C:\Users\diaaa\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

Set-Location $ProjectDir

try {
  $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 5
  $ngrokUrl = ($tunnels.tunnels | Where-Object { $_.public_url -like "https://*" } | Select-Object -First 1).public_url
} catch {
  throw "ngrok is not running. Start it first: ngrok http 5173"
}

if (-not $ngrokUrl) {
  throw "No HTTPS ngrok tunnel found. Start it first: ngrok http 5173"
}

$env:WEBAPP_URL = $ngrokUrl
$env:WEB_PORT = "5173"

$savedTelegramToken = [Environment]::GetEnvironmentVariable("TELEGRAM_BOT_TOKEN", "User")
if ($savedTelegramToken) {
  $env:TELEGRAM_BOT_TOKEN = $savedTelegramToken
}

$savedGeminiKey = [Environment]::GetEnvironmentVariable("GEMINI_API_KEY", "User")
if ($savedGeminiKey) {
  $env:GEMINI_API_KEY = $savedGeminiKey
}

$existingBots = Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*new-chat*bot.py*" -or $_.CommandLine -like "* bot.py*" }

foreach ($bot in $existingBots) {
  if ($bot.ProcessId -ne $PID) {
    Stop-Process -Id $bot.ProcessId -Force
    Write-Host "Stopped existing bot.py process $($bot.ProcessId)"
  }
}

Write-Host "WEBAPP_URL=$env:WEBAPP_URL"
Write-Host "Starting bot.py..."
& $PythonExe bot.py
