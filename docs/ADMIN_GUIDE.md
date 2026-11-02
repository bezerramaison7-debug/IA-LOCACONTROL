# LocaControl — Guia do administrador

Para quem responde pelo sistema na locadora: usuários, permissões, numeração, modelo de contrato, backup, restauração e atualização. Instalação em [INSTALLATION.md](INSTALLATION.md); uso das telas em [USER_GUIDE.md](USER_GUIDE.md).

## 1. Usuários e perfis

Em **Gestão → Usuários** o administrador cria contas (**Novo usuário**), troca o perfil (**Editar**), define uma nova senha temporária (**Redefinir senha**) e desativa ou reativa a conta (**Desativar** / **Reativar**). A senha temporária tem de 12 a 128 caracteres e o sistema exige a troca no primeiro acesso. Contas não são apagadas: desative quem saiu, para preservar o histórico.

| Perfil | O que faz |
| --- | --- |
| Administrador | Tudo, incluindo usuários, permissões, numeração, modelo de contrato e backups |
| Comercial | Clientes, orçamentos (criar, enviar, aprovar), contratos (criar, confirmar, renovar, gerar documento), relatórios |
| Operação | Produtos, equipamentos, estoque, retiradas e devoluções; consulta contratos |
| Financeiro | Preços, relatórios, faturamento e fiscal; consulta clientes, produtos, orçamentos e contratos |
| Cliente | Somente o portal, com os dados do cliente ao qual a conta foi vinculada |

Em **Gestão → Perfis e permissões**, o botão **Editar** de cada perfil ajusta as permissões de Comercial, Operação e Financeiro (**Salvar permissões** → **Aplicar permissões**). Administrador e Cliente aparecem como "Perfil protegido" e são fixos. De fábrica, só o administrador acessa Importações, Usuários, Perfis e permissões, Auditoria e Backups. Duas permissões nascem só com o administrador e podem ser concedidas a quem deve negociar valores: **alterar o preço de tabela em orçamentos** e **alterar o preço de tabela em contratos e renovações**.

O sistema sempre mantém pelo menos um administrador ativo. Alterar perfil, senha ou permissões encerra as sessões do usuário afetado.

### Conta de cliente para o portal

1. Em **Gestão → Usuários**, crie o usuário com perfil **CLIENTE**.
2. Na linha desse usuário, clique em **Vincular cliente**. O botão só aparece em contas cujo único perfil é Cliente.
3. Busque e selecione o cliente em **Cliente do portal** e clique em **Salvar vínculo**.
4. Entregue usuário e senha provisória; o sistema pede a troca no primeiro acesso.

A conta enxerga apenas contratos, itens, documentos e orçamentos do cliente vinculado. Trocar o vínculo ou usar **Remover vínculo** encerra as sessões da conta. Conta sem vínculo entra, mas vê somente o aviso "Portal ainda não liberado para esta conta".

Os pedidos de renovação feitos pelos clientes no portal chegam em **Comercial → Renovações**, no cartão **Solicitações de renovação dos clientes**.

## 2. Numeração de contratos

O próximo contrato recebe o maior número já usado mais um; em banco novo, começa em 1. Para continuar a sequência que a locadora já usava, abra **Gestão → Configurações**, cartão **Numeração de contratos**, preencha **Próximo número de contrato** (por exemplo, 9193) e clique em **Salvar numeração**. O cartão só aparece para quem tem a permissão de configurar contratos (de fábrica, o administrador). O sistema recusa um número igual ou menor que um já existente. Renovações recebem o mesmo número com sufixo: 9193.1, 9193.2.

Um contrato cancelado mantém o seu número; números não são reaproveitados.

## 3. Modelo de contrato

O sistema vem com um **modelo provisório**, e todo PDF gerado com ele traz o aviso "MODELO PROVISÓRIO" no topo. Para usar o texto da locadora, abra **Gestão → Configurações**, cartão **Modelo de contrato**, preencha **Nome do modelo** e **Texto do modelo** e clique em **Publicar nova versão**. Deixe desmarcada a opção **Publicar como modelo provisório**; ela serve apenas para textos de exemplo. A própria tela lista os campos e os blocos aceitos.

- Linhas iniciadas por `# ` viram títulos; linha em branco separa parágrafos.
- Campos disponíveis: `{{ company.name }}`, `{{ company.document }}`, `{{ company.address }}`, `{{ company.contact }}`, `{{ contract.number }}`, `{{ contract.start_date }}`, `{{ contract.end_date }}`, `{{ contract.total }}`, `{{ contract.notes }}`, `{{ customer.legal_name }}`, `{{ customer.trade_name }}`, `{{ customer.document }}`, `{{ customer.address }}`, `{{ customer.contact }}`, `{{ today }}`.
- Blocos que precisam ficar sozinhos na linha: `{{ items }}` (tabela de itens), `{{ totals }}` (valor total) e `{{ signatures }}` (assinaturas).
- Um campo desconhecido impede a publicação, com a lista do que está errado.

Publicar cria uma nova versão, que passa a valer para os próximos documentos. Documentos já gerados não mudam. O sistema gera somente PDF.

### Documentos do contrato

Os documentos ficam no cartão **Documentos** de cada contrato (**Comercial → Contratos**). **Gerar documento** cria uma nova versão numerada, disponível depois que o contrato é confirmado. Use **Marcar como assinado** na versão que o cliente assinou: a partir daí ele nunca é substituído, e gerar outra versão exige informar o motivo. O sistema guarda um código de verificação de cada PDF e recusa o download se o arquivo for alterado fora do sistema. Não há envio do documento digitalizado; guarde a via assinada conforme a rotina da locadora.

## 4. Backup

Um backup é um arquivo `.zip` com tudo o que é necessário para recuperar o sistema: cópia consistente do banco, planilhas importadas, contratos em PDF, arquivos fiscais e uma lista de conferência. Nome: `locacontrol_AAAA-MM-DD_HHMMSS.zip`.

Em **Gestão → Backups** (de fábrica, somente administrador):

- **Fazer backup agora** cria um conjunto imediatamente.
- **Backup automático**: marque **Fazer backup automático todos os dias**, escolha o **Horário do backup diário** e **Quantos backups manter** e clique em **Salvar configuração**. O backup do dia é feito na primeira verificação depois do horário, desde que o sistema esteja ligado. Ele só é dispensado se já existir um backup feito **depois do horário configurado**: um backup manual feito de manhã não substitui o da noite. Os mais antigos além do limite são removidos; as cópias de segurança de restauração são mantidas.
- **Pasta dos backups**: em branco, usa a pasta padrão `data\backups`. Informe o caminho completo de outra pasta para gravar em outro disco.
- **Verificar** confere cada arquivo do conjunto e a integridade do banco. O resultado esperado é "Backup íntegro: pode ser restaurado."
- **Baixar** entrega o `.zip` para guardar fora do computador. O arquivo passa pela memória do navegador; conjuntos muito grandes devem ser copiados diretamente da pasta de backups.

**Guarde cópias fora deste computador.** Backup na mesma máquina não protege contra roubo, incêndio ou falha do disco. Baixe o conjunto periodicamente para um pendrive, HD externo ou serviço de armazenamento da locadora.

### Restaurar

Restaurar faz o sistema voltar exatamente ao estado do backup escolhido. Tudo o que foi lançado depois deixa de aparecer.

1. Em **Gestão → Backups**, clique em **Restaurar** no conjunto desejado. A janela verifica o conjunto sozinha e só libera os campos se ele estiver íntegro.
2. Digite a frase pedida — `RESTAURAR ` seguida do nome exato do arquivo, respeitando maiúsculas e minúsculas — e, em **Sua senha**, a sua própria senha.
3. Clique em **Restaurar este backup**.
4. O sistema grava antes uma cópia de segurança do estado atual (`..._pre-restore.zip`, que aparece na lista com o tipo "Anterior a uma restauração"), restaura o banco e os arquivos e pede que todos entrem novamente.

Nada é apagado: as pastas de arquivos anteriores vão para `replaced_AAAA-MM-DD_HHMMSS` dentro da pasta de backups, e a cópia `_pre-restore` permite desfazer a restauração. Um backup feito por uma versão mais nova do sistema é recusado: atualize o LocaControl antes.

**Modo manutenção e desfazer automático.** Durante a restauração o sistema entra em manutenção: quem tentar usar o sistema recebe "Sistema em manutenção (restauração em andamento). Tente novamente em instantes." e `/health` responde 503 com status `maintenance`. A restauração só começa depois que as operações em andamento terminam; se elas não terminarem em 30 segundos, ela desiste sem alterar nada (tente de novo). Se algum passo falhar depois de o banco ter sido substituído (mover pastas, atualizar a estrutura do banco), o sistema volta sozinho ao estado anterior a partir da cópia `_pre-restore` e das pastas em `replaced_*`, registra o motivo no log e avisa que nada foi alterado. Se nem isso for possível, a mensagem informa o nome da cópia `_pre-restore` para restauração manual.

**O que o sistema garante numa queda de energia.** Uma operação só é confirmada na tela depois de gravada no banco. Uma queda (ou um travamento do Windows) no meio de uma gravação não corrompe o banco nem deixa operação pela metade: na próxima abertura o SQLite descarta o que não foi confirmado. Mas a operação que ainda não tinha sido confirmada no instante da queda é perdida e precisa ser lançada de novo. Não há promessa de perda zero em qualquer falha de energia; o backup diário fora do computador continua sendo a proteção contra perda do disco.

Recomendação: uma vez por trimestre, restaure um backup em outro computador de teste para confirmar que a recuperação funciona.

## 5. Estoque e contratos

Retirada, devolução e renovação movimentam o estoque automaticamente. Enquanto um equipamento ou uma quantidade está com o cliente por contrato, o sistema recusa tirá-lo de "Locado" pela tela de estoque: registre a devolução no contrato. Itens devolvidos como avariados vão para Manutenção e voltam a Disponível pelo botão **Liberar** em **Operação → Manutenção**.

A confirmação de um contrato não reserva estoque; a disponibilidade é conferida na retirada.

## 6. Faturamento e fiscal

A tela fica em **Financeiro → Faturamento e fiscal** (perfis Administrador e Financeiro, de fábrica). Esta versão traz apenas o **provedor de simulação**, e a tela exibe o aviso "SIMULAÇÃO — sem valor fiscal" o tempo todo. Ele serve para treinar o fluxo; os documentos saem marcados "SIMULAÇÃO — documento sem valor fiscal" e nada é transmitido a órgão ou provedor. Para emitir documentos reais é necessário definir com a contabilidade qual documento a locação exige, escolher um provedor, obter credenciais de teste e implementar e homologar a integração. Enquanto isso não for feito, a emissão fiscal continua sendo feita fora do sistema.

## 7. Auditoria e logs

**Gestão → Auditoria** mostra quem fez o quê e quando: acessos, usuários, cadastros, preços, orçamentos, contratos, retiradas, devoluções, documentos, backups e restaurações. Os registros não são apagados pela interface.

Os logs técnicos ficam em `data\logs\web.stdout.log` e `web.stderr.log` e são sobrescritos a cada início. Não há rotação automática.

## 8. Atualização

Siga a seção 6 de [INSTALLATION.md](INSTALLATION.md). Em resumo: backup, substituir os arquivos sem tocar em `data\` e `.env`, `scripts\update.ps1`, iniciar. A estrutura do banco é atualizada no início, sempre depois de uma cópia em `data\backups\pre-upgrade-*.db`.

## 9. Recuperar o acesso do administrador

No computador do sistema, na pasta do LocaControl:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\admin.ps1 -Action recover
```

O comando pergunta a nova senha no terminal. Só funciona para quem tem acesso físico ao computador e à pasta do sistema.

## 10. Limites conhecidos desta versão

- Uma empresa por instalação; não há multiempresa nem cobrança de assinatura.
- Banco SQLite em disco local; uso simultâneo intenso ou acesso pela internet exigem outra arquitetura.
- Importação do Excel: clientes, produtos, equipamentos, estoque inicial e preços. O histórico de contratos e renovações da planilha antiga não é convertido.
- Manutenção registra a ida e a volta do equipamento, sem ordem de serviço própria.
- O histórico mostra o número do usuário, não o nome.
