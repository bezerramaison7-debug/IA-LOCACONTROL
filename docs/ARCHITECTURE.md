# LocaControl — Arquitetura

## Base aprovada

Monorepo local com `frontend/`, `backend/`, `scripts/` e `docs/`. Frontend React + TypeScript + Vite + Tailwind CSS. TanStack Query controla estado de servidor; React Hook Form e Zod são a base para formulários/validação futuros; Radix fornece primitivas acessíveis. Backend Python + FastAPI + Pydantic + SQLAlchemy 2 + Alembic. SQLite inicial, com futura migração para PostgreSQL.

## Responsabilidades

- `backend/app/api`: transporte HTTP, schemas Pydantic e dependências; não concentra regras comerciais.
- `backend/app/core`: configurações (`config.py`) e data comercial em UTC−3 (`clock.py`).
- `backend/app/domain`: regras e entidades de domínio, sem dependência de React/HTTP.
- `backend/app/services`: casos de uso e coordenação de transações.
- `backend/app/persistence`: SQLAlchemy, metadata e acesso ao banco.
- `backend/app/documents`: pacote reservado e vazio; os documentos de contrato estão em `backend/app/contracts/documents.py`.
- `backend/app/imports`: análise e importação com preview na etapa própria.
- `backend/app/auth`: autenticação/autorização na Etapa 2.
- `backend/app/masters`: cadastros, estoque e preços da Etapa 3 (concluída).
- `backend/app/quotes`: orçamentos — cálculo puro (`calc.py`), regras (`service.py`) e PDF (`pdf.py`).
- `backend/app/contracts`: contratos e numeração (`service.py`), retirada/devolução/renovação (`operations.py`), modelos e PDFs versionados (`documents.py`).
- `backend/app/reports`: dashboard, resumo por cliente, relatórios (`service.py`) e exportação Excel/PDF (`export.py`).
- `backend/app/portal`: vínculo conta–cliente, consultas isoladas e solicitações de renovação.
- `backend/app/fiscal`: documentos fiscais, interface `FiscalProvider` (`provider.py`) e provedor de simulação (`fake.py`).
- `backend/app/ops`: backup, verificação, agendador diário e restauração (`backup.py`).
- `backend/app/integrations`: pacote reservado e vazio; o provedor fiscal ficou em `backend/app/fiscal`.
- `frontend/src/lib`: comunicação HTTP e validação de respostas.
- `frontend/src/components`: biblioteca visual acessível e diagnóstico real.
- `frontend/src/theme`: preferência visual e sincronização com sistema/storage.
- `frontend/src/layout`: shell, navegação, busca de páginas e breadcrumbs.
- `frontend/src/pages`: telas reais de identidade, cadastros, estoque, preços, importações, orçamentos, contratos, ciclo operacional, dashboard, relatórios, portal, fiscal e backups; `Placeholder` atende apenas endereços inexistentes (404).
- `frontend/src/demo` foi removido no commit `82e0845`: não há fixtures de demonstração na aplicação.

Diretórios reservados não representam funcionalidades implementadas. A Etapa 0 implementou saúde técnica e conexão; a Etapa 1 acrescentou a fundação visual. A Etapa 2 implementa identidade em backend/app/auth, autenticação frontend em frontend/src/auth e telas Login/Profile/Users/Roles/Audit. Em 08/10/2026 a Etapa 3 foi concluída: masters real no backend e cinco telas persistentes no frontend. Etapa 4 implementa backend/app/imports e tela Imports, com upload multipart, openpyxl, análise dinâmica, mapeamento, prévia, confirmação, lotes/origens e relatório. Banco local 0004_imports. Health verifica compatibilidade do schema. Excel real e histórico de contratos/renovações ainda requerem homologação.

Em 11/10/2026 foram implementados os backends das Etapas 5 a 11 (módulos acima, migrations 0005–0010, banco local em 0010_backups). Dependências entre módulos: contratos reutilizam o cálculo e os preços de orçamentos; relatórios, portal e fiscal leem contratos; `masters` consulta a custódia de contratos para impedir ajuste manual contraditório (import local para evitar ciclo); backup lê as pastas de importações, documentos e fiscal. O `lifespan` do FastAPI inicia o agendador de backup quando `LOCACONTROL_BACKUP_SCHEDULER` está ativo. Telas: todas entregues até o commit `82e0845` (orçamentos, contratos, ciclo operacional, dashboard real, relatórios, portal, fiscal e backups). `create_app` configura o log de mensagens da aplicação (`2036cea`). Backup e restauração compartilham uma trava de processo, de modo que duas operações não se sobrepõem.

## Execução

Desenvolvimento: navegador → Vite (127.0.0.1:5173) → proxy `/health` e `/api` → FastAPI (127.0.0.1:8000) → SQLAlchemy → arquivo SQLite local. Frontend compilado também pode ser servido pelo FastAPI em `/`, após build e reinício do backend. Endpoints HTTP têm precedência sobre arquivos estáticos.

Configuração via `.env` na raiz e variáveis de ambiente. Paths relativos do banco resolvidos a partir da raiz do projeto, independentemente do diretório de execução. Migrations são explícitas: nenhuma chamada a `create_all` e nenhuma alteração automática de schema no startup.

Frontend usa HashRouter (`/#/clientes`, `/#/configuracoes`) para que links diretos e refresh funcionem no build servido pelo FastAPI sem fallback novo de URLs. Configurações é carregada sob demanda. Estado visual fica no React; somente tema e recolhimento do menu ficam em localStorage protegido contra indisponibilidade. Não armazenar dados comerciais ou autenticação nesse mecanismo por inferência.

## Persistência e evolução

SQLAlchemy mantém os detalhes do driver fora do domínio. Foreign keys habilitadas por conexão SQLite. Transações comerciais futuras ficam nos serviços; gravação de operação e auditoria deve ser atômica. Migrations são a fonte de verdade do schema. Constraints têm nomes estáveis para facilitar evolução. Alterar URL não constitui migração dos dados para PostgreSQL: serão necessários driver, testes e plano de transferência.

Valores financeiros devem usar `Decimal` e armazenamento exato; a escolha da representação no SQLite precisa ser validada antes dos módulos financeiros. Não assumir que afinidade NUMERIC do SQLite equivale a decimal exato do PostgreSQL. IDs internos são distintos de códigos comerciais; snapshots e vínculos de renovação preservam histórico.

## Segurança e operação

Bind padrão em loopback. CORS com origens explícitas, sem wildcard. LAN pode ser habilitada explicitamente em rede confiável; não disponibilizar dados comerciais antes da autenticação/RBAC. SQLite não é compartilhado pela rede nem exposto à internet. Segredos, `.env`, bancos, backups e artefatos locais ficam fora do Git.

Autorização é verificada na API por dependências de sessão e permissão. Sessões opacas revogáveis, senhas Argon2id, cookie HttpOnly e proteção CSRF/origem. Frontend filtra navegação e protege rotas para UX; o backend é a autoridade. Usuário Cliente acessa somente a própria conta nesta etapa. Bootstrap/recuperação são CLI local interativa, sem credenciais padrão. Detalhes, configuração de HTTPS e fronteira de confiança em SECURITY.md.

Mutações usam serviço de identidade e transação SQLite com BEGIN IMMEDIATE; commit antes da resposta, auditoria atômica e invariantes de primeiro/último administrador. Segredos nunca entram nas respostas de erro nem nos eventos. Saúde não revela caminhos, queries ou exceções internas. Recursos de banco são liberados no shutdown. Backup, restauração e inicialização sem terminal foram entregues na Etapa 11 (ADR-021): `Iniciar LocaControl.cmd` e `Parar LocaControl.cmd` na raiz chamam `scripts/launch.ps1` e `scripts/stop.ps1`; `scripts/update.ps1` atualiza dependências e interface sem tocar em `data/`.

## Qualidade

Backend: pytest com bancos temporários e FastAPI TestClient; Ruff para lint/formatação. Frontend: Vitest + Testing Library, TypeScript, ESLint e Prettier. Playwright/Chromium e Axe verificam temas, navegação, acessibilidade e quatro viewports. Smoke HTTP verifica os dois processos e o proxy real. A aplicação não contém fixtures; dados simulados existem somente nos testes. Interceptação do health existe somente no E2E, nunca no HealthPanel.

## Publicação pública — planejamento pendente

A arquitetura atual atende execução local/LAN. Publicação na internet exige frente adicional com backend Python supervisionado, frontend compilado, banco/arquivos persistentes, HTTPS, origens/cookies, backup/restore, monitoramento e homologação. Empresa única ou multiempresa, infraestrutura e banco de produção ainda precisam de definição. O backend atual utiliza BEGIN IMMEDIATE do SQLite; mudar para PostgreSQL requer adaptar transações/tipos e executar testes, não apenas alterar URL. Roteiro em PUBLICATION_ROADMAP.md; nenhuma implantação foi feita até 11/10/2026. O backup pelo sistema só atende SQLite local.

