````markdown
# Infra Monitoring System

---

## 📘 Visão Geral

O Infra Monitoring System é uma plataforma local de observabilidade projetada para
coletar, estruturar e expor métricas a nível de host em um ambiente controlado.

A versão 1.x enfatiza intencionalmente a engenharia de base.
Componentes centrais de observabilidade — incluindo coleta de métricas,
persistência estruturada e lógica do exportador — são implementados com limites
arquitetônicos explícitos para priorizar entendimento interno, modularidade e controle.

Ao invés de abstrair cedo por meio de ferramentas externas, esta versão foca
na clareza do design, rastreabilidade das decisões e transparência operacional.
As compensações e restrições de implementação estão documentadas em `docs/DECISIONS.md`,
enquanto detalhes de execução estão disponíveis em `docs/RUN.md`.

Este documento serve como um mergulho técnico na arquitetura,
modelo de execução e postura operacional.

---

## 🖼️ Artefatos / Evidências

Uma seleção compacta de evidências visuais (diagramas, dashboards e capturas de execução).
Imagens em tamanho real estão organizadas em uma galeria dedicada para manter o README principal
conciso e de fácil leitura.

<div>
   <a href="prints/README.md"><img src="prints/architecture.png" alt="architecture" style="width:240px;margin-right:12px;border:1px solid #ddd"/></a>
   <a href="prints/README.md"><img src="prints/dashboard_panel_grafana.png" alt="grafana" style="width:240px;border:1px solid #ddd"/></a>
</div>

[Ver galeria completa de artefatos →](prints/README.md)

---

## 🧩 Arquitetura & Fluxo

1. **Integração Contínua (CI)** — valida código, dependências e testes.
2. **Cobertura de Testes** — mede a cobertura dos testes automatizados.
3. **Entrega Contínua (CD)** — constrói e publica a imagem Docker.
4. **Automação de Segurança:**
   - Dependabot (dependências)
   - TruffleHog (segredos)
   - Snyk (vulnerabilidades de pacotes)
   - Trivy (análise de imagem)
5. **Infraestrutura como Código (IaC)** — Terraform está incluído como um módulo didático e é validado no CI, mas não é aplicado automaticamente.

Postura de entrega (alto nível): o CD foi desenhado para ativação controlada. Etapas que
requerem credenciais/permissões podem ser protegidas ou mantidas como não-padrão,
portanto o pipeline permanece seguro ao mesmo tempo que documenta o fluxo de release pretendido.

---

## ⚙️ Execução Local

```shell
git clone https://github.com/Jeferson681/infra-monitoring-system.git
cd infra-monitoring-system
docker compose -f docker/docker-compose.yml up --build
```

**Serviços locais:**
- Prometheus → http://localhost:9090
- Grafana → http://localhost:3000
- Loki → http://localhost:3100
- Exporter → http://localhost:8000/metrics (acessível do host apenas se `ports:` estiver publicado; veja `docs/RUN.md`)

Executar via virtualenv (veja `docs/RUN.md` para comandos específicos por plataforma e ativação do exporter):

```shell
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Nota rápida sobre exposição de métricas:

O projeto registra métricas Prometheus via o exportador (habilite com `MONITORING_EXPORTER_ENABLE=1`).
Servir o endpoint HTTP `/metrics` é uma responsabilidade separada: no Compose o serviço `main_http`
fornece o endpoint `/metrics` a ser scrapeado, e localmente você pode iniciar o servidor HTTP de fallback
definindo `MONITORING_HTTP_ENABLE=1`. Habilitar o exportador registra métricas; servir `/metrics` depende
ou do `main_http` (Compose) ou do servidor HTTP de fallback — não habilite ambos ao mesmo tempo para evitar
conflitos de bind de porta. Veja `docs/RUN.md` para detalhes e observações sobre reachability do host.

Para ativação do exportador, limites do `psutil` e detalhes sobre persistência JSONL estão em `docs/DECISIONS.md`.

---

## 🏗️ Estrutura de Diretórios

```
infra-monitoring-system/
├── src/                  # Código-fonte principal
├── tests/                # Testes automatizados
├── infra/                # Configurações (promtail, terraform, prometheus)
│   └── terraform/        # Demo IaC
├── .github/workflows/    # Pipelines CI/CD
├── docker/Dockerfile     # Imagem Docker
├── docker/docker-compose.yml  # orquestração de containers
└── README.md
```

---

## 🧑‍💻 Pilha Tecnológica

- **Linguagem:** Python
- **Monitoramento:** Prometheus, Grafana, Loki
- **Orquestração:** Docker, Docker Compose
- **IaC:** Terraform
- **Pipeline:** GitHub Actions
- **SO:** Linux, WSL2 e Windows nativo
- A pilha atual reflete uma baseline arquitetural intencionalmente definida.
Versões maiores futuras podem alinhar estrategicamente certos componentes internos com ferramentas
de observabilidade da indústria, preservando limites arquiteturais enquanto melhoram interoperabilidade
e adequação à produção.

---

## 🔒 Segurança & Conformidade

- **TruffleHog** — previne exposição de segredos.
- **Snyk** — detecta vulnerabilidades.
- **Trivy** — analisa imagens Docker.
- **Dependabot** — mantém dependências seguras e atualizadas.
-

Todos os checks são automatizados via pipelines do GitHub Actions.

Webhook & segredos:

- O webhook do Discord (quando usado) é gerenciado via GitHub Actions Secrets e nunca é commitado ao repositório.
- Tokens e chaves de acesso usadas pelos pipelines devem ficar em `Settings > Secrets and variables > Actions`.

---

## ⚠️ Limitações Conhecidas

- A coleta no host não é garantida dentro de containers.
- O exportador depende da persistência JSONL local e expõe o snapshot mais recente.
- Endpoints HTTP são sem autenticação (destinado a uso local/demo).

---

## 🏕️ Terraform (demo IaC)

O Terraform está incluído como um módulo didático (veja `infra/terraform/`).

- O CI valida a configuração (format/lint/validate).
- Intencionalmente não é aplicado automaticamente.
- O objetivo é documentar e revisar uma estrutura declarativa esperada, não provisionar infra real como parte da coleta de métricas local.

Se desejar adaptar para ambientes reais, use uma conta/workspace isolada e revise segredos/permissões primeiro.

---

## 📎 Licença

Distribuído sob a licença **MIT**.
Portal de documentação disponível em [`/docs/DOCS.md`](./DOCS.md).

````
