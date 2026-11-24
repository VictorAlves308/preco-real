# Cria um atalho "Monitor de preços" na área de trabalho que abre a tela de cadastro.
# Uso:  powershell -ExecutionPolicy Bypass -File criar_atalho.ps1
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyw = Join-Path $raiz ".venv\Scripts\pythonw.exe"
$destino = Join-Path ([Environment]::GetFolderPath("Desktop")) "Monitor de precos.lnk"
$atalho = (New-Object -ComObject WScript.Shell).CreateShortcut($destino)
$atalho.TargetPath = $pyw
$atalho.Arguments = "-m precos --cadastro"
$atalho.WorkingDirectory = $raiz
$atalho.Description = "Produtos monitorados e configuracoes"
$atalho.Save()
Write-Host "Atalho criado em $destino"
