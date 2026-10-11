# LocaControl — Identidade e segurança

Implementação da Etapa 2. O resultado da validação e o estado das migrations estão em PROJECT_STATE e AI_HANDOFF.

## Primeiro administrador

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
- Restaurar exige, no mesmo pedido, a frase exata `RESTAURAR <nome do backup>` e a **senha do próprio usuário**. Senha incorreta responde 403, não restaura e é auditada (`backup.restore_denied`).
- Antes de substituir qualquer coisa o sistema verifica manifesto, hashes e integridade do banco, recusa conjunto de versão desconhecida ou mais nova, cria uma cópia `_pre-restore` do estado atual e move as pastas de arquivos atuais para `replaced_<data>` em vez de apagá-las.
- Depois da restauração, sessões e contas voltam ao estado do backup: é preciso entrar novamente. O evento `backup.restored` é gravado com o rótulo do usuário que restaurou.
- Configuração e execução manual são auditadas (`backup.configured`, `backup.requested`).

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
