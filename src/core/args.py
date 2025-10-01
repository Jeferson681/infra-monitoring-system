"""Parser de argumentos (console vs UI).

Docstrings em português.
"""


def parse_args(argv: list[str] | None = None) -> None:
    """Parse command-line or UI arguments and return a config dict."""
    pass


def validate_args(args: dict) -> None:
    """Validate parsed arguments."""
    pass


def configure_argparser() -> None:
    """Configura o parser de argumentos com opções padrão do programa.

    Inclui opções de logging, verbosidade, intervalo e ciclos.
    """
    pass


def add_logging_args(parser) -> None:
    """Adiciona argumentos relacionados a logging (-l / --log, --logpath)."""
    pass


def add_verbosity_args(parser) -> None:
    """Adiciona argumentos de verbosidade (-v, -vv)."""
    pass


def add_interval_args(parser) -> None:
    """Adiciona argumento de intervalo (-i / --interval)."""
    pass


def add_cycle_args(parser) -> None:
    """Adiciona argumento de ciclos (-c / --cycle)."""
    pass


def get_log_config(args) -> None:
    """Gera configuração de logging (nível, path) a partir dos args."""
    pass
