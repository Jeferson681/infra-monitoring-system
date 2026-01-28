# Como Rodar (resumo)

Objetivo: instruções concisas para iniciar o projeto localmente (venv) e com Docker, além de verificações rápidas.

## Pré-requisitos
- Python 3.8+ instalado
- `docker` e `docker-compose` (opcional, para fluxo com containers)
 - `pre-commit` (recomendado) — para executar hooks de qualidade e segurança
 - `hadolint` (opcional) — `hadolint` is executed in CI during image scans. To run it locally use the `hadolint/hadolint` Docker image or install `hadolint` natively.

## Execução local (resumo)

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

3) Exemplos de execução

Observações:
- O arquivo `./.env` presente na raiz contém defaults (ex.: `MONITORING_EXPORTER_ADDR=127.0.0.1`). O entrypoint `src.main` tenta ler esse arquivo automaticamente e só define variáveis que não estejam presentes no ambiente do processo (conveniência para desenvolvimento local). Se preferir controlar o ambiente externamente, carregue o `.env` no shell antes de executar.

PowerShell — carregar `.env` e executar (útil para testes locais):

```powershell
Get-Content .env | ForEach-Object {
	if ($_ -and $_ -notmatch '^\s*#') {
		$p = $_ -split '=',2
		if ($p.Length -eq 2) { [Environment]::SetEnvironmentVariable($p[0].Trim(), $p[1].Trim(), 'Process') }
	}
}
& .\.venv\Scripts\python.exe -u -m src.main -c 0 -i 1 -vv
```

Exemplo mínimo (ligar exporter e servidor HTTP apenas localmente):

```powershell
$env:MONITORING_EXPORTER_ENABLE = '1'
$env:MONITORING_HTTP_ENABLE = '1'
# MONITORING_HTTP_ADDR não definido -> default é 127.0.0.1
& .\.venv\Scripts\python.exe -u -m src.main -c 0 -i 1 -vv
```

Expor em todas as interfaces do host (cuidado — exposição externa):

```powershell
$env:MONITORING_EXPORTER_ENABLE = '1'
$env:MONITORING_HTTP_ENABLE = '1'
$env:MONITORING_HTTP_ADDR = '0.0.0.0'  # Risco: permite acesso externo se porta for publicada
& .\.venv\Scripts\python.exe -u -m src.main -c 0 -i 1 -vv
```

## Execução com Docker / docker-compose

O `docker-compose.yml` já contém serviços para `prometheus`, `grafana`, `loki`, `promtail` e o serviço da aplicação. Por padrão o compose define `MONITORING_HTTP_ADDR=0.0.0.0` no serviço da aplicação, mas **não publica portas para o host** — isto significa:

- Prometheus (no mesmo compose) consegue raspá‑lo via rede do compose: `http://infra-monitoring-system_app:8000/metrics`.
- O serviço NÃO estará acessível do host/externo a menos que você adicione um `ports:` mapping (ex.: `"8000:8000"`).

Iniciar compose (na raiz do projeto):

```bash
docker compose up --build -d
```

Endpoints comuns quando portas são publicadas:
- Prometheus → http://localhost:9090
- Grafana → http://localhost:3000
- Loki → http://localhost:3100
- Exporter → http://localhost:8000/metrics (somente se `ports:` estiver configurado)

Nota sobre compose: o `docker-compose.yml` inclui um serviço `main_http` que executa `src.exporter.main_http`; por isso o `observability/prometheus.yml` é configurado para raspar `main_http:8000`. O serviço da aplicação (`infra-monitoring-system`) pode iniciar o servidor HTTP de métricas quando `MONITORING_HTTP_ENABLE=1`, mas no compose padrão o servidor de métricas é servido por `main_http` para separar responsabilidades.

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

### Pre-commit

Rodar todos os hooks locais:

```powershell
python -m pip install --upgrade pip
python -m pip install pre-commit
pre-commit run --all-files
```

Nota: `hadolint` é executado no CI durante os scans de imagem. Para executá-lo localmente sem instalá-lo, execute:

```powershell
docker run --rm -v "${PWD}":/data -w /data hadolint/hadolint:latest hadolint Dockerfile
```

Ou instale `hadolint` nativamente e rode `hadolint Dockerfile`.

## Variáveis de ambiente (exposição de métricas e runtime)

Principais variáveis que afetam exposição e execução:

- `MONITORING_EXPORTER_ENABLE` (0|1) — inicializa/registrador das métricas (chama `start_exporter()`); *não* inicia um servidor HTTP por si só após o refactor.
- `MONITORING_EXPORTER_ADDR`, `MONITORING_EXPORTER_PORT` — defaults e metadata (ex.: `.env` define `127.0.0.1`/8000).
- `MONITORING_HTTP_ENABLE` (0|1) — inicia o fallback HTTP server que expõe `/metrics` e `/health` (controlado em `src/exporter/main_http.py`).

	Observação: o entrypoint principal (`src/main.py`) verifica a variável de ambiente `MONITORING_HTTP_ENABLE` em tempo de execução e, quando definida para `1`, inicia o servidor HTTP de fallback chamando o handler em `src.exporter.main_http`.
- `MONITORING_HTTP_ADDR`, `MONITORING_HTTP_PORT` — bind do fallback HTTP server. Default local: `127.0.0.1`. Orquestradores podem usar `0.0.0.0` dentro de containers para permitir raspagem por outros serviços.
- `MONITORING_PROMTAIL_ENABLE` (0|1) — inicia o worker interno que envia heartbeats diretamente ao Loki (complementar ao serviço `promtail` do compose).
- `MONITORING_INTERVAL_SEC`, `MONITORING_CYCLES` — controle de intervalo e tempo de execução; também podem ser definidos via CLI (`-i`, `-c`) — CLI tem precedência sobre env.

Boas práticas e recomendações:

- Mantenha default do app em `127.0.0.1` para execuções locais.
- Em `docker-compose`, use `MONITORING_HTTP_ADDR=0.0.0.0` **sem** publicar portas (`ports:`) para limitar exposição ao escopo do compose (outros containers), não ao host.
- Só publique portas no `docker-compose.yml` se precisar acessar `/metrics` a partir do host; se publicar, proteja com firewall/proxy/TLS se necessário.
- Para evitar diferenças de runtime entre serviços, padronize a imagem base Python usada em `docker-compose` (ex.: `python:3.13-slim`).
- Para CI: adicione checks de segurança (Trivy) e linting de Dockerfile (hadolint) para detectar regressões de segurança e estilo.
- Para testes que precisam que o post-treatment seja síncrono, use `POST_TREATMENT_SYNC=1`.

## Troubleshooting breve

- Se `/metrics` não aparecer: verificar `MONITORING_EXPORTER_ENABLE` e `MONITORING_EXPORTER_PORT`.
- Permissões de rede/portas podem bloquear o binding; escolha `127.0.0.1` para testes locais.
- Em containers, `psutil` coleta o contexto do container — use `node_exporter` para métricas do host.

## Notas
- Paths importantes: `logs/json/`, `docs/prints/` (artefatos visuais).
- Windows vs Unix: comandos de export/definição de variáveis diferem (veja exemplos acima).
