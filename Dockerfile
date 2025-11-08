# Dockerfile para o sistema de monitoramento
FROM python:3.13-slim

# Diretório de trabalho
WORKDIR /app

# Copia dependências e instala
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# Corrige vulnerabilidade do pip (CVE-2025-8869)
RUN pip install --upgrade pip>=25.3
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY src/ ./src/
COPY pyproject.toml ./
COPY .flake8 ./

# Comando padrão
CMD ["python", "-m", "src.main"]
