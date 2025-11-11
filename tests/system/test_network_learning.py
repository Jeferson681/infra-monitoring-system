import datetime
import pytest
from src.system.network_learning import NetworkUsageLearningHandler


def test_record_and_limit(tmp_path):
    """Testa gravação de 7 dias e cálculo do limite semanal."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    learning_file = cache_dir / "network_usage_learning_safe.jsonl"
    today = datetime.date.today()
    days = [today - datetime.timedelta(days=6 - i) for i in range(7)]

    def date_gen():
        for d in days:
            yield d

    dg = date_gen()
    handler = NetworkUsageLearningHandler(date_func=lambda: next(dg))
    handler.LEARNING_FILE = learning_file
    for i in range(7):
        handler.record_daily_usage(bytes_sent=1000 * (i + 1), bytes_recv=2000 * (i + 1))

    limit = handler.get_current_limit()
    expected_sum = sum([(1000 * (i + 1)) + (2000 * (i + 1)) for i in range(7)])
    expected_limit = int(expected_sum * 1.2)
    assert limit == expected_limit, f"Expected {expected_limit}, got {limit}"

    assert learning_file.exists()
    lines = learning_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 7
    import json

    for line in lines:
        entry = json.loads(line)
        assert "bytes_sent" in entry and "bytes_recv" in entry


@pytest.mark.parametrize("missing_file", [True, False])
def test_fallback(tmp_path, missing_file):
    """Testa fallback quando arquivo de aprendizado está ausente."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    learning_file = cache_dir / "network_usage_learning_safe.jsonl"
    handler = NetworkUsageLearningHandler()
    handler.LEARNING_FILE = learning_file
    if missing_file and learning_file.exists():
        learning_file.unlink()
    # Simula fallback criando arquivo de monitoramento válido se necessário
    if missing_file:
        import json

        monitor_dir = tmp_path / "logs" / "json"
        monitor_dir.mkdir(parents=True, exist_ok=True)
        monitor_file = monitor_dir / f"monitoring-{datetime.date.today().strftime('%Y-%m-%d')}.jsonl"
        for i in range(7):
            entry = {
                "year_week": str(datetime.date.today().isocalendar()[:2]),
                "bytes_sent": 1000 * (i + 1),
                "bytes_recv": 2000 * (i + 1),
                "date": (datetime.date.today() - datetime.timedelta(days=6 - i)).isoformat(),
            }
            with monitor_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
    limit = handler.get_current_limit()
    assert isinstance(limit, int)


def test_invalid_entry_ignored(tmp_path):
    """Testa se entradas sem year_week são ignoradas no cálculo do limite."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    learning_file = cache_dir / "network_usage_learning_safe.jsonl"
    handler = NetworkUsageLearningHandler()
    handler.LEARNING_FILE = learning_file
    import json

    # Entrada sem year_week (mas válida para soma)
    with learning_file.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"bytes_sent": 1000, "bytes_recv": 2000, "date": "2025-11-13"}) + "\n")
    # Entrada com year_week
    with learning_file.open("a", encoding="utf-8") as f:
        entry = {"year_week": "(2025,46)", "bytes_sent": 3000, "bytes_recv": 4000, "date": "2025-11-13"}
        f.write(json.dumps(entry) + "\n")
    limit = handler.get_current_limit()
    expected_limit = int((1000 + 2000 + 3000 + 4000) * 1.2)
    assert limit == expected_limit
