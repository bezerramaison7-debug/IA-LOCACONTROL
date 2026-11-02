# LocaControl — TRD: requisitos técnicos

Versão documental 1.1 — 2026-10-11. Responsáveis: arquitetura, backend, frontend, dados, segurança e operação.
Especificação da base existente e evolução. Atualizado após a implementação dos backends e das telas das etapas 5–11 e da entrega técnica da etapa 12; estado e evidências em PROJECT_STATE.

## 1. Referências e limites
[PRD](PRD.md), [ARCHITECTURE](ARCHITECTURE.md), [BACKEND_SCHEMA](BACKEND_SCHEMA.md), [SECURITY](SECURITY.md), [DATABASE](DATABASE.md), [DECISIONS](DECISIONS.md).
Preservar código, conta e banco existentes. Não executar bootstrap, reset ou migration de produção por inferência. Não trocar stack sem decisão registrada.

## 2. Arquitetura
Navegador → frontend React → API FastAPI → serviços/transações → SQLAlchemy → SQLite.
Desenvolvimento: Vite em 127.0.0.1:5173 com proxy; build pode ser servido por FastAPI em 127.0.0.1:8000.
Módulos de backend existentes: identidade, cadastros, importação, orçamentos, contratos/operação/documentos, relatórios, portal, fiscal (simulação) e backup. Telas existentes em 11/10 (commit `82e0845`): identidade, cadastros, estoque, preços, importações, orçamentos, contratos, ciclo operacional, dashboard real, relatórios, portal do cliente, faturamento e fiscal (simulação) e backups. Nenhum item de menu aponta para página provisória.
Domínio não deve depender de React ou detalhes HTTP.

## 3. Stack e configuração
Frontend: React/TypeScript/Vite/Tailwind, Radix, TanStack Query, React Hook Form e Zod.
Backend: Python/FastAPI/Pydantic/SQLAlchemy/Alembic. Excel: openpyxl com proteção de leitura (também usado nas exportações). PDF: reportlab (orçamentos, contratos, relatórios e simulação fiscal).
Versões exatas: manifests e lockfiles; não copiar versões supostas para este documento.
Configuração em ambiente/.env, sem segredos em Git. Paths relativos resolvidos contra raiz.
SQLite local, nunca arquivo em pasta de rede. PostgreSQL exige adaptação de transações, driver, tipos, transferência e testes; suporte ainda não homologado.

## 4. Requisitos técnicos rastreáveis
| ID | Requisitos PRD | Implementação/condição |
| --- | --- | --- |
| RT-API-001 | Todos RF | Schemas de entrada/saída; erros compreensíveis; filtros/paginação; permissão na API |
| RT-DAD-001 | RF-PRE/ORC/CON | Decimal nos cálculos; dinheiro em centavos e quantidade em milésimos; API decimal textual |
| RT-TXN-001 | RF-EST/RET/REN/DEV | Operação e auditoria atômicas; concorrência e repetição testadas |
| RT-HIS-001 | RF-PRE/ORC/CON/REN | Revisões e snapshots preservados; documentos assinados não substituídos |
| RT-IMP-001 | RF-IMP | Original/checksum/origem; limites; DRY RUN; digest e revalidação |
| RT-SEG-001 | RF-ID/POR | Sessão revogável, RBAC, origem/CSRF, escopo por cliente em toda consulta/download |
| RT-UI-001 | RNF-UX | Tokens existentes, temas, teclado, estados e responsividade |
| RT-FIS-001 | RF-FIS | Interface desacoplada; adapters; sandbox identificado; repetição segura — atendido só com o provedor de simulação |
| RT-OPS-001 | RF-OPS | Backup consistente do banco e arquivos; restore comprovado; atualização controlada — atendido em testes automatizados com dados temporários; ensaio com dados reais pendente |

## 5. Frontend
HashRouter mantém links diretos no build. TanStack Query gerencia dados do servidor; invalidar consultas após mutações coerentes.
Formulários validam para UX, sem substituir backend. Conflito de versão oferece revisão; não sobrescrever silenciosamente.
Autenticação não fica em localStorage. Sessão expirada remove conteúdo privado e conduz ao login.
Toda tela, inclusive as de dashboard, relatórios, portal, fiscal e backups, deve possuir loading, vazio, erro, sucesso, sem permissão e conflito quando aplicável.
Temas e sidebar preservam preferências existentes. Não misturar fixtures com dados comerciais.

## 6. Backend e API
Rotas delegam regras a serviços. Modelos, schemas, permissões e endpoints existentes são detalhados em BACKEND_SCHEMA.
IDs internos separados de códigos comerciais. DELETE existente deve ser interpretado pelo serviço, sem presumir exclusão física.
APIs futuras terão contrato definido antes da implementação: método/rota, request, response, permissões, erros, efeitos e idempotência.
Numeração e confirmação comercial são protegidas por transação e unicidade: (year, sequence) nos orçamentos, (base_number, renewal_number) e quote_id nos contratos, request_key em retirada, devolução e documento fiscal (mesma chave com conteúdo diferente responde 409).
Data comercial: fuso fixo UTC−3 em `app/core/clock.py`; instantes continuam inteiros UTC.

## 7. Banco e transações
Schema somente por Alembic; startup não usa create_all para alterar banco.
FKs habilitadas por conexão. Atualizações editáveis utilizam versão; estoque/preços preservam histórico.
SQLite atual utiliza BEGIN IMMEDIATE nas mutações pertinentes. Não transportar essa instrução literalmente para PostgreSQL.
Testar rollback de auditoria, conflito de versão, estoque concorrente, duplicação de request e colisão de numeração.
Migration complexa exige checkpoint e backup consistente; downgrade destrutivo não é rollback operacional padrão.

## 8. Segurança
Sessões opacas revogáveis, cookie HttpOnly, hash Argon2id e limitação de tentativas existentes.
Origem autorizada, cabeçalho de requisição e CSRF em mutações conforme SECURITY.
Downloads exigem autorização e, no portal, vínculo com o cliente (registro alheio responde 404).
Não expor paths, SQL, tokens ou dados privados em health/erros/logs.
HTTPS, cookie Secure e proxy confiável devem ser configurados e ensaiados antes de acesso web público.
Controle de cliente não implica tenant multiempresa; essa evolução depende de escopo adicional.

## 9. Arquivos e documentos
Originais Excel em diretório privado, nomes gerados pelo servidor. Limites em EXCEL_IMPORT.
Fórmulas/macros não executadas; cache é tratado com aviso. .xls binário exige conversão para .xlsx.
Documentos de contrato: modelo versionado com placeholders, PDF imutável com checksum em `data/documents`, download autorizado. DOCX e upload do assinado não existem.
Backup cobre banco, originais, documentos e arquivos fiscais em um `.zip` com manifesto; retenção por quantidade de conjuntos é configurável. Política de cópia externa e de dados pessoais ainda precisa de definição operacional.

## 10. Fiscal e integrações
FiscalProvider: emit, status, cancel, get_pdf, get_xml.
Fake valida arquitetura e é o único adapter existente (`LOCACONTROL_FISCAL_PROVIDER=fake`); sandbox do provedor valida integração externa e ainda não existe. Nenhum deles comprova emissão em produção.
Definir correlação, timeout, repetição, conciliação e callbacks conforme contrato oficial do provedor escolhido.
Regras fiscais e espécie documental dependem de contabilidade; segredos somente em configuração segura.

## 11. Operação e publicação
Local/LAN permanece base. Entregue em 11/10: inicialização e parada por atalho no Windows, logs do servidor e mensagens da aplicação em `data/logs`, health, backup/restauração e atualização que não toca em `data/` (ADR-021). Não há logging estruturado nem rotação de logs.
Web exige processo Python supervisionado, frontend, persistência, domínio/HTTPS, configuração segura e monitoramento.
Definir capacidade, RPO e RTO antes de afirmar metas. Seguir PUBLICATION_ROADMAP; publicar requer autorização concreta.

## 12. Verificação
Ferramentas existentes: pytest/Ruff; Vitest/Testing Library; TypeScript/ESLint/Prettier; Playwright/Axe; smoke HTTP.
Comandos centrais: scripts/check.ps1 e scripts/test.ps1; parâmetros reais devem ser conferidos.
Build deve preceder smoke/E2E; nunca limpar dist enquanto testes o utilizam.
Usar bancos/arquivos temporários, não dados reais. Aceite cobre unidade, API, frontend, integração, concorrência, migrations e restore conforme risco.
Registrar comando, ambiente, resultado e falhas. Não reclassificar evidências antigas como atuais.

## 13. Decisões resolvidas e abertas
Resolvidas em 11/10/2026: duração/cobrança e arredondamento (ADR-014); estados e transições de orçamento e contrato, numeração e limiar de vencimento (ADR-014/015); ciclo operacional e renovação (ADR-016); formato e versionamento de documentos (ADR-017); relatórios (ADR-018); isolamento do portal (ADR-019); arquitetura fiscal (ADR-020); backup/retenção local (ADR-021).
Abertas: template real do contrato; reserva de estoque na confirmação; upload do documento assinado; regras fiscais e provedor; capacidade; infraestrutura; banco web; cópia externa de backup; multiempresa.
Atualizar DECISIONS e documentos associados ao resolver cada decisão.
