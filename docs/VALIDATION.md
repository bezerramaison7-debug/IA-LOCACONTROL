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

## 2026-11-03 — SHA `9156985` (P1-C após a auditoria: A3 limites de espaço e M2 durabilidade)

Cabeça da branch `p1/c-protecao` (PR #6) depois das correções autorizadas pela diretiva do arquiteto de 2026-11-03. Bateria executada num **checkout limpo e destacado nesse SHA** (`git worktree add --detach`, `npm ci` do zero), no **Linux da nuvem**, não no Windows; bancos, pastas e servidores temporários.

| Verificação | Resultado |
| --- | --- |
| `ruff check` / `ruff format --check` | aprovado |
| `pytest backend/tests` | 202 passaram, 1 pulado (ACL do Windows). Novos: `test_storage.py` (7: reserva em discos de 32 GB a 2 TB, teto com remoção na ordem segura, recuperação acima do teto, segunda cópia e importação respeitando a reserva, nova tentativa por hora) e `test_durability.py` (3: fsync, conjunto reprovado após gravar não apaga nada, segunda cópia verificada) |
| Frontend: `npm ci`, lint, `format:check`, Vitest, build | sem erros; 79 testes em 16 arquivos |
| E2E (`scripts/e2e-auth.py`) | 36 + 4 |
| Smoke | aprovado |

Discos nos testes: a suíte usa um disco simulado (1 TB, 900 GB livres) por padrão, para não depender da máquina; `test_storage.py` simula discos pequenos, grandes e cheios. No E2E, as bases temporárias recebem limites reduzidos (1 GB livre, 0 %), porque o disco desta máquina (252 GB, 29 GB livres) **não atende** a reserva padrão de 15 % — com o padrão, o backup é recusado, como projetado. Medição do M1 em `docs/P1_SQLITE_CONCORRENCIA.md`.

Pendente no Windows: limites com discos reais, `fsync` no NTFS, pendrive/HD externo, medição do M1 com `scripts/measure_backup_lock.py`. Não declarar homologado.

Este registro foi acrescentado em commit posterior ao SHA testado e não altera código.
