"""Emissor de snapshots extraído de `core`.

Contém a formatação da mensagem humana, impressão curta/longa e a rotina
de escrita/emitção para o subsistema de logs. Mantido em módulo separado
para reduzir responsabilidades do `core` e facilitar testes.
"""

import logging
from ..monitoring.formatters import normalize_for_display, format_snapshot_human
from ..system.logs import write_log

_NO_DATA_STR = "Sem dados"


def _format_human_msg(snapshot: dict | None, result: dict) -> str:
    """Format a human-readable message from snapshot/result.

    Delegates to centralized formatter when possible and falls back to a
    minimal representation on error.
    """
    try:
        return format_snapshot_human(snapshot, result)
    except Exception:
        return f"state={result.get('state')}"


def _print_snapshot_short(snap: dict | None) -> None:
    """Print a short summary of the snapshot to stdout.

    Prints a default message when snapshot is not available.
    """
    if not isinstance(snap, dict):
        print(_NO_DATA_STR)
        return

    summary_short = snap.get("summary_short")
    if summary_short:
        print(summary_short)
        return

    metrics = snap.get("metrics")
    if isinstance(metrics, dict):
        nf = normalize_for_display(metrics)
        print(nf.get("summary_short") or _NO_DATA_STR)
        return

    print(_NO_DATA_STR)


def _print_snapshot_long(snap: dict | None) -> None:
    """Print a long multi-line snapshot to stdout.

    Falls back to a metric-derived long summary when explicit summary is
    not present.
    """
    if not isinstance(snap, dict):
        print("SNAPSHOT: Sem dados")
        return

    summary_long = snap.get("summary_long")
    if summary_long and isinstance(summary_long, list):
        for line in summary_long:
            print(line)
        return

    metrics = snap.get("metrics")
    if isinstance(metrics, dict):
        nf = normalize_for_display(metrics)
        long_lines = nf.get("summary_long") or []
        if isinstance(long_lines, list) and long_lines:
            for line in long_lines:
                print(line)
            return

    print("SNAPSHOT:", snap)


def emit_snapshot(snapshot: dict | None, result: dict, verbose_level: int) -> None:
    """Emit a snapshot to logging subsystem and optionally to stdout.

    - writes JSON canonical feed for ingestion
    - if verbose_level > 0, prints human readable short/long output
    """
    logger = logging.getLogger(__name__)

    try:
        human_msg = _format_human_msg(snapshot, result)
        try:
            # Write only JSON for the canonical monitoring feed here.
            write_log("monitoring", "INFO", human_msg, extra=snapshot, human_enable=False, json_enable=True)
        except Exception as exc:
            logger.info("Falha ao escrever log via write_log: %s", exc)
    except Exception:
        logger.info("Falha ao construir/emitir snapshot", exc_info=True)

    if not verbose_level:
        return

    if verbose_level == 1:
        _print_snapshot_short(snapshot)
    else:
        _print_snapshot_long(snapshot)
