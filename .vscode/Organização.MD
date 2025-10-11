# Organização — Preceitos de módulos

Este documento lista papéis (preceitos) comuns que um módulo de software pode assumir, com uma breve explicação do que cada um faz. Use isto como referência quando for reorganizar o projeto por responsabilidade única.

1. Escritor (writer)
   - O que faz: Persiste dados (arquivos, filas, bases de dados).
   - Entradas: objetos/str para gravar.
   - Saídas/efeitos: arquivo/registro gravado; possível retorno de sucesso/erro.

2. Leitor (reader)
   - O que faz: Lê dados persistidos e retorna estruturas em memória.
   - Entradas: caminho/handle/stream.
   - Saídas: dict/list/iteradores; erros em caso de formato inválido.

3. Coletor (collector)
   - O que faz: Consulta fontes externas (sensors, APIs, sistema) e produz métricas brutas.
   - Entradas: parâmetros de coleta (opcionais).
   - Saídas: dicionários com métricas.

4. Gerador (generator)
   - O que faz: Produz artefatos derivados (strings, relatórios, snapshots) a partir de dados.
   - Entradas: dados brutos/estruturados.
   - Saídas: payloads formatados, strings, arquivos temporários.

5. Calculador / Agregador (calculator / aggregator)
   - O que faz: Processa séries/ventos para produzir agregados (médias, contagens, janelas).
   - Entradas: listas/janelas de eventos.
   - Saídas: números/estatísticas/estruturas agregadas.

6. Validador (validator)
   - O que faz: Verifica conformidade dos dados (tipos, ranges, schemas).
   - Entradas: dados a validar.
   - Saídas: boolean/falhas detalhadas/exceções.

7. Normalizador / Sanitizador (normalizer / sanitizer)
   - O que faz: Converte dados para uma forma canónica, limpa/filtra campos impróprios.
   - Usado para: compatibilidade entre versões e segurança.

8. Serializador / Desserializador (serializer / deserializer)
   - O que faz: Converte objetos em bytes/strings (JSON, msgpack) e vice-versa.

9. Enriquecedor (enricher)
   - O que faz: Adiciona metadados ou valores derivados aos dados (geoip, lookup, tags).

10. Cache (cache/store)
	- O que faz: Armazena valores temporários para reduzir custo de operações repetidas.

11. Adaptador / Conector (adapter / connector)
	- O que faz: Tradução/ponte para APIs externas (DBs, filas, serviços).

12. Orquestrador / Coordenador (orchestrator / coordinator)
	- O que faz: Coordena várias partes do sistema, fluxos e dependências.

13. Agendador / Scheduler (scheduler)
	- O que faz: Dispara tarefas em intervalos ou em horários específicos.

14. Roteador / Dispatcher (router / dispatcher)
	- O que faz: Encaminha mensagens/requests para handlers apropriados.

15. Observador / Monitor (observer / monitor)
	- O que faz: Recolhe métricas de saúde, logs e expõe status.

16. Exportador / Integrador (exporter / integrator)
	- O que faz: Envia dados para sistemas externos (prometheus, cloud logs, APIs).

17. Importador / Ingest (importer / ingest)
	- O que faz: Consome e normaliza fluxos de entrada (files, streams) para o sistema.

18. Transformador (transformer)
	- O que faz: Converte formatos e transforma dados entre domínios.

19. Persistidor durável (persister)
	- O que faz: Persiste dados com garantias (fsync, transações) quando necessário.

20. Worker / Executor assíncrono (worker / executor)
	- O que faz: Executa tarefas em background ou em pools de threads/processos.

21. Reconciliador (reconciler)
	- O que faz: Garante que o estado atual converge para um estado desejado (ex.: re-apply config).

22. Health-check / Watchdog
	- O que faz: Verifica periódica de integridade e reinicia ou alerta quando necessário.

23. Migrador / Versionador (migrator / versioner)
	- O que faz: Transforma dados/DBs entre versões e aplica migrações.

24. Notificador / Alertador (notifier / alerter)
	- O que faz: Envia notificações/alertas (email, slack, webhooks).

25. Exportador de métricas para monitorização (metrics exporter)
	- O que faz: Expõe métricas em formato consumível por sistemas de monitorização.

---

Use essa lista para planejar a reorganização do código: agrupe funções com responsabilidades semelhantes em módulos claros (ex.: `collectors.py`, `formatters.py`, `persistence.py`, `workers.py`, `adapters/`), e exponha uma API curta por módulo.
