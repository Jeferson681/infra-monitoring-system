2025-10-10 - ETAPA 6 (state.py validation)

- Mudanças:
  - Adicionado `_lock: Lock` e `self._lock = Lock()` em `SystemState.__init__`.
  - Protegidos trechos críticos com `with self._lock` em `_update_snapshots`, `_activate_treatment` (guard set), `_record_post_treatment_snapshot`, `normalize_for_display`, e `reset`.
  - Garantido que `_activate_treatment` disparará o worker fora do lock para evitar deadlocks.
- Motivação: evitar condições de corrida entre o loop principal (que chama `evaluate_metrics`) e o worker de pós-tratamento.
- Testes: `tests/monitoring/test_state.py` passou.
- Pendências:
  - Revisar e decidir tratamento para avisos do bandit (B110) em blocos `try/except/pass` intencionais.
  - Ação tomada: adicionado `# nosec B110` em blocos intencionais em `src/monitoring/state.py` com comentário explicativo. Outros avisos em `system/helpers.py` e `system/log_helpers.py` permanecem para revisão futura.
  - Opcional: adicionar documentação em `copilot_instructions.md` sobre por que alguns `try/except/pass` são aceitáveis.
