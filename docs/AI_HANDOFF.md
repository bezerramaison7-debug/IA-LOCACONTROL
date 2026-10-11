# LocaControl — AI Handoff

Checkpoint de retomada. Última atualização: 2026-10-11 (America/Sao_Paulo).

## Identificação

- Projeto: LocaControl (locação de equipamentos). Raiz: pasta `SAAS LOCACAO`.
- Branch: `dev/etapas-4-12`. Commit conferido: `892b6bd`. Baseline: `2b3d1d2` em `master`. Sem remoto configurado.
- Autorização vigente do usuário: "Sim, executar 4–12", com commits por etapa validada nesta branch. Publicação, contratação e uso de credenciais reais NÃO estão autorizados.
- Etapa atual: frontends das etapas 8–11, depois etapa 12. A etapa 4 segue PARCIAL por depender do Excel real.

## Concluído (não refazer)

| Item | Commit | Evidência |
| --- | --- | --- |
| Etapas 0–3 e mecanismo da etapa 4 | `2b3d1d2` | Baseline |
| Etapa 5: backend e tela de orçamentos | `d687a00`, `6f7dffc` | `test_quotes.py` |
| Etapas 6/7: backend de contratos, documentos, retirada, renovação e devolução | `7420b75` | `test_contracts.py`, `test_operations.py` |
| Etapas 6/7: telas de contratos, renovações, retiradas, devoluções e manutenção | `2caa3e3` | Relatado no commit; não reexecutado na atualização documental |
| Custódia de contratos protege o estoque manual | `2b44e8e` | `test_operations.py` |
| Filtro por origem na listagem de contratos | `d3916f3` | `test_reports.py` |
| Etapa 8: API de dashboard, relatórios e exportações | `f92cb22` | `test_reports.py` |
| Etapa 9: API do portal | `a6638d6` | `test_portal.py` |
| Etapa 10: API fiscal em simulação | `68374a7` | `test_fiscal.py` |
| Etapa 11: API de backup/restauração e scripts Windows | `70c1d5e`, `3062f8f` | `test_backups.py` |
| Etapa 12 (início): teste de aceite do cenário oficial pela API | `892b6bd` | `test_release_journey.py`, 1 passed isoladamente |

Não refazer: autenticação e perfis, estrutura visual, cadastros, estoque, preços, importador, orçamentos, contratos, operação e os backends das etapas 8–11; migrations 0001–0010. Não recriar arquivos por checklist antiga. Não resetar usuário nem banco. Não executar bootstrap: existe uma conta.

## Em andamento

- Telas de contratos/operação: commitadas em `2caa3e3`. Falta validá-las nesta máquina (build, Vitest, E2E real e visual) e conferir com o usuário.
- Dashboard: no commit `892b6bd` a tela ainda usa `frontend/src/demo/data.ts`; a API real é `GET /api/dashboard`.
- Telas das etapas 8–11: havia arquivos não commitados de outro agente em `frontend/src/lib` (reports, portal, fiscal, backups) e `frontend/src/pages` (Reports, customer-summary, portal-shared), além de alterações em Dashboard e navegação. Conferir `git status` e `git log` para saber o que já foi concluído antes de recomeçar qualquer tela.

## Pendente, com condição de desbloqueio

| Pendência | Condição |
| --- | --- |
| Telas de dashboard real, relatórios, portal, fiscal e backups | Nenhuma externa: as APIs existem (catálogo em BACKEND_SCHEMA seção 8) |
| Homologação do Excel (etapa 4) | Usuário enviar o arquivo real em Gestão → Importações; nunca pedir caminho local |
| Conversão do histórico de contratos/renovações (IMP-04B) | Excel real, para definir o mapeamento; as entidades de destino já existem (origem IMPORTADO) |
| Modelo real de contrato | Usuário fornecer o modelo; publicar como nova versão em `POST /api/contracts/templates` sem `is_provisional` |
| Cabeçalho dos documentos | Usuário informar os dados da locadora para `LOCACONTROL_COMPANY_*` no `.env` |
| Provedor fiscal real | Regras da contabilidade, provedor escolhido e credenciais de sandbox; registrar o adapter em `app/fiscal/provider.py` |
| Publicação web | Decisões P1–P4 de PUBLICATION_ROADMAP; nada foi publicado |
| Etapa 12 | Telas das etapas 8–11 concluídas |

Decisões técnicas revisáveis que o usuário pode querer mudar: sem reserva de estoque na confirmação do contrato; renovação já nasce ativa; só PDF, sem DOCX; sem upload do documento assinado; aprovação de solicitação do portal só registra a decisão; backup em `.zip`; fuso UTC−3 fixo. Ver ADR-015 a ADR-021.

## PRÓXIMA AÇÃO EXATA

a) Concluir e validar as telas de contratos/operação: rodar build, Vitest e o E2E real (comandos abaixo), corrigir o que falhar e registrar os números observados em PROJECT_STATE.

b) Construir, sobre as APIs existentes, as telas de: dashboard real (`/api/dashboard`, substituindo a demonstração), relatórios (`/api/reports`), portal do cliente (`/api/portal/*`, mais o vínculo em `/api/users/{id}/customer` e a fila `/api/renewal-requests`), fiscal (`/api/fiscal/*`, sempre identificando a simulação) e backups (`/api/backups`). Seguir DESIGN_SYSTEM e os padrões de `frontend/src/pages/Quotes.tsx` e `Contracts.tsx`. Commit por etapa validada.

c) Etapa 12 (o teste de aceite pela API já existe em `test_release_journey.py`): auditoria funcional, de segurança e de UX; E2E pela interface do fluxo integral (cliente → produto/preço/estoque → orçamento aprovado → contrato → retirada → renovação → devolução parcial → nova renovação → devolução total → encerramento); guias INSTALLATION, USER_GUIDE, ADMIN_GUIDE e RELEASE_NOTES_1.0. Esses quatro arquivos ainda não existem e só devem ser escritos depois das telas.

Em paralelo, quando o usuário enviar o Excel real: conferir o lote, mapear, rodar o DRY RUN, comparar com o original e só então confirmar.

## Comandos de verificação

Executar na raiz. Caminho com espaço: usar aspas.

```powershell
# Backend completo — observado em 11/10: 133 passed em d3916f3; 892b6bd acrescentou test_release_journey.py (1 passed isolado)
.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider

# Um módulo
.\.venv\Scripts\python.exe -m pytest backend/tests/test_operations.py -q -p no:cacheprovider

# Lint, formato, TypeScript e build (não reexecutado na atualização documental de 11/10)
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check.ps1

# Testes de frontend
npm.cmd --prefix frontend run test -- --run

# E2E real (API + banco temporário), sempre depois do build, nunca em paralelo com ele
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
- Vários agentes podem estar editando a árvore ao mesmo tempo (backend, frontend e documentação). Conferir `git status` e `git log` antes de afirmar o estado; durante esta atualização chegaram os commits `2b44e8e`, `2caa3e3` e `d3916f3`.
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

Testes usam SQLite, usuários, pastas e workbooks temporários. Nenhum fixture na base real. O Dashboard da interface ainda é demonstração identificada. O provedor fiscal é simulação e marca seus documentos como tal.

## Credenciais e segredos

Nenhuma credencial registrada em documentos. Não copiar tokens, senhas, hashes ou conteúdo de `.env`. O `.zip` de backup contém o banco inteiro, inclusive hashes de senha: tratar como confidencial.

## Erros conhecidos

Nenhuma suíte de backend falhando em `d3916f3`; em `892b6bd` só o módulo novo foi executado. Limites: `.xls` binário não suportado; uma aba/módulo por importação; backup pelo sistema só para SQLite local; sem rotação de logs. O `.env.example` não lista as variáveis novas além de `LOCACONTROL_COMPANY_*` (as demais têm padrão em `backend/app/core/config.py` e estão descritas no README).

## Documentos a ler na retomada

PROJECT_STATE (estado por etapa), DECISIONS (ADR-014 a ADR-021), BUSINESS_RULES (regras confirmadas), BACKEND_SCHEMA (tabelas e APIs), SECURITY (permissões e portal), DESIGN_SYSTEM e CONTINUE_PROMPT.

## Últimas sessões

- 2026-10-08: etapa 3 concluída; etapa 4 implementada e testada com fixtures; banco em 0004.
- 2026-10-11 (manhã): documentos estruturantes PRD, TRD, APP_FLOW, DESIGN_BRIEF e BACKEND_SCHEMA.
- 2026-10-11: baseline no Git; backends das etapas 5–11; telas de orçamentos e de contratos/operação; banco em 0010; documentação permanente atualizada.
