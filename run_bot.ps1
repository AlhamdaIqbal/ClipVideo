# PowerShell Script to run ClipVideo Telegram Bot 24/7 with Auto-Restart

Write-Host "=============================================" -ForegroundColor Green
Write-Host "   ClipVideo Telegram Bot Auto-Restart 24/7" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green

$bot_script = "tools/telegram_bot.py"
$python_exe = ".venv/Scripts/python.exe"

# Check if Virtual Environment exists
if (-not (Test-Path $python_exe)) {
    Write-Host "Error: Virtual environment (.venv) tidak ditemukan!" -ForegroundColor Red
    Write-Host "Harap buat .venv dan install dependensi terlebih dahulu." -ForegroundColor Yellow
    exit 1
}

# Run loop
while ($true) {
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Menjalankan Bot Telegram..." -ForegroundColor Cyan
    
    # Run the python command
    & $python_exe $bot_script
    
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Bot terhenti/crash! Melakukan restart dalam 5 detik..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}
