"""Ponto de entrada do programa de monitorização.

Este módulo realiza a inicialização da aplicação: parsing de argumentos CLI,
configuração de logging, instalação de handlers de debug e inicialização do
loop principal de monitorização. Mantemos a lógica de runtime em `core` para
facilitar testes e reutilização.
"""

from .core.args import parse_args, get_log_config
import logging as _logging
import sys
from .system.logs import get_debug_file_path
from .core.core import run_loop
import os

# Usa helper de averages para garantir existência do estado hourly/.cache
from .monitoring.averages import ensure_default_last_ts

import json as _json


def main(argv: list[str] | None = None) -> None:
    """Inicializa a aplicação e inicia o loop principal.

    Args:
        argv: Lista de argumentos (usada em testes). Quando ``None`` a função
            utiliza os argumentos de linha de comando do processo.

    Returns:
        None

    """
    # Comportamento de argumentos:
    # - Se argv for None -> usa os argumentos do processo (sys.argv via argparse)
    # - Se argv for lista vazia (chamadas de teste), aplica defaults locais
    if argv is None:
        args = parse_args(None)
    else:
        if isinstance(argv, list) and len(argv) == 0:
            argv = ["-i", "1", "-c", "0"]
        args = parse_args(argv)
    log_conf = get_log_config(args)

    level = getattr(_logging, log_conf.get("level", "WARNING"), _logging.WARNING)
    _logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        _setup_debug_file_handler()
    except Exception as exc:
        _logging.getLogger(__name__).debug("falha ao configurar debug file handler: %s", exc, exc_info=True)

    # Garantir arquivo de controle (.cache/last_ts.json) antes de iniciar o loop.
    # Erros aqui são não-fatais e são registrados em debug para diagnóstico.
    try:
        ensure_default_last_ts()
    except Exception:
        _logging.getLogger(__name__).debug("falha ao garantir arquivo de controle no startup", exc_info=True)
    # Optionally start Prometheus exporter if enabled via env
    try:
        from .exporter.prometheus import start_exporter

        if os.getenv("MONITORING_EXPORTER_ENABLE", "0") in ("1", "true", "yes"):
            try:
                start_exporter()
            except Exception:
                _logging.getLogger(__name__).debug("falha ao iniciar exporter Prometheus", exc_info=True)
    except Exception:
        _logging.getLogger(__name__).debug("exporter não disponível", exc_info=True)

    # Inicia o servidor HTTP de métricas em thread separada
    try:
        from src.exporter.main_http import run_http_server
        import threading

        port = int(os.getenv("MONITORING_HTTP_PORT", "8000"))
        http_thread = threading.Thread(target=run_http_server, kwargs={"addr": "0.0.0.0", "port": port}, daemon=True)
        http_thread.start()
    except Exception as exc:
        _logging.getLogger(__name__).warning("Falha ao iniciar servidor HTTP de métricas: %s", exc, exc_info=True)

    run_loop(interval=args.interval, cycles=args.cycles, verbose_level=getattr(args, "verbose", 0) or 0)


def _setup_debug_file_handler() -> None:
    """Instala handlers de ficheiro para debug e hook global de exceções.

    Esta função adiciona dois handlers ao logger root: um human-readable
    (texto) e um JSONL (uma linha de JSON por evento) para ingestão. Ambos os
    handlers são configurados em modo "best-effort": qualquer falha na escrita
    do handler é capturada para evitar que logging provoque falhas na
    aplicação. Também instala um ``sys.excepthook`` que envia exceções
    não tratadas para o logger root.

    Comportamento notável:
    - Evita duplicar handlers se já existirem handlers de ficheiro com os
      mesmos caminhos.
    - Substitui dinamicamente o método ``emit`` do handler por uma versão
      segura que suprime exceções do próprio handler (intencional).
    """
    debug_path = get_debug_file_path()

    # Handler texto (legível por humanos)
    fh = _logging.FileHandler(str(debug_path), encoding="utf-8")
    fh.setLevel(_logging.INFO)
    fmt = _logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh.setFormatter(fmt)

    jpath = debug_path.with_suffix(".jsonl")
    jfh = _logging.FileHandler(str(jpath), encoding="utf-8")
    jfh.setLevel(_logging.INFO)
    jfh.setFormatter(_get_json_formatter())

    root = _logging.getLogger()
    if not _has_existing_file_handler(root, fh, jfh):
        _wrap_emit_safe(fh)
        _wrap_emit_safe(jfh)
        root.addHandler(fh)
        root.addHandler(jfh)

    def _exc_hook(exc_type, exc_value, exc_tb):
        try:
            root.error("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
        except Exception:
            sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _exc_hook


# Auxiliares extraídas para reduzir complexidade


def _get_json_formatter():
    class _JSONFormatter(_logging.Formatter):
        def format(self, record):
            try:
                ts = self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                ts = ""
            obj = {
                "ts": ts,
                "level": record.levelname,
                "name": record.name,
                "msg": record.getMessage(),
            }
            if record.exc_info:
                try:
                    import traceback as _tb

                    obj["exc"] = "".join(_tb.format_exception(*record.exc_info))
                except Exception:
                    _logging.getLogger(__name__).warning("Falha ao formatar exc_info para JSON", exc_info=True)
            return _json.dumps(obj, ensure_ascii=False)

    return _JSONFormatter()


def _has_existing_file_handler(root, fh, jfh):
    try:
        bases = (getattr(fh, "baseFilename", None), getattr(jfh, "baseFilename", None))
        for h in root.handlers:
            if isinstance(h, _logging.FileHandler):
                if getattr(h, "baseFilename", None) in bases:
                    return True
    except Exception:
        _logging.getLogger(__name__).exception("erro inspeccionando handler")
    return False


def _wrap_emit_safe(handler):
    import types as _types

    orig = handler.emit

    def _emit_safe(self, record):
        try:
            return orig(record)
        except Exception:
            try:
                _logging.getLogger(__name__).warning("debug handler emit failed", exc_info=True)
            except Exception:
                _logging.getLogger(__name__).info("Falha ao registrar falha do handler de debug (emit)", exc_info=True)

    handler.emit = _types.MethodType(_emit_safe, handler)  # type: ignore[assignment]


# Observação: anteriormente `_maybe_start_exporter` estava neste módulo como
# um wrapper fino. Preferimos chamar `start_exporter` diretamente em `main`
# para evitar indirection por wrappers.


if __name__ == "__main__":
    main()
