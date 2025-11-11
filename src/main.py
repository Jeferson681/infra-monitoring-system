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

    # JSONL handler: linhas JSON por evento (útil para ingestores)
    import json as _json

    class _JSONFormatter(_logging.Formatter):
        def format(self, record):
            # Estrutura JSON básica: ts, level, name, msg
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
            # Inclui informação de exceção quando disponível
            if record.exc_info:
                try:
                    import traceback as _tb

                    # format_exception retorna uma lista de strings; juntamos em
                    # uma única string para compatibilidade com consumidores.
                    obj["exc"] = "".join(_tb.format_exception(*record.exc_info))
                except Exception:
                    # A formatação de exceção é de melhor esforço; ignoramos
                    # falhas para não comprometer a escrita do registo.
                    # nosec B110 - intenção explícita de silenciar erro por robustez
                    pass
            return _json.dumps(obj, ensure_ascii=False)

    jpath = debug_path.with_suffix(".jsonl")
    jfh = _logging.FileHandler(str(jpath), encoding="utf-8")
    jfh.setLevel(_logging.INFO)
    jfh.setFormatter(_JSONFormatter())

    root = _logging.getLogger()
    existing = False
    for h in root.handlers:
        try:
            if isinstance(h, _logging.FileHandler):
                bases = (getattr(fh, "baseFilename", None), getattr(jfh, "baseFilename", None))
                if getattr(h, "baseFilename", None) in bases:
                    existing = True
                    break
        except Exception:
            _logging.getLogger(__name__).exception("erro inspeccionando handler")

    if not existing:
        # Substitui emit para evitar que exceções do handler propaguem-se à
        # aplicação; handlers operam em modo de melhor esforço e não devem
        # causar a queda do processo.
        import types as _types

        def _wrap_emit(orig):
            def _emit_safe(self, record):
                try:
                    return orig(record)
                except Exception:
                    # Em modo de melhor esforço: registra falha do handler em
                    # nível debug e prossegue. Não queremos que um handler
                    # cause a queda da aplicação.
                    try:
                        _logging.getLogger(__name__).warning("debug handler emit failed", exc_info=True)
                    except Exception:
                        # nosec B110 - swallow intencional de último recurso
                        pass

            return _emit_safe

        # Vincula a implementação segura de emit às instâncias.
        # O mypy não consegue raciocinar facilmente sobre atribuições dinâmicas
        # de método em tempo de execução; isto é intencional.
        fh.emit = _types.MethodType(_wrap_emit(fh.emit), fh)  # type: ignore[assignment]
        jfh.emit = _types.MethodType(_wrap_emit(jfh.emit), jfh)  # type: ignore[assignment]

        root.addHandler(fh)
        root.addHandler(jfh)

    def _exc_hook(exc_type, exc_value, exc_tb):
        try:
            root.error("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
        except Exception:
            sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _exc_hook


# Observação: anteriormente `_maybe_start_exporter` estava neste módulo como
# um wrapper fino. Preferimos chamar `start_exporter` diretamente em `main`
# para evitar indirection por wrappers.


if __name__ == "__main__":
    main()
