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

## 2026-11-03 — SHA `f106d08` (P1-D após a auditoria: A1, A2, M4, M5 e importação só no principal)

Cabeça da branch `p1/d-rede` (PR #7), que incorpora o P1-C validado em `9156985`. Bateria num **checkout limpo e destacado nesse SHA**, no **Linux da nuvem**, não no Windows; as "estações" são clientes pelo endereço de rede do contêiner, com cookies próprios.

| Verificação | Resultado |
| --- | --- |
| `ruff check` / `ruff format --check` | aprovado |
| `pytest backend/tests` | 235 passaram, 1 pulado (ACL do Windows). Novos: `test_station_rotation.py` (4: cópia detectada nos dois sentidos, sem falso positivo para resposta perdida, navegador ocioso e abas em paralelo, oferta a cada sessão), `test_registry_resilience.py` (8: fsync e cópia, recuperação pela `.bak` preservando revogação, quatro formas de arquivo ilegível com o principal funcionando, reparo auditado), `test_station_identity.py` (2), importação só no principal (`test_stations.py`), servidor real com data comercial controlada e cópia de credencial detectada (`test_network_server.py`, 7) |
| Frontend: `npm ci`, lint, `format:check`, Vitest, `build` | sem erros; 85 testes em 18 arquivos |
| E2E (`scripts/e2e-auth.py`) | 36 + 4 + 1 (rede) |
| Smoke | aprovado |

Correção de registro: a validação de `a01dce3` (acima, 208 passaram) dependia do horário — `test_two_stations_withdraw_the_same_unit_at_once` só passava entre 21h e 24h de Brasília (achado M5). Desde `e7a552d` o servidor do teste roda com a data comercial fixada; a suíte passou nesta máquina em duas execuções completas na manhã de 2026-11-03 (UTC−3), fora da janela de 21h–24h em que o teste antigo passava, e o teste novo `test_the_server_uses_the_controlled_business_date` prova o controle (2 diárias → VENCENDO, 10 → ATIVO). Durante o desenvolvimento, o commit `39c8e02` (A1) foi feito com quatro testes de atualização de bases antigas falhando, corrigidos em `0e52a49`.

Pendente no Windows: duas estações reais, rotação por horas sem revogação indevida, cópia de cookies entre PCs, `fsync` do `stations.json` no NTFS, firewall, acesso pelo nome do computador. Não declarar homologado.

Este registro foi acrescentado em commit posterior ao SHA testado e não altera código.

## 2026-11-03 — SHA `cf6de29643214586a46fd785f7122c428417f738` (P1-E: instalador do Windows, HTTPS local, reserva de espaço)

Cabeça da branch `p1/e-instalador` (PR sobre `p1/d-rede`). Duas execuções independentes no **mesmo SHA**: (1) checkout limpo e destacado no **Linux da nuvem** (Python 3.13, Node 22, Chromium 1243); (2) **CI do GitHub**, execução [41653655941](https://github.com/bezerramaison7-debug/LocaControl/actions/runs/41653655941), com um job Linux (`ubuntu-24.04`) e dois jobs Windows (`windows-2022`, Windows Server 2022 descartável, Python 3.13.17). Sem dados comerciais reais; bancos, pastas e servidores temporários.

| Verificação | Linux (nuvem) | CI Linux | CI Windows |
| --- | --- | --- | --- |
| `ruff check` / `ruff format --check` | aprovado | aprovado | — |
| `pytest backend/tests` | 256 passaram, 2 pulados (ACL e DPAPI, só Windows) | aprovado | **257 passaram, 1 pulado** (caminhos POSIX); DPAPI, ACL e restauração da pasta de backups em outra unidade (C: × D:) executados |
| Frontend: `npm ci`, lint, `format:check`, Vitest, `build` | 86 testes em 18 arquivos | aprovado | `build` |
| E2E (`scripts/e2e-auth.py`; rede pelo servidor real em **HTTPS**, Chromium confiando só na chave do certificado do servidor) | 36 + 4 + 1 | aprovado | — |
| Smoke | aprovado | aprovado | — |
| Name Constraints no verificador do Windows (`X509Chain`/CryptoAPI, CA na Raiz da máquina) | — | — | certificado permitido aceito; nome/IP públicos recusados com status de Name Constraint |
| Instalador (PyInstaller 6.22.3 + Inno Setup 6) e teste silencioso `scripts/ci/windows-install-test.ps1` | — | — | **27 conferências aprovadas** (abaixo) |

Conferências do teste de instalação no Windows da CI: instalador com código 0; programa em Arquivos de Programas; `.env` com edição local e modo rede; regra de firewall limitada à sub-rede local; servidor responde em `http://127.0.0.1:8000`; CA local criada; cliente gravado; HTTPS da loja disponível; IP privado no certificado do servidor (10.1.0.x); **HTTPS recusado pelo Windows antes de confiar na CA**; HTTP não escuta na rede; `conectar` com código errado sai com 2 e não grava nada; com o código certo instala a CA em `Cert:\LocalMachine\Root`; **HTTPS validado pelo Windows depois de confiar**; `desconectar` remove a CA; atualização com o servidor em execução (código 0), linha própria do `.env` preservada, escolha anterior reaproveitada, servidor de volta, cliente preservado; desinstalação silenciosa (código 0), programa removido, **banco preservado**, regra de firewall removida.

Correções feitas durante esta validação (todas em commits próprios antes deste SHA):
- a primeira execução da CI (`6abce79`, [41651611002](https://github.com/bezerramaison7-debug/LocaControl/actions/runs/41651611002)) falhou em dois testes no Linux: o runner tinha **12,7 GB livres**, abaixo da reserva padrão (≈ 13,6 GB), e o produto recusou corretamente. Os testes dependiam do disco real sem querer (`monkeypatch.undo()` desfazia o disco simulado; um teste de processos à parte não tinha reserva própria) — corrigido em `4f7bff3`, sem mudar a regra do produto;
- o teste de instalação passou em todas as conferências mas o passo saía com 1 por causa do `$LASTEXITCODE` do último `netsh` (regra já removida) — corrigido em `fa8cece`;
- o teste de restauração de outro disco era pulado no Windows — passou a usar outra unidade em `cf6de29`.

Observação de desempenho (não é falha): no Windows da CI, dois testes de `test_storage.py` que criam dezenas de backups levam ~110 s cada (segundos no Linux), provavelmente pelo `fsync` de cada arquivo no NTFS. Medir em computador físico com a frequência real de 20 minutos.

**O que esta validação NÃO comprova**: Windows 10/11 de usuário (UAC, SmartScreen com instalador sem assinatura, antivírus); o assistente gráfico (a CI só usa o modo silencioso); uma estação em **outro** computador (na CI, a mesma máquina faz os dois papéis); Edge, Chrome e Firefox reais diante da CA; nome do computador e `.local`; DHCP; DPAPI após reinício e migração; atalho de inicialização; pendrive/HD externo; disco pequeno real. Lista completa em `docs/P1_BRIEFING.md` ("P1-E — o que falta validar em computador físico"). **Não declarar homologado.**

Este registro foi acrescentado em commit posterior ao SHA testado e não altera código.
