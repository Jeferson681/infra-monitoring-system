# Documentação do Projeto de Monitoramento

## Limitações e Observações Importantes

- **Separação de Containers:**
  - O projeto está estruturado para rodar dois containers principais:
    - `monitoring-app`: executa o monitoramento principal (main.py).
    - `monitoring-metrics`: executa o exporter HTTP/Promtail (main_http.py), responsável por expor métricas e enviar logs para Loki.
  - **Propósito Didático:** O container `monitoring-metrics` é destinado apenas para fins didáticos e demonstração de integração com Prometheus/Grafana/Loki. Ele não deve ser usado em produção para coleta de métricas físicas do host, pois pode afetar a precisão dos dados.
  - Para coleta real de métricas do host, recomenda-se rodar o exporter no mesmo ambiente do monitoramento principal ou integrar via volumes/API.

## Estrutura de Volumes e Logs
- Os containers compartilham o volume `/logs` para garantir que o Promtail possa ler e enviar todos os arquivos `.log` e `.json` (inclusive em subdiretórios) para o Loki.
- O arquivo de configuração Promtail (`infra/promtail/promtail-config.yml`) está preparado para ler todos os logs recursivamente.

## Integração com Observabilidade
- O projeto integra com Prometheus, Grafana e Loki via containers dedicados, conforme exemplos em `docker-compose.yml` e `infra/terraform/main.tf`.
- Recomenda-se revisar as variáveis de ambiente e volumes para garantir que os dados corretos estejam disponíveis para cada serviço.

## Recomendações de Uso
- Para ambientes produtivos, avalie cuidadosamente a arquitetura de containers e a integração entre monitoramento e exporter.
- Documente e versiona as configurações de observabilidade para facilitar manutenção e auditoria.

## Outros Dados e Informações
- Utilize este arquivo para registrar decisões de arquitetura, limitações conhecidas, recomendações de deploy, e quaisquer observações relevantes para o time ou usuários do projeto.
- Atualize este documento conforme novas integrações, mudanças de infraestrutura ou requisitos de negócio.

---

*Última atualização: 07/11/2025*
