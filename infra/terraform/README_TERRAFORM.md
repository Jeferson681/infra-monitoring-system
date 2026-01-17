# Exemplos de Terraform — Uso Educacional e Demonstrativo

Esta pasta contém arquivos de exemplo de Terraform que demonstram conceitos de Infraestrutura como Código (IaC) aplicados ao projeto.
Os arquivos podem ser utilizados livremente para estudo, testes locais ou provisionamento controlado de ambientes simples.

## Considerações Importantes

Os exemplos são mínimos e ilustrativos, voltados à compreensão de blocos, variáveis e fluxos de provisionamento.

Antes de aplicar em qualquer ambiente real, revise e adapte conforme suas necessidades (rede, segurança, políticas IAM, backend remoto etc.).

Não há integração de estado remoto (remote state) ou bloqueios de concorrência configurados por padrão.

### Para validação local da sintaxe:

```sh
cd infra/terraform
terraform init -backend=false
terraform validate
```

### Para execução segura em ambiente de testes:

```sh
terraform plan
terraform apply
```

Recomendação: utilize uma conta ou workspace isolado para evitar modificações não intencionais em ambientes críticos.

---

Para detalhes sobre limites de coleta (`psutil`), persistência (JSONL) e ativação do exporter, consulte `docs/DECISIONS.md`. Instruções de execução e exemplos estão em `docs/RUN.md`.

---
## Em resumo

O uso de Terraform neste projeto é plenamente funcional e opcional.
Ele serve como base didática e também pode ser adaptado para implantações reais, considerando as diferenças entre métricas de host físico e métricas do ambiente provisionado.
