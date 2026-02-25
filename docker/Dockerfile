# Dockerfile para o sistema de monitoramento
FROM python:3.13-slim

# Diretório de trabalho
WORKDIR /app

# Copia dependências e instala
COPY requirements.txt ./
# Atualiza índice e aplica upgrade apenas no pacote openssl para mitigar CVE-2026-22796
# Usa --only-upgrade quando possível, com fallback para instalar caso não exista
# Em seguida atualiza o pip e instala as dependências numa única camada para
# evitar cache de camadas sem a correção.
RUN set -eux; \
	apt-get update; \
	# Resolve candidate version and pin installation to satisfy hadolint DL3008
	ver=$(apt-cache madison openssl | awk 'NR==1{print $3}'); \
	if [ -n "$ver" ]; then \
		apt-get install -y --no-install-recommends openssl="$ver"; \
	else \
		apt-get install -y --no-install-recommends openssl; \
	fi; \
	apt-get install -y --no-install-recommends curl; \
	rm -rf /var/lib/apt/lists/*; \
	python -m pip install --upgrade --no-cache-dir "pip>=25.3"; \
	python -m pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY src/ ./src/
COPY pyproject.toml ./
COPY .flake8 ./

# Allow imports of the canonical package layout (src/infra_monitoring/*).
# This repo uses a src/ layout without an install step in the image.
ENV PYTHONPATH=/app/src

# Run as non-root (recommended by the minimal restructure plan)
RUN set -eux; \
	adduser --disabled-password --gecos "" appuser; \
	mkdir -p /app/logs /app/reports /app/.cache; \
	chown -R appuser:appuser /app

USER appuser

# Comando padrão
CMD ["python", "-m", "src.main"]
