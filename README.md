Projeto de monitoramento minimal — coletores, logs e tratamentos.

Objetivo: demonstrar pequenos subsistemas: coleta de métricas, persistência e rotação de logs,
tratamentos automáticos (limpeza de temporários, tentativas de recuperação de rede),
e exportador simples.

Como usar (dev):
- Criar virtualenv e instalar dependências (opcionais: psutil, portalocker)
- Rodar testes: `pytest`

Dependências opcionais:
- psutil: heurísticas Windows para trimming de memória
- portalocker: locks duráveis ao escrever logs

Diretivas de contribuição: ver `.vscode/diretrizes.txt` para padrões de docstring e estilo.
