# LocaControl — Identidade e segurança

Implementação da Etapa 2. O resultado da validação e o estado das migrations estão em PROJECT_STATE e AI_HANDOFF.

## Edição local sem login (ADR-023, 2026-11-01)

Ligada por `LOCACONTROL_LOCAL_MODE=true` (padrão `false`; com `false` tudo abaixo deste capítulo vale sem mudança). Não há login, senha, `admin/admin`, usuários, perfis nem portal. As ações são feitas pelo **operador local** (`operador.local`, perfil Administrador, senha aleatória desconhecida) e auditadas como `operador local · instalação <8 primeiros do id da instalação>` — rótulo de origem, não de pessoa.

### Sessão automática e por que ela não abre a rede

`GET /api/auth/me` sem sessão válida cria uma sessão do operador (mesmo cookie HttpOnly, SameSite Strict, `Path=/api`, mesma expiração) e devolve o `csrf_token` somente quando **todas** as condições valem (`app/auth/local.py`, `is_this_computer`):

1. o par TCP (`request.client.host`) é loopback — outro computador da rede recebe 401;
2. o `Host` pedido é `localhost`, `127.0.0.1` ou `[::1]` — um nome estranho que resolva para 127.0.0.1 (DNS rebinding) recebe 401;
3. há o cabeçalho `X-LocaControl-Request: 1` — uma página de outro site não consegue enviá-lo sem pré-verificação CORS, que é recusada fora de `cors_origins`;
4. a `Origin`, quando enviada, está em `allowed_origins`.

Escritas continuam exigindo origem permitida, o cabeçalho do app e o `X-CSRF-Token` da sessão (403 caso contrário). O launcher escuta só em `127.0.0.1`. Limite: um proxy local que repasse pedidos da rede para o servidor (por exemplo o Vite exposto com `--host`) faria pedidos externos parecerem locais; não exponha o servidor nem o proxy de desenvolvimento na rede em modo local. Estações da rede são autorizadas por código de pareamento (seção seguinte, ADR-025).

Respostas de `/api` em modo local trazem `X-LocaControl-Edition: local`, para a interface mostrar "sem acesso" em vez de uma tela de login.

### Rede da loja e estações (ADR-025, P1-D)

Só com `LOCACONTROL_LOCAL_MODE=true` e `LOCACONTROL_NETWORK_MODE=true` o servidor escuta na rede. O resto da rede continua recebendo 401; um computador da rede privada recebe 401 com `X-LocaControl-Pairing: available`, para a interface mostrar a tela de pareamento.

- **Pareamento** (`POST /api/stations/pair`, único caminho sem sessão): par TCP na rede da loja (10/8, 172.16/12, 192.168/16, fc00::/7, fe80::/10 e `LOCACONTROL_STATION_NETWORKS`), `Host` = IP dessas redes, nome deste computador ou `LOCACONTROL_STATION_HOSTS` (bloqueia DNS rebinding), `Origin` = `http://<Host>` e `X-LocaControl-Request: 1`. Código de 8 caracteres (~40 bits) gerado no principal, 10 minutos, uso único, só o hash guardado; 5 erros cancelam o código; 10 erros de um endereço em 15 minutos → 429 por 15 minutos.
- **Credencial da estação**: token aleatório de 32 bytes no cookie `locacontrol_station` (HttpOnly, SameSite=Strict, `Path=/api`, sem `Secure` enquanto o transporte for HTTP); no servidor só hashes SHA-256 (atual, ofertas pendentes e aposentados), em `stations.json` e na cópia `.bak`, fora do banco e dos backups. Não há senha de usuário.
- **Verificação a cada requisição** (`bound_station`): sessão de estação exige o cookie da mesma estação, ativa, e par na rede da loja; sessão do principal, com o modo rede ligado, exige par loopback. Revogar apaga as sessões da estação; sessões antigas trazidas por uma restauração também são recusadas. **O cookie de sessão sozinho não funciona em outro computador; os dois cookies juntos funcionam em outro computador da rede privada até a próxima rotação** (testado; ver o item seguinte).
- **Rotação do token com detecção de reuso** (A1): token pendente oferecido a cada sessão nova e a cada 15 min de uso; o anterior se aposenta quando o novo é usado; token aposentado apresentado depois de 2 min de tolerância revoga a estação ("reuso de credencial detectado"), com evento, auditoria `station.reuse_detected` (endereço e navegador como indícios) e alerta no principal. Garante a detecção quando as duas cópias são usadas depois de uma rotação; **não impede** o uso da cópia antes disso. Testes: `test_station_rotation.py` (relógio controlado, sem falso positivo para resposta perdida, navegador ocioso e abas em paralelo) e `test_network_server.py` (servidor real).
- **Lista de estações ilegível** (A2): estações recusadas (falha fechada), principal funcionando, reparo explícito e auditado com a frase `RECOMEÇAR ESTAÇÕES`; recuperação automática pela cópia `.bak` com aviso.
- **Escritas de estação**: `Origin` = `http://<Host>` (com o `Host` validado acima), `X-LocaControl-Request: 1` e `X-CSRF-Token` da sessão; CORS sem mudança (mesma origem).
- **Só no computador principal** (403): configurar, baixar, importar e restaurar backups; enviar, pré-visualizar e confirmar importações do Excel; gerar e cancelar código, listar, revogar e consultar estações; reparar a lista de estações.
- **Auditoria** por estação: rótulo `operador local · estação <nome> (<id8>) · instalação <id8>` para leitura e `audit_logs.station_id` para filtros (M4); nome de estação sem parênteses, até 40 caracteres e único entre as ativas. Eventos de pareamento, recusa, reuso e revogação também no próprio registro (preservados nas restaurações).
- **Risco aceito** (decisão do usuário 9, reafirmado em 2026-11-03 até o HTTPS do P1-E): HTTP sem criptografia na rede da loja. Quem capturar o tráfego ou copiar o perfil do navegador de uma estação pode usar a cópia de outro computador **da mesma rede privada** até a próxima rotação; depois, o uso das duas cópias revoga a estação. Fora da rede privada os cookies não funcionam. Não há afirmação de que a clonagem seja impossível.

### Matriz de rotas em modo local

| Rota | Modo local |
| --- | --- |
| `GET /health` | igual |
| `GET /api/auth/me` | sessão automática (condições acima); devolve `edition: "local"` e `installation_id`; omite as permissões `users.*`, `roles.*` e `portal.*` |
| `PATCH /api/auth/me` (nome do perfil) | **404** |
| `POST /api/auth/login` | **404** |
| `POST /api/auth/logout` | igual (encerra a sessão; a próxima chamada a `/me` abre outra) |
| `POST /api/auth/password` | **404** |
| `GET/POST /api/users`, `PATCH /api/users/{id}`, `POST /api/users/{id}/reset-password` | **404** |
| `GET /api/roles`, `PUT /api/roles/{id}/permissions`, `GET /api/permissions` | **404** |
| `GET /api/audit-logs` | igual (`audit.read`, que o operador tem) |
| `GET/PUT /api/users/{id}/customer` (vínculo do portal) | **404** |
| `/api/portal/*` (painel, contratos, equipamentos, documentos, orçamentos, cadastro, solicitações de renovação) | **404** |
| `GET /api/renewal-requests`, `POST /api/renewal-requests/{id}/decide` | **404** (as solicitações só nascem no portal) |
| Cadastros, estoque, preços (`/api/customers`, `/products`, `/equipment`, `/stock`, `/prices`) | igual, como operador local |
| Importações (`/api/imports*`) | igual |
| Orçamentos (`/api/quotes*`) | igual |
| Contratos, documentos, retiradas, devoluções, renovações (`/api/contracts*`) | igual |
| Dashboard, relatórios, resumo do cliente (`/api/dashboard`, `/api/reports*`, `/api/customers/{id}/summary`) | igual |
| Fiscal (`/api/fiscal/*`) | igual |
| Backups: listar, configurar, executar, verificar, baixar | igual |
| `POST /api/backups/{nome}/restore` | **sem senha**; exige a frase exata `RESTAURAR <nome>` (422 se diferente), modo manutenção e cópia `_pre-restore`; só no computador principal (estação: 403) |
| `PUT /api/backups/config`, download e importação de backup | só no computador principal (estação: 403) |
| `/api/stations*` | `pair` para a rede da loja; o resto só no computador principal |

O 404 vem de uma guarda explícita (`not_in_local_mode`) que roda antes da autenticação e responde "Recurso indisponível na edição local." O código dessas rotas permanece para a edição com login e para uma futura edição web.

## Primeiro administrador

Edição com login. Desde 11/10/2026 (ADR-022) o atalho de início cria, em banco sem nenhum usuário, a conta `admin` com senha `admin` e troca obrigatória: até a troca por uma senha de 12+ caracteres a API responde 403 a qualquer função. A conta nunca é recriada. É uma credencial pública por definição: aceitável apenas na instalação local de máquina única, e a senha deve ser trocada logo após instalar. Em instalação acessível por rede, use o bootstrap interativo abaixo antes do primeiro início.

Na raiz do projeto, após as migrations, execute em um terminal PowerShell interativo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/admin.ps1
```

O operador informa usuário, nome e senha de 12 a 128 caracteres, com confirmação e entrada oculta. Não há senha padrão, senha por argumento, variável de ambiente ou cadastro público. O bootstrap funciona somente enquanto não existe nenhum usuário; duas tentativas concorrentes não podem criar dois administradores iniciais. O comando registra a operação na auditoria.

Não executar o bootstrap de testes contra o banco local. As contas e senhas dos testes pertencem exclusivamente a bancos temporários.

## Recuperação local

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/admin.ps1 -Action recover
```

Exige acesso ao terminal do computador servidor, nome do usuário, confirmação RECUPERAR e nova senha oculta. Revoga todas as sessões, registra password.recovered_local e exige troca no próximo login. Não reativa usuários desativados nem altera perfis. Não há link público, envio de e-mail ou pergunta de segurança. A proteção do Windows, da pasta do projeto e do SQLite faz parte da fronteira de confiança: quem controla esses arquivos pode alterar o banco.

## Senhas e sessões

- Hash Argon2id, memória 64 MiB, três iterações, paralelismo 1 e salt por hash. Rehash quando os parâmetros mudarem. Senhas nunca entram em resposta ou auditoria.
- Sessão aleatória com 32 bytes de entropia; apenas SHA-256 do identificador fica no banco. Prazo absoluto padrão de oito horas, configurável de 1 a 24 horas. Sem renovação automática infinita.
- Cookie locacontrol_session, HttpOnly, SameSite=Strict, Path=/api e prazo equivalente. Tokens não são armazenados em localStorage. Habilitar Secure no HTTPS.
- Logout revoga a sessão corrente. Mudanças de senha, redefinição, desativação ou perfis revogam todas as sessões do usuário. Alteração de permissões de um perfil revoga sessões de seus membros.
- Senhas temporárias exigem troca antes de acessar funções administrativas; perfil pessoal, troca e logout continuam disponíveis.
- Tentativas de login inválidas: bloqueio temporário de 15 minutos após cinco por usuário ou 30 por endereço remoto. Estado no banco, sem confiar em X-Forwarded-For vindo diretamente do cliente. Erros de usuário inexistente/senha incorreta/inativo são genéricos. Troca de senha também limita tentativas da senha atual.

Argon2id segue a orientação de armazenamento de senhas da [OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html); a atualização do hash usa a API do [argon2-cffi](https://argon2-cffi.readthedocs.io/en/stable/api.html).

## Origem, CSRF e transporte

Ações exigem Origin presente na lista LOCACONTROL_ALLOWED_ORIGINS e X-LocaControl-Request: 1. Ações autenticadas também exigem X-CSRF-Token correspondente à sessão. O token CSRF é obtido via login/me e não autentica sozinho. Requests de formulário simples e origens não autorizadas são rejeitados. CORS não usa wildcard e permite apenas origens configuradas. Referência: [OWASP — prevenção de CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

HTTP padrão é para loopback local. Para uso autenticado entre computadores, configurar HTTPS, LOCACONTROL_COOKIE_SECURE=true e a origem exata no servidor; não enviar senhas pela rede em HTTP. Não declarar implantação de HTTPS pronta: a configuração de rede/instalação pertence à etapa de operação.

Respostas /api têm Cache-Control: no-store. Cabeçalhos X-Content-Type-Options, X-Frame-Options e Referrer-Policy são enviados. Erros de validação não ecoam entradas; falhas SQL não expõem queries ou caminhos.

## Matriz inicial de acesso

| Capacidade | ADMINISTRADOR | COMERCIAL / OPERAÇÃO / FINANCEIRO | CLIENTE |
| --- | --- | --- | --- |
| Conta própria, senha e logout | Sim | Sim | Sim |
| Prévia visual dos módulos internos (workspace.view) | Sim | Sim | Não |
| Consultar usuários (users.read) | Sim | Não | Não |
| Gerir usuários/senhas/perfis atribuídos (users.write) | Sim | Não | Não |
| Consultar perfis/permissões (roles.read) | Sim | Não | Não |
| Alterar permissões internas (roles.write) | Sim | Não | Não |
| Consultar auditoria (audit.read) | Sim | Não | Não |

Administrador e Cliente têm grants protegidos. Cliente não pode ser combinado com um perfil interno; na Etapa 2 acessava somente sua conta e aparência. Desde a Etapa 9 a API do portal existe (seção "Etapas 6 a 11"); a tela do portal ainda não. Os perfis internos podem receber permissões administrativas por decisão explícita de quem tem roles.write. Conceder users.write permite atribuir perfis e redefinir senhas; trata-se de uma permissão administrativa ampla. As restrições sempre são verificadas no backend, inclusive por chamada HTTP direta.

As permissões de clientes, contratos, estoque e financeiro serão criadas com os módulos correspondentes. workspace.view dá acesso apenas às prévias visuais identificadas, sem conceder operações comerciais ainda inexistentes. A UI de usuários atribui um perfil por edição; a API aceita múltiplos perfis internos e valida combinações. Manter pelo menos um usuário ativo com perfil ADMINISTRADOR.

## API implementada

| Método / caminho | Acesso |
| --- | --- |
| POST /api/auth/login | Origem autorizada, credenciais e limite de tentativas |
| GET /api/auth/me | Sessão válida |
| PATCH /api/auth/me | Sessão, origem e CSRF; nome próprio |
| POST /api/auth/password | Sessão, origem, CSRF e senha atual |
| POST /api/auth/logout | Sessão, origem e CSRF |
| GET /api/users | users.read; busca e paginação |
| POST /api/users | users.write |
| PATCH /api/users/{id} | users.write; proteção do último admin |
| POST /api/users/{id}/reset-password | users.write |
| GET /api/roles e /api/permissions | roles.read |
| PUT /api/roles/{id}/permissions | roles.write; perfis protegidos imutáveis |
| GET /api/audit-logs | audit.read; paginação |

Nenhum endpoint remove usuários ou registros de auditoria. Usuários são desativados, preservando as referências.

## Transações e auditoria

Mutações SQLite usam BEGIN IMMEDIATE para serializar a verificação do primeiro/último administrador. O commit ocorre antes do envio da resposta. A operação e a auditoria são atômicas; falha na auditoria reverte a alteração. Falhas de login persistem apenas o contador e o evento de falha antes de retornar erro.

AuditLogs guardam identificador, instante UTC em segundos, autor/identificação local, ação, entidade, registro e campos anteriores/novos permitidos. Eventos: criação/edição de usuário, perfil próprio, alteração de grants, bootstrap, login/logout, troca/reset/recuperação de senha. Hashes, senhas, cookies e tokens não entram nos campos auditados. A tela converte o instante para o horário local do navegador. Não existe garantia de imutabilidade contra um operador com acesso direto ao arquivo SQLite.

## Validação

Testes backend verificam sessão, expiração, revogação, senhas, CSRF/origens, perfis, bootstrap/recuperação, último administrador, concorrência e rollback. Testes frontend verificam login, erros, sessão, isolamento visual de Cliente, troca obrigatória e navegação. scripts/e2e-auth.py aplica migrations em SQLite temporário, cria um administrador exclusivamente de teste e exercita a aplicação compilada via Chromium/API real. Não usa o banco local. Regressão visual anterior está em frontend/e2e/visual.spec.ts com identidade simulada, separada desse teste real.


## Etapas 6 a 11 — permissões, portal, downloads e restauração (2026-10-11)

Conferido nas migrations 0006–0010 e no banco local. Total de permissões: 32.

| Permissão | ADMINISTRADOR | COMERCIAL | OPERAÇÃO | FINANCEIRO | CLIENTE |
| --- | --- | --- | --- | --- | --- |
| contracts.read (contratos, documentos, dashboard, resumo do cliente, lista de solicitações) | Sim | Sim | Sim | Sim | Não |
| contracts.write (criar, confirmar, cancelar, encerrar, renovar, gerar/assinar documento, decidir solicitação) | Sim | Sim | Não | Não | Não |
| contracts.negotiate (preço diferente da tabela em contrato/renovação) | Sim | Não | Não | Não | Não |
| contracts.configure (numeração e modelos) | Sim | Não | Não | Não | Não |
| operations.write (retiradas e devoluções) | Sim | Não | Sim | Não | Não |
| reports.read (relatórios e exportações) | Sim | Sim | Não | Sim | Não |
| fiscal.read / fiscal.write | Sim | Não | Não | Sim | Não |
| backups.manage | Sim | Não | Não | Não | Não |
| portal.access | Não | Não | Não | Não | Sim |

Estas são as concessões iniciais das migrations; quem tem roles.write pode alterá-las nos perfis internos. O perfil COMERCIAL não registra retirada nem devolução; o perfil OPERAÇÃO não renova nem cancela. As restrições são verificadas na API e testadas por perfil (`test_contracts.py`, `test_reports.py`, `test_fiscal.py`, `test_backups.py`).

### Isolamento do portal

- `portal.access` existe só no perfil CLIENTE, que não se combina com perfil interno. A conta precisa estar vinculada a um cliente (`PUT /api/users/{id}/customer`, users.write); sem vínculo, o portal responde 403 com orientação.
- Toda rota `/api/portal/*` filtra pelo cliente do vínculo, inclusive detalhes por ID e downloads. Contrato, documento, orçamento ou solicitação de outro cliente responde **404**, nunca 403, para não confirmar que o identificador existe.
- Também respondem 404 no portal: contrato em rascunho, documento substituído e orçamento em rascunho ou cancelado.
- Alterar ou remover o vínculo **revoga todas as sessões** da conta, para que uma sessão antiga nunca alcance outro cliente. A mudança é auditada (`portal.link_changed`).
- O portal expõe um subconjunto de campos: sem preço de tabela, autores internos ou auditoria.
- Cobertura: `test_portal.py` (lista, detalhe, download, solicitação, vínculo e revogação).

### Downloads

Todo arquivo é entregue por rota autenticada e autorizada, como anexo, sem caminho do servidor: PDF de orçamento (quotes.read), prévia e documento de contrato (contracts.read), exportação de relatório (reports.read), PDF/XML fiscal (fiscal.read), conjunto de backup (backups.manage) e as versões do portal (portal.access + vínculo). Arquivos no disco usam nome UUID gerado pelo servidor. O download do documento de contrato confere o SHA-256 e é recusado se o arquivo foi alterado fora do sistema. O nome de backup aceito segue um padrão fixo sem separadores de caminho; a restauração recusa membros do zip que apontem para fora das pastas de destino.

### Backup e restauração

- Tudo sob backups.manage (somente administrador de início). O conjunto contém todos os dados da empresa e os hashes de senha do banco: tratar o `.zip` como confidencial e guardá-lo em local protegido.
- Restaurar exige, no mesmo pedido, a frase exata `RESTAURAR <nome do backup>` e a **senha do próprio usuário** (na edição local, só a frase; ver ADR-023). Senha incorreta responde 403, não restaura e é auditada (`backup.restore_denied`).
- Antes de substituir qualquer coisa o sistema verifica manifesto, hashes e integridade do banco, recusa conjunto de versão desconhecida ou mais nova, cria uma cópia `_pre-restore` do estado atual e move as pastas de arquivos atuais para `replaced_<data>` em vez de apagá-las.
- Depois da restauração, sessões e contas voltam ao estado do backup: é preciso entrar novamente. O evento `backup.restored` é gravado com o rótulo do usuário que restaurou.
- Configuração e execução manual são auditadas (`backup.configured`, `backup.requested`).
- Importação de um `.zip` de outro disco (`POST /api/backups/import`, `backups.manage`): o arquivo é gravado com nome gerado, verificado por inteiro antes de ser aceito e auditado (`backup.imported`); o nome enviado nunca vira caminho. Limite de 8 GiB. A segunda cópia (`mirror_directory`) recebe o mesmo `.zip`: proteja aquela pasta como a de backups.
- Proteção contra esgotamento do disco (A3): teto da pasta de backups e reserva de espaço livre (maior entre 10 GB e 15 %, configuráveis); nada é gravado se não couber; recuperação respeita a reserva. Gravação com `fsync` e verificação do conjunto antes de valer (M2).
- O histórico das execuções (`backup-history.json`, ao lado do banco) guarda nomes, tamanhos e o motivo curto da falha, sem caminhos nem conteúdo.
- Restauração em modo manutenção (`app/ops/maintenance.py`): um middleware conta as requisições em andamento; durante a restauração toda requisição nova recebe 503 (exceto `/health`, que responde `maintenance` sem tocar no banco), e a restauração espera as em andamento terminarem (até 30 s; senão 409 sem alterar nada). Nenhuma requisição observa banco ou pastas restaurados pela metade.
- Desfazer automático: falha depois de o banco vivo ter sido sobrescrito recoloca as pastas movidas para `replaced_*` e o banco da cópia `_pre-restore`, registra em log e responde 500 dizendo que nada foi alterado; se o desfazer falhar, a mensagem aponta a cópia `_pre-restore` para restauração manual.
- Limite honesto: cada requisição de escrita só responde sucesso depois do `COMMIT` (dependência `database` com `scope="function"`). O SQLite com journal de rollback protege contra corrupção e transação pela metade numa queda, mas a operação ainda não confirmada no instante da queda é perdida: não há promessa de perda zero em qualquer falha de energia.

### Rascunhos automáticos (ADR-024)

Rascunhos ficam na tabela `form_drafts`, com o conteúdo digitado (que pode incluir dados de clientes), e entram nos backups como o resto da base. Cada rascunho pertence a quem o digitou (`owner`); a API só lê, grava ou apaga os do próprio dono e exige a permissão da operação definitiva. Gravar é substituição completa (repetível), sem auditoria; o rascunho nunca é lido pelos serviços de estoque, contratos, documentos ou relatórios. Expiração de 7 dias.

### Sessão local e formulários

Na edição local, a interface renova a sessão expirada (401) ou desatualizada (403 com `X-LocaControl-Retry: csrf`, enviado só na falha de CSRF) por `GET /api/auth/me`, com as mesmas condições da sessão automática. Leituras são repetidas uma vez; escritas nunca são repetidas automaticamente — a única exceção é a gravação do rascunho, que é substituição completa e portanto repetível. As verificações de origem, cabeçalho do app e CSRF não mudaram.

### Fiscal

Não há credencial fiscal em parte alguma: só existe o provedor de simulação. O retorno bruto do provedor é guardado para conciliação; um adapter real deverá remover credenciais antes de devolvê-lo (contrato descrito em `app/fiscal/provider.py`). Credenciais futuras ficam somente em `.env`.

### Garantias acrescentadas pelas correções da auditoria (commit `b0d9ec4`)

Conferidas no código e cobertas por testes nos módulos indicados. A auditoria independente foi somente leitura e cobriu o backend; **não cobriu o frontend, a importação de Excel nem as rotas de identidade**.

- Portal não expõe motivo interno: os eventos de cancelamento e de encerramento aparecem para o cliente com texto fixo ("Contrato cancelado.", "Contrato encerrado."), nunca com o motivo escrito pela locadora (`app/portal/service.py`, `test_portal.py`).
- Reenvio com a mesma chave de operação só é tratado como repetição se autor, contrato, data e itens (ou, no fiscal, cliente, contrato, período, valor e descrição) forem os mesmos; com conteúdo diferente responde **409**, sem gravar nada (`app/contracts/operations.py`, `app/fiscal/service.py`).
- Verificação de backup exige manifesto completo: o banco precisa estar listado, nenhum arquivo do `.zip` pode estar fora do manifesto, todos os hashes precisam conferir e o banco precisa ter ao menos um usuário. Conjunto reprovado não é restaurado (`app/ops/backup.py`, `test_backups.py`).
- Restauração serializada: backup e restauração usam a mesma trava de processo; os arquivos são extraídos e conferidos antes de qualquer dado vigente ser tocado, e, se a restauração falhar, a resposta informa a cópia de segurança criada.
- Documento fiscal só é enviado, consultado ou cancelado no provedor e no ambiente em que foi criado; configuração diferente responde 409.
- Renovação recusa a mesma unidade física informada mais de uma vez (achado de severidade alta).
- Exportação em Excel grava como texto qualquer valor iniciado por "=", sem criar fórmula.

### Limites conhecidos

Sem HTTPS configurado, sem antimalware nos uploads, sem imutabilidade da auditoria contra quem acessa o arquivo SQLite, sem criptografia dos conjuntos de backup e sem isolamento multiempresa. Nada foi publicado na internet.

## Módulos comerciais e upload — 2026-10-08

Etapa 5 adiciona quotes.read, quotes.write, quotes.approve e quotes.negotiate. Alterar o preço de tabela em um orçamento exige quotes.negotiate, verificada no serviço; quem não a possui pode manter um preço já negociado, mas não alterá-lo. O PDF do orçamento exige sessão e quotes.read. Total de permissões após a Etapa 5: 22 (32 após a Etapa 11, ver seção anterior).

Etapa 3 adiciona dez permissões de leitura/escrita. Etapa 4 adiciona imports.read/write, inicialmente para administrador; conversão também exige escrita no módulo de destino. Não conceder imports.read indiscriminadamente: original/relatórios contêm dados da empresa.

Uploads exigem sessão, CSRF e origem; original usa UUID gerado, nunca caminho enviado pelo cliente. Leitura .xlsx/.xlsm com openpyxl e defusedxml, limite de tamanho/expansão/células, sem executar macros/fórmulas/referências externas. Downloads são protegidos e anexos, sem caminhos expostos. Arquivos preservados fora do Git; incluir data/imports em backup com o banco.

Prévia não persiste registros/auditoria/origem. Confirmação revalida digest, serializa escrita SQLite e audita na mesma transação. Savepoint por linha isola erro de conteúdo; falha inesperada desfaz a confirmação. Não sobrescrever conflitos nem repetir origem. Segurança pública/antimalware/retencão e isolamento multiempresa exigem planejamento antes de publicar na internet.
