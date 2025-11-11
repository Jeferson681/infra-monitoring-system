"""Emissor de snapshots extraído de `core`.

Contém a formatação da mensagem humana, impressão curta/longa e a rotina
de escrita/emitção para o subsistema de logs. Mantido em módulo separado
para reduzir responsabilidades do `core` e facilitar testes.
"""

import logging

# ruff: noqa: D401
from ..monitoring.formatters import normalize_for_display, format_snapshot_human
from ..system.logs import write_log

_NO_DATA_STR = "Sem dados"


def _format_human_msg(snapshot: dict | None, result: dict) -> str:  # noqa: D401
    """Formate uma mensagem legível por humanos a partir do snapshot/result.

    Delegará para o formatador centralizado quando possível e, em caso de
    erro, retorna uma representação mínima.
    """
    try:
        return format_snapshot_human(snapshot, result)
    except Exception:
        return f"state={result.get('state')}"


def _print_snapshot_short(snap: dict | None) -> None:  # noqa: D401
    """Imprima um resumo curto do snapshot no stdout.

    Imprime uma mensagem padrão quando o snapshot não estiver disponível.
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


def _print_snapshot_long(snap: dict | None) -> None:  # noqa: D401
    """Imprima um snapshot longo multilinha no stdout.

    Em falta de sumário explícito, tenta derivar um resumo longo a partir das métricas.
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


def emit_snapshot(snapshot: dict | None, result: dict, verbose_level: int) -> None:  # noqa: D401
    """Emita um snapshot para o subsistema de logs e opcionalmente para stdout.

    - escreve o feed JSON canônico para ingestão
    - se verbose_level > 0, imprime saída humana (curta/longa)
    """
    logger = logging.getLogger(__name__)

    try:
        human_msg = _format_human_msg(snapshot, result)
        try:
            # Escreve apenas JSON para o feed canônico de monitoring.
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
