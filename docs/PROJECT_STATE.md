# LocaControl — Estado do projeto

Atualização: 2026-10-11 (America/Sao_Paulo). Branch `dev/etapas-4-12`, commit `892b6bd`; baseline `2b3d1d2` em `master`. Sem repositório remoto configurado.

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
| 8 Dashboard e relatórios | EXISTENTE (API) | PENDENTE | PARCIAL | Dashboard da interface ainda é demonstração; não há tela de relatórios |
| 9 Portal do cliente | EXISTENTE (API) | PENDENTE | PARCIAL | Telas do portal e do vínculo conta–cliente |
| 10 Faturamento e fiscal | EXISTENTE só em simulação | PENDENTE | PARCIAL | Telas; regras da contabilidade; provedor real; credenciais de sandbox |
| 11 Backup, restauração, inicialização | EXISTENTE (API e scripts Windows) | PENDENTE (backups) | PARCIAL | Tela de backups; ensaio de restauração com dados reais |
| 12 QA, E2E integral, guias, release | Teste de aceite pela API (`892b6bd`) | — | INICIADA | Auditoria, E2E integral pela interface e guias; depende das telas das etapas 8–11 |

As telas das etapas 6 e 7 foram entregues por outro agente no commit `2caa3e3`; esta atualização documental conferiu as rotas e os arquivos, não reexecutou build nem E2E. Ao fim desta atualização havia trabalho NÃO commitado de outro agente em `frontend/` (arquivos novos de relatórios, portal, fiscal e backups em `src/lib` e `src/pages`): está em andamento e não foi conferido, por isso as telas das etapas 8–11 continuam registradas como PENDENTES.

## O que existe e foi conferido no código

- Orçamentos: valor do item = quantidade × preço do período × nº de períodos; períodos de 1/7/15/30 dias corridos; preço de tabela e negociado guardados; estados rascunho, enviado, aprovado, rejeitado, cancelado e convertido, com expirado derivado; número ORC-AAAA-NNNNNN; duplicação; PDF.
- Contratos: diretos ou de orçamento aprovado (conversão única); número `N` e renovações `N.1`, `N.2`; próximo número configurável; estados rascunho, aguardando retirada, ativo, encerrado e cancelado, com vencendo/vencido derivados da data de devolução (antecedência padrão de 3 dias).
- Documentos de contrato: modelos com placeholders, PDF versionado e imutável com checksum; assinado nunca é substituído.
- Operação: retirada parcial ou total com vínculo de unidade física, devolução com condição e destino, renovação parcial ou total com três opções de preço e sem movimentar estoque, encerramento automático, linha do tempo por cadeia, repetição segura por identificador de operação.
- Estoque: ajuste manual não contradiz a custódia de contratos ativos.
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

- `.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider`: **133 passed, 1 warning** no commit `d3916f3` (153 s). Execução anterior no mesmo dia, antes dos dois últimos commits: 132 passed.
- `backend/tests/test_release_journey.py` (commit `892b6bd`, cenário oficial da versão 1.0 percorrido pela API): **1 passed** quando executado isoladamente. A suíte completa não foi reexecutada depois desse commit; o esperado, ainda não observado, é 134.
- Aviso não bloqueante: depreciação Starlette/AnyIO.
- Não reexecutados nesta atualização: Ruff, build do frontend, Vitest, E2E e smoke. O commit `2caa3e3` registra "Vitest 49, E2E real 20 cenários e visual 16 conforme relatório do subagente"; esse resultado não foi reproduzido aqui.
- Os testes usam bancos e pastas temporários; não provam nada sobre dados reais.

## Pendências externas (dependem do usuário ou de terceiros)

| Pendência | Desbloqueia |
| --- | --- |
| Excel real enviado em Gestão → Importações | Homologação da etapa 4 e mapeamento do histórico de contratos |
| Modelo real de contrato | Substituir o modelo provisório (etapa 6) |
| Dados da locadora (`LOCACONTROL_COMPANY_*`) | Cabeçalho correto de orçamentos, contratos e relatórios (hoje "LocaControl") |
| Regras fiscais com a contabilidade, provedor escolhido e credenciais de sandbox | Adapter fiscal real e homologação (etapa 10) |
| Decisões de publicação P1–P4 (público, empresa única ou várias, infraestrutura, banco, domínio) | Qualquer acesso pela internet, inclusive uso remoto do portal |

## Decisões técnicas revisáveis em aberto

Reserva de estoque na confirmação do contrato (não implementada); upload do documento assinado e DOCX (não existem); registro próprio de manutenção; aprovação da solicitação do portal apenas registra a decisão; fuso comercial fixo UTC−3.

## Publicação web

Nada foi publicado. Arquitetura atual local/LAN, sem deploy público, multiempresa ou cobrança de assinatura. Roteiro em PUBLICATION_ROADMAP.md.

## Próximos passos

1. Validar as telas de contratos e operação.
2. Construir as telas de dashboard real, relatórios, portal, fiscal e backups sobre as APIs existentes.
3. Etapa 12: auditoria, E2E do fluxo integral e guias.

Detalhe e comandos em AI_HANDOFF.md.
