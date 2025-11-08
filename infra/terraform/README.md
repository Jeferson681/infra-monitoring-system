# Exemplos de Terraform — Conteúdo Educacional

Esta pasta contém arquivos de exemplo de Terraform usados apenas para demonstração e aprendizado.

Notas importantes:

- Estes exemplos NÃO devem ser executados em ambientes de produção.
- Não execute os scripts Terraform em contas reais sem revisar e adaptar conforme necessário.
- Os exemplos referenciam recursos mínimos para demonstração e não incluem configurações avançadas como estado remoto seguro, reforço de IAM ou boas práticas de rede.

Recomendações para revisores/aprendizes:

- Leia este arquivo com atenção antes de rodar qualquer comando Terraform.
- Para validar a sintaxe localmente, execute:

```sh
cd infra/terraform
terraform init -backend=false
terraform validate
```

- Se quiser testar o provisionamento, utilize uma conta de teste descartável e habilite backend seguro (S3/remote state) antes de aplicar.

Este diretório demonstra padrões básicos de IaC para o projeto e é mantido para fins educacionais e demonstração técnica.

---

## Observação sobre métricas

Este projeto coleta métricas do host usando a biblioteca psutil (CPU, RAM, disco, etc.).
Quando executado em ambientes cloud (AWS ECS, Docker, etc.), as métricas refletem o ambiente do container ou VM, não do host físico.

Para coletar métricas reais do host físico, execute o monitoramento diretamente no servidor ou adapte a arquitetura para expor métricas via API.

> **Nota sobre Terraform:** Este diretório contém apenas exemplos didáticos. O programa coleta métricas do host onde está rodando; se executado em ambientes como AWS/ECS ou via Terraform, as métricas refletirão o ambiente do container/VM, não do host físico, o que não atende ao propósito do monitoramento. O único deploy real recomendado é o envio da imagem Docker para o DockerHub.
