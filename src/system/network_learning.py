import json
import datetime
from pathlib import Path


class NetworkUsageLearningHandler:
    """Handler para aprendizagem e ajuste dinâmico do limite de consumo de rede."""

    def __init__(self, date_func=None):
        """Inicializa o handler de aprendizagem de rede.

        Parâmetros:
            date_func: Função para obter a data atual (default: datetime.date.today).
        """
        self.date_func = date_func or (lambda: datetime.date.today())

    """Handler para aprendizagem e ajuste dinâmico do limite de consumo de rede.

    Coleta consumo diário de bytes enviados/recebidos.
    Calcula média mensal após 4 semanas.
    Atualiza limite com margem (ex: 20%).
    Persiste dados em arquivo.
    """
    LEARNING_FILE = Path(".cache/network_usage_learning_safe.jsonl")
    LEARNING_WEEKS = 4
    DEFAULT_LIMIT = 20 * 1024**3  # 20GB
    MARGIN = 0.2  # 20%

    def record_daily_usage(self, bytes_sent: int, bytes_recv: int):
        """Registra o consumo diário de bytes enviados e recebidos, persistindo em .jsonl.

        Sempre sobrescreve a linha do dia atual, evitando duplicidade.
        Adiciona campo timestamp preciso.
        """
        today = self.date_func()
        now_dt = datetime.datetime.now().isoformat()
        entry = {"bytes_sent": bytes_sent, "bytes_recv": bytes_recv, "date": today.isoformat(), "timestamp": now_dt}
        from src.system.helpers import ensure_cache_dir_exists

        ensure_cache_dir_exists()
        # Carrega todas as entradas existentes
        from src.system.helpers import read_jsonl

        entries = read_jsonl(self.LEARNING_FILE)
        # Remove qualquer entrada do mesmo dia
        entries = [e for e in entries if e.get("date") != today.isoformat()]
        # Adiciona a entrada atual
        entries.append(entry)
        # Salva todas as entradas, uma por linha
        with self.LEARNING_FILE.open("w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def calculate_weekly_limit(self) -> int:
        """Calcula o limite semanal adaptativo (+20%) baseado apenas na soma da última semana.

        Returns
        -------
        int
            Limite calculado em bytes.

        """
        # Soma sempre os últimos 7 dias completos
        data = self._load_data()
        # Ordena por data decrescente
        valid_entries = [e for e in data if "bytes_sent" in e and "bytes_recv" in e and "date" in e]
        valid_entries.sort(key=lambda e: e["date"], reverse=True)
        last_7 = valid_entries[:7]
        if not last_7:
            return self.DEFAULT_LIMIT
        total = sum(e["bytes_sent"] + e["bytes_recv"] for e in last_7)
        limit = int(total * (1 + self.MARGIN))
        return limit

    def reset_learning_cycle(self):
        """Reinicia o ciclo de aprendizagem (após estipular novo limite)."""
        self._save_data({})

    def _load_data(self):
        from src.system.helpers import read_jsonl

        entries = read_jsonl(self.LEARNING_FILE)
        # Fallback: tentar ler do jsonl de monitoramento se não houver dados suficientes
        if not entries or len(entries) < self.LEARNING_WEEKS * 7:
            monitor_path = Path("logs/json/monitoring-{}.jsonl".format(datetime.date.today().strftime("%Y-%m-%d")))
            entries += read_jsonl(monitor_path)
        return entries

    def _save_data(self, data):
        from src.system.helpers import ensure_cache_dir_exists

        ensure_cache_dir_exists()
        with self.LEARNING_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f)

    def get_current_limit(self) -> int:
        """Retorna o limite semanal atual para consulta por tratamentos."""
        return self.calculate_weekly_limit()


# Exemplo de uso:
# handler = NetworkUsageLearningHandler()
# handler.record_daily_usage(bytes_sent, bytes_recv)
# limit = handler.get_current_limit()
# if consumo > limit: ...
