# LocaControl — Estado do projeto

Atualização: 2026-10-11 (America/Sao_Paulo). Branch `dev/etapas-4-12`, commit `82e0845`; baseline `2b3d1d2` em `master`. Sem repositório remoto configurado.

Legenda: EXISTENTE = implementado e coberto por testes automatizados; PARCIAL = falta a parte indicada; PENDENTE = não iniciado. Nenhuma etapa foi homologada com dados reais da locadora: o banco local não tem dados comerciais.

## Estado por etapa

| Etapa | Backend | Tela | Estado | O que falta |
| --- | --- | --- | --- | --- |
| 0–2 Fundação, interface, identidade | EXISTENTE | EXISTENTE | CONCLUÍDA | — |
| 3 Cadastros, estoque, preços | EXISTENTE | EXISTENTE | CONCLUÍDA | — |
| 4 Importador do Excel | EXISTENTE para clientes, produtos, equipamentos, estoque inicial e preços | EXISTENTE | PARCIAL | Excel real nunca foi enviado (`import_batches` vazia); conversão do histórico de contratos/renovações não implementada (IMP-04B) |
| 5 Orçamentos | EXISTENTE | EXISTENTE (`6f7dffc`) | Implementada; validação do usuário pendente | Dados da locadora no cabeçalho do PDF |
| 6 Contratos e documentos | EXISTENTE | EXISTENTE (`2caa3e3`) | PARCIAL | Modelo de contrato é PROVISÓRIO; sem DOCX; sem upload do documento assinado |
| 7 Retirada, renovação, devolução | EXISTENTE | EXISTENTE (`2caa3e3`) | Implementada; validação do usuário pendente | Sem reserva na confirmação; manutenção sem registro próprio |
| 8 Dashboard e relatórios | EXISTENTE | EXISTENTE (`82e0845`): Dashboard real ("Visão geral"), Relatórios e resumo do cliente | Implementada; validação do usuário pendente | Conferência dos indicadores com dados reais |
| 9 Portal do cliente | EXISTENTE | EXISTENTE (`82e0845`): `/portal/*`, "Vincular cliente" em Usuários e solicitações em Renovações | Implementada; validação do usuário pendente | Uso fora do computador da locadora depende de publicação |
| 10 Faturamento e fiscal | EXISTENTE só em simulação | EXISTENTE (`82e0845`): `/faturamento` (`/fiscal` redireciona) | PARCIAL | Regras da contabilidade; provedor real; credenciais de teste; nenhum documento tem valor fiscal |
| 11 Backup, restauração, inicialização | EXISTENTE (API e scripts Windows) | EXISTENTE (`82e0845`): `/backups` em Gestão | Implementada; validação do usuário pendente | Ensaio de restauração com dados reais; `update.ps1` nunca foi executado |
| 12 QA, E2E integral, guias, release | Auditoria independente corrigida (`b0d9ec4`); teste de aceite pela API (`892b6bd`) | E2E real de 9 roteiros em 4 tamanhos de tela | ENTREGA TÉCNICA FEITA; ACEITE DO USUÁRIO PENDENTE | Aceite do usuário e insumos externos (seção de pendências). **A versão 1.0 não está declarada concluída nem homologada** |

No commit `82e0845` nenhum item de menu aponta para página provisória: `frontend/src/demo`, o formulário e a tabela de demonstração foram removidos, e `Placeholder` serve apenas a endereços inexistentes (404). Os quatro guias da etapa 12 (INSTALLATION, ADMIN_GUIDE, USER_GUIDE e RELEASE_NOTES_1.0) estão escritos em `docs/` e ainda não commitados.

## O que existe e foi conferido no código

- Orçamentos: valor do item = quantidade × preço do período × nº de períodos; períodos de 1/7/15/30 dias corridos; preço de tabela e negociado guardados; estados rascunho, enviado, aprovado, rejeitado, cancelado e convertido, com expirado derivado; número ORC-AAAA-NNNNNN; duplicação; PDF.
- Contratos: diretos ou de orçamento aprovado (conversão única); número `N` e renovações `N.1`, `N.2`; próximo número configurável; estados rascunho, aguardando retirada, ativo, encerrado e cancelado, com vencendo/vencido derivados da data de devolução (antecedência padrão de 3 dias).
- Documentos de contrato: modelos com placeholders, PDF versionado e imutável com checksum; assinado nunca é substituído.
- Operação: retirada parcial ou total com vínculo de unidade física, devolução com condição e destino, renovação parcial ou total com três opções de preço e sem movimentar estoque, encerramento automático, linha do tempo por cadeia, repetição segura por identificador de operação.
- Estoque: ajuste manual não contradiz a custódia de contratos ativos.
- Telas: todas as rotas do menu interno e do portal têm tela real; filtros avançados em Contratos (origem, produto, equipamento, período e data).
- Relatórios: dashboard, resumo por cliente, doze relatórios e exportação Excel/PDF; valor contratado nunca apresentado como recebido.
- Portal: dados somente do cliente vinculado; registro alheio responde 404; solicitação de renovação exige decisão interna e não renova sozinha.
- Fiscal: documentos, trilha de retornos e interface de provedor; único provedor é a simulação, sem valor fiscal.
- Backup: conjunto `.zip` com banco, importações, documentos, fiscal e manifesto; verificação; agendamento diário opcional; retenção; restauração com frase + senha, cópia prévia e sem apagar arquivos.
- Windows: "Iniciar LocaControl.cmd", "Parar LocaControl.cmd", `scripts/launch.ps1`, `stop.ps1`, `update.ps1`.

Regras em BUSINESS_RULES; decisões em DECISIONS (ADR-014 a ADR-021); tabelas e APIs em BACKEND_SCHEMA; permissões em SECURITY.

## Banco configurado

Conferido por leitura somente em 11/10/2026: SQLite `data/locacontrol.db` na revisão **0010_backups**, 5 perfis, **32 permissões**, 1 usuário preservado, 1 modelo de contrato provisório. Zero linhas em clientes, orçamentos, contratos, documentos fiscais, vínculos de portal, `import_batches` e `app_settings`.

Migrations 0005–0010 aplicadas em 11/10, com cópias prévias em `data/backups`: `pre-quotes-20261011-084445.db` (banco em 0004), `pre-contracts-20261011-090635.db` (em 0005) e `pre-upgrade-20261011-092925.db` (em 0006, criada pelo `launch.ps1`). Nenhum fixture ou usuário de teste na base real. Não executar bootstrap: há conta existente.

## Verificação observada em 2026-10-11

Observada pelo coordenador sobre o código do commit `82e0845`. É evidência de testes automatizados com dados temporários, **não homologação pelo usuário**.

- Backend: `pytest backend/tests` com **141 passed, 1 warning** (depreciação Starlette/AnyIO, não bloqueante); `ruff check` sem erros. Inclui `test_release_journey.py` (cenário oficial de 26 passos pela API) e os 7 testes novos das correções da auditoria.
- Frontend: ESLint sem erros; Prettier `format:check` aprovado; Vitest **63 testes em 13 arquivos**, todos aprovados; build concluído com aviso do Vite de chunk principal acima de 500 kB.
- E2E real (`scripts/e2e-auth.py`, backend e banco temporários): **36 cenários aprovados** — 9 specs (auth, masters, imports, quotes, contracts, reports, portal, fiscal, backups) nos 4 projetos de `frontend/playwright.auth.config.ts`: desktop 1366×768, full-hd 1920×1080, tablet 820×1180 e mobile 390×844. Verificação Axe e de overflow horizontal nos temas claro e escuro conforme os specs.
- Visual (`npx playwright test`): **16 aprovados**. Smoke (`scripts/smoke.py`): aprovado.
- Scripts Windows: `launch.ps1` e `stop.ps1` exercitados em portas alternativas (subir, health, login recusado com 401, parar, PID inválido).

Ressalvas:

- Depois do E2E, duas frases de interface foram alteradas (`Roles.tsx` e `Imports.tsx`). Lint, format, Vitest, build e smoke foram repetidos e passaram; o E2E **não** foi repetido após essa mudança de texto.
- O agente de frontend relatou uma falha intermitente em `backups.spec.ts` (navegador fechado durante captura) numa execução anterior, sem causa identificada; não se repetiu.
- `update.ps1` não foi executado.
- Nenhuma verificação com dados reais da locadora nem por um usuário humano; sem teste com leitor de tela.
- A auditoria independente (11 achados, 1 de severidade alta — renovação com a mesma unidade física repetida —, todos corrigidos em `b0d9ec4`) foi somente leitura e cobriu só o backend: **não cobriu frontend, importação de Excel nem rotas de identidade**.

## Pendências externas (dependem do usuário ou de terceiros)

| Pendência | Desbloqueia |
| --- | --- |
| Excel real enviado em Gestão → Importações | Homologação da etapa 4; só depois, implementação da conversão do histórico de contratos/renovações (IMP-04B), que não existe |
| Modelo real de contrato, publicado em Configurações | Substituir o modelo provisório (etapa 6) |
| Dados da locadora (`LOCACONTROL_COMPANY_*` no `.env`) | Cabeçalho correto de orçamentos, contratos e relatórios (hoje "LocaControl") |
| Regras fiscais com a contabilidade, provedor escolhido e credenciais de teste | Adapter fiscal real e homologação (etapa 10) |
| Usuário percorrer o fluxo no navegador e dar o aceite | Declaração da versão 1.0 |
| Decisões de publicação P1–P4 (público, empresa única ou várias, infraestrutura, banco, domínio) | Qualquer acesso pela internet, inclusive uso remoto do portal |
| Decisão sobre mesclar `dev/etapas-4-12` em `master` | Integração do trabalho das etapas 4–12 (não há remoto configurado) |

## Melhorias técnicas em aberto

Conferidas no código em `82e0845`; nenhuma bloqueia o uso local. Lista completa de limites em RELEASE_NOTES_1.0 seção 6.

- Retiradas e Manutenção carregam as listas e filtram no navegador; com muito volume ficam lentas ou parciais.
- O histórico de orçamentos e contratos mostra "Usuário nº N", não o nome.
- Logs em `data/logs` sem rotação: sobrescritos a cada início.
- As cópias `pre-upgrade-*.db` (criadas pelo `launch.ps1`) e os conjuntos `_pre-restore` nunca são podados; a retenção só alcança os backups regulares.
- A descrição da permissão `workspace.view` em `backend/app/auth/catalog.py` ainda fala em "prévia dos módulos internos (sem dados comerciais reais)".
- Chunk principal do frontend acima de 500 kB (aviso do Vite).
- Áreas fora da auditoria independente: frontend, importação de Excel e rotas de identidade.
- E2E não repetido após a última mudança de texto; falha intermitente de `backups.spec.ts` sem causa identificada.

## Decisões técnicas revisáveis em aberto

Reserva de estoque na confirmação do contrato (não implementada); upload do documento assinado e DOCX (não existem); registro próprio de manutenção; aprovação da solicitação do portal apenas registra a decisão; fuso comercial fixo UTC−3.

## Publicação web

Nada foi publicado. Arquitetura atual local/LAN, sem deploy público, multiempresa ou cobrança de assinatura. Roteiro em PUBLICATION_ROADMAP.md.

## Próximos passos

Não há próxima tarefa de implementação desbloqueada: tudo o que resta depende do usuário (tabela de pendências acima). A lista ordenada, com a condição de cada item, está em AI_HANDOFF.md, seção PRÓXIMA AÇÃO EXATA.

Detalhe e comandos em AI_HANDOFF.md.
