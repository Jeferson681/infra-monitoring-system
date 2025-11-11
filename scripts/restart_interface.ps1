# Reinicia a interface de rede (exemplo para Ethernet)
Start-Process powershell -Verb runAs -ArgumentList '-Command "Disable-NetAdapter -Name \"Ethernet\" -Confirm:$false; Start-Sleep -Seconds 2; Enable-NetAdapter -Name \"Ethernet\" -Confirm:$false"'

# Observação:
# - Altere "Ethernet" para o nome correto da interface de rede se necessário.
# - Scripts exigem execução como administrador.
# - Não execute automaticamente, apenas para testes manuais.
