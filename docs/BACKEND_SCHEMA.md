# LocaControl — Esquema do back-end

Versão documental 1.1 — 2026-10-11. Responsáveis: backend, dados e segurança.
Fontes consultadas: modelos, serviços e rotas de masters, imports, quotes, contracts, reports, portal, fiscal e ops; migrations 0005–0010; DATABASE e SECURITY.

## 1. Convenções e autoridade
EXISTENTE indica entidade/rota encontrada; PROPOSTO indica evolução sem migration entregue.
Modelos/migrations são evidência do schema; regras oficiais definem comportamento. Tipos completos e defaults devem ser conferidos nos fontes antes de alterações.
IDs internos não são números comerciais. Dinheiro em centavos inteiros, quantidade em milésimos; Decimal nos serviços e strings decimais na API.
Stamp comercial: created_at inteiro UTC e created_by FK users. Editable acrescenta updated_at e version.
Não impor esses campos retroativamente a tabelas que têm estrutura diferente.

## 2. Módulos existentes
| Módulo | Fontes | Escopo |
| --- | --- | --- |
| Identidade | backend/app/auth | Sessão, usuários, RBAC e auditoria |
| Cadastros | backend/app/masters | Clientes, produtos, equipamentos, estoque e preços |
| Importação | backend/app/imports | Workbook, mapeamento, prévia, confirmação e relatórios |
| Orçamentos | backend/app/quotes | Cálculo, estados, numeração e PDF |
| Contratos e operação | backend/app/contracts | Contratos, numeração, modelos/documentos, retirada, devolução e renovação |
| Relatórios | backend/app/reports | Dashboard, resumo por cliente, relatórios e exportações |
| Portal | backend/app/portal | Vínculo conta–cliente, consultas isoladas e solicitações de renovação |
| Fiscal | backend/app/fiscal | Documentos fiscais, interface de provedor e simulação |
| Operação do sistema | backend/app/ops | Backup, verificação, agendamento e restauração |
| Núcleo | backend/app/core | Configuração (`config.py`) e data comercial UTC−3 (`clock.py`) |
| Persistência | backend/app/persistence | Base e conexão SQLAlchemy |
| Migrations | backend/migrations/versions | Schema versionado 0001–0010 |

## 3. Identidade — EXISTENTE
| Tabela | Estrutura/garantia principal |
| --- | --- |
| users | Identidade normalizada única, hash, ativo, troca obrigatória e autoria |
| roles / permissions | Catálogo com código único |
| user_roles / role_permissions | Associações com chaves compostas |
| auth_sessions | Hash SHA-256 do token, usuário e expiração UTC |
| login_throttles | Chave de limitação, contador e expiração |
| audit_logs | Autor, instante, ação, entidade e alterações sem segredos |

Detalhes e API em SECURITY. Não apagar usuário/auditoria pela API; preservar último administrador ativo.

## 4. Cadastros — EXISTENTE
| Entidade/tabela | Campos específicos | Integridade |
| --- | --- | --- |
| Customer / customers | id, person_type, legal_name, trade_name, document, state_registration, phone, mobile, email, contact, notes, is_active + Editable | PF/PJ por CHECK; document único; nome indexado |
| CustomerAddress / customer_addresses | id, customer_id, street, city, state, postal_code, label | FK cliente; índice customer_id |
| Product / products | id, code, name, description, category, unit, individual_tracking, is_active + Editable | code único; name indexado |
| Equipment / equipment | id, product_id, code, asset_tag, serial_number, brand, model, status, notes + Editable | FK produto; code/asset_tag/serial_number únicos; CHECK status |

asset_tag e serial_number podem ser nulos. Endereços têm cascade delete-orphan na relação ORM; isso não autoriza apagar cliente comercial fisicamente.
Documentos PF/PJ: formato/normalização/unicidade; não declarar consulta externa ou dígitos verificadores entregues.

## 5. Estoque e preços — EXISTENTE
| Entidade | Campos | Garantias |
| --- | --- | --- |
| StockMovement / stock_movements | id, product_id, equipment_id opcional, from_status opcional, to_status, quantity_milli, reason, request_key opcional + Stamp | quantidade > 0; estados válidos/diferentes; request_key único; FKs |
| Price / prices | id, product_id, period, effective_date, amount_cents opcional, reason, supersedes_id opcional + Stamp | valor nulo ou >= 0; período válido; FK de revisão |

Estados: DISPONIVEL, RESERVADO, LOCADO, MANUTENCAO, INDISPONIVEL, BAIXADO.
Períodos: DIARIA, SEMANAL, QUINZENAL, MENSAL. effective_date é string comercial YYYY-MM-DD.
Saldos são tratados pelo serviço com movimentos; não inventar tabela de saldo existente.
Preços revisados preservam anterior; significado de valor nulo deve seguir o serviço/schema, sem tratá-lo como zero.

## 6. Importação — EXISTENTE
| Entidade | Campos | Garantias |
| --- | --- | --- |
| ImportBatch / import_batches | id string(32), filename, checksum, created_at/by, imported_at/by opcionais, status, total_rows, successful_rows, warning_rows, failed_rows, ignored_rows, mapping/report JSON opcionais | autores FK users; default status UPLOADED |
| ImportOrigin / import_origins | id, source_key, batch_id, sheet, row_number, entity, entity_id, source JSON, warnings | source_key único; FK lote |

entity_id é referência polimórfica inteira, não FK comercial genérica. Não afirmar integridade referencial de destino via FK que não existe.
Original privado usa nome gerado pelo servidor. checksum/aba/linha/módulo permitem deduplicação de origem.
DRY RUN: savepoints/rollback comercial; confirmação: digest + revalidação sob transação; erro de conteúdo por linha e rollback global em falha técnica inesperada.

## 6A. Orçamentos — EXISTENTE (Etapa 5, migration 0005_quotes)
| Entidade | Campos | Garantias |
| --- | --- | --- |
| Quote / quotes | id, year, sequence, customer_id, customer_snapshot JSON, status, status_reason, start_date, valid_until, notes, total_cents, duplicated_from_id opcional + Editable | (year, sequence) único; CHECK status; total ≥ 0; FKs cliente/origem/autor |
| QuoteItem / quote_items | id, quote_id, position, product_id, product_code/product_name/unit (snapshot), quantity_milli, period, period_count, price_id opcional, table_price_cents, unit_price_cents, total_cents, end_date | quantidade e períodos > 0; período válido; valores ≥ 0; FKs |
| QuoteTransition / quote_transitions | id, quote_id, from_status opcional, to_status, reason, created_at, created_by | histórico append-only das mudanças de estado |

Número exibido `ORC-{year}-{sequence:06d}` é derivado, não coluna. Status persistidos: RASCUNHO, ENVIADO, APROVADO, REJEITADO, CANCELADO, CONVERTIDO; EXPIRADO é derivado na leitura e nos filtros. `price_id` aponta a revisão de preço usada; `table_price_cents` é o snapshot e nunca é relido sem pedido explícito.
Cálculo em `backend/app/quotes/calc.py` (puro, Decimal → inteiros); regras em `service.py`; PDF em `pdf.py`.

## 6B. Contratos e documentos — EXISTENTE (Etapa 6, migration 0006_contracts)
| Entidade / tabela | Campos | Garantias |
| --- | --- | --- |
| Contract / contracts | id, base_number, renewal_number, root_id, previous_id, customer_id, customer_snapshot JSON, quote_id opcional, origin, price_option opcional, status, status_reason, start_date, end_date, due_date opcional, notes, total_cents + Editable | (base_number, renewal_number) único; quote_id único; CHECK status, origin, price_option; base_number > 0 e renewal_number ≥ 0; total ≥ 0; índices em customer_id, root_id, status, due_date |
| ContractItem / contract_items | id, contract_id, position, product_id, product_code/product_name/description/unit/individual_tracking (snapshot), quantity_milli, period, period_count, price_id opcional, table_price_cents, unit_price_cents, total_cents, start_date, end_date, source_item_id opcional, carried_milli | quantidade e períodos > 0; período válido; valores ≥ 0; 0 ≤ carried_milli ≤ quantity_milli |
| ContractEvent / contract_events | id, contract_id, chain_id, kind, description, created_at, created_by | linha do tempo append-only por cadeia |
| ContractTemplate / contract_templates | id, name, version, body, is_provisional, is_active, created_at, created_by opcional | (name, version) único |
| ContractDocument / contract_documents | id, contract_id, template_id, version, stored_name, checksum, size, status, reason, signed_at/by opcionais, created_at/by | (contract_id, version) único; CHECK status GERADO/ASSINADO/SUBSTITUIDO |
| AppSetting / app_settings | key, value JSON, updated_at, updated_by opcional | chaves em uso: `contracts.next_number` e `backup` |

Código exibido `base_number[.renewal_number]` é derivado. Status gravados: RASCUNHO, AGUARDANDO_RETIRADA, ATIVO, ENCERRADO, CANCELADO; VENCENDO e VENCIDO são derivados de `due_date` na leitura e nos filtros. Origens: DIRETO, ORCAMENTO, RENOVACAO, IMPORTADO (esta última sem uso: não há conversão do Excel). Opções de preço da renovação: ANTERIORES, ATUAIS, NEGOCIADOS.
Arquivos PDF ficam em `data/documents` (`LOCACONTROL_DOCUMENT_DIRECTORY`) com nome UUID; o arquivo é escrito depois da linha e o download confere o SHA-256. A migration semeia um modelo provisório ativo.
Fontes: `backend/app/contracts/models.py`, `service.py` (regras, numeração, listagem), `documents.py` (modelos e PDF), `schemas.py`, `routes.py`.

## 6C. Operação — EXISTENTE (Etapa 7, migration 0006_contracts)
| Entidade / tabela | Campos | Garantias |
| --- | --- | --- |
| Withdrawal / withdrawals | id, contract_id, occurred_on, notes, request_key + Stamp | request_key único |
| WithdrawalItem / withdrawal_items | id, withdrawal_id, contract_item_id, quantity_milli, equipment_id opcional | quantidade > 0 |
| RentalReturn / returns | id, contract_id, occurred_on, notes, request_key + Stamp | request_key único |
| ReturnItem / return_items | id, return_id, contract_item_id, quantity_milli, equipment_id opcional, condition, destination, notes | quantidade > 0; CHECK condition BOM/AVARIADO; destination DISPONIVEL/MANUTENCAO |
| ItemUnit / contract_item_units | id, contract_item_id, equipment_id, state | CHECK state EM_POSSE/DEVOLVIDO/RENOVADO |

Saldos não são colunas. Por linha: retirado = soma de withdrawal_items; devolvido = soma de return_items; renovado = soma de carried_milli das linhas que a continuam. Com o cliente = retirado + carried_milli − devolvido − renovado; a retirar = quantity_milli − carried_milli − retirado. O serviço recusa operações que excedam esses saldos.
Retirada e devolução gravam StockMovement (DISPONIVEL → LOCADO; LOCADO → destino) e auditoria na mesma transação; renovação não grava movimento. Regras em `backend/app/contracts/operations.py`. `MasterService` bloqueia saída manual de LOCADO que contradiga a custódia de contrato ativo.

## 6D. Portal — EXISTENTE (Etapa 9, migration 0008_portal)
| Entidade / tabela | Campos | Garantias |
| --- | --- | --- |
| CustomerUser / customer_users | user_id (PK), customer_id, created_at, created_by | uma conta → um cliente; índice customer_id |
| RenewalRequest / renewal_requests | id, contract_id, customer_id, requested_by, period, period_count, notes, status, decision_reason, decided_by/at opcionais, created_at | CHECK status PENDENTE/APROVADA/RECUSADA/CANCELADA; período válido; period_count > 0 |

Uma solicitação pendente por contrato é regra de serviço, não constraint. A solicitação não aponta para um contrato de renovação: aprovar não cria renovação. Fontes: `backend/app/portal`.

## 6E. Fiscal — EXISTENTE em simulação (Etapa 10, migration 0009_fiscal)
| Entidade / tabela | Campos | Garantias |
| --- | --- | --- |
| FiscalDocument / fiscal_documents | id, customer_id, customer_snapshot JSON, contract_id opcional, period_start, period_end, amount_cents, description, status, provider, environment, request_key, provider_ref, number, series, access_key, error_message, cancel_reason, pdf_name, xml_name + Editable | request_key único; CHECK status; amount_cents > 0; period_end ≥ period_start |
| FiscalEvent / fiscal_events | id, document_id, action, status, response JSON, created_at, created_by | trilha append-only de CREATE/EMIT/STATUS/CANCEL |

Interface `FiscalProvider` em `backend/app/fiscal/provider.py`; único adapter: `fake.py` (ambiente SIMULACAO). PDF/XML em `data/fiscal` (`LOCACONTROL_FISCAL_DIRECTORY`). Nenhum adapter de provedor real existe.

## 6F. Relatórios e backup — EXISTENTE (Etapas 8 e 11)
Relatórios não têm tabelas: `backend/app/reports/service.py` consulta as entidades acima e `export.py` gera Excel/PDF em memória. A migration 0007_reports só cria a permissão `reports.read`.
Backup não tem tabela própria: configuração em `app_settings` (chave `backup`), conjuntos `.zip` na pasta configurada, lógica em `backend/app/ops/backup.py`. A migration 0010_backups só cria a permissão `backups.manage`. Desde a ADR-024 o histórico de execuções fica em `backup-history.json`, ao lado do banco (fora da base).

## 6H. Estações da rede — P1-D (ADR-025)
`auth_sessions.station_id` (String 36, índice; migration 0012_stations) liga a sessão à estação pareada; nulo = computador principal. A lista de estações, o código de pareamento e o histórico da rede ficam em `stations.json`, ao lado do banco, fora da base e dos backups (`backend/app/network/stations.py`).

## 6G. Rascunhos automáticos — EXISTENTE (P1-C, ADR-024)
| Model / tabela | Campos | Restrições |
| --- | --- | --- |
| FormDraft / form_drafts | id, owner, kind, scope, payload JSON, base_version opcional, created_at, updated_at, expires_at (índice) | único (owner, kind, scope); migration 0011_drafts; sem FK: o conteúdo é opaco e nenhum serviço de domínio o lê |

## 7. Relacionamentos existentes
- Customer 1:N Quote; Quote 1:N QuoteItem e QuoteTransition; Quote → Quote de origem por duplicated_from_id; QuoteItem → Product e Price.
- users → autoria comercial, auditoria e sessões.
- Customer 1:N CustomerAddress.
- Product 1:N Equipment, StockMovement e Price.
- Equipment 1:N StockMovement quando identificado.
- Price → Price anterior por supersedes_id.
- ImportBatch 1:N ImportOrigin.
- Customer 1:N Contract; Quote 0..1 Contract (quote_id único); Contract → Contract raiz (root_id) e anterior (previous_id).
- Contract 1:N ContractItem, ContractEvent, ContractDocument, Withdrawal e RentalReturn; ContractItem → ContractItem de origem (source_item_id) nas renovações.
- ContractItem 1:N WithdrawalItem, ReturnItem e ItemUnit; ItemUnit, WithdrawalItem e ReturnItem → Equipment quando há unidade física.
- ContractTemplate 1:N ContractDocument.
- User 0..1 CustomerUser → Customer; Contract 1:N RenewalRequest.
- Customer 1:N FiscalDocument; Contract 0..N FiscalDocument; FiscalDocument 1:N FiscalEvent.
Relações de domínio não substituem constraints reais; consultar migration para política de exclusão.

## 8. Catálogo de APIs existentes
Prefixos: /api para comercial; /api/imports para importação.

| Recurso | Métodos/rotas | Permissão |
| --- | --- | --- |
| Clientes | GET/POST /customers; GET/PUT/DELETE /customers/{id} | customers.read/write conforme ação |
| Produtos | GET/POST /products; GET/PUT/DELETE /products/{id} | products.read/write |
| Equipamentos | GET/POST /equipment; GET/PUT/DELETE /equipment/{id}; POST /equipment/{id}/status | equipment.read/write |
| Estoque | GET /stock; GET/POST /stock/movements | stock.read/write |
| Preços | GET /prices/effective; GET/POST /prices; GET/PUT/DELETE /prices/{id} | prices.read/write |
| Importação | GET /fields e raiz; POST /upload; GET /{id} | imports.read/write conforme ação |
| Conversão | POST /{id}/preview, /confirm, /new-conversion | imports.write e escrita de destino conforme serviço |
| Arquivos | GET /{id}/original e /report | imports.read |
| Orçamentos | GET /api/quotes (q, status, customer_id, offset, limit); GET /api/quotes/{id}; GET /api/quotes/pricing; GET /api/quotes/{id}/pdf | quotes.read |
| Orçamentos — escrita | POST /api/quotes; PUT /api/quotes/{id} (version, refresh_prices); POST /{id}/duplicate; POST /{id}/send, /reject, /cancel, /reopen | quotes.write; preço diferente da tabela exige quotes.negotiate |
| Orçamentos — aprovação | POST /api/quotes/{id}/approve | quotes.approve |
| Contratos — leitura | GET /api/contracts (q, status, customer_id, origin, product, equipment, period, start_from, start_to, offset, limit); GET /api/contracts/{id}; GET /api/contracts/{id}/preview.pdf; GET /api/contracts/documents/{id}/download; GET /api/contracts/numbering; GET /api/contracts/templates | contracts.read |
| Contratos — escrita | POST /api/contracts; PUT /api/contracts/{id}; POST /api/contracts/from-quote/{quote_id}; POST /api/contracts/{id}/confirm, /cancel, /close, /renew; POST /api/contracts/{id}/documents; POST /api/contracts/documents/{id}/sign | contracts.write; preço diferente da tabela exige contracts.negotiate |
| Contratos — configuração | PUT /api/contracts/numbering; POST /api/contracts/templates | contracts.configure |
| Operação | POST /api/contracts/{id}/withdrawals; POST /api/contracts/{id}/returns | operations.write |
| Dashboard | GET /api/dashboard; GET /api/customers/{id}/summary | contracts.read |
| Relatórios | GET /api/reports; GET /api/reports/{key} (date_from, date_to, customer_id, product_id, q, offset, limit); GET /api/reports/{key}/export (format xlsx ou pdf) | reports.read |
| Portal | GET /api/portal/dashboard, /contracts, /contracts/{id}, /equipment, /documents, /documents/{id}/download, /quotes, /quotes/{id}, /quotes/{id}/pdf, /profile, /renewal-requests; POST /api/portal/renewal-requests; POST /api/portal/renewal-requests/{id}/cancel | portal.access e conta vinculada a um cliente |
| Portal — lado interno | GET /api/users/{id}/customer; PUT /api/users/{id}/customer; GET /api/renewal-requests; POST /api/renewal-requests/{id}/decide | users.read; users.write; contracts.read; contracts.write, nessa ordem |
| Fiscal — leitura | GET /api/fiscal/provider; GET /api/fiscal/documents (status, customer_id, contract_id, offset, limit); GET /api/fiscal/documents/{id}; GET /api/fiscal/documents/{id}/pdf e /xml | fiscal.read |
| Fiscal — escrita | POST /api/fiscal/documents; POST /api/fiscal/documents/{id}/emit, /refresh, /cancel | fiscal.write |
| Backup | GET /api/backups; GET /api/backups/status; PUT /api/backups/config; POST /api/backups; POST /api/backups/import; POST /api/backups/{name}/verify; GET /api/backups/{name}/download; POST /api/backups/{name}/restore | backups.manage |
| Estações (rede local) | POST /api/stations/pair (sem sessão: rede da loja + código); GET /api/stations; POST e DELETE /api/stations/pairing; POST /api/stations/{id}/revoke; GET /api/stations/{id}/activity | edição local; tudo exceto `pair` só no computador principal |
| Rascunhos | GET /api/drafts; GET, PUT e DELETE /api/drafts/{kind}/{scope} | sessão; permissão da operação definitiva (quotes.write, contracts.write ou operations.write) |

Chaves de relatório: active_rentals, due_soon, overdue, rented_products, available_products, equipment_by_customer, equipment_history, renewals, returns, contracted_revenue, top_products, top_customers.
Retirada, devolução e criação de documento fiscal exigem `request_key` (UUID) para repetição segura. Ações de estado de contrato e fiscal exigem `version`. Restauração exige `confirmation` = `RESTAURAR <nome>` e `password`.

DELETE comercial segue serviço e preservação de histórico, sem presumir remoção física.
Schemas exatos, filtros, paginação e payloads: backend/app/masters/schemas.py e imports/schemas.py. Identidade: catálogo em SECURITY.
Erros esperados: não autenticado, proibido, validação, não encontrado e conflito conforme implementação. Não inventar contrato de status code futuro.

## 9. O que ainda NÃO existe — PROPOSTO
Orçamento, contrato, operação, portal e fiscal deixaram de ser propostas em 11/10/2026 (seções 6A–6F). Continuam sem implementação e sem schema:

| Item | Situação | Depende de |
| --- | --- | --- |
| Conversão do histórico de contratos/renovações do Excel (IMP-04B) | Sem mapeamento; a origem IMPORTADO existe no CHECK mas nenhum serviço a grava | Excel real |
| Reserva de estoque na confirmação do contrato | Não implementada; RESERVADO não é usado por contratos | Decisão de negócio (ADR-016) |
| Upload do documento assinado digitalizado e geração de DOCX | Não existem; assinatura é só marcação | Modelo real e decisão do usuário |
| Registro próprio de manutenção (ordem, intervenção, custo) | Não existe; há apenas o estado MANUTENCAO e os movimentos | Definição de escopo |
| Adapter de provedor fiscal real, callbacks e conciliação externa | Não existem; só o provedor de simulação | Contabilidade, provedor e credenciais de sandbox |
| Renovação criada automaticamente a partir da solicitação do portal | Não existe por decisão (ADR-019) | — |
| Multiempresa (tenant) | Não existe | Decisão de publicação |

Não tratar estes itens como entregues nem prometer endpoints para eles.

## 10. Serviços e contratos futuros
Para cada novo caso de uso registrar: requisito PRD, entradas/schema, ator/permissão, validações, transação, efeitos, auditoria, retorno e conflitos, e atualizar as seções 6–8 junto com a migration.

## 11. Concorrência e migrations
Version nas edições; request_key no movimento; source_key na origem; BEGIN IMMEDIATE nas operações SQLite pertinentes.
Novos números e operações comerciais precisam de constraints + serviço + testes concorrentes.
Cadeia existente: 0001_foundation → 0002_identity → 0003_masters → 0004_imports → 0005_quotes → 0006_contracts → 0007_reports → 0008_portal → 0009_fiscal → 0010_backups → 0011_drafts → 0012_stations.
Todas aplicadas ao banco local em 11/10 após cópias prévias; ver DATABASE.
Numeração de contrato e de renovação, retirada concorrente do mesmo saldo e criação concorrente têm testes em `test_contracts.py` e `test_operations.py`.
Comandos existentes: scripts/migrate.ps1; -Action current; -Action check. Aplicar migration exige plano/backup.
Downgrade/upgrade de teste somente em temporários. PostgreSQL ainda requer validação específica.

## 12. Segurança, arquivos e aceite
Downloads autenticados; o portal filtra pelo cliente vinculado inclusive por ID e em downloads (404 para registro alheio). Segredos fora de responses/logs/auditoria.
Backup cobre banco + originais do Excel + documentos de contrato + arquivos fiscais, com manifesto.
Testar invariantes de dinheiro, estoque, snapshots, deduplicação, auditoria, isolamento, numeração e recuperação.
Atualizar este esquema junto com migrations e contratos de API; resultados em AI_HANDOFF/PROJECT_STATE.
