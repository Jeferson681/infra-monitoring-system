"""Parser de argumentos (console vs UI).

Docstrings e mensagens em português.

Este módulo fornece um parser simples que expõe:
- intervalo entre coletas (-i / --interval)
- número de ciclos (-c / --cycles), 0 = infinito
- verbosidade (-v)
- opções de logging (nivel e caminho raiz)

As funções retornam objetos compatíveis com argparse.Namespace para
serem consumidos por `src.main`.

Nota: Ajusta sys.path automaticamente se necessário para evitar erros de importação
quando o programa é executado como script ou módulo.
"""

# Ajuste automático do sys.path para execução direta ou via -m
import sys
from pathlib import Path

if __name__ == "__main__" or (hasattr(sys, "_getframe") and sys._getframe(1).f_globals.get("__name__") == "__main__"):
    src_path = Path(__file__).resolve().parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

import argparse
from typing import Sequence

# ========================
# 0. Configuração do parser e argumentos padrão
# ========================


# Função principal do módulo; cria e retorna o ArgumentParser configurado
def configure_argparser() -> argparse.ArgumentParser:
    """Cria e retorna ArgumentParser configurado para o monitoramento."""
    parser = argparse.ArgumentParser(
        prog="monitoring",
        description="Programa de monitoramento: coletas, logs e tratamentos automáticos",
    )

    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=1.0,
        help="Intervalo em segundos entre coletas (float). Valor mínimo recomendado: 0.1",
    )
    parser.add_argument(
        "-c",
        "--cycles",
        type=int,
        default=1,
        help="Número de ciclos a executar (0 = infinito) ou tempo total em minutos se --cycle-mode=time.",
    )
    parser.add_argument(
        "--cycle-mode",
        choices=["cycles", "time"],
        default="cycles",
        help="Modo de execução: 'cycles' para número de ciclos, 'time' para tempo total em minutos.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Aumenta a verbosidade (-v, -vv)",
    )
    parser.add_argument(
        "--log-root",
        dest="log_root",
        type=str,
        default=None,
        help="Caminho raiz para os logs (substitui MONITORING_LOG_ROOT)",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        type=str,
        default=None,
        help="Nível de logging (DEBUG/INFO/WARNING/ERROR). Se ausente, definido por -v",
    )

    return parser


# ========================
# 1. Funções auxiliares para análise e validação de argumentos
# ========================


# Auxilia src.main; criado para analisar argv e validar argumentos
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Analisa argv e retorna Namespace validado para uso no programa."""
    import os

    parser = configure_argparser()
    ns = parser.parse_args(argv)
    # Se modo time, permite override via env
    if getattr(ns, "cycle_mode", "cycles") == "time":
        env_time = os.getenv("MONITORING_CYCLE_TIME_MIN")
        if env_time is not None:
            try:
                ns.cycles = int(env_time)
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    f"MONITORING_CYCLE_TIME_MIN inválido ('{env_time}'): {exc}. Usando valor do argumento."
                )
    validate_args(ns)
    return ns


# Auxilia parse_args; criado para garantir valores corretos e seguros
def validate_args(args: argparse.Namespace) -> None:
    """Valida e normaliza argumentos do programa de monitoramento."""
    if getattr(args, "interval", 1.0) is None:
        args.interval = 1.0
    try:
        args.interval = float(args.interval)
    except (TypeError, ValueError) as exc:
        # Mensagem para usuário em PT; mantém o nome técnico 'interval' em inglês
        raise ValueError("intervalo deve ser um número") from exc
    if args.interval < 0.0:
        raise ValueError("intervalo deve ser >= 0.0")

    try:
        args.cycles = int(args.cycles)
    except (TypeError, ValueError) as exc:
        raise ValueError("cycles/time deve ser um inteiro >= 0") from exc
    if args.cycles < 0:
        raise ValueError("cycles/time deve ser >= 0")


# ========================
# 2. Função auxiliar para configuração de logging
# ========================


# Auxilia src.main; criado para extrair configuração de logging dos argumentos
def get_log_config(args: argparse.Namespace) -> dict:
    """Retorna dict com configuração de logging ('level' e 'root') para o monitoramento."""
    if getattr(args, "log_level", None):
        level = str(args.log_level).upper()
    else:
        v = getattr(args, "verbose", 0) or 0
        if v >= 1:
            level = "INFO"
        else:
            level = "WARNING"

    return {"level": level, "root": getattr(args, "log_root", None)}
