
# Segurança

Em caso de vulnerabilidade ou possível vazamento de credenciais neste repositório, seguir as orientações abaixo:

1. Não divulgue detalhes da vulnerabilidade publicamente.
2. Abra um issue privado (se disponível) ou envie um e-mail para jefersonoliveiradesousa681@gmail.com com o máximo de detalhes possível (passos para reproduzir, impacto, sugestões de correção).

Avisos importantes:

- Nunca faça commit/versionamento de segredos (tokens, chaves privadas, senhas). Caso encontre um segredo, remova-o do histórico e gere novas credenciais imediatamente.
- Antes de realizar push, execute o Gitleaks local para detectar segredos:
  ```powershell
  docker run --rm -v ${PWD}:/repo -w /repo zricethezav/gitleaks:latest detect --source /repo
  ```

O escopo de cobertura é o código-fonte deste repositório. Para reportar problemas em dependências externas, utilize os canais oficiais dos projetos afetados.

Esta abordagem contribui para a segurança do projeto.
