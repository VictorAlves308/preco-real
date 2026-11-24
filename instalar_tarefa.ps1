# Agenda o monitor de preços no Windows: roda ao entrar no Windows e a cada N minutos,
# com prioridade baixa. Uso:
#   powershell -ExecutionPolicy Bypass -File instalar_tarefa.ps1              (a cada 180 min)
#   powershell -ExecutionPolicy Bypass -File instalar_tarefa.ps1 -Minutos 30  (ex.: Black Friday)
param([ValidateRange(30, 1440)][int]$Minutos = 180)
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyw = Join-Path $raiz ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pyw)) { throw "Não achei $pyw. Crie o ambiente antes (veja o README)." }

$nome = "Monitor de precos"
$usuario = "$env:USERDOMAIN\$env:USERNAME"
$acao = New-ScheduledTaskAction -Execute $pyw -Argument "-m precos" -WorkingDirectory $raiz
$gatilhos = @(
    (New-ScheduledTaskTrigger -AtLogOn -User $usuario),
    (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $Minutos))
)
$config = New-ScheduledTaskSettingsSet -Priority 7 -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $nome -Action $acao -Trigger $gatilhos -Settings $config `
    -Principal $principal -Description "Verifica precos no Zoom e avisa promocoes" -Force | Out-Null
Write-Host "Tarefa '$nome' instalada: roda ao entrar no Windows e a cada $Minutos minutos."
