# LocaControl — Decisões técnicas

## ADR-013 — Excel enviado pelo usuário (2026-10-08)

ACEITA. O usuário envia o arquivo pelo sistema, sem caminho local. Análise dinâmica, mapeamento explícito por aba/módulo, prévia sem persistência comercial, revalidação por digest e confirmação. Sem presumir cabeçalhos/layout antes do upload real. Original imutável, checksum, ImportBatch e origem por linha. openpyxl lê .xlsx/.xlsm sem executar macros/fórmulas/referências; defusedxml protege leitura XML e python-multipart atende upload. Limites e fluxo em EXCEL_IMPORT.md.

Uma aba/módulo por operação; nova conversão reaproveita original e não repete origens. Campos sem destino não desaparecem: relatório informa pendências, original preserva conteúdo. Não sobrescrever conflitos nem somar estoque inicial a produto já movimentado. Contratos/renovações aguardam Etapas 6/7; a Etapa 4 permanece PARCIAL até homologação real e encaminhamento desses dados. Não confundir fixtures com arquivo da empresa.

## ADR-012 — Cadastros, estoque e preços (2026-10-08)

ACEITA. Decimal nos serviços e inteiros escalados: centavos para preços e milésimos para quantidades. Cadastros com versão; movimentos e preços preservam histórico. Endereços em tabela própria. Autorização e auditoria reutilizadas da Etapa 2. Baixa definitiva bloqueia itens reservados/locados. Testes de precisão, concorrência, permissão e rollback passaram, frontend real integrado e migration aplicada. Não declarar PostgreSQL validado; BEGIN IMMEDIATE é específico de SQLite.

Publicação pública continua pendente de decisões de público, empresa única/multiempresa, infraestrutura e banco. PUBLICATION_ROADMAP.md organiza sem autorizar deploy.

## ADR-010 — Identidade e segurança local (2026-09-16)

Etapa 2 autorizada. Sessões opacas revogáveis em banco, cookie HttpOnly/SameSite Strict, hash do identificador e CSRF/origens explícitas. Senhas Argon2id via argon2-cffi. Bootstrap e recuperação somente por CLI local interativa, sem senha fixa ou segredo por argumento. Primeiro/último administrador protegido por transação SQLite BEGIN IMMEDIATE. Auditoria na mesma transação das alterações, sem segredos. Recuperação local pressupõe controle do computador e da pasta do projeto.

## ADR-011 — Permissões e alcance da Etapa 2 (2026-09-16)

Cinco perfis e seis permissões relativas a funções já existentes. Administrador e Cliente são protegidos; Cliente não pode ser combinado com perfil interno. Perfis internos inicialmente só acessam as prévias visuais; permissões comerciais virão com seus módulos. Administradores podem editar grants de perfis internos. UI de usuários atribui um perfil por edição; API suporta múltiplos perfis internos. Não apagar usuários nem auditoria. Detalhamento e API em SECURITY.md; estado de validação em PROJECT_STATE.

## ADR-001 — Escopo e estrutura (2026-09-12)

Na Etapa 0 autorizada, criar monorepo `backend`, `frontend`, `scripts`, `docs`, sem módulos comerciais antecipados. Pacotes de domínio/serviços/infra separados. A autorização posterior da Etapa 1 está registrada na ADR-007.

## ADR-002 — Banco e baseline (2026-09-12)

SQLAlchemy 2 síncrono com SQLite local é adequado à base local. URL configurável, paths estáveis e foreign keys habilitadas. Alembic é a única fonte de schema. Baseline `0001_foundation` sem tabela artificial; somente `alembic_version`. Health exige conexão e revisão correta. Migração PostgreSQL requer validação posterior, não apenas troca de URL.

## ADR-003 — Dependências e qualidade (2026-09-12)

Ambiente virtual Python isolado na raiz, manifesto em `backend/pyproject.toml` e lock de requisitos para instalação reproduzível. Node/npm com `package-lock.json` no frontend. Ruff, pytest, ESLint, Prettier, TypeScript, Vitest e Testing Library. Versões concretas serão fixadas nos locks após instalação. Scripts PowerShell propagam falhas e funcionam com caminhos contendo espaços.

## ADR-004 — Comunicação e execução (2026-09-12)

Frontend acessa caminhos relativos via proxy Vite no desenvolvimento e mesma origem quando servido pelo FastAPI após build. Bind padrão loopback; LAN é opção explícita. Health técnico sem informações sensíveis. Sem autenticação nesta etapa por não haver APIs comerciais.

## ADR-005 — Valores monetários futuros (2026-09-12)

Manter exigência Decimal e armazenamento exato. Não definir colunas monetárias antes da Etapa 3. SQLite NUMERIC pode converter para representação aproximada: decidir tipo exato e validar round trips na etapa de preços. Nenhuma mudança na regra de negócio de não usar float.

## ADR-006 — Interface e dados (2026-09-12)

Na Etapa 0, tela técnica mínima mostra saúde real usando TanStack Query e validação Zod, sem dados comerciais fictícios. A Etapa 1 mantém o diagnóstico real em Configurações e adiciona fixtures explicitamente visuais conforme ADR-009.

## ADR-007 — Etapa 1 e navegação (2026-09-12)

Etapa 1 autorizada explicitamente pelo usuário. Implementar apenas fundação visual e sete telas. HashRouter mantém links e refresh no backend estático existente, sem alteração de endpoints. URLs usam fragmento (`/#/clientes`). Itens de etapas futuras mostram escopo indisponível; não fingem implementação. Configurações carrega sob demanda para reduzir o bundle inicial. Etapa 2 depende de autorização separada.

## ADR-008 — Temas e acessibilidade (2026-09-12)

Tokens semânticos CSS para claro/escuro; sistema operacional como padrão. Preferência e menu recolhido persistem em localStorage com tratamento de acesso bloqueado. Script de tema anterior à renderização, listener de media query e sincronização entre abas. Radix Dialog/AlertDialog para contenção/restauração do foco e cancelamento. Campos nativos com RHF/Zod. Ajustados texto secundário e bordas de controles para contraste; status com texto, ícone e cor. Playwright/Axe validam quatro viewports e dois temas.

## ADR-009 — Demonstração visual isolada (2026-09-12)

Fixtures em frontend/src/demo/data.ts são somente exemplos visuais desta etapa, identificados na interface e por códigos DEMO. Formulários validam uma prévia e avisam que nada foi salvo; não enviam mutações nem criam seeds. Sidebar informa ausência de sessão. O health continua consultando a API real. Quando os módulos reais forem implementados, substituir as respectivas fixtures por consultas e serviços testados, sem tratar a demonstração como histórico do banco.

