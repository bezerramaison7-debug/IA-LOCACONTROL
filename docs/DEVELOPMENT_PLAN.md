# LOCACONTROL — PLANO OFICIAL DE DESENVOLVIMENTO

## Plano operacional integrado — 2026-10-11

Este bloco complementa os prompts oficiais abaixo sem apagar seu conteúdo. O plano de implementação é este arquivo; não há segundo plano concorrente.
Documentos estruturantes: [PRD](PRD.md), [TRD](TRD.md), [Fluxo do aplicativo](APP_FLOW.md), [Briefing de design](DESIGN_BRIEF.md), [Esquema do back-end](BACKEND_SCHEMA.md) e este plano.
Prompt mestre de continuidade: [CONTINUE_PROMPT.md](CONTINUE_PROMPT.md).

### Escopo e autorização
A sessão de 11/10 cria documentação, não executa etapas funcionais. O prompt de continuidade contém autorização para 4–12 quando enviado pelo usuário como instrução de execução. Sem essa instrução, permanece a autorização específica da sessão.
Quando a continuidade integral for explicitamente ativada, a parada obrigatória entre etapas nos prompts históricos é substituída pelo avanço após aceite/documentação. Requisitos e critérios permanecem válidos.
Publicação, custos, fiscal real e multiempresa exigem autorização/definição próprias.

### Baseline e evidências
Checkpoint de 08/10: 0–3 concluídas; 4 parcial; 5–12 não iniciadas; conta existente/banco 0004 preservados.
Em 11/10 foram lidos fontes de modelos/rotas de masters/imports, manifests e documentos. Banco, testes, servidor e migrations não foram revalidados.
Sem commits no checkpoint; preservar fontes untracked. Não executar bootstrap nem refazer base.

### Responsáveis por especialidade
Coordenador/arquiteto integra e mantém checkpoint; negócio define regras comerciais; Excel concilia origem/histórico; backend implementa serviços/APIs; dados cria constraints/migrations; frontend integra telas; UX revisa temas/teclado; documentos implementa templates/PDFs; segurança verifica permissões/isolamento; fiscal valida adapters/sandbox; operação comprova recuperação; QA integra evidências.
Delegação exige autorização aplicável e definição prévia de arquivos/contratos. Papéis podem ser executados sequencialmente. Revisão pelo autor não é revisão independente.

### Marcos, tarefas e critérios
Todas as tarefas abaixo são pendentes, salvo mecanismo de importação já implementado. Não confundir especificação com execução.

| ID | PRD | Responsáveis | Trabalho concreto | Dependências | Verificação e saída |
| --- | --- | --- | --- | --- | --- |
| IMP-04A | RF-IMP-001 | Excel/negócio/QA | Receber Excel na interface, analisar/mapear, DRY RUN e conciliar amostras/totais | Arquivo real | Relatório real revisado, conflitos sem sobrescrita |
| IMP-04B | RF-IMP-002 | Excel/backend/dados | Mapear histórico após entidades 6/7, preservar códigos/vínculos | IMP-04A, CON-06, OPE-07 | Históricos conciliados; pendências explícitas |
| ORC-05A | RF-ORC-001 | Negócio/arquitetura | Decidir duração, arredondamento, descontos e cancelamento | Respostas comerciais | Regras registradas e cenários numéricos aprovados |
| ORC-05B | RF-ORC-001 | Backend/dados | Entidades/migration/serviço/API, snapshots e numeração | ORC-05A | Cálculos, conflitos, permissões e upgrade temporário |
| ORC-05C | RF-ORC-001 | Frontend/UX/documentos | Tela, filtros, estados, duplicação, aprovação e PDF | Contratos API 05B | Integração real e documento coerente |
| CON-06A | RF-CON-001 | Negócio/documentos | Modelo real, condições e matriz de estados | Modelo contratual | Template/regras homologados |
| CON-06B | RF-CON-001 | Backend/dados | Contrato direto/conversão, itens, snapshots, números, documentos | 05B e decisões 06A | Conversão repetida/numeração concorrente/histórico |
| CON-06C | RF-CON-001 | Frontend/UX/documentos | Resumo, itens, datas, valores, versões e timeline | API 06B | Fluxo e PDF homologados; assinado preservado |
| OPE-07A | RF-RET/REN/DEV/MAN | Negócio/backend/dados | Modelar saldos pendentes, eventos, unidade física e transições | Contratos/estoque | Design transacional sem duplicar obrigação |
| OPE-07B | RF-RET/REN/DEV/MAN | Backend/frontend/QA | Retirar, renovar, devolver parcial/total, manter/encerrar | OPE-07A | Concorrência, idempotência, saldos e timeline |
| REL-08 | RF-REL-001 | Backend/frontend/QA | Consultas reais, filtros, dashboard e exportações | Dados 5–7 | Totais conciliáveis e mocks retirados das entregas |
| POR-09 | RF-POR-001 | Segurança/backend/frontend | Vínculo cliente, escopo, downloads e solicitação | Contratos/documentos | Acesso cruzado por ID/arquivo negado |
| FIS-10A | RF-FIS-001 | Fiscal/negócio/backend | Confirmar regras; criar interface, estados e provider fake | Contabilidade | Arquitetura testada, simulação identificada |
| FIS-10B | RF-FIS-001 | Fiscal/segurança/QA | Adapter escolhido, credenciais sandbox, retornos/conciliação | Provedor/credenciais | Sandbox externo homologado; sem fiscal real |
| OPS-11A | RF-OPS-001 | Operação/backend/QA | Backup DB+arquivos, agenda, retenção e restore assistido | Armazenamento definido | Recuperação isolada completa demonstrada |
| OPS-11B | RF-OPS-001 | Operação/segurança | Inicialização Windows, logs/health e atualização | OPS-11A | Uso sem terminal diário e conta/dados preservados |
| QA-12 | RF-REL-002/RNF | QA/todos | Auditoria, correções, E2E, upgrades/restores e guias | Aceites anteriores | Fluxo integral e critérios oficiais comprovados |

Cada implementação detalhará arquivos, classes, payloads, migration e testes após conferir o código. Não criar antecipadamente migrations sem decisão de schema.

### Ordem e paralelismo
Retomar 4; executar 5 → 6 → 7 → 8/9 → 10 → 11 → 12 respeitando dependências.
Homologação 4 pode permanecer pendente enquanto tarefas independentes avançam; não marcar concluída.
Frontend/UX pode preparar componentes após contrato de API aprovado. Dados/backend coordenam alterações de schema. Segurança/QA podem revisar módulos estabilizados em paralelo quando autorizado.
Não executar build em paralelo com smoke/E2E que usa dist.

### Insumos e bloqueios
Excel pela interface; regras de cobrança; modelo real; transições/vencimento; contabilidade/provedor/sandbox; destino/capacidade/recuperação web.
Registrar requisito afetado, responsável pela resposta, condição de desbloqueio e trabalho independente liberado.
Não inventar regra comercial; não solicitar credenciais em documentos ou código.

### Qualidade e rastreabilidade
Cadeia: RF/RNF → FL → RT → entidade/API → tarefa → teste/aceite.
Conferir scripts/check.ps1, scripts/test.ps1, scripts/e2e-auth.py e scripts/smoke.py antes de executar; scripts existentes são referência.
Testes novos devem cobrir comportamento, risco e invariantes: precisão, snapshots, concorrência, autorização, isolamento, duplicação, migrations e recuperação.
Migrations aplicadas em base real exigem backup e registro; testes destrutivos em temporários.
Registrar resultados observados, falhas e limitações; evidência histórica não comprova execução atual.

### Release e publicação
Entregar RELEASE_NOTES_1.0, INSTALLATION, USER_GUIDE e ADMIN_GUIDE.
P1–P3 de PUBLICATION_ROADMAP preparam produção/segurança/homologação após decisões necessárias. P4 depende de aceite/autorização concretos.
Localhost não é URL pública. Multiempresa/assinaturas não fazem parte do aceite atual.

### Continuidade e conclusão
Atualizar AI_HANDOFF por unidade significativa; PROJECT_STATE/CHANGELOG em marcos; documentos estruturantes conforme alterações.
Próxima ação deve indicar arquivo/função/tela, mudança e teste.
Conclusão exige critérios das etapas, Excel/histórico conciliados, documentos/regras homologados, segurança e recuperação comprovadas.
Se faltar aceite externo, registrar entrega técnica parcial e pendência objetiva. Sem estimativas/prazos/percentuais inventados.

---



## Como utilizar estes prompts

O desenvolvimento será dividido em etapas independentes.

Antes de executar qualquer etapa, forneça ao Agente A:

1. O **PROMPT MESTRE**.
2. O prompt específico da etapa.
3. O repositório atualizado do projeto.

O agente deve executar **somente a etapa solicitada**.

Ao terminar, deverá parar e apresentar:

* resumo do que foi desenvolvido;
* arquivos criados;
* arquivos alterados;
* migrations criadas;
* testes executados;
* resultado dos testes;
* comandos necessários para executar;
* decisões técnicas tomadas;
* pendências;
* riscos encontrados;
* sugestões para a próxima etapa.

Ele NÃO deve iniciar a etapa seguinte automaticamente.

---

# PROMPT MESTRE — CONTEXTO PERMANENTE

Você é o arquiteto de software e desenvolvedor full-stack responsável pelo projeto **LocaControl**, um sistema profissional para gestão de locação de equipamentos e materiais utilizados principalmente na construção civil.

Seu trabalho será realizado em etapas.

Antes de alterar qualquer código, leia obrigatoriamente:

* `/docs/PROJECT_STATE.md`
* `/docs/ARCHITECTURE.md`
* `/docs/BUSINESS_RULES.md`
* `/docs/DATABASE.md`
* `/docs/DESIGN_SYSTEM.md`
* `/docs/DECISIONS.md`
* `/docs/CHANGELOG.md`

Caso algum desses arquivos ainda não exista, ele deverá ser criado na etapa apropriada.

Nunca contradiga decisões registradas nesses documentos sem justificar e registrar formalmente a mudança.

## OBJETIVO DO PRODUTO

Substituir gradualmente um processo atualmente realizado em Excel por um sistema integrado capaz de administrar:

* clientes;
* produtos;
* equipamentos;
* estoque;
* preços;
* orçamento;
* contratos;
* renovações;
* retiradas;
* devoluções;
* documentos;
* usuários;
* permissões;
* auditoria;
* relatórios;
* importação de Excel;
* faturamento/documentação fiscal;
* futuramente portal remoto para clientes.

O Excel existente é a fonte inicial de dados e não deve ser descartado.

O sistema deverá conseguir importar o histórico existente preservando os códigos e informações originais sempre que possível.

---

# ARQUITETURA BASE

Frontend:

* React;
* TypeScript;
* Vite;
* Tailwind CSS;
* componentes acessíveis;
* biblioteca de componentes baseada em Radix/shadcn ou equivalente;
* TanStack Query para estado de servidor;
* React Hook Form;
* Zod para validações.

Backend:

* Python;
* FastAPI;
* SQLAlchemy;
* Alembic;
* Pydantic.

Banco inicial:

* SQLite.

A arquitetura deverá permitir migração futura para PostgreSQL sem reescrever as regras de negócio.

O sistema inicialmente será executado localmente.

Exemplo:

`http://localhost:8000`

Também deverá ser possível disponibilizá-lo dentro da LAN.

Não exponha o SQLite diretamente para a internet.

---

# PRINCÍPIOS DE ARQUITETURA

Separar claramente:

* domínio;
* API;
* persistência;
* serviços;
* geração de documentos;
* importação;
* autenticação;
* integrações externas.

Evitar colocar regras de negócio diretamente em componentes React ou controllers.

Preferir serviços de domínio.

Nunca utilizar `float` para valores financeiros.

Utilizar Decimal/numeric.

Todo registro importante deverá possuir:

* id interno;
* created_at;
* updated_at;
* created_by quando aplicável.

Registros comerciais importantes não devem ser excluídos fisicamente sem necessidade.

Utilizar soft delete quando apropriado.

Contratos, orçamentos e preços devem guardar snapshots históricos.

Uma mudança na tabela de preço NÃO poderá alterar contratos antigos.

---

# REGRA DOS CONTRATOS

Exemplo:

Contrato original:

9193

Primeira renovação:

9193.1

Segunda renovação:

9193.2

Terceira renovação:

9193.3

Internamente, não modelar simplesmente como texto.

Exemplo conceitual:

base_number = 9193
renewal_number = 2

Código exibido:

9193.2

Toda renovação deverá manter relação com o contrato original.

Deve ser possível reconstruir:

9193
└─ 9193.1
└─ 9193.2
└─ 9193.3

Nunca perder histórico.

---

# PERÍODOS DE LOCAÇÃO

Os períodos comerciais suportados inicialmente são:

* diária;
* semanal;
* quinzenal;
* mensal.

Cada produto poderá possuir preços diferentes para cada período.

Exemplo:

Produto: Betoneira 400 L

Diária: R$ 90
Semanal: R$ 390
Quinzenal: R$ 650
Mensal: R$ 980

O sistema deverá suportar histórico das tabelas de preço.

---

# PRODUTO X EQUIPAMENTO

Não confundir produto com unidade física.

Produto:

Betoneira 400 L

Equipamentos:

BET-001
BET-002
BET-003

Cada equipamento poderá futuramente possuir:

* patrimônio;
* número serial;
* marca;
* modelo;
* situação;
* observação;
* localização;
* histórico.

Alguns produtos poderão ser controlados somente por quantidade.

O sistema deverá suportar os dois modelos.

---

# STATUS DE EQUIPAMENTO

Inicialmente:

* disponível;
* reservado;
* locado;
* manutenção;
* indisponível;
* baixado.

O sistema nunca deverá permitir estoque negativo silenciosamente.

---

# DEVOLUÇÃO

Deverá existir devolução total e parcial.

Exemplo:

Contrato possui:

2 betoneiras
3 lixadeiras
1 martelete

Cliente devolve:

1 betoneira
2 lixadeiras

O contrato continuará ativo com:

1 betoneira
1 lixadeira
1 martelete

O estoque deverá ser atualizado adequadamente.

---

# USUÁRIOS E PERMISSÕES

Preparar RBAC.

Perfis iniciais:

ADMINISTRADOR

Acesso completo.

COMERCIAL

* clientes;
* orçamentos;
* contratos;
* renovações.

OPERAÇÃO

* equipamentos;
* estoque;
* retirada;
* devolução;
* manutenção.

FINANCEIRO

* faturamento;
* valores;
* documentos fiscais.

CLIENTE

Somente suas próprias informações.

Nunca confiar apenas no frontend para autorização.

A API deverá validar as permissões.

---

# AUDITORIA

Operações importantes devem ser auditáveis.

Exemplo:

Usuário: Maria
Data: 12/09/2026 14:32
Contrato: 9193
Campo alterado: quantidade
Anterior: 3
Novo: 2

Registrar principalmente alterações em:

* clientes;
* preços;
* orçamentos;
* contratos;
* estoque;
* devoluções;
* usuários;
* permissões.

---

# DESIGN E EXPERIÊNCIA DO USUÁRIO

O sistema será utilizado durante muitas horas por funcionários.

A interface deve priorizar:

* conforto visual;
* legibilidade;
* baixa fadiga;
* simplicidade;
* consistência;
* velocidade;
* pouco excesso visual.

Evitar:

* cores excessivamente saturadas;
* preto puro;
* branco excessivamente agressivo;
* excesso de bordas;
* excesso de sombras;
* tabelas apertadas;
* fontes pequenas;
* telas cheias de informações sem hierarquia.

---

# SISTEMA DE TEMAS

Implementar:

* Claro;
* Escuro;
* Seguir sistema operacional.

Preferência inicial:

`system`

Salvar preferência do usuário.

## Tema claro

Sugestão:

Background:
#F6F8FB

Surface:
#FFFFFF

Surface secundária:
#F1F5F9

Texto principal:
#172033

Texto secundário:
#64748B

Border:
#E2E8F0

Primary:
#2563EB

Primary hover:
#1D4ED8

## Tema escuro

Não utilizar preto puro.

Background:
#0B1120

Surface:
#111827

Surface secundária:
#182235

Texto principal:
#E5E7EB

Texto secundário:
#94A3B8

Border:
#263349

Primary:
#60A5FA

---

# CORES DE STATUS

Sucesso:
verde.

Atenção:
âmbar.

Erro:
vermelho.

Informativo:
azul.

Status nunca deve ser identificado SOMENTE pela cor.

Utilizar:

ícone + texto + cor.

Exemplo:

✓ Ativo

⚠ Vencendo

✕ Vencido

---

# TIPOGRAFIA

Utilizar fonte extremamente legível.

Preferencialmente:

Inter

ou fallback:

system-ui.

Texto normal:

14–16px.

Evitar textos importantes abaixo de 14px.

Títulos devem possuir hierarquia clara.

---

# ACESSIBILIDADE

Objetivo mínimo:

WCAG AA.

Garantir:

* contraste;
* navegação por teclado;
* estados de foco;
* labels;
* aria quando necessário;
* áreas clicáveis confortáveis;
* mensagens de erro compreensíveis.

---

# LAYOUT PRINCIPAL

Desktop:

Sidebar esquerda recolhível.

Topbar superior.

Área central de conteúdo.

Sidebar:

LocaControl

Dashboard

COMERCIAL
Clientes
Orçamentos
Contratos
Renovações

OPERAÇÃO
Produtos
Equipamentos
Estoque
Retiradas
Devoluções
Manutenção

FINANCEIRO
Faturamento
Fiscal

GESTÃO
Relatórios
Importações
Usuários
Auditoria
Configurações

Rodapé da sidebar:

Usuário atual
Tema
Sair

---

# TABELAS

As tabelas são fundamentais.

Devem possuir:

* busca;
* filtros;
* ordenação;
* paginação;
* cabeçalho fixo quando apropriado;
* boa visualização;
* coluna de ações;
* estados vazios;
* loading state;
* erro;
* responsividade.

Evitar tabela excessivamente compacta.

Criar futuramente opção:

Densidade:

* confortável;
* compacta.

Padrão:

confortável.

---

# REGRAS DE UX

Não apagar registros importantes com um único clique.

Operações destrutivas devem pedir confirmação.

Exibir mensagens claras.

Exemplo ruim:

“Erro 422”.

Exemplo correto:

“Não foi possível salvar o contrato porque a data final é anterior à data inicial.”

Utilizar feedback visual para:

* carregamento;
* sucesso;
* erro;
* salvamento.

---

# DOCUMENTAÇÃO

Após TODA etapa atualizar:

`PROJECT_STATE.md`

com:

* funcionalidades concluídas;
* funcionalidades pendentes;
* decisões;
* migrations;
* testes;
* problemas conhecidos.

Atualizar também:

`CHANGELOG.md`

Nunca deixar o repositório sem indicar claramente seu estado atual.

---

# TESTES

Nunca considerar uma funcionalidade pronta apenas porque compilou.

Testar:

* regra de negócio;
* API;
* banco;
* frontend quando aplicável.

Sempre executar os testes existentes antes de finalizar uma etapa.

Nunca remover testes apenas para fazer a suíte passar.

---

# SEGURANÇA

Senhas nunca podem ser armazenadas em texto puro.

Utilizar hash seguro.

Não armazenar segredos no código.

Criar `.env.example`.

Nunca commitar credenciais reais.

Validar uploads.

Validar extensões.

Sanitizar nomes de arquivo.

Não confiar em dados enviados pelo frontend.

---

# IMPORTAÇÃO EXCEL

Nunca modificar o Excel original.

Toda importação deverá possuir identificação.

Exemplo:

ImportBatch

* filename;
* checksum;
* imported_at;
* imported_by;
* total_rows;
* successful_rows;
* warning_rows;
* failed_rows.

Importação deverá primeiro executar preview.

Somente depois confirmação.

Nunca importar cegamente.

---

# INTEGRAÇÃO FISCAL

Não acoplar a aplicação diretamente a um fornecedor.

Criar abstração:

FiscalProvider

com ações como:

* emitir;
* consultar;
* cancelar;
* obter PDF;
* obter XML.

Implementações externas deverão usar adapters.

Não implementar regras tributárias arbitrariamente.

Os códigos e configurações fiscais deverão ser configuráveis.

---

# REGRA ABSOLUTA DE DESENVOLVIMENTO

Você está executando uma ETAPA de um projeto maior.

NÃO:

* reescreva módulos já funcionando sem necessidade;
* altere arquitetura silenciosamente;
* avance para etapas futuras;
* invente dados como se fossem reais;
* faça mocks e declare a funcionalidade concluída;
* esconda erros;
* elimine histórico;
* faça alterações destrutivas em banco sem migration.

Quando encontrar algo que depende de uma decisão futura, prepare a arquitetura e registre a pendência.

---

# ETAPA 0 — FUNDAÇÃO DO PROJETO

## PROMPT

Utilizando integralmente o PROMPT MESTRE do LocaControl, execute somente a ETAPA 0.

Objetivo:

Criar a fundação técnica e documental do sistema.

Ainda não desenvolva módulos comerciais completos.

Crie:

* estrutura do monorepo/projeto;
* frontend;
* backend;
* banco SQLite inicial;
* configuração de migrations;
* configuração de desenvolvimento;
* lint;
* formatação;
* testes;
* `.env.example`;
* `.gitignore`;
* README;
* documentação arquitetural.

Criar obrigatoriamente:

`/docs/PROJECT_STATE.md`

`/docs/ARCHITECTURE.md`

`/docs/BUSINESS_RULES.md`

`/docs/DATABASE.md`

`/docs/DESIGN_SYSTEM.md`

`/docs/DECISIONS.md`

`/docs/CHANGELOG.md`

Registrar nesses documentos todas as regras já conhecidas.

Criar endpoints técnicos:

`GET /health`

Resposta esperada:

status saudável da aplicação.

Criar banco SQLite e comprovar que migrations funcionam.

Não implementar clientes, contratos ou orçamento completos ainda.

Criar scripts simples para:

* iniciar backend;
* iniciar frontend;
* executar migrations;
* executar testes.

Ao finalizar:

1. execute backend;
2. execute frontend;
3. teste conexão;
4. execute migrations;
5. execute testes;
6. atualize PROJECT_STATE;
7. pare.

---

# ETAPA 1 — DESIGN SYSTEM, TEMA E APP SHELL

## PROMPT

Execute somente a ETAPA 1 do LocaControl.

Implemente a fundação visual completa da aplicação.

Objetivo:

Criar uma interface extremamente confortável para uso profissional durante várias horas.

Implementar:

* Design System;
* tema claro;
* tema escuro;
* tema seguindo sistema operacional;
* persistência da preferência;
* sidebar;
* topbar;
* layout;
* navegação;
* breadcrumbs;
* cards;
* badges;
* botões;
* campos;
* selects;
* modais;
* dialogs;
* toasts;
* tabelas;
* skeleton loading;
* empty states;
* error states;
* página 404.

Criar seletor:

Tema:
Sistema / Claro / Escuro

Sidebar deverá ser recolhível.

Criar telas visuais ainda sem funcionalidade comercial completa:

Dashboard
Clientes
Produtos
Equipamentos
Orçamentos
Contratos
Configurações

O Dashboard poderá utilizar dados de demonstração claramente marcados como mock APENAS nesta etapa visual.

Não misturar dados mock com banco real.

Criar componentes reutilizáveis.

Garantir responsividade adequada.

Prioridade:

Desktop 1366×768 e superiores.

Também permitir utilização aceitável em notebook e tablet.

Validar contraste e navegação por teclado.

Criar exemplos dos status:

Ativo
Vencendo
Vencido
Encerrado
Cancelado

Ao finalizar, atualizar DESIGN_SYSTEM.md e PROJECT_STATE.md.

---

# ETAPA 2 — BANCO DE DADOS, AUTENTICAÇÃO E PERMISSÕES

## PROMPT

Execute somente a ETAPA 2.

Objetivo:

Criar a fundação de dados e segurança.

Implementar banco e migrations para:

Users
Roles
Permissions
AuditLogs

Implementar autenticação.

Senhas com hash seguro.

Criar inicialmente:

ADMINISTRADOR
COMERCIAL
OPERAÇÃO
FINANCEIRO
CLIENTE

Criar autorização no backend.

Criar:

Login
Logout
Usuário atual
Alterar senha

Preparar recuperação de senha local de forma segura.

Criar usuário administrador inicial através de mecanismo seguro de bootstrap.

Não deixar senha default fixa no código.

Criar telas:

Login
Meu perfil
Usuários
Perfis/permissões

Implementar auditoria inicial.

Toda operação administrativa relevante deverá registrar usuário e horário.

Não implementar clientes e contratos nesta etapa.

Criar testes de segurança básicos.

---

# ETAPA 3 — CLIENTES, PRODUTOS, EQUIPAMENTOS, ESTOQUE E PREÇOS

## PROMPT

Execute somente a ETAPA 3.

Criar módulos mestres.

## CLIENTES

Campos iniciais:

* pessoa física/jurídica;
* razão social;
* nome fantasia;
* CPF/CNPJ;
* inscrição estadual quando aplicável;
* telefone;
* celular;
* e-mail;
* contato responsável;
* endereço;
* cidade;
* estado;
* CEP;
* observações;
* status.

Permitir múltiplos endereços futuramente.

Validar duplicidades relevantes.

## PRODUTOS

Campos:

* código;
* nome;
* descrição;
* categoria;
* unidade;
* controla equipamento individual;
* ativo.

## EQUIPAMENTOS

Quando produto possuir controle individual:

* código interno;
* patrimônio;
* número serial;
* marca;
* modelo;
* status;
* observações.

## ESTOQUE

Controlar:

Disponível
Reservado
Locado
Manutenção
Indisponível
Baixado

Não permitir estoque negativo silencioso.

## PREÇOS

Criar quatro períodos:

DIÁRIA
SEMANAL
QUINZENAL
MENSAL

Permitir preço específico por produto.

Criar histórico.

Não sobrescrever preços antigos utilizados comercialmente.

Criar interface confortável e filtros.

Implementar CRUD completo com permissões e auditoria.

Criar testes.

---

# ETAPA 4 — IMPORTADOR DO EXCEL LEGADO

## PROMPT

Execute somente a ETAPA 4.

Esta é uma etapa crítica.

Objetivo:

Permitir trazer para o LocaControl os dados do Excel utilizado atualmente pela empresa.

NÃO presuma a estrutura definitiva antes de analisar o arquivo real fornecido pelo usuário.

O usuário deverá fornecer o Excel atual.

Primeiramente faça uma análise técnica do workbook.

Identifique:

* abas;
* cabeçalhos;
* fórmulas;
* células mescladas;
* tipos;
* códigos;
* clientes;
* preços;
* contratos;
* renovações;
* datas;
* referências entre abas.

Não altere o arquivo original.

Criar um mecanismo de importação em etapas:

1. upload;
2. análise;
3. escolha da aba;
4. mapeamento;
5. preview;
6. validação;
7. avisos;
8. conflitos;
9. confirmação;
10. importação.

Permitir mapear:

Coluna Excel → Campo LocaControl

Exemplo:

CLIENTE → cliente.razao_social
CNPJ → cliente.cnpj
CÓDIGO → contrato.codigo
MATERIAL → produto.nome

Criar detecção de:

* duplicados;
* campos ausentes;
* datas inválidas;
* valores inválidos;
* registros conflitantes.

Nunca interromper toda importação por uma única linha problemática.

Criar relatório:

Total
Importados
Ignorados
Avisos
Erros

Registrar ImportBatch.

Armazenar origem/importação.

Permitir baixar relatório de erros.

Criar modo DRY RUN.

Nenhuma alteração deve ser persistida durante DRY RUN.

Somente importar após confirmação explícita.

Criar testes utilizando planilhas de teste.

Após análise do Excel real, atualizar:

BUSINESS_RULES.md
DATABASE.md
PROJECT_STATE.md

---

# ETAPA 5 — ORÇAMENTOS

## PROMPT

Execute somente a ETAPA 5.

Criar módulo profissional de orçamento.

Fluxo:

Cliente
→ produtos
→ quantidade
→ período
→ preço
→ desconto
→ total
→ orçamento.

Permitir múltiplos produtos.

Períodos:

Diária
Semanal
Quinzenal
Mensal

Ao selecionar produto e período, preencher o preço automaticamente.

Permitir alteração manual somente para usuários autorizados.

Registrar preço de tabela e preço negociado.

Nunca recalcular automaticamente um orçamento histórico devido a alteração futura da tabela.

Status:

Rascunho
Enviado
Aprovado
Rejeitado
Expirado
Convertido

Criar número do orçamento.

Exemplo:

ORC-2026-000123

Permitir:

Duplicar orçamento
Editar rascunho
Gerar PDF
Aprovar
Cancelar
Converter em contrato

Criar página visual profissional para impressão/PDF.

Mostrar disponibilidade do equipamento durante elaboração.

Não efetuar reserva definitiva apenas por adicionar item ao orçamento.

Criar testes de cálculos financeiros.

Utilizar Decimal.

---

# ETAPA 6 — CONTRATOS E GERAÇÃO DE DOCUMENTOS

## PROMPT

Execute somente a ETAPA 6.

Criar módulo de contratos.

Contrato poderá nascer:

* diretamente;
* ou através de orçamento aprovado.

Código comercial seguirá modelo existente.

Exemplo:

9193

Não utilizar apenas o texto como identidade interna.

Criar relação segura entre id interno e código comercial.

Criar ContractItems com snapshot:

* produto;
* descrição;
* quantidade;
* período;
* preço;
* desconto;
* valor;
* datas.

Criar estados:

Rascunho
Aguardando retirada
Ativo
Vencendo
Vencido
Encerrado
Cancelado

Criar sistema de templates de contrato.

O usuário fornecerá o modelo de contrato atualmente usado.

Não descaracterizar o documento original.

Criar placeholders.

Exemplos:

{{ contract.number }}

{{ customer.legal_name }}

{{ customer.document }}

{{ customer.address }}

{{ contract.start_date }}

{{ contract.end_date }}

{{ items }}

{{ totals }}

Gerar:

PDF

e, se tecnicamente adequado:

DOCX.

Manter documento gerado vinculado ao contrato.

Permitir regeneração controlada e histórico.

Nunca substituir silenciosamente documento já assinado.

Criar tela de contrato com:

Resumo
Cliente
Itens
Datas
Valores
Documentos
Histórico
Auditoria

---

# ETAPA 7 — RETIRADA, RENOVAÇÃO E DEVOLUÇÃO

## PROMPT

Execute somente a ETAPA 7.

Implementar o ciclo operacional da locação.

## RETIRADA

Contrato aprovado deverá permitir registrar retirada.

Associar unidades físicas quando necessário.

Atualizar estoque:

Disponível → Locado.

## RENOVAÇÕES

Contrato original:

9193

Primeira renovação:

9193.1

Segunda:

9193.2

Terceira:

9193.3

Criar automaticamente o próximo número.

Nunca sobrescrever contrato anterior.

Permitir escolher:

* manter preços anteriores;
* utilizar preços atuais;
* negociar novos preços.

Registrar explicitamente a opção utilizada.

Renovação poderá conter todos ou apenas alguns itens.

## DEVOLUÇÃO

Permitir:

* total;
* parcial.

Registrar:

* data;
* quantidade;
* equipamento;
* observação;
* condição de devolução.

Atualizar estoque.

Equipamento poderá retornar como:

Disponível

ou:

Manutenção

dependendo da condição registrada.

Criar timeline completa.

Exemplo:

9193 criado
→ retirada
→ 9193.1
→ devolução parcial
→ 9193.2
→ devolução total
→ encerrado.

Testar exaustivamente quantidade e estoque.

---

# ETAPA 8 — DASHBOARD, FILTROS E RELATÓRIOS

## PROMPT

Execute somente a ETAPA 8.

Criar Dashboard operacional real.

Não utilizar mais mocks.

Cards principais:

Contratos ativos
Itens locados
Contratos vencendo
Contratos vencidos
Equipamentos disponíveis
Equipamentos em manutenção
Valor atualmente contratado

Criar seção:

Contratos vencendo.

Criar seção:

Movimentações recentes.

Criar filtros avançados.

Contratos deverão ser pesquisáveis por:

* código;
* cliente;
* CPF/CNPJ;
* produto;
* equipamento;
* status;
* data;
* período.

Na página de cliente mostrar:

Contratos ativos
Total de contratos
Itens atualmente locados
Histórico
Documentos
Valor atualmente contratado

Criar relatórios:

Locações ativas
Contratos vencendo
Contratos vencidos
Produtos locados
Produtos disponíveis
Equipamentos por cliente
Histórico de equipamento
Renovações
Devoluções
Receita contratada por período
Produtos mais locados
Clientes com maior volume

Permitir exportação:

Excel
PDF

Relatórios grandes não devem travar a interface.

---

# ETAPA 9 — PORTAL DO CLIENTE

## PROMPT

Execute somente a ETAPA 9.

Criar portal específico para perfil CLIENTE.

O cliente nunca poderá acessar dados de outros clientes.

Backend deve garantir isolamento.

Menu:

Dashboard
Meus contratos
Meus equipamentos
Orçamentos
Renovações
Documentos
Meu cadastro

Dashboard:

Contratos ativos
Equipamentos locados
Próximos vencimentos

Cliente poderá:

Visualizar contrato
Baixar documento
Visualizar itens
Visualizar datas
Solicitar renovação

Solicitação de renovação NÃO deverá criar renovação definitiva automaticamente.

Ela deverá gerar uma solicitação para aprovação do funcionário.

IMPORTANTE:

Nesta versão, o portal poderá funcionar em ambiente local/LAN.

Não tente expor o SQLite diretamente à internet.

Documentar claramente que acesso remoto será uma arquitetura posterior.

---

# ETAPA 10 — FATURAMENTO E INTEGRAÇÃO FISCAL

## PROMPT

Execute somente a ETAPA 10.

Criar arquitetura fiscal desacoplada.

Implementar interface conceitual:

FiscalProvider

Métodos:

emit
status
cancel
get_pdf
get_xml

Não acoplar regras de domínio a um fornecedor.

Criar estrutura para adapters.

Exemplos futuros:

Nuvem Fiscal
Focus NFe
eNotas
outros.

Criar módulo:

Documentos fiscais.

Relacionar documento a:

Cliente
Contrato
Período
Valor

Status:

Pendente
Processando
Emitido
Erro
Cancelado

Guardar:

Número
Série
Chave quando aplicável
PDF
XML
Retorno do provedor

IMPORTANTE:

Não pressupor automaticamente que toda locação gera determinada espécie tributária.

Regras fiscais deverão ser configuráveis e validadas com a contabilidade.

Criar primeiro um provider fake/sandbox para validar arquitetura.

Somente integrar provedor real quando forem fornecidas credenciais de ambiente de testes.

Nunca armazenar credenciais no código.

---

# ETAPA 11 — BACKUP, RECUPERAÇÃO, SEGURANÇA E INSTALAÇÃO

## PROMPT

Execute somente a ETAPA 11.

Objetivo:

Transformar o sistema em aplicação confiável para uso diário.

Criar backup automático do banco.

Configurações:

Ativado/desativado
Horário
Diretório
Quantidade de backups mantidos

Exemplo:

C:\LocaControl\Backups

Criar nome:

locacontrol_2026-09-12_2200.db

Criar verificação do backup.

Criar restauração assistida.

Restaurar banco deverá exigir confirmação forte.

Nunca restaurar silenciosamente.

Criar cópia de segurança antes de restauração.

Criar exportação de backup manual.

Criar logs.

Criar health checks.

Criar mecanismo amigável para inicializar aplicação no Windows.

Objetivo final:

Usuário não deverá precisar abrir terminal diariamente.

Preparar execução semelhante a:

LocaControl.exe

ou:

Iniciar LocaControl

que:

* inicia backend;
* disponibiliza frontend;
* verifica banco;
* abre navegador.

Criar documentação para instalação.

Preparar atualização futura sem apagar banco de dados.

---

# ETAPA 12 — QA FINAL E RELEASE 1.0

## PROMPT

Execute somente a ETAPA 12.

Não adicione novas funcionalidades.

Faça auditoria completa do projeto.

Revisar:

Arquitetura
Banco
Migrations
Segurança
Permissões
UX
Dark mode
Light mode
Excel
Clientes
Produtos
Preços
Orçamentos
Contratos
Renovações
Devoluções
Estoque
Dashboard
Relatórios
Portal
Backup
Auditoria

Executar fluxo real completo:

Criar cliente.

Criar produto.

Criar preço.

Cadastrar estoque.

Criar orçamento.

Aprovar orçamento.

Gerar contrato.

Registrar retirada.

Renovar contrato.

Registrar devolução parcial.

Renovar novamente.

Registrar devolução total.

Encerrar contrato.

Validar estoque final.

Validar histórico.

Validar auditoria.

Criar testes end-to-end para principais fluxos.

Testar tema claro.

Testar tema escuro.

Testar resolução 1366×768.

Testar resolução Full HD.

Testar erros de entrada.

Testar backup e restauração.

Executar migrations a partir de banco vazio.

Executar cenário de atualização de banco existente.

Corrigir bugs encontrados.

Não esconder erros.

Ao finalizar, gerar:

`RELEASE_NOTES_1.0.md`

`INSTALLATION.md`

`USER_GUIDE.md`

`ADMIN_GUIDE.md`

Atualizar PROJECT_STATE.

Somente considerar versão 1.0 pronta se os fluxos críticos estiverem funcionando.

---

# CRITÉRIO GERAL DE SUCESSO DA VERSÃO 1.0

O seguinte cenário deverá funcionar integralmente:

1. funcionário abre o LocaControl;
2. pesquisa ou cadastra cliente;
3. seleciona produtos;
4. sistema informa disponibilidade;
5. escolhe diária, semana, quinzena ou mensal;
6. preço é carregado;
7. orçamento é gerado;
8. orçamento é aprovado;
9. contrato 9193 é criado;
10. documento é gerado;
11. equipamentos são retirados;
12. estoque é atualizado;
13. contrato aparece como ativo;
14. cliente solicita ou funcionário cria renovação;
15. sistema cria 9193.1;
16. parte dos equipamentos é devolvida;
17. estoque é atualizado;
18. nova renovação cria 9193.2;
19. cliente devolve os demais itens;
20. contrato é encerrado;
21. equipamentos retornam ao estoque;
22. todo histórico permanece consultável;
23. filtros encontram qualquer contrato rapidamente;
24. dashboard mostra informações reais;
25. backups protegem o banco;
26. nenhum dado histórico foi sobrescrito.

Este será o critério central de aceite do LocaControl 1.0.
