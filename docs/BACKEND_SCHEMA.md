# LocaControl — Esquema do back-end

Versão documental 1.0 — 2026-10-11. Responsáveis: backend, dados e segurança.
Fontes consultadas: modelos e rotas de masters/imports; DATABASE e SECURITY. Não foi aplicado schema nesta sessão.

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
| Persistência | backend/app/persistence | Base e conexão SQLAlchemy |
| Migrations | backend/migrations/versions | Schema versionado 0001–0004 |

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

## 7. Relacionamentos existentes
- users → autoria comercial, auditoria e sessões.
- Customer 1:N CustomerAddress.
- Product 1:N Equipment, StockMovement e Price.
- Equipment 1:N StockMovement quando identificado.
- Price → Price anterior por supersedes_id.
- ImportBatch 1:N ImportOrigin.
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

DELETE comercial segue serviço e preservação de histórico, sem presumir remoção física.
Schemas exatos, filtros, paginação e payloads: backend/app/masters/schemas.py e imports/schemas.py. Identidade: catálogo em SECURITY.
Erros esperados: não autenticado, proibido, validação, não encontrado e conflito conforme implementação. Não inventar contrato de status code futuro.

## 9. Modelo futuro — PROPOSTO, sujeito a aprovação da etapa
| Domínio | Entidades conceituais | Relações/invariantes |
| --- | --- | --- |
| Orçamento (5) | Quote, QuoteItem, snapshots/transições | Cliente 1:N orçamentos; orçamento 1:N itens; número único; dinheiro exato |
| Contrato (6) | Contract, ContractItem, Document, TemplateVersion | Cliente e origem orçamento opcional; snapshots; documentos versionados |
| Operação (7) | Withdrawal/Item, Return/Item, relações de renovação/manutenção | Eventos por contrato/item/unidade; saldo pendente não negativo |
| Portal (9) | Vínculo user/customer, RenewalRequest | Escopo por cliente; solicitação distinta de renovação |
| Fiscal (10) | FiscalDocument, tentativas/retornos | Cliente/contrato/período/valor; correlação e idempotência |

Nomes são propostas, não tabelas criadas. Definir campos, FKs, cardinalidades e constraints antes de cada migration.
Contrato: base_number e renewal_number separados, relação à raiz e unicidade adequada. Definir representação de renovações e saldos para evitar duplicar obrigações.
Estados previstos no APP_FLOW; resolver cancelamento e vencimento antes de persistir enums.

## 10. Serviços e contratos futuros
Para cada caso de uso registrar: requisito PRD, entradas/schema, ator/permissão, validações, transação, efeitos, auditoria, retorno e conflitos.
Casos centrais: cálculo de orçamento; conversão única em contrato; atribuição de número; retirada; renovação; devolução; geração documental; solicitação portal; emissão/conciliação fiscal.
Rotas futuras devem ser propostas e revisadas; este documento não promete endpoints inexistentes.

## 11. Concorrência e migrations
Version nas edições; request_key no movimento; source_key na origem; BEGIN IMMEDIATE nas operações SQLite pertinentes.
Novos números e operações comerciais precisam de constraints + serviço + testes concorrentes.
Cadeia existente: 0001_foundation → 0002_identity → 0003_masters → 0004_imports.
Aplicação local de 0004 foi registrada em 08/10; não revalidada nesta sessão.
Comandos existentes: scripts/migrate.ps1; -Action current; -Action check. Aplicar migration exige plano/backup.
Downgrade/upgrade de teste somente em temporários. PostgreSQL ainda requer validação específica.

## 12. Segurança, arquivos e aceite
Downloads autenticados; portal deve filtrar cliente inclusive por ID. Segredos fora de responses/logs/auditoria.
Backup cobre DB + originais + futuros documentos.
Testar invariantes de dinheiro, estoque, snapshots, deduplicação, auditoria, isolamento, numeração e recuperação.
Atualizar este esquema junto com migrations e contratos de API; resultados em AI_HANDOFF/PROJECT_STATE.
