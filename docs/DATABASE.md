# LocaControl — Banco de dados

## Fundação (Etapa 0)

SQLite local em `data/locacontrol.db`, fora do Git. URL configurável por `LOCACONTROL_DATABASE_URL`; paths relativos resolvem contra a raiz do repositório. SQLAlchemy 2 gerencia engine/conexões. `PRAGMA foreign_keys=ON` em cada conexão e timeout de lock limitado. Pasta do banco criada quando necessário; schema somente por Alembic.

Revisão planejada: `0001_foundation`. Baseline sem tabelas comerciais; Alembic cria a tabela técnica `alembic_version`. Uma migration sem tabelas fictícias é suficiente para estabelecer a cadeia de revisões e testar upgrade/downgrade. O status de execução fica em `PROJECT_STATE.md` e `AI_HANDOFF.md`.

`GET /health` deve consultar o banco e comparar revisões aplicadas com os heads Alembic. Banco acessível mas não migrado deve responder 503. Não expor URL ou traceback ao consumidor.

## Identidade — Etapa 2

Migration criada: `0002_identity`, posterior a `0001_foundation`. Estado da aplicação ao banco local em PROJECT_STATE/AI_HANDOFF.

- users: usuário normalizado e único, nome, hash, ativo, troca obrigatória, created_at/updated_at/created_by.
- roles e permissions: catálogos com código único; associações user_roles e role_permissions com chaves compostas.
- auth_sessions: SHA-256 do token como chave, usuário, criação e expiração UTC.
- login_throttles: chave derivada de usuário/IP ou troca de senha, contador e expiração.
- audit_logs: autor, instante UTC, ação, entidade/registro e alterações JSON sem segredos.

Instantes UTC são inteiros Unix em segundos. FKs habilitadas; remoção de associações/sessões tem cascata, mas a API não exclui usuários ou auditoria. A migration insere cinco perfis e seis permissões, sem usuário ou senha. Seed congelado na própria migration. Bootstrap inicial é operação explícita local. Nenhuma tabela comercial antecipada. Ver SECURITY.md para invariantes e transações.

## Cadastros, estoque e preços — Etapa 3 concluída

Migration 0003_masters cria customers, customer_addresses, products, equipment, stock_movements e prices, com FKs, índices, constraints e dez permissões comerciais. Dinheiro em centavos inteiros e quantidades em milésimos, expostos como texto decimal. Revisões de preços preservam registros; cadastros usam versão para conflitos. Movimentos são append-only e auditados na mesma transação.

## Importação — Etapa 4

Migration 0004_imports cria import_batches e import_origins e duas permissões imports.read/write (administrador inicialmente). ImportBatch registra filename, checksum, criação/autor, confirmação/autor, status, contagens de linhas, mapeamento e relatório JSON. ImportOrigin associa checksum+aba+linha+módulo a registro, preservando células originais, tipos, formatos e avisos. source_key única impede repetição da mesma origem.

Originais binários ficam fora do Git em data/imports, com nome UUID gerado pelo servidor. A configuração LOCACONTROL_IMPORT_DIRECTORY altera o diretório. Não usar filename fornecido como caminho. Preservar banco e diretório juntos em backup. Fórmulas não são executadas; cached values geram aviso.

DRY RUN usa savepoints e rollback de registros, auditoria e origens. O upload anterior persiste somente lote/original. Confirmação revalida sob BEGIN IMMEDIATE e exige digest correspondente à prévia. Savepoint por linha permite importar as válidas; falha técnica inesperada reverte a transação. Registros existentes não são sobrescritos; saldo inicial de produto com movimentos é conflito.

Estado local em 08/10/2026: **0004_imports aplicada**, 5 perfis, 18 permissões, 1 usuário, tabelas comerciais/importação vazias. Conta e hash comparados com backup e preservados. integrity_check ok, foreign_key_check sem ocorrências e Alembic check sem drift. Backup: data/backups/pre-imports-20261008-214138.db, feito consistentemente antes de aplicar 0003 e 0004. Testes de upgrade/downgrade/reupgrade somente em temporário.

## Orçamentos — Etapa 5

Migration 0005_quotes cria quotes, quote_items e quote_transitions e quatro permissões (quotes.read/write/approve/negotiate; administrador recebe todas, comercial read/write/approve, financeiro read). Valores em centavos e quantidades em milésimos; datas comerciais como texto AAAA-MM-DD. (year, sequence) único sustenta o número ORC-AAAA-NNNNNN. Itens guardam snapshot de produto e de preço de tabela, além do preço negociado. Status EXPIRADO não é coluna: deriva da validade.

Checkpoint intermediário de 11/10/2026 (08:44): 0005_quotes aplicada, 22 permissões, após a cópia data/backups/pre-quotes-20261011-084445.db. Superado pelo estado local atual, abaixo.

## Contratos, documentos e operação — Etapas 6 e 7

Migration 0006_contracts cria app_settings, contract_templates, contracts, contract_items, contract_events, contract_documents, withdrawals, withdrawal_items, returns, return_items e contract_item_units, com cinco permissões (contracts.read/write/negotiate/configure e operations.write). Concessões: administrador todas; comercial contracts.read/write; operação contracts.read e operations.write; financeiro contracts.read. Semeia um modelo de contrato provisório, ativo e marcado como tal.

Número comercial = base_number com renewal_number opcional, unicidade (base_number, renewal_number); quote_id único garante conversão única do orçamento. Datas comerciais em texto AAAA-MM-DD; due_date indexada sustenta os filtros de vencendo/vencido, que não são colunas de estado. Saldos de retirada, devolução e renovação são somas dos itens de movimento, não colunas. PDFs gerados ficam fora do banco em data/documents (LOCACONTROL_DOCUMENT_DIRECTORY), com nome UUID, SHA-256 e tamanho na linha.

## Relatórios — Etapa 8

Migration 0007_reports não cria tabelas: apenas a permissão reports.read para administrador, comercial e financeiro. Indicadores são calculados na consulta.

## Portal — Etapa 9

Migration 0008_portal cria customer_users (PK user_id: uma conta, um cliente) e renewal_requests (estados PENDENTE, APROVADA, RECUSADA, CANCELADA), e a permissão portal.access concedida somente ao perfil CLIENTE.

## Fiscal — Etapa 10

Migration 0009_fiscal cria fiscal_documents (request_key único, valor em centavos > 0, período ordenado, provedor e ambiente gravados) e fiscal_events (retorno bruto de cada chamada), e as permissões fiscal.read/write para administrador e financeiro. Arquivos PDF/XML em data/fiscal (LOCACONTROL_FISCAL_DIRECTORY). Só há dados de simulação possíveis: não existe adapter real.

## Backup — Etapa 11

Migration 0010_backups não cria tabelas: apenas a permissão backups.manage para o administrador. A configuração do backup usa app_settings (chave `backup`). Os conjuntos são arquivos `locacontrol_AAAA-MM-DD_HHMMSS.zip` em data/backups (LOCACONTROL_BACKUP_DIRECTORY ou pasta definida na configuração), contendo locacontrol.db, imports/, documents/, fiscal/ e manifest.json. Cópias feitas antes de uma restauração recebem o sufixo `_pre-restore` e não entram na retenção.

## Estado local em 11/10/2026

Conferido por leitura somente em 11/10: revisão **0010_backups**, 5 perfis, **32 permissões**, 1 usuário preservado, 1 modelo de contrato (provisório, ativo). Sem dados comerciais: clientes, orçamentos, contratos, documentos fiscais, vínculos de portal e import_batches com zero linhas; app_settings vazia (numeração começa em 1, backup automático desativado).

Cópias prévias em data/backups, uma antes de cada grupo de migrations do dia: pre-quotes-20261011-084445.db (antes de 0005), pre-contracts-20261011-090635.db (antes de 0006) e pre-upgrade-20261011-092925.db (antes de 0007–0010, criada por scripts/launch.ps1). Permanecem também pre-identity-20260916.db e pre-imports-20261008-214138.db. Essas cópias `.db` são anteriores ao formato `.zip` e contêm só o banco.

## Próximas migrations previstas

Nenhuma migration está pendente ou planejada com schema definido. Podem exigir schema novo, quando decididos: conversão do histórico de contratos do Excel (depende do arquivo real), upload de documento assinado, registro de manutenção, campos exigidos por um provedor fiscal real e multiempresa. Não criar migrations antecipadas.

## Convenções

ID interno separado de código comercial, timestamps em UTC e autor quando aplicável. Soft delete conforme necessidade comercial, constraints nomeadas, chaves estrangeiras e unicidade explícitas. Não reutilizar textos exibidos como identidade. `base_number` e `renewal_number` têm unicidade conjunta e a renovação aponta para o contrato raiz (`root_id`) e para o anterior (`previous_id`).

Valores financeiros: Decimal no Python; nunca float. SQLite NUMERIC não garante decimal exato: a Etapa 3 usa unidades mínimas inteiras e round trips testados; PostgreSQL pode usar NUMERIC. Nenhum campo monetário existe na Etapa 0.

Preço histórico e snapshots não podem ser sobrescritos. Operações de estoque/contrato/auditoria devem ser transacionais e impedir saldo negativo; concorrência será testada nas etapas de negócio. Não colocar arquivo SQLite em pasta de rede.

## Operação

No uso diário, `Iniciar LocaControl.cmd` (scripts/launch.ps1) aplica migrations pendentes sozinho, sempre depois de copiar o banco para data/backups/pre-upgrade-*.db. Manualmente — aplicar: `./scripts/migrate.ps1`. Consultar: `./scripts/migrate.ps1 -Action current`. Verificar drift: `./scripts/migrate.ps1 -Action check`. As reversões são testadas somente em bancos temporários; nunca reverter um banco comercial sem plano e cópia de segurança.

Trocar URL por PostgreSQL exigirá driver adequado, migração dos dados e validação de tipos/constraints, sem reescrever regras de domínio. Não declarar suporte PostgreSQL validado nesta etapa.

