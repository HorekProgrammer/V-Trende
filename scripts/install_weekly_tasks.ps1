$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual environment Python was not found: $python"
}

$timeZone = Get-TimeZone
if ($timeZone.Id -ne "Russian Standard Time") {
    throw "Set Windows time zone to 'Russian Standard Time'. Current: $($timeZone.Id)"
}

$prepareAction = New-ScheduledTaskAction `
    -Execute $python `
    -Argument "-m parser.scheduler prepare" `
    -WorkingDirectory $projectRoot
$prepareTrigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Sunday -At "22:00"
$prepareSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 15)

$publishAction = New-ScheduledTaskAction `
    -Execute $python `
    -Argument "-m parser.scheduler publish" `
    -WorkingDirectory $projectRoot
$publishTrigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Monday -At "00:00"
$publishSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5)

$backendAction = New-ScheduledTaskAction `
    -Execute $python `
    -Argument "-m backend" `
    -WorkingDirectory $projectRoot
$backendTrigger = New-ScheduledTaskTrigger -AtLogOn
$backendSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask `
    -TaskName "V-Trende Backend" `
    -Description "Start the local V-Trende API when the user logs on" `
    -Action $backendAction `
    -Trigger $backendTrigger `
    -Settings $backendSettings `
    -Force | Out-Null

Register-ScheduledTask `
    -TaskName "V-Trende Prepare Weekly Data" `
    -Description "Sunday 22:00 MSK: collect parsers and Wordstat without publishing" `
    -Action $prepareAction `
    -Trigger $prepareTrigger `
    -Settings $prepareSettings `
    -Force | Out-Null

Register-ScheduledTask `
    -TaskName "V-Trende Publish Weekly Rating" `
    -Description "Monday 00:00 MSK: publish the prepared weekly rating" `
    -Action $publishAction `
    -Trigger $publishTrigger `
    -Settings $publishSettings `
    -Force | Out-Null

Get-ScheduledTask -TaskName "V-Trende Backend", "V-Trende Prepare Weekly Data", "V-Trende Publish Weekly Rating" |
    Select-Object TaskName, State
