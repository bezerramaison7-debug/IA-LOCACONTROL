# LocaControl — Changelog

## 2026-10-11 — Documentos estruturantes e prompt integral de continuidade
- Criados PRD, TRD, APP_FLOW, DESIGN_BRIEF e BACKEND_SCHEMA com requisitos, jornadas, direção visual e separação de schema existente/proposto.
- Complementado DEVELOPMENT_PLAN com tarefas, responsáveis, dependências, rastreabilidade e critérios; preservados prompts oficiais.
- Atualizado CONTINUE_PROMPT com os seis documentos, papéis especialistas, etapas 4–12 e limites de publicação/fiscal/custos.
- Corrigida próxima ação antiga da seção 8 de PUBLICATION_ROADMAP; indexação em README e registros em PROJECT_STATE/AI_HANDOFF.
- Sessão documental: sem alteração funcional, testes de aplicação, migrations, consulta ao banco ou deploy. Verificação de arquivos/referências feita ao final.


## 2026-10-08 — Etapa 3 concluída e importação por upload implementada

- Concluídos cadastros reais de clientes/endereço, produtos e equipamentos, estoque com seis estados e preços com vigência/histórico. Validados precisão, conflitos, concorrência, permissões e auditoria.
- Implementados upload .xlsx/.xlsm, análise dinâmica, mapeamento, DRY RUN sem persistência comercial, confirmação com revalidação, conflitos por linha e conversão dos módulos existentes.
- Criados ImportBatch/ImportOrigin, preservação de original/checksum/células, relatório JSON, histórico e nova conversão do mesmo original. Excel enviado pelo usuário na interface, sem caminho local.
- Etapa 4 PARCIAL: falta homologação do Excel real; contratos/renovações e dados sem destino preservados como pendentes, sem declaração de conversão integral.
- Aplicadas 0003_masters e 0004_imports após backup data/backups/pre-imports-20261008-214138.db. Banco íntegro, sem drift/FK inválida, cinco perfis/18 permissões/uma conta preservada; zero fixtures comerciais na base real.
- Validações: 66 backend, 29 frontend, 16 visuais e 12 cenários E2E reais aprovados; 10 testes do importador e 4 E2E de upload repetidos após ajustes finais. Check oficial e smoke aprovados; capturas mobile claro e desktop escuro inspecionadas.
- Corrigidos seletores/fixtures de teste; smoke deve ser sequencial ao build para evitar limpeza de dist. Avisos não bloqueantes registrados no handoff.
- Atualizados documentação permanente, guia EXCEL_IMPORT, AI_HANDOFF, roteiro e prompt de continuidade. Aplicação local disponível em 127.0.0.1:8000, health ok. Etapas 5–12 e deploy não iniciados.


## 2026-10-08 — Checkpoint da Etapa 3 e roteiro de publicação

- Conferido o código real: backend/app/masters e migration 0003 já existem, mas ainda não possuem aceite funcional; frontend comercial permanece demonstrativo.
- Etapa 3 registrada como PARCIAL; sete erros Ruff confirmados na migration. Nenhum fonte corrigido nesta sessão documental.
- Banco auditado somente leitura: revisão 0002_identity, cinco perfis, seis permissões e um usuário; nenhuma tabela comercial e integridade ok. Conta existente preservada, sem execução de migration.
- Atualizados AI_HANDOFF e PROJECT_STATE com arquivos existentes, testes pendentes, erros e próxima ação exata; sincronizados README, ARCHITECTURE, DATABASE e DECISIONS (ADR-012 em validação).
- Criado PUBLICATION_ROADMAP.md com a conclusão da Etapa 3, Etapas 4–12, insumos, decisões de arquitetura remota e preparação/homologação/publicação.
- Testes funcionais, build, E2E e smoke não executados nesta sessão; resultados de setembro permanecem históricos da Etapa 2.
- Nenhuma funcionalidade, contratação, configuração pública ou implantação realizada.


## 2026-09-20 — Etapa 2 concluída

- Criados modelos e migration `0002_identity` para usuários, perfis, permissões, auditoria, sessões e controle de tentativas. Aplicada ao banco local em 16/09 após backup; current/check e integridade confirmados em 20/09. Seeds: cinco perfis e seis permissões, sem usuários ou dados comerciais.
- Implementados login/logout/me, conta própria, troca de senha, gestão de usuários, redefinição de senha e gestão de permissões, com autorização no backend.
- Implementados Argon2id, sessões opacas com hash no banco/cookie HttpOnly, CSRF/origens, limites de tentativas, troca obrigatória e revogação de sessões.
- Criados bootstrap e recuperação local por CLI interativa, sem senha padrão. Primeiro administrador local deve ser configurado pelo operador.
- Protegidos primeiro/último administrador, grants de ADMINISTRADOR/CLIENTE e isolamento do perfil CLIENTE; adicionadas transações e testes concorrentes.
- Criadas telas reais de Login, Meu perfil, Usuários, Perfis/permissões e Auditoria, com menu/rotas por acesso e auditoria de operações administrativas.
- Corrigidos retorno à rota solicitada após login, sincronização do teste de teclado e encerramento da árvore dos servidores temporários no Windows.
- Validação final: check/build, 35 testes backend, 25 frontend, 16 cenários visuais e 4 cenários reais de navegador aprovados em 16/09; 96 auditorias Axe sem violações detectadas. Smoke final aprovado em 20/09, incluindo limpeza.
- Consolidados README, SECURITY, DATABASE, ARCHITECTURE, DESIGN_SYSTEM, DECISIONS, PROJECT_STATE e AI_HANDOFF. Etapa 3 registrada como NÃO INICIADA; não houve avanço para módulos comerciais.

## 2026-09-12 — Etapa 1 concluída

- Implementados design system, temas claro/escuro/sistema persistidos e sincronizados com o sistema operacional.
- Criados shell responsivo, sidebar recolhível, menu móvel, topbar, breadcrumbs, busca de páginas e 404.
- Criadas sete telas visuais: Dashboard, Clientes, Produtos, Equipamentos, Orçamentos, Contratos e Configurações.
- Adicionadas primitivas acessíveis, status, tabelas com busca/filtro/ordenação/paginação, dialogs, formulário de prévia, toasts e estados.
- Fixtures visuais explicitamente identificadas e isoladas; formulários não gravam registros. Health real preservado em Configurações.
- Adicionados Router, Radix Dialog/AlertDialog, Lucide e testes Playwright/Axe. Configurações usa carregamento sob demanda.
- Passaram 14 testes backend, 20 frontend e 16 cenários de navegador; 56 auditorias de acessibilidade sem violações detectadas, em quatro viewports e dois temas.
- Passaram lint, formatação, TypeScript/build, smoke HTTP e Alembic current/check. Nenhuma migration nova ou alteração no banco comercial.
- Consolidada documentação e AI_HANDOFF; Etapa 2 — Banco de dados, autenticação e permissões registrada como NÃO INICIADA.

## 2026-09-12 — Etapa 0 concluída

- Recebida autorização explícita para a fundação técnica.
- Preservados plano e protocolo e atualizado checkpoint operacional.
- Criados documentos de estado, arquitetura, regras de negócio, banco, design e decisões.
- Criado monorepo com backend FastAPI/SQLAlchemy/Alembic, frontend React/TypeScript/Vite/Tailwind e scripts PowerShell.
- Criado `GET /health` com conexão de banco e verificação da revisão Alembic.
- Criada/aplicada migration `0001_foundation` no SQLite local, sem tabelas comerciais antecipadas.
- Criada tela técnica de fundação com TanStack Query e validação Zod; sem dados comerciais fictícios.
- Passaram 14 testes backend, 10 testes frontend, lint, formatação, TypeScript/build, migrations e smoke HTTP real.
- Etapa 1 registrada como NÃO INICIADA.

