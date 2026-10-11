# LocaControl — AI Handoff

Checkpoint de retomada. Última atualização: 2026-10-11 (America/Sao_Paulo).

## Identificação

- Projeto: LocaControl (locação de equipamentos). Raiz: pasta `SAAS LOCACAO`.
- Branch: `dev/etapas-4-12`. Commit conferido: `82e0845`. Baseline: `2b3d1d2` em `master`. Sem remoto configurado.
- Autorização vigente do usuário: "Sim, executar 4–12", com commits por etapa validada nesta branch. Publicação, contratação e uso de credenciais reais NÃO estão autorizados.
- Etapa atual: 12, com a **entrega técnica concluída** (auditoria do backend corrigida, teste de aceite, telas das etapas 8–11, E2E e guias). **A versão 1.0 NÃO está declarada concluída nem homologada**: faltam o aceite do usuário e os insumos externos listados em PRÓXIMA AÇÃO EXATA. A etapa 4 segue PARCIAL por depender do Excel real.

## Concluído (não refazer)

| Item | Commit | Evidência |
| --- | --- | --- |
| Etapas 0–3 e mecanismo da etapa 4 | `2b3d1d2` | Baseline |
| Etapa 5: backend e tela de orçamentos | `d687a00`, `6f7dffc` | `test_quotes.py` |
| Etapas 6/7: backend de contratos, documentos, retirada, renovação e devolução | `7420b75` | `test_contracts.py`, `test_operations.py` |
| Etapas 6/7: telas de contratos, renovações, retiradas, devoluções e manutenção | `2caa3e3` | `contracts.spec.ts` no E2E real |
| Custódia de contratos protege o estoque manual | `2b44e8e` | `test_operations.py` |
| Filtro por origem na listagem de contratos | `d3916f3` | `test_reports.py` |
| Etapa 8: API de dashboard, relatórios e exportações | `f92cb22` | `test_reports.py` |
| Etapa 9: API do portal | `a6638d6` | `test_portal.py` |
| Etapa 10: API fiscal em simulação | `68374a7` | `test_fiscal.py` |
| Etapa 11: API de backup/restauração e scripts Windows | `70c1d5e`, `3062f8f` | `test_backups.py` |
| Etapa 12: teste de aceite do cenário oficial (26 passos) pela API | `892b6bd` | `test_release_journey.py` |
| Log de mensagens da aplicação e variáveis novas no `.env.example` | `2036cea` | `backend/app/main.py`, `.env.example` |
| Etapa 12: correções da auditoria independente do backend (11 achados, 1 de severidade alta) | `b0d9ec4` | 7 testes novos nos módulos afetados |
| Etapas 8–11: telas de Dashboard real ("Visão geral"), Relatórios, resumo do cliente, Portal, Faturamento e fiscal, Backups, "Vincular cliente" em Usuários, solicitações em Renovações e filtros avançados em Contratos; remoção de `frontend/src/demo` | `82e0845` | Vitest e specs `reports`, `portal`, `fiscal` e `backups` do E2E real |
| Etapa 12: guias INSTALLATION, ADMIN_GUIDE, USER_GUIDE e RELEASE_NOTES_1.0 | Não commitados | Arquivos em `docs/` |

Não refazer: autenticação e perfis, estrutura visual, cadastros, estoque, preços, importador, orçamentos, contratos, operação, os backends e as telas das etapas 8–11 e os guias; migrations 0001–0010. Não recriar arquivos por checklist antiga. Não resetar usuário nem banco. Não executar bootstrap: existe uma conta.

## Em andamento

Nada em implementação. Trabalho não commitado ao fim desta atualização: os quatro guias novos, `docs/EXCEL_IMPORT.md` e a passada de consistência da documentação. Conferir `git status` antes de afirmar o estado.

## PRÓXIMA AÇÃO EXATA

Não há tarefa de implementação desbloqueada. Tudo abaixo depende do usuário; não iniciar nenhum item sem a condição indicada.

| # | Ação do usuário | Condição de desbloqueio e o que vem depois |
| --- | --- | --- |
| 1 | Enviar o Excel real em Gestão → Importações e homologar | O arquivo ser enviado pela tela (nunca pedir caminho local). Conferir o lote, mapear, rodar o DRY RUN, comparar com o original e só então confirmar. **Só depois disso** implementar a conversão do histórico de contratos/renovações (IMP-04B), que não existe; as entidades de destino já existem (origem IMPORTADO) |
| 2 | Fornecer o modelo real de contrato | Texto entregue pelo usuário; publicar em Gestão → Configurações → Modelo de contrato, sem marcar "provisório" |
| 3 | Preencher `LOCACONTROL_COMPANY_*` no `.env` | Usuário informar nome, documento, endereço e contato da locadora; reiniciar o sistema |
| 4 | Definir as regras fiscais com a contabilidade, escolher o provedor e fornecer credenciais de teste | Com os três em mãos, implementar um adapter real (contrato em `backend/app/fiscal/provider.py`) e homologar em ambiente de teste. Hoje só existe a simulação |
| 5 | Percorrer o fluxo no navegador e dar o aceite | Usuário usar as telas (roteiro em USER_GUIDE) e apontar ajustes. Sem isso a versão 1.0 não é declarada |
| 6 | Decidir a publicação web | Decisões P1–P4 de PUBLICATION_ROADMAP. Nada foi publicado; publicação, contratação e credenciais reais não estão autorizadas |
| 7 | Decidir se `dev/etapas-4-12` é mesclada em `master` | Decisão explícita do usuário. Não há remoto configurado |

## Limites conhecidos e melhorias técnicas em aberto

Conferidos no código em `82e0845`; lista completa para o usuário em RELEASE_NOTES_1.0 seção 6.

- Listas de Retiradas e Manutenção filtram no navegador (`frontend/src/pages/Operations.tsx`, `Maintenance.tsx`).
- Histórico de orçamentos e contratos mostra "Usuário nº N", não o nome (`quotes-detail.tsx`, `contracts-detail.tsx`).
- Sem reserva de estoque na confirmação do contrato; a disponibilidade é conferida na retirada (ADR-016).
- Logs em `data/logs` sem rotação, sobrescritos a cada início (`scripts/launch.ps1`).
- Cópias `pre-upgrade-*.db` e conjuntos `_pre-restore` nunca são podados; `prune` em `backend/app/ops/backup.py` só alcança backups regulares.
- Descrição da permissão `workspace.view` desatualizada em `backend/app/auth/catalog.py` ("prévia dos módulos internos").
- Chunk principal do frontend acima de 500 kB (aviso do Vite no build).
- A auditoria independente foi somente leitura e só do backend: frontend, importação de Excel e rotas de identidade não foram cobertos.
- E2E não repetido depois da alteração de duas frases (`Roles.tsx`, `Imports.tsx`); falha intermitente de `backups.spec.ts` relatada uma vez, sem causa identificada.
- `scripts/update.ps1` nunca foi executado. Sem teste com leitor de tela. Sem ensaio de restauração com dados reais.
- Só PDF, sem DOCX; sem upload do documento assinado; manutenção sem registro próprio; `.xls` binário não suportado; uma aba/módulo por importação; backup pelo sistema só para SQLite local.

Decisões técnicas revisáveis que o usuário pode querer mudar: sem reserva de estoque na confirmação do contrato; renovação já nasce ativa; aprovação de solicitação do portal só registra a decisão; backup em `.zip`; fuso UTC−3 fixo. Ver ADR-015 a ADR-021.

## Comandos de verificação

Executar na raiz. Caminho com espaço: usar aspas.

```powershell
# Backend completo — observado em 11/10 sobre 82e0845: 141 passed, 1 warning
.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider

# Um módulo
.\.venv\Scripts\python.exe -m pytest backend/tests/test_operations.py -q -p no:cacheprovider

# Lint, formato, TypeScript e build
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check.ps1

# Testes de frontend — observado em 11/10: 63 testes em 13 arquivos
npm.cmd --prefix frontend run test -- --run

# E2E real (API + banco temporário), sempre depois do build, nunca em paralelo com ele
# Observado em 11/10: 36 cenários (9 specs em 4 tamanhos de tela)
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE = "$env:LOCALAPPDATA\ms-playwright\chromium-1234\chrome-win64\chrome.exe"
$env:PYTHONPATH = 'backend'
.\.venv\Scripts\python.exe scripts/e2e-auth.py

# Revisão do banco local
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\migrate.ps1 -Action current
```

Usar `-p no:cacheprovider`: o cache antigo `backend/.pytest_cache` pode negar acesso.

## Avisos operacionais desta máquina

- Plugin GateGuard (ecc): pode negar a primeira criação ou edição de cada arquivo, e alguns comandos, até os fatos serem declarados. Declarar em uma frase o que o arquivo é, quem o importa, o efeito em API/schema e a instrução do usuário, e repetir a mesma operação.
- E2E: precisa de `PLAYWRIGHT_CHROMIUM_EXECUTABLE=%LOCALAPPDATA%\ms-playwright\chromium-1234\chrome-win64\chrome.exe` e de `PYTHONPATH=backend`.
- Build do frontend limpa `frontend/dist`: não rodar smoke ou E2E enquanto o build está em andamento.
- Vários agentes podem estar editando a árvore ao mesmo tempo (backend, frontend e documentação). Conferir `git status` e `git log` antes de afirmar o estado.
- Heredocs longos no Bash da ferramenta falharam com texto contendo crases; scripts temporários gravados em arquivo funcionaram.
- Não encerrar processos alheios; `scripts/stop.ps1` só encerra o servidor registrado em `data/locacontrol.pid`.

## Banco de dados e arquivos

- Local: revisão `0010_backups`, 5 perfis, 32 permissões, 1 usuário, 1 modelo de contrato provisório; sem dados comerciais.
- Cópias prévias de 11/10 em `data/backups`: `pre-quotes-20261011-084445.db`, `pre-contracts-20261011-090635.db`, `pre-upgrade-20261011-092925.db`.
- Nenhuma migration pendente. Downgrade só em bancos temporários de teste.
- Arquivos fora do banco: `data/imports`, `data/documents`, `data/fiscal`. O backup do sistema leva tudo junto.
- `Iniciar LocaControl.cmd` aplica migrations pendentes sozinho, depois de copiar o banco.

## Dependências

Backend acrescentou `reportlab` (PDF) em 11/10; manifesto e lock atualizados. openpyxl agora também gera as exportações. Frontend: conferir `frontend/package.json` antes de afirmar mudanças.

## Dados temporários e mocks

Testes usam SQLite, usuários, pastas e workbooks temporários. Nenhum fixture na base real. Não há mais dados de demonstração na interface: `frontend/src/demo` foi removido em `82e0845`. O provedor fiscal é simulação e marca seus documentos como tal.

## Credenciais e segredos

Nenhuma credencial registrada em documentos. Não copiar tokens, senhas, hashes ou conteúdo de `.env`. O `.zip` de backup contém o banco inteiro, inclusive hashes de senha: tratar como confidencial.

## Erros conhecidos

Nenhuma suíte falhando na verificação de 11/10 sobre `82e0845` (números e ressalvas em PROJECT_STATE). Limites na seção "Limites conhecidos e melhorias técnicas em aberto" acima.

## Documentos a ler na retomada

PROJECT_STATE (estado por etapa), DECISIONS (ADR-014 a ADR-021), BUSINESS_RULES (regras confirmadas), BACKEND_SCHEMA (tabelas e APIs), SECURITY (permissões e portal), RELEASE_NOTES_1.0 (limites e pendências), DESIGN_SYSTEM e CONTINUE_PROMPT.

## Últimas sessões

- 2026-10-08: etapa 3 concluída; etapa 4 implementada e testada com fixtures; banco em 0004.
- 2026-10-11 (manhã): documentos estruturantes PRD, TRD, APP_FLOW, DESIGN_BRIEF e BACKEND_SCHEMA.
- 2026-10-11: baseline no Git; backends das etapas 5–11; telas de orçamentos e de contratos/operação; banco em 0010; documentação permanente atualizada.
- 2026-10-11 (fechamento técnico): correções da auditoria do backend, telas das etapas 8–11, guias da etapa 12 e verificação completa; versão 1.0 não declarada, aguardando o usuário.
