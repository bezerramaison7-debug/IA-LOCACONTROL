# LocaControl — Decisões técnicas

Convenção das ADRs de 11/10/2026: "decisão do usuário" é regra comercial respondida por ele; "decisão do implementador" é escolha técnica revisável, registrada para não ser confundida com regra de negócio. Autorização de processo dada pelo usuário em 11/10: commits por etapa validada na branch `dev/etapas-4-12`, a partir do baseline `2b3d1d2` em `master`.

## ADR-024 — Proteção automática: backup por intervalo e rascunhos (2026-11-02)

ACEITA, P1-C. Decisões do usuário (P1_BRIEFING itens 9 a 12): backup automático a cada 20 minutos por padrão, com opção de 60; rascunhos guardados **no servidor**, por computador/estação, com expiração de **7 dias**. Decisões do implementador, revisáveis:

- **Frequência** em `app_settings.backup.frequency` = `20min` | `60min` | `daily`. Instalação nova (sem linha salva) nasce **ligada, a cada 20 minutos**. Linha salva antes desta ADR, sem `frequency`, continua **diária no horário salvo** (compatibilidade); `time`, `keep` e `directory` mantêm o significado. No intervalo, o backup é devido quando o conjunto regular mais novo (manual ou automático) ou a última verificação "sem alterações" tem a idade do intervalo.
- **Sem cópia repetida**: antes de copiar, o agendador compara uma impressão digital (tamanho e data de alteração do banco e de cada arquivo das pastas) com a do último conjunto; sem mudança, registra `unchanged_at` e não grava outro `.zip`. Evita que horas ociosas empurrem cópias úteis para fora da retenção.
- **Retenção** (`keep` = dias): todos os conjuntos regulares das últimas 24 horas, mais o mais novo de cada um dos `keep` dias mais recentes (com um conjunto por dia equivale ao antigo "manter N"). `_pre-restore` e `_importado` ficam fora da retenção.
- **Histórico** em `backup-history.json`, ao lado do banco (fora do `.zip` e da impressão digital; sobrevive a restaurações): as 100 últimas execuções com início, fim, tipo, resultado, nome, tamanho, motivo da falha (texto curto, sem caminho) e resultado da segunda cópia; mais `last_success`, `last_failure`, `fingerprint`, `unchanged_at`. `GET /api/backups/status` resume e calcula o aviso (falha na última execução; desativado; nenhum backup; último sucesso mais velho que 3 intervalos; falha na segunda cópia). A interface mostra em Backups e, para `backups.manage`, na Visão geral.
- **Sem sobreposição**: o agendador tenta `OPERATION_LOCK` sem esperar; ocupado (backup manual ou restauração), pula o minuto. Falha automática é tentada de novo após 5 minutos, não a cada minuto. Dois conjuntos no mesmo segundo: o segundo espera o próximo segundo.
- **Segunda cópia** opcional (`mirror_directory`): cópia do `.zip`, conferência por SHA-256, troca atômica e retenção também lá; falha não invalida o backup principal, fica no histórico e gera aviso.
- **Restauração com a pasta de backups em outro disco**: a preparação (`.restore_*`), as pastas substituídas (`replaced_*`) e o banco temporário ficam ao lado de cada pasta de dados, no disco dela; o `.zip` só é lido. A recusa "pasta de backups em outro disco" (P0) deixou de existir. `replaced_files` passa a ser o caminho completo.
- **Importação** (`POST /api/backups/import`, `backups.manage`, até 8 GiB): o `.zip` enviado é gravado como `.import-*.part`, verificado por inteiro (mesma verificação da restauração) e só então renomeado para `locacontrol_<created_at do manifesto>_importado.zip`; reprovado não deixa arquivo; o mesmo conteúdo já presente responde 409 com o nome existente. Auditoria `backup.imported`. A trava de escrita do banco é liberada antes da cópia.
- **Rascunhos**: tabela `form_drafts` (migration `0011_drafts`), chave única (owner, kind, scope); `owner` = `user:<id>` (a edição em rede acrescenta a estação); `kind` ∈ quote, contract, withdrawal, return, renewal; `scope` = `new` ou o id do registro; `payload` JSON opaco até 200 KB; `base_version` do registro. API `/api/drafts` (GET lista sem conteúdo; GET/PUT/DELETE por `{kind}/{scope}`), exigindo a permissão da operação definitiva. PUT é substituição completa, portanto repetível. Rascunhos não são auditados e nenhum serviço de estoque, contrato, documento ou relatório os lê. Expiram 7 dias após a última alteração; os vencidos são apagados em cada gravação e não são oferecidos.
- **Interface**: salva 1,2 s depois da última alteração; não salva nada antes de o usuário recuperar ou descartar o rascunho oferecido; falha mostra aviso e tenta de novo em 10 s; depois de uma renovação de sessão a gravação do rascunho é repetida na hora, por ser substituição completa (as escritas definitivas nunca são); envio bem-sucedido apaga o rascunho. Retirada e devolução guardam o `request_key`, então reenviar um rascunho de operação já registrada é reconhecido como repetição.
- **Sessão local preservada**: na edição local, 401 (sessão expirada) ou 403 com `X-LocaControl-Retry: csrf` (sessão renovada em outra aba) renova a sessão por `/api/auth/me` sem desmontar a tela; leitura é repetida uma vez; escrita **nunca** é repetida automaticamente — o usuário recebe a mensagem e reenvia o formulário intacto. A verificação de sessão ao focar a janela não derruba a tela por falha de rede ou 5xx.

- **Limites de armazenamento (A3, decisão do arquiteto de 2026-11-03)**: `max_total_gb` (teto da pasta de backups, padrão 10 GB), `min_free_gb` (padrão 10 GB) e `min_free_percent` (padrão 15 %) em `app_settings.backup`; a reserva de espaço livre é o maior dos dois mínimos. Antes de gravar, estimativa = banco + arquivos (+ manifesto) e pico = estimativa + cópia temporária do banco; se o pico não couber mantendo a reserva, ou o teto não puder ser respeitado, nada é gravado (507, falha registrada, aviso). Retenção segura sob pressão: saem primeiro as cópias intermediárias mais antigas, depois as diárias mais antigas; nunca a mais recente, `_pre-restore` ou `_importado`. Recuperação (cópia antes de restaurar, importação) ignora o teto, nunca a reserva; a restauração confere o espaço no disco dos dados antes de tocar em qualquer coisa. Recusa por espaço é tentada de novo a cada hora. Política em `app/ops/storage.py` (funções puras).
- **Durabilidade (M2)**: conjuntos, histórico, segunda cópia e importação são gravados com `fsync` do arquivo antes da renomeação e da pasta depois (`app/core/durable.py`; no Windows a pasta não pode ser aberta para `fsync` e a renomeação fica a cargo do journal do NTFS). O conjunto é relido e verificado antes de contar como backup; reprovado vai para `.<nome>.reprovado`. Antes de gravar só sai o que a reserva exige; teto e retenção rodam depois de um conjunto verificado, então um conjunto ruim nunca apaga os anteriores.

Limites: o backup automático depende do computador e do servidor ligados; a segunda cópia só protege se o outro disco estiver conectado; **com o padrão de 15 %, um disco grande e cheio (por exemplo 1 TB com menos de 150 GB livres) suspende os backups automáticos até liberar espaço ou ajustar o percentual** (o aviso aparece em Backups e na Visão geral); a verificação após a gravação pode ler do cache do sistema operacional, não necessariamente da superfície do disco; o rascunho perde as alterações feitas com o servidor fora do ar se o navegador for fechado antes de ele voltar.

## ADR-023 — Edição local sem login (2026-11-01)

ACEITA. Decisão do usuário (P1, `P1_BRIEFING.md` item 1 e 7): no uso local não há senha, login, criação de administrador nem gestão de usuários/perfis, e o portal do cliente fica desativado. Substitui, **na edição local**, a ADR-022 (admin/admin) e as partes de login da ADR-010; a edição com login continua existindo e é o padrão do código.

Decisões do implementador sobre a forma:

- Chave `LOCACONTROL_LOCAL_MODE` (`Settings.local_mode`), padrão `false`. Com `false` nada muda. A edição empacotada e o atalho passarão a ligá-la (PRs de instalador/rede); `scripts/launch.ps1` já lê a chave (ambiente ou `.env`) e, ligada, não cria `admin/admin` nem mostra o aviso de primeiro acesso.
- Identidade da instalação: `app_settings` chave `installation` = `{"id": uuid4, "created_at"}`, criada no startup (em qualquer edição) se não existir e nunca regenerada. Vive no banco, então um backup restaurado traz a identidade que tinha.
- Operador local: conta de sistema `operador.local` ("Operador local", perfil ADMINISTRADOR, `must_change_password=false`, senha aleatória que ninguém conhece), criada uma vez no startup ou no primeiro `/api/auth/me` e reutilizada; as FKs (`created_by`, `actor_id`, `updated_by`...) apontam para ela. Contas existentes não são tocadas.
- Sessão automática: em modo local, `GET /api/auth/me` sem sessão válida abre uma sessão do operador com o mesmo cookie HttpOnly/SameSite Strict e devolve o `csrf_token`, **somente** se o par TCP for loopback, o `Host` for `localhost`/`127.0.0.1`/`[::1]`, o cabeçalho `X-LocaControl-Request: 1` estiver presente e a `Origin`, se enviada, estiver entre as permitidas. Fora disso, 401. Expiração, CSRF e verificação de origem nas escritas ficam iguais. Estações da rede serão autorizadas por pareamento (PR de rede).
- Auditoria: ações do operador gravam `actor_label = "operador local · instalação <8 primeiros do id>"`. O rótulo diz de onde veio a ação; **não identifica uma pessoa**. Cada sessão aberta é auditada (`local_session.opened`).
- Rotas desativadas (404 por guarda explícita `not_in_local_mode`): login, troca de senha, edição do próprio perfil, usuários, perfis, permissões e todo o roteador do portal (inclusive vínculo de conta e solicitações de renovação). Auditoria continua disponível. A matriz completa está em `SECURITY.md`.
- Restauração: sem senha; continuam a frase exata `RESTAURAR <nome>`, o modo manutenção e a cópia `_pre-restore`.

Riscos aceitos: qualquer pessoa com acesso ao computador (ou a um programa rodando nele) usa o sistema com todas as funções, incluindo restaurar backup; não há identificação individual nas ações. Mitigações: o servidor escuta só em `127.0.0.1` (launcher), a sessão só nasce para pedidos locais e com o cabeçalho do app, e a restauração continua com frase, manutenção e cópia prévia. Uma conta humana chamada exatamente `operador.local`, se existir, seria reutilizada como operador.

## ADR-022 — Conta inicial admin/admin com troca obrigatória (2026-10-11)

ACEITA na edição com login; substituída pela ADR-023 na edição local. Decisão do usuário: como o sistema roda na máquina do próprio usuário, o primeiro acesso passa a ser `admin` / `admin`, sem terminal. Substitui, para a instalação local, a regra da ADR-010 de não existir senha fixa. Decisão do implementador sobre a forma: a conta é criada por `scripts/launch.ps1` (`python -m app.auth.cli default`) somente quando a tabela de usuários está vazia, nunca recriada, e nasce com `must_change_password`, de modo que a API recusa qualquer função até a troca por uma senha de 12+ caracteres; a criação é auditada (`bootstrap.default_created`). O bootstrap interativo (`scripts/admin.ps1`) continua disponível. Risco aceito e documentado: entre a instalação e a troca, quem alcançar o sistema entra como administrador; por isso esta conta não deve existir em instalação exposta em rede ou na internet — antes de publicar, criar o administrador pelo bootstrap interativo ou trocar a senha antes de liberar o acesso.

## ADR-021 — Backup, restauração e inicialização no Windows (2026-10-11)

ACEITA, backend e scripts da Etapa 11. Decisões do implementador, revisáveis.

- Conjunto de backup é um único `.zip` (`locacontrol_AAAA-MM-DD_HHMMSS.zip`) com cópia consistente do banco (API de backup online do SQLite + `integrity_check`), as pastas `imports`, `documents` e `fiscal` e um `manifest.json` com SHA-256 de cada arquivo, revisão Alembic e versão do app. O exemplo do plano citava um `.db` isolado; o zip foi escolhido porque banco sem os arquivos não restaura documentos nem originais do Excel.
- Configuração (ativado, horário, retenção, pasta) fica em `app_settings` chave `backup`; padrão desativado, 22:00, 14 conjuntos, pasta `data/backups`. Um agendador em thread verifica a cada minuto se o backup diário é devido; a retenção remove só conjuntos regulares, nunca as cópias `_pre-restore`.
- Restauração exige a frase exata `RESTAURAR <nome do arquivo>` e a senha do próprio usuário; verifica o conjunto, recusa revisão desconhecida/mais nova, cria cópia prévia `_pre-restore`, move as pastas atuais para `replaced_<data>` (nunca apaga) e aplica migrations se o conjunto for de revisão anterior. Disponível apenas para SQLite local.
- Inicialização: `Iniciar LocaControl.cmd` → `scripts/launch.ps1` (confere saúde/porta, copia o banco para `data/backups/pre-upgrade-*.db` antes de qualquer upgrade de schema, sobe o servidor oculto com logs em `data/logs`, abre o navegador). `Parar LocaControl.cmd` → `scripts/stop.ps1` encerra só o processo registrado e conferido. `scripts/update.ps1` reinstala dependências e recompila a interface sem tocar em `data/`.
- Não existe configuração dedicada de logging nem rotação: os logs são a saída do servidor redirecionada pelo `launch.ps1`.

## ADR-020 — Fiscal desacoplado e somente simulação (2026-10-11)

ACEITA, backend da Etapa 10. Decisões do implementador; nenhuma regra tributária foi definida.

- `FiscalProvider` (emit, status, cancel, get_pdf, get_xml) em `app/fiscal/provider.py`; o domínio não depende de fornecedor. O único adapter existente é `FakeFiscalProvider` (`LOCACONTROL_FISCAL_PROVIDER=fake`, ambiente `SIMULACAO`); qualquer outro valor responde 409 "Provedor fiscal não configurado".
- Documentos da simulação são marcados `is_simulation`, e PDF/XML trazem "SIMULAÇÃO — documento sem valor fiscal". Nada é transmitido a órgão ou provedor.
- `request_key` (UUID do cliente, único) acompanha toda tentativa para que repetição não gere segundo documento. Cada chamada ao provedor grava um `FiscalEvent` com o retorno bruto, na mesma transação da auditoria.
- A espécie do documento é texto livre em `LOCACONTROL_FISCAL_DOCUMENT_KIND`; o sistema não infere tipo fiscal da locação.
- PENDENTE: regras com a contabilidade, escolha do provedor e credenciais de sandbox. Sem isso não há adapter real nem homologação.

## ADR-019 — Portal do cliente e isolamento (2026-10-11)

ACEITA, backend da Etapa 9. Decisões do implementador, revisáveis.

- Uma conta de portal vê exatamente um cliente (`customer_users`, PK `user_id`). Só usuário com perfil exclusivamente CLIENTE pode ser vinculado; sem vínculo o portal responde 403 com orientação.
- Toda consulta é filtrada pelo cliente do vínculo. Registro de outro cliente responde 404, nunca 403, para não confirmar a existência do identificador.
- Alterar ou remover o vínculo revoga todas as sessões da conta.
- O portal não mostra contratos em rascunho, documentos SUBSTITUÍDOS nem orçamentos em rascunho/cancelados; o cadastro é somente leitura.
- Solicitação de renovação é registro próprio (`renewal_requests`): uma pendente por contrato, cancelável pelo cliente. Aprovar ou recusar apenas registra a decisão (recusa exige motivo); a renovação continua sendo feita pelo funcionário no contrato.
- Permissão `portal.access` concedida somente ao perfil CLIENTE.

## ADR-018 — Dashboard, relatórios e exportações (2026-10-11)

ACEITA, backend da Etapa 8. Decisões do implementador.

- Indicadores e relatórios são calculados na consulta a partir de contratos, itens, movimentos e eventos reais; não há tabela de agregados nem cache.
- Doze relatórios em catálogo fixo (`app/reports/service.py`), filtros comuns (datas, cliente, produto, busca) e exportação Excel (openpyxl, números e datas tipados) ou PDF (reportlab) gerados em memória pela mesma consulta.
- "Valor contratado" é a soma dos contratos conforme pactuado; os relatórios de receita levam a nota de que não representam pagamentos recebidos.
- `GET /api/dashboard` e o resumo por cliente exigem `contracts.read`; o catálogo e as exportações exigem `reports.read` (administrador, comercial e financeiro).

## ADR-017 — Documentos e modelos de contrato (2026-10-11)

ACEITA, backend da Etapa 6. Decisão do usuário: usar agora um modelo PROVISÓRIO, claramente identificado, até ele fornecer o modelo real da locadora.

- A migration 0006 semeia um modelo provisório (`is_provisional`); todo PDF gerado a partir dele imprime o aviso "MODELO PROVISÓRIO".
- Modelos são texto com placeholders `{{ campo }}` validados contra uma lista fechada, mais os blocos `items`, `totals` e `signatures`. Publicar cria nova versão ativa; as anteriores ficam para histórico.
- Decisões do implementador: somente PDF (reportlab); DOCX não é gerado. Documento gerado é imutável, com nome UUID em `data/documents`, SHA-256 e tamanho; o download confere o checksum e recusa arquivo alterado fora do sistema.
- Nova geração marca as versões apenas GERADAS como SUBSTITUÍDAS. Documento ASSINADO nunca é substituído; havendo assinado, nova versão exige motivo.
- "Assinado" é uma marcação (quem e quando). Não existe upload do documento assinado digitalizado.
- Documento só é gerado após a confirmação; o rascunho oferece prévia em PDF sem gravar.

## ADR-016 — Ciclo operacional, custódia e renovação (2026-10-11)

ACEITA, backend da Etapa 7. Decisões do implementador, revisáveis.

- Não há reserva de estoque na confirmação do contrato: o plano pede Disponível → Locado na retirada, e é isso que existe. O estado RESERVADO do estoque não é usado pelos contratos.
- Retirada e devolução são idempotentes por `request_key` e atômicas com movimentos de estoque e auditoria. Produto por unidade exige uma unidade física por unidade retirada/devolvida; `contract_item_units` registra qual equipamento está com qual linha.
- Renovação nasce já ATIVA em uma única operação: recebe o próximo `renewal_number` da mesma base e transfere a custódia (`carried_milli`, unidades RENOVADO → EM_POSSE na nova linha) sem movimentar estoque, pois os bens não saíram do cliente.
- O contrato anterior encerra sozinho quando nada resta com o cliente nem a retirar. Encerramento manual existe para contrato ativo cujo restante nunca foi retirado, com motivo.
- Devolução: condição BOM → Disponível por padrão (pode ir para Manutenção); AVARIADO → Manutenção obrigatoriamente.
- Movimento manual de estoque não pode contradizer a custódia: saída manual de Locado é bloqueada quando a quantidade ou a unidade está com cliente por contrato ativo (commit `2b44e8e`).

## ADR-015 — Contratos: numeração e estados derivados (2026-10-11)

ACEITA, backend da Etapa 6. Decisões do usuário em 11/10:

- Numeração com próximo número configurável: o sistema usa o maior número existente + 1; o administrador pode definir o número inicial; sem configuração começa em 1.
- "Vencendo" e "vencido" são calculados pela data de devolução, não gravados.
- Antecedência de "vencendo": 3 dias, configurável em `LOCACONTROL_CONTRACT_DUE_SOON_DAYS` (0 a 60).

Decisões do implementador: identidade é o `id` interno; o código exibido é `base_number` ou `base_number.renewal_number`, com unicidade (base_number, renewal_number) e alocação sob BEGIN IMMEDIATE. O próximo número fica em `app_settings` e só pode ser definido acima do maior já usado (permissão `contracts.configure`). Estados gravados: RASCUNHO, AGUARDANDO_RETIRADA, ATIVO, ENCERRADO, CANCELADO. `due_date` é a menor devolução prevista entre as linhas ainda com o cliente. Orçamento aprovado converte uma única vez (`quote_id` único) e passa a CONVERTIDO; o contrato copia os snapshots do orçamento. Só rascunho é editável; cancelamento só antes de qualquer retirada, com motivo. Preço negociado em contrato/renovação exige `contracts.negotiate`. A origem IMPORTADO existe no schema, mas nenhuma conversão do Excel a utiliza ainda.

## ADR-014 — Orçamentos: cálculo, estados e documento (2026-10-11)

ACEITA. Regras comerciais respondidas pelo usuário em 11/10: valor do item = quantidade × preço do período × número de períodos, sem fração de período; duração em dias corridos (diária 1, semanal 7, quinzenal 15, mensal 30) e devolução prevista = início + dias × períodos; desconto somente como preço negociado por item, com preço de tabela e negociado guardados; cancelamento é estado próprio (CANCELADO, decisão da locadora com motivo), distinto de REJEITADO (recusa do cliente).

Decisões técnicas do implementador, revisáveis: arredondamento do item em meio centavo para cima (ROUND_HALF_UP) e total = soma dos itens; EXPIRADO não é persistido, é ENVIADO com validade anterior à data comercial (UTC−3 fixo em `app/core/clock.py`); numeração `ORC-AAAA-NNNNNN` por ano com unicidade (year, sequence) e alocação sob BEGIN IMMEDIATE; rascunho salvo mantém o preço de tabela do snapshot até pedido explícito `refresh_prices` ou mudança da data de início; duplicação gera rascunho com a tabela atual e informa itens não copiados; aprovação aceita rascunho ou enviado. Permissões: quotes.read/write/approve/negotiate; negociar preço nasce apenas com o administrador.

PDF gerado no backend com reportlab a partir dos snapshots (nunca da tabela corrente). Dados da locadora no cabeçalho vêm de `LOCACONTROL_COMPANY_*`; sem configuração, o cabeçalho mostra "LocaControl". A conversão em contrato foi entregue na Etapa 6 (ADR-015).

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

