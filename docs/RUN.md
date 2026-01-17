# Como Rodar (resumo)

Objetivo: instruções concisas para iniciar o projeto localmente (venv) e com Docker, além de verificações rápidas.

## Pré-requisitos
- Python 3.8+ instalado
- `docker` e `docker-compose` (opcional, para fluxo com containers)

## Execução local (3 passos)

1) Criar e ativar virtualenv

```powershell
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

ou (Unix)

```bash
python -m venv .venv
source .venv/bin/activate
```

2) Instalar dependências

```bash
python -m pip install -r requirements.txt
```

3) Ativar exporter e iniciar

Windows (cmd):

```cmd
set MONITORING_EXPORTER_ENABLE=1
set MONITORING_EXPORTER_ADDR=127.0.0.1
set MONITORING_EXPORTER_PORT=8000
python -m src.main
```

Unix / PowerShell (alternativa PowerShell usa $env:VAR=valor):

```bash
export MONITORING_EXPORTER_ENABLE=1
export MONITORING_EXPORTER_ADDR=127.0.0.1
export MONITORING_EXPORTER_PORT=8000
python -m src.main
```

## Execução com Docker

```bash
docker-compose up --build
```

Serviços esperados (padrão):
- Prometheus → http://localhost:9090
- Grafana → http://localhost:3000
- Loki → http://localhost:3100
- Exporter → http://localhost:8000/metrics

## Verificações rápidas

- Verificar endpoint metrics:

```bash
curl -s http://127.0.0.1:8000/metrics | head
```

- Verificar arquivos JSONL (persistência): `logs/json/` (ex.: `logs/json/monitoring-YYYY-MM-DD.jsonl`).
- Executar testes:

```bash
pytest -q
```

## Variáveis de ambiente (exposição de métricas)

O projeto expõe métricas Prometheus através de um único servidor HTTP. Para evitar conflitos de bind na mesma porta, há dois mecanismos relacionados, mas **não devem ser usados simultaneamente**:

- `start_exporter()` (recomendado): principal mecanismo para expor métricas Prometheus.
	- Habilitar: `MONITORING_EXPORTER_ENABLE=1`
	- Endereço: `MONITORING_EXPORTER_ADDR` (default `127.0.0.1`)
	- Porta: `MONITORING_EXPORTER_PORT` (default `8000`)

- Fallback HTTP server (`run_http_server`): expõe `/health` e um fallback `/metrics`, e executa o worker de envio de logs (Promtail heartbeat). Use apenas quando necessário.
	- Habilitar: `MONITORING_HTTP_ENABLE=1`
	- Endereço: `MONITORING_HTTP_ADDR` (default `127.0.0.1`)
	- Porta: `MONITORING_HTTP_PORT` (default `8000`)

Recomendações:
- Prefira `MONITORING_EXPORTER_ENABLE=1` (se `prometheus_client` estiver instalado, o servidor oficial será usado).
- Se usar o fallback HTTP (`MONITORING_HTTP_ENABLE=1`), desative o exporter ou garanta que apenas um serviço esteja escutando na porta escolhida.
- Por padrão o código tenta evitar inicialização duplicada: o processo verifica se o exporter já iniciou um servidor e, nesse caso, não inicializa o fallback.

Variável de teste/execução síncrona do pós-tratamento:
- `POST_TREATMENT_SYNC=1` — força a execução síncrona do worker de post-treatment (útil em testes). Por padrão está desabilitada para evitar duplicação de trabalho em operação normal.

## Troubleshooting breve

- Se `/metrics` não aparecer: verificar `MONITORING_EXPORTER_ENABLE` e `MONITORING_EXPORTER_PORT`.
- Permissões de rede/portas podem bloquear o binding; escolha `127.0.0.1` para testes locais.
- Em containers, `psutil` coleta o contexto do container — use `node_exporter` para métricas do host.

## Notas
- Paths importantes: `logs/json/`, `docs/prints/` (artefatos visuais).
- Windows vs Unix: comandos de export/definição de variáveis diferem (veja exemplos acima).
