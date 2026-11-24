# Remove o agendamento do monitor de preços.
Unregister-ScheduledTask -TaskName "Monitor de precos" -Confirm:$false
Write-Host "Tarefa removida."
