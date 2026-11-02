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
