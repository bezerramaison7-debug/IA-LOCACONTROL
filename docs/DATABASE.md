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

## Próximas migrations previstas

- Etapas 5–7: orçamentos/itens/snapshots, contratos/itens/documentos, relações de renovação, retirada e devolução.
- Etapas 9–10: solicitações do portal e documentos fiscais/retornos de adapters.

Este mapa é conceitual: não cria migrations antecipadas nem fixa schema sem analisar a etapa.

## Convenções

ID interno separado de código comercial, timestamps em UTC e autor quando aplicável. Soft delete conforme necessidade comercial, constraints nomeadas, chaves estrangeiras e unicidade explícitas. Não reutilizar textos exibidos como identidade. `base_number` e `renewal_number` terão relação com contrato original e unicidade adequada.

Valores financeiros: Decimal no Python; nunca float. SQLite NUMERIC não garante decimal exato: a Etapa 3 usa unidades mínimas inteiras e round trips testados; PostgreSQL pode usar NUMERIC. Nenhum campo monetário existe na Etapa 0.

Preço histórico e snapshots não podem ser sobrescritos. Operações de estoque/contrato/auditoria devem ser transacionais e impedir saldo negativo; concorrência será testada nas etapas de negócio. Não colocar arquivo SQLite em pasta de rede.

## Operação

Aplicar: `./scripts/migrate.ps1`. Consultar: `./scripts/migrate.ps1 -Action current`. Verificar drift: `./scripts/migrate.ps1 -Action check`. As reversões são testadas somente em bancos temporários; nunca reverter um banco comercial sem plano e cópia de segurança.

Trocar URL por PostgreSQL exigirá driver adequado, migração dos dados e validação de tipos/constraints, sem reescrever regras de domínio. Não declarar suporte PostgreSQL validado nesta etapa.

