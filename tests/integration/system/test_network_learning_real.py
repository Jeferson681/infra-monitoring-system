import datetime
from src.system.network_learning import NetworkUsageLearningHandler


def test_network_learning_real():
    """Teste real do aprendizado de uso de rede.

    Executa registro de bytes enviados/recebidos e valida persistência no jsonl.
    """
    handler = NetworkUsageLearningHandler()
    # Simula valores reais (exemplo: 1234567 enviados, 7654321 recebidos)
    bytes_sent = 1234567
    bytes_recv = 7654321
    handler.record_daily_usage(bytes_sent, bytes_recv)
    # Verifica se o arquivo foi criado e contém a entrada do dia
    today = datetime.date.today().isoformat()
    entries = []
    if handler.LEARNING_FILE.exists():
        with handler.LEARNING_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = __import__("json").loads(line)
                    entries.append(entry)
                except Exception:
                    continue
    found = any(
        e.get("date") == today and e.get("bytes_sent") == bytes_sent and e.get("bytes_recv") == bytes_recv
        for e in entries
    )
    assert found, f"Entrada de hoje não encontrada no jsonl: {handler.LEARNING_FILE}"
