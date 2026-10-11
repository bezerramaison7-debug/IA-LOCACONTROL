# LocaControl — TRD: requisitos técnicos

Versão documental 1.0 — 2026-10-11. Responsáveis: arquitetura, backend, frontend, dados, segurança e operação.
Especificação da base existente e evolução; resultados de testes anteriores permanecem históricos.

## 1. Referências e limites
[PRD](PRD.md), [ARCHITECTURE](ARCHITECTURE.md), [BACKEND_SCHEMA](BACKEND_SCHEMA.md), [SECURITY](SECURITY.md), [DATABASE](DATABASE.md), [DECISIONS](DECISIONS.md).
Preservar código, conta e banco existentes. Não executar bootstrap, reset ou migration de produção por inferência. Não trocar stack sem decisão registrada.

## 2. Arquitetura
Navegador → frontend React → API FastAPI → serviços/transações → SQLAlchemy → SQLite.
Desenvolvimento: Vite em 127.0.0.1:5173 com proxy; build pode ser servido por FastAPI em 127.0.0.1:8000.
Módulos: identidade, cadastros, importação existentes; documentos, comercial, operação integrada, portal e fiscal serão evoluídos nas etapas oficiais.
Domínio não deve depender de React ou detalhes HTTP.

## 3. Stack e configuração
Frontend: React/TypeScript/Vite/Tailwind, Radix, TanStack Query, React Hook Form e Zod.
Backend: Python/FastAPI/Pydantic/SQLAlchemy/Alembic. Excel: openpyxl com proteção de leitura.
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
| RT-FIS-001 | RF-FIS | Interface desacoplada; adapters; sandbox identificado; repetição segura |
| RT-OPS-001 | RF-OPS | Backup consistente do banco e arquivos; restore comprovado; atualização controlada |

## 5. Frontend
HashRouter mantém links diretos no build. TanStack Query gerencia dados do servidor; invalidar consultas após mutações coerentes.
Formulários validam para UX, sem substituir backend. Conflito de versão oferece revisão; não sobrescrever silenciosamente.
Autenticação não fica em localStorage. Sessão expirada remove conteúdo privado e conduz ao login.
Telas futuras devem possuir loading, vazio, erro, sucesso, sem permissão e conflito quando aplicável.
Temas e sidebar preservam preferências existentes. Não misturar fixtures com dados comerciais.

## 6. Backend e API
Rotas delegam regras a serviços. Modelos, schemas, permissões e endpoints existentes são detalhados em BACKEND_SCHEMA.
IDs internos separados de códigos comerciais. DELETE existente deve ser interpretado pelo serviço, sem presumir exclusão física.
APIs futuras terão contrato definido antes da implementação: método/rota, request, response, permissões, erros, efeitos e idempotência.
Numeração e confirmação comercial devem ser protegidas por transação e unicidade.

## 7. Banco e transações
Schema somente por Alembic; startup não usa create_all para alterar banco.
FKs habilitadas por conexão. Atualizações editáveis utilizam versão; estoque/preços preservam histórico.
SQLite atual utiliza BEGIN IMMEDIATE nas mutações pertinentes. Não transportar essa instrução literalmente para PostgreSQL.
Testar rollback de auditoria, conflito de versão, estoque concorrente, duplicação de request e colisão de numeração.
Migration complexa exige checkpoint e backup consistente; downgrade destrutivo não é rollback operacional padrão.

## 8. Segurança
Sessões opacas revogáveis, cookie HttpOnly, hash Argon2id e limitação de tentativas existentes.
Origem autorizada, cabeçalho de requisição e CSRF em mutações conforme SECURITY.
Downloads exigem autorização e, no portal futuro, vínculo com o cliente.
Não expor paths, SQL, tokens ou dados privados em health/erros/logs.
HTTPS, cookie Secure e proxy confiável devem ser configurados e ensaiados antes de acesso web público.
Controle de cliente não implica tenant multiempresa; essa evolução depende de escopo adicional.

## 9. Arquivos e documentos
Originais Excel em diretório privado, nomes gerados pelo servidor. Limites em EXCEL_IMPORT.
Fórmulas/macros não executadas; cache é tratado com aviso. .xls binário exige conversão para .xlsx.
Documentos futuros: template/versionamento, metadados, armazenamento privado e download autorizado.
Backup cobre banco, originais e documentos; retenção e políticas de dados precisam de definição operacional.

## 10. Fiscal e integrações
FiscalProvider: emit, status, cancel, get_pdf, get_xml.
Fake valida arquitetura; sandbox do provedor valida integração externa. Nenhum deles comprova emissão em produção.
Definir correlação, timeout, repetição, conciliação e callbacks conforme contrato oficial do provedor escolhido.
Regras fiscais e espécie documental dependem de contabilidade; segredos somente em configuração segura.

## 11. Operação e publicação
Local/LAN permanece base. Preparar inicialização Windows, logs, health, backup/restore e atualização sem perda.
Web exige processo Python supervisionado, frontend, persistência, domínio/HTTPS, configuração segura e monitoramento.
Definir capacidade, RPO e RTO antes de afirmar metas. Seguir PUBLICATION_ROADMAP; publicar requer autorização concreta.

## 12. Verificação
Ferramentas existentes: pytest/Ruff; Vitest/Testing Library; TypeScript/ESLint/Prettier; Playwright/Axe; smoke HTTP.
Comandos centrais: scripts/check.ps1 e scripts/test.ps1; parâmetros reais devem ser conferidos.
Build deve preceder smoke/E2E; nunca limpar dist enquanto testes o utilizam.
Usar bancos/arquivos temporários, não dados reais. Aceite cobre unidade, API, frontend, integração, concorrência, migrations e restore conforme risco.
Registrar comando, ambiente, resultado e falhas. Não reclassificar evidências antigas como atuais.

## 13. Decisões abertas
Duração/cobrança; estados e transições; template real; fiscal/provedor; capacidade; infraestrutura; banco web; backup/retencão; multiempresa.
Atualizar DECISIONS e documentos associados ao resolver cada decisão.
