# LocaControl — Registro de validação

Cada validação vale apenas para o SHA indicado. Resultados de SHAs anteriores não substituem a validação do SHA atual.

## 2026-11-01 — SHA `af0474fa0cc50dd60c9ddf03d458757a0ae53688`

Cabeça do PR #1 (`dev/etapas-4-12` → `master`), aberto e não mesclado no momento da validação. Árvore de trabalho limpa. Executado em ambiente isolado: bancos SQLite e pastas de documentos, importação, fiscal e backup temporários; o banco operacional `data/locacontrol.db` não foi aberto para escrita nem recebeu fixtures.

| Verificação | Comando | Resultado |
| --- | --- | --- |
| Lint e formato do backend | `ruff check` / `ruff format --check` | aprovado; 92 arquivos formatados |
| Backend, incluindo migrations de banco vazio, upgrade a partir de revisões antigas, downgrade e `alembic check` | `pytest backend/tests` | 142 passaram, 1 aviso de depreciação (starlette/anyio) |
| Frontend: lint, formato, unitários, build | `npm run lint`, `format:check`, `test`, `build` | sem erros; 63 testes em 13 arquivos; build concluído (aviso de chunk acima de 500 kB) |
| E2E real (9 specs × desktop 1366×768, Full HD, tablet, mobile; Axe e overflow em claro/escuro) | `scripts/e2e-auth.py` | 36 passaram em 7,2 min |
| Regressão visual | `npx playwright test` | 16 passaram |
| Smoke (backend, revisão do banco, HTML de produção, proxy Vite) | `scripts/smoke.py` | aprovado |

Ao final, `data/` continha apenas `backups`, `locacontrol.db` e `logs`, como antes, e `git status` não mostrava alterações.

Não coberto por esta validação: instalação em máquina Windows limpa, `scripts/update.ps1`, uso em rede local, leitores de tela e homologação com dados reais.

## 2026-11-01 — SHA `27945bdef0d35a39202ed2680bc83191fc2cb132`

Cabeça do PR #3 (`p0/integridade`, sobre o PR #2), com o modo manutenção, o desfazer automático da restauração, o teste de falha na migration pós-restauração e a recusa de restauração com a pasta de backups em outro disco. Árvore limpa; ambiente isolado; banco operacional não aberto para escrita.

| Verificação | Resultado |
| --- | --- |
| `ruff check` | aprovado |
| `pytest backend/tests` | 154 passaram (142 do SHA anterior + 12 de integridade) |
| Vitest e build do frontend | 63 testes; build concluído |
| E2E real (`scripts/e2e-auth.py`) | 36 passaram |
| Smoke | aprovado |

Este registro foi acrescentado em commit posterior ao SHA testado e não altera código.

## 2026-11-02 — SHA `00d4b59` (P1-C, proteção automática)

Cabeça da branch `p1/c-protecao` (PR sobre `p1/b-instalacao`). Executado no **Linux da nuvem** (Python 3.13, Node 22, Chromium 1243 do Playwright), não no Windows; bancos, pastas e servidores temporários; nenhum banco operacional.

| Verificação | Resultado |
| --- | --- |
| `ruff check backend scripts/smoke.py scripts/e2e-auth.py` / `ruff format --check backend` | aprovado; 104 arquivos formatados |
| `pytest backend/tests` | 192 passaram, 1 pulado (ACL do Windows, `os.name != "nt"`), 1 aviso de depreciação. Referência Windows no `b027d7a`: 183; no Linux, o `b027d7a` deu 182 + 1 pulado. Novos: 10 (`test_protection.py`, `test_drafts.py`, restauração com pasta de backups em outro sistema de arquivos) |
| Frontend: `lint`, `format:check`, Vitest, `build` | sem erros; 78 testes em 16 arquivos; build concluído (aviso conhecido de chunk acima de 500 kB) |
| E2E (`scripts/e2e-auth.py`) | 36 passaram (edição com login, 4 tamanhos de tela) + 4 (edição local, desktop e mobile: rascunho que sobrevive a recarregar e à perda da sessão; restauração só com a frase) |
| Smoke (`scripts/smoke.py`) | aprovado |

Não coberto: Windows (instalador, pendrive/HD externo como pasta de backups ou segunda cópia, `msvcrt`/ACL), backup automático real de 20 minutos durante horas, leitores de tela.

Este registro foi acrescentado em commit posterior ao SHA testado e não altera código.

## 2026-11-03 — SHA `a01dce3` (P1-D, rede local e pareamento)

Cabeça da branch `p1/d-rede` (PR sobre `p1/c-protecao`). Executado no **Linux da nuvem**, não no Windows; bancos, pastas e servidores temporários. As "estações" são clientes que chegam ao servidor pelo endereço de rede do contêiner (não loopback), com cookies próprios.

| Verificação | Resultado |
| --- | --- |
| `ruff check backend scripts/smoke.py scripts/e2e-auth.py` / `ruff format --check backend` | aprovado; 110 arquivos formatados |
| `pytest backend/tests` | 208 passaram, 1 pulado (ACL do Windows), 1 aviso de depreciação. Novos: 11 em `test_stations.py` e 5 em `test_network_server.py` (servidor real `python -m app.server` em modo rede: edição concorrente, retirada concorrente da mesma unidade, confirmação concorrente, backup durante escritas de duas estações, queda e retorno do principal) |
| Frontend: `lint`, `format:check`, Vitest, `build` | sem erros; 82 testes em 18 arquivos; build concluído (aviso conhecido de chunk acima de 500 kB) |
| E2E (`scripts/e2e-auth.py`) | 36 (edição com login) + 4 (edição local) + 1 (rede: principal em 127.0.0.1 e estação pelo endereço de rede — pareamento, limites da estação, revogação) |
| Smoke (`scripts/smoke.py`) | aprovado |

Não coberto: estações Windows reais, firewall do Windows, acesso por nome do computador, IPv6, desempenho com muitas estações.

Este registro foi acrescentado em commit posterior ao SHA testado e não altera código.
