````markdown
# Infra Monitoring System — Technical Documentation

## 1. Purpose & Context

This system was developed for educational purposes and to demonstrate best practices in monitoring, automation, and continuous integration.
Implements collection and exposition of enriched metrics and logs, integrating with leading observability tools: **Prometheus**, **Grafana**, and **Loki**.

... (conteúdo completo copiado para backup) ...

---

## Final Technical Note — `psutil` Collection Limit

The `psutil` module collects metrics only from the environment where the process is running.
In containers or isolated namespaces, these metrics represent only the container context, not the host system.

Thus, its use is suitable for local diagnostics or in-process monitoring.
For real observability, it is recommended to integrate **node_exporter** or **cadvisor**, ensuring access to host metrics without breaking isolation.

> **Future improvement:** include a dedicated intermediate agent for host collection, maintaining isolation and compatibility with distributed observability.

---

## CONTATOS

- Página pessoal: https://jeferson681.github.io/PAGE/
- Email: jefersonoliveiradesousa681@gmail.com
- LinkedIn: https://www.linkedin.com/in/jeferson-oliveira-de-sousa-ab8764164/

---

````
