# LocaControl — Design system

## Etapa 2 — telas de segurança

Login com formulário de usuário/senha, erros genéricos e ajuda para bootstrap/recuperação local. Meu perfil permite editar o próprio nome e alterar senha com confirmação; troca obrigatória redireciona para essa tela. Usuários consulta dados reais com busca/paginação, criação, edição, desativação/reativação confirmada e reset explícito de senha. Perfis e permissões exibe matriz e confirma alterações de grants; Administrador/Cliente são protegidos. Auditoria lista eventos reais paginados com autor, horário e mudanças não sensíveis.

AuthProvider consulta a sessão real antes de mostrar áreas protegidas, sem token em localStorage. Menu e busca filtram permissões, rodapé mostra a conta conectada e Sair chama logout real (também no menu móvel). A rota solicitada é preservada após login se o usuário tiver permissão. Erros de sessão removem conteúdo privado. As prévias comerciais continuam identificadas; telas de segurança não exibem o aviso de dados fictícios.

Novas telas reutilizam tokens, campos, cards e Radix. Login é centralizado; formulários de perfil se empilham em telas estreitas; tabelas/matriz usam rolagem dentro do componente. Resultados de QA em PROJECT_STATE/AI_HANDOFF. A especificação histórica abaixo descreve a entrega visual da Etapa 1; onde houver diferença no usuário/logout, aplica-se este comportamento da Etapa 2.

## Estado e fontes

Etapa 1 implementada em 2026-09-12. Tokens em `frontend/src/styles.css`; componentes em `frontend/src/components`; shell em `frontend/src/layout`; telas em `frontend/src/pages`. Interface de demonstração explicitamente identificada, sem operações comerciais persistidas.

## Princípios

Conforto para uso prolongado, hierarquia clara, espaço entre controles e densidade confortável. Fonte Inter quando instalada, com fallback system-ui/Segoe UI; nenhuma fonte externa obrigatória. Texto principal e dados/status de tabela com 14px ou mais; títulos 15–32px. Rótulos auxiliares e metadados podem ser menores. Evitar preto puro, saturação excessiva e sombras decorativas; sombra reservada a overlays.

## Tokens implementados

| Token CSS | Claro | Escuro |
| --- | --- | --- |
| --background | #F6F8FB | #0B1120 |
| --surface | #FFFFFF | #111827 |
| --surface-alt | #F1F5F9 | #182235 |
| --text | #172033 | #E5E7EB |
| --muted | #526277 | #A3B1C6 |
| --border | #E2E8F0 | #263349 |
| --control-border | #8290A3 | #667791 |
| --primary | #2563EB | #60A5FA |
| --primary-hover | #1D4ED8 | #93C5FD |
| --on-primary | #FFFFFF | #0B1120 |
| --active-bg | #EAF1FF | #192E50 |
| --active-text | #1D4ED8 | #93C5FD |
| --success / --success-bg | #166534 / #ECFDF3 | #86EFAC / #112F29 |
| --warning / --warning-bg | #92400E / #FFFBEB | #FCD34D / #332A18 |
| --danger / --danger-bg | #B91C1C / #FEF2F2 | #FCA5A5 / #361E28 |
| --info / --info-bg | #1E40AF / #EFF6FF | #93C5FD / #182D49 |

Bordas decorativas são sutis; controles usam token separado para distinção contra o fundo. Status combinam ícone, texto e cor: Ativo, Vencendo, Vencido, Encerrado e Cancelado. Também há Disponível, Manutenção e Rascunho. Nunca transmitir estado somente pela cor.

## Temas e persistência

Preferências `system`, `light`, `dark`, exibidas como Sistema / Claro / Escuro. Padrão sistema operacional. `ThemeProvider` acompanha mudanças de `prefers-color-scheme` e eventos de storage entre abas; aplica `data-theme` e `color-scheme` ao documento. Script inicial no HTML resolve a preferência antes da renderização para reduzir flashes. Chave localStorage: `locacontrol.theme`. Valores inválidos retornam a sistema e falha de armazenamento mantém a sessão utilizável.

Seletor no rodapé do menu e controles de aparência em Configurações. Restaurar padrão exige confirmação e altera apenas a preferência visual.

## App shell e rotas

Sidebar de 238px, recolhida com 78px. Abaixo de 1024px vira drawer acessível. Navegação com scroll próprio; rodapé fixa identificação de demonstração, tema e saída explicativa. Não existe usuário autenticado nesta etapa. Topbar de 72px com breadcrumbs, botão do menu e busca de páginas. Conteúdo limitado a 1600px.

Grupos: Dashboard; Comercial (Clientes, Orçamentos, Contratos, Renovações); Operação (Produtos, Equipamentos, Estoque, Retiradas, Devoluções, Manutenção); Financeiro (Faturamento, Fiscal); Gestão (Relatórios, Importações, Usuários, Auditoria, Configurações). Itens futuros mostram página explicativa. Rotas desconhecidas mostram 404 e retorno ao dashboard.

HashRouter mantém links diretos como `/#/clientes` e refresh sem configuração extra do servidor. Alteração de rota atualiza título e foco do conteúdo. Chave `locacontrol.sidebar` persiste recolhimento. Configurações carrega sob demanda com fallback Skeleton.

## Componentes reutilizáveis

| Componente | Uso e comportamento |
| --- | --- |
| Button | Primary, secondary, ghost, danger, ícone e composição Radix Slot. |
| Card, PageHeader | Hierarquia de seções, descrições e ações. |
| Badge | Status com ícone e texto; tokens semânticos. |
| Field, Select | Label associado, ajuda, erro, aria-invalid e controles nativos. |
| Modal, ConfirmDialog | Radix Dialog/AlertDialog; foco contido, Escape e retorno ao acionador; cancelamento inicial em confirmação. |
| ToastProvider | Feedback anunciado por aria-live e botão explícito para dispensar. |
| DataTable | Busca, filtro, ordenação com aria-sort, paginação, tamanho da página e detalhes. |
| Skeleton, EmptyState, ErrorState | Carregamento anunciado, ausência de resultados/estado inicial, erro e nova tentativa. |
| DemoForm | React Hook Form/Zod; valida prévia e notifica sem gravar nem chamar API comercial. |
| HealthPanel | Diagnóstico verdadeiro da API/banco/migration em Configurações. |

Tabelas mantêm cabeçalho e hierarquia, rolagem horizontal contida em telas estreitas e nomes completos no modal de detalhes. Filtros e paginação operam apenas sobre fixtures; estados vazio/loading/erro podem ser demonstrados pelo seletor Estado da prévia nos catálogos.

## Telas desta etapa

Dashboard com indicadores, contratos, disponibilidade, movimentações e atalhos fictícios. Clientes, Produtos, Equipamentos, Orçamentos e Contratos com listas e formulário de prévia. Configurações com temas, status, dialogs, toast, estados e diagnóstico real. Dados em `frontend/src/demo/data.ts`, marcados com nomes de exemplo e códigos DEMO; nunca importados pelo backend nem gravados no banco.

## Responsividade e acessibilidade

Verificação de navegador em 1366×768, 1920×1080, 820×1180 e 390×844, temas claro e escuro. Cards reorganizam colunas; dashboard usa coluna lateral apenas quando há espaço. Em telas estreitas, tabelas rolam dentro do componente e não provocam overflow do documento.

Foco visível, link Pular para o conteúdo, labels, headings, landmarks, botões semânticos, dialogs com gestão de foco e `prefers-reduced-motion`. Suíte `frontend/e2e/visual.spec.ts` verifica sete páginas por tema e viewport com Axe (WCAG 2 A/AA e 2.1 AA), além de teclado, temas, menu, formulário, busca, filtros e 404. Auditoria automática é evidência para as telas e estados testados; não substitui avaliação com leitor de tela e usuários. Evidências finais e comandos em PROJECT_STATE e AI_HANDOFF.


## Evolução verificada em 2026-10-08

Clientes, Produtos, Equipamentos, Estoque e Preços são telas reais. Importações usa upload, seleção/mapeamento, prévia paginada, confirmação explícita, relatório e histórico. Campos mantêm rótulos associados, conteúdo com espaçamento, tabelas com rolagem contida e estados de erro/carregamento. Dashboard mantém prévia e inclui atalho para importar Excel quando autorizado. Orçamentos/Contratos continuam demonstrações. As descrições anteriores documentam a Etapa 1 e não substituem o estado atual em PROJECT_STATE.
