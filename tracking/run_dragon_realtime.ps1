# 龙首阴实时跟踪 - 每日收盘后更新持仓
# 由 Windows 任务计划程序调用

$ROOT = "C:\Users\Administrator\AppData\Roaming\reasonix\global-workspace\quant-reasonix"
$LOG_DIR = "$ROOT\tracking\logs"
$LOG_FILE = "$LOG_DIR\dragon_realtime_$(Get-Date -Format 'yyyyMMdd').log"

# 创建日志目录
if (-not (Test-Path $LOG_DIR)) { New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null }

# 写日志头
"=== 龙首阴实时更新 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Out-File -FilePath $LOG_FILE -Encoding UTF8

# 切到项目目录
Push-Location $ROOT

# 清除代理（腾讯API不需要代理）
$env:HTTP_PROXY = ""
$env:HTTPS_PROXY = ""

# 运行实时更新
$output = python paper_trading/dragon_monitor.py --realtime 2>&1
$output | Out-File -FilePath $LOG_FILE -Encoding UTF8 -Append

# 统计出场和持仓
$closed = ($output | Select-String "今日出场").Count
$exited = if ($closed -gt 0) { ($output | Select-String "今日出场").Line } else { "无出场" }
"出场: $exited" | Out-File -FilePath $LOG_FILE -Encoding UTF8 -Append

"=== 完成 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Out-File -FilePath $LOG_FILE -Encoding UTF8 -Append

Pop-Location

# 输出最后几行摘要
Write-Output "龙首阴更新完成 - 日志: $LOG_FILE"