total = 2000
import json
import random
from datetime import datetime, timedelta

# Parâmetros
TOTAL = 2000
cpu_states = (["CRITICAL"] * 77) + (["WARNING"] * 574) + (["STABLE"] * (TOTAL - 77 - 574))
ram_states = (["CRITICAL"] * 12) + (["WARNING"] * 1200) + (["STABLE"] * (TOTAL - 12 - 1200))
disk_states = ["WARNING"] * TOTAL
other_state = "STABLE"

random.shuffle(cpu_states)
random.shuffle(ram_states)

base_time = datetime(2025, 10, 12, 19, 0, 0)

with open("logs/json/monitoring-2025-10-12.jsonl", "w", encoding="utf-8") as f:
    for i in range(TOTAL):
        ts = base_time + timedelta(seconds=i)
        cpu = random.uniform(0, 100)
        ram = random.uniform(0, 100)
        disk = random.uniform(0, 100)
        ping = random.uniform(1, 20)
        lat = random.uniform(1, 20)
        state_cpu = cpu_states[i]
        state_ram = ram_states[i]
        state_disk = disk_states[i]
        # Estado global: prioriza critical > warning > stable
        if "CRITICAL" in (state_cpu, state_ram):
            global_state = "CRITICAL"
        elif "WARNING" in (state_cpu, state_ram, state_disk):
            global_state = "WARNING"
        else:
            global_state = "STABLE"
        metrics = {
            "cpu_percent": cpu,
            "cpu_freq_ghz": round(random.uniform(2.0, 4.0), 1),
            "memory_percent": ram,
            "disk_percent": disk,
            "memory_used_bytes": int(ram / 100 * 25094406144),
            "memory_total_bytes": 25094406144,
            "bytes_sent": random.uniform(1e6, 1e9),
            "bytes_recv": random.uniform(1e6, 1e9),
            "ping_ms": ping,
            "latency_ms": lat,
            "latency_method": "tcp",
            "latency_estimated": False,
            "temperature": None,
            "timestamp": ts.timestamp(),
            "disk_used_bytes": int(disk / 100 * 495912480768),
            "disk_total_bytes": 495912480768,
        }
        summary_short = f"CPU {metrics['cpu_freq_ghz']}GHz • {int(cpu)}% | RAM {int(ram)}% | Ping {int(ping)} ms | Disco {int(disk)}%"
        summary_long = [
            f"CPU: {metrics['cpu_freq_ghz']}GHz • {int(cpu)}%",
            f"RAM: {metrics['memory_used_bytes'] // (1024**3)} / {metrics['memory_total_bytes'] // (1024**3)} GB • {int(ram)}%",
            f"Disco: {metrics['disk_used_bytes'] // (1024**3)} / {metrics['disk_total_bytes'] // (1024**3)} GB • {int(disk)}%",
            f"Ping: {int(ping)}.0 ms",
            f"Latência: {int(lat)}.0 ms",
            "Temperatura: Indisponivel",
            f"Bytes enviados: {metrics['bytes_sent'] / (1024**3):.2f} GB",
            f"Bytes recebidos: {metrics['bytes_recv'] / (1024**3):.2f} GB",
            f"Data/hora: {ts.strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        entry = {
            "ts": ts.isoformat() + "+00:00",
            "level": "INFO",
            "msg": summary_short,
            "state": global_state,
            "timestamp": ts.isoformat() + "+00:00",
            "metrics": metrics,
            "summary_short": summary_short,
            "summary_long": summary_long,
        }
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
