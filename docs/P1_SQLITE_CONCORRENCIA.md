# LocaControl — Concorrência no SQLite: backup (M1) e importação (M3)

Investigação pedida pela diretiva do arquiteto de 2026-11-03: medir e propor antes de alterar transações ou a configuração do SQLite. **Nada foi alterado** no modo de journal (`delete`), no `timeout` (5 s) nem nas transações.

## M1 — gravações durante o backup

O backup usa a API de backup online do SQLite (`sqlite3.Connection.backup`), que mantém uma leitura no banco enquanto copia as páginas. No modo `delete` (rollback journal), uma gravação que precisa confirmar espera a leitura terminar; se esperar mais que o `timeout` de 5 s, a requisição recebe 503 e a transação é desfeita (sem corromper nada).

Medição no Linux da nuvem (SSD, `scripts/measure_backup_lock.py`, gravações de rascunho em sequência durante o backup):

| Banco | Só a cópia SQLite | Backup completo (cópia + zip + verificação) | Gravações durante | Pior espera | Falhas |
| --- | --- | --- | --- | --- | --- |
| 100 MB | 0,22 s | 4,2 s | 389 | 0,33 s | 0 |
| 400 MB | 2,92 s | 18,4 s | 1.806 | 0,82 s | 0 |
| 1 GB | 6,83 s | 50,7 s | 4.752 | 2,03 s | 0 |

Na auditoria, com a máquina ocupada por outra bateria de testes, 400 MB chegaram a 3,66 s de pior espera, ainda sem falha. Conclusão: **o risco não se materializou até 1 GB neste disco**, mas a margem para os 5 s encolhe com disco lento (HD) e máquina ocupada.

Opções, em ordem de preferência (nenhuma aplicada):

1. **Medir no Windows** do usuário (H12 do roteiro) com o tamanho real esperado da base. Se a pior espera ficar abaixo de 1 s para 2× o tamanho atual, manter como está.
2. **Cópia em etapas** (`backup(pages=N, sleep=...)`): libera a leitura entre etapas; porém, no modo `delete`, uma gravação de outra conexão no meio reinicia a cópia, e com gravação contínua a cópia pode não terminar. Exige limite de reinícios e testes.
3. **WAL** (`journal_mode=wal`): leitores não bloqueiam escritores e vice-versa; resolveria M1 e ajudaria as estações. Pontos a avaliar antes (por isso **não migrar automaticamente**): arquivos `-wal`/`-shm` ao lado do banco (backup e restauração precisam considerar; a API de backup continua consistente); `checkpoint` e crescimento do `-wal`; restauração por cópia do arquivo exige `checkpoint` antes; antivírus e indexação no Windows sobre `-shm`; disco local obrigatório (já é); testes de queda de energia; migração reversível.
4. **Aumentar o `timeout`** (por exemplo 15 s): mitigação simples, mas a estação fica esperando sem retorno visual.

## M3 — confirmação de importação do Excel

`POST /api/imports/{id}/confirm` roda numa única transação `BEGIN IMMEDIATE` (savepoint por linha). Durante toda a confirmação as demais gravações esperam; com mais de 5 s, recebem 503. A importação do histórico real (IMP-04B) tende a ser longa.

Decisão do arquiteto (2026-11-03): **confirmação só no computador principal**; estações consultam; sem importação concorrente de histórico nesta fase. Proposta para o IMP-04B, a decidir antes de implementar:

- confirmação em **lotes** (por exemplo 500 linhas por transação), com progresso e retomada idempotente pela origem (`import_origins` já impede repetir uma linha), liberando as estações entre lotes; **ou**
- **janela de manutenção** explícita (como a restauração): o sistema avisa as estações, conclui a importação e volta;
- nos dois casos, backup automático suspenso durante a confirmação e um backup logo antes.
