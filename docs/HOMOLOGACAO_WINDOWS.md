# LocaControl — Roteiro de homologação física no Windows (P1-E)

Checklist para homologar em **computadores físicos** o que a CI (Windows Server descartável, modo silencioso, uma máquina só) não comprova. Base: ADR-026 e ADR-027, `docs/INSTALLATION.md` 1.1, `docs/P1_BRIEFING.md` ("o que falta validar"). Resultados vão para `docs/VALIDATION.md`, com o SHA e as versões do Windows usadas.

**Versão sob teste**: SHA de código `667582a` (PR #8). Instalador: artefato `LocaControl-Setup-0.1.0` da [execução 41701446712](https://github.com/bezerramaison7-debug/LocaControl/actions/runs/41701446712) (expira em 7 dias) ou gerado com `scripts\installer.ps1` nesse SHA. Para atualização, um segundo instalador com `-AppVersion 0.1.1`.

**Regras**
- **Nenhum dado comercial real.** Use clientes, produtos e contratos fictícios.
- Anote cada item: ✅ passou, ❌ falhou (com evidência: foto da tela, trecho de `logs\servidor.log` ou `comandos.log`, código de saída) ou ➖ não aplicável (com motivo).
- Um item bloqueante que falhou **reprova** a homologação; registre e não "conserte na mão" para seguir — reinstale do zero se for preciso continuar.
- Comandos com `LocaControl.exe` usam `"C:\Program Files\LocaControl\LocaControl.exe"`, num terminal **como administrador**, salvo indicação.

## 0. Preparação

- [ ] **H-00.1** Computador **principal**: Windows 10 ou 11 de usuário (não Server), atualizado, com Microsoft Defender ativo. Anotar edição e build (`winver`).
- [ ] **H-00.2** **Estação A**: Windows 11. **Estação B**: Windows 10. Mesmo roteador do principal (uma por cabo, outra por Wi-Fi, se possível).
- [ ] **H-00.3** Contas em cada máquina: um **administrador** e um **usuário comum** (sem administrador). No principal, o usuário comum é quem vai usar o sistema no dia a dia.
- [ ] **H-00.4** Mídias: pendrive **FAT32 ou exFAT**; HD externo **NTFS**; opcional: uma pasta compartilhada em outro computador (`\\servidor\pasta`).
- [ ] **H-00.5** Um terceiro computador ou celular na mesma rede, **sem** conectar à loja (para testar o aviso de certificado).
- [ ] **H-00.6** Planilha de resultados com colunas: ID, data/hora, máquina, Windows (edição/build), resultado, evidência, observação.

## 1. Instalação do computador principal (assistente gráfico)

- [ ] **H-01.1** Executar o instalador como usuário comum: o Windows pede credenciais de administrador (UAC). *Esperado*: aviso do SmartScreen por instalador sem assinatura (registrar o texto); com "Executar assim mesmo", o assistente abre em português.
- [ ] **H-01.2** Escolher **"Usar neste computador"** e marcar **"Permitir que outros computadores da loja usem este"**. Concluir com "Abrir o LocaControl agora". *Esperado*: o navegador **do usuário que iniciou o instalador** abre `http://127.0.0.1:8000` sem login.
- [ ] **H-01.3** `services.msc`: serviço **LocaControl** em execução, início **Automático**, "Fazer logon como" = `NT SERVICE\LocaControl`.
- [ ] **H-01.4** `wf.msc`: regra de entrada "LocaControl (HTTPS da loja)" — TCP 8443, escopo **sub-rede local**, perfis **Privado e Domínio**, programa `LocaControl.exe`.
- [ ] **H-01.5** Gestão → Estações da rede: HTTPS disponível; "Redes da loja no certificado" mostra `127.0.0.0/8`, `::1/128` e a **/24 do IP do principal**; proteção das chaves "DPAPI do Windows (conta do serviço LocaControl)".
- [ ] **H-01.6** Cadastrar dados fictícios: 3 clientes, 3 produtos com preço, 1 orçamento, 1 contrato com retirada. *Esperado*: tudo grava e aparece após recarregar.

## 2. Isolamento local (SEC-P1E-01) — bloqueante

- [ ] **H-02.1** Como **usuário comum** do principal, abrir `C:\ProgramData\LocaControl` no Explorer. *Esperado*: acesso negado (não lista banco, `.env`, `tls\`, backups).
- [ ] **H-02.2** Como usuário comum, `type C:\ProgramData\LocaControl\tls\ca.key` e `copy C:\ProgramData\LocaControl\locacontrol.db %TEMP%`. *Esperado*: acesso negado nos dois.
- [ ] **H-02.3** Como usuário comum, usar o sistema pelo navegador (ícone "LocaControl"): consultar, cadastrar, gerar PDF. *Esperado*: funciona normalmente.
- [ ] **H-02.4** Como administrador: `LocaControl.exe parar`. Depois, como **usuário comum**, abrir o ícone "LocaControl". *Esperado*: o serviço sobe sozinho e o sistema abre.
- [ ] **H-02.5** Como usuário comum, num terminal comum: `LocaControl.exe parar`. *Esperado*: código de saída 13 ("Sem permissão"); o serviço continua rodando.
- [ ] **H-02.6** Reiniciar o Windows e **não** fazer logon por 2 minutos; da estação (depois da seção 3), abrir o sistema. *Esperado*: o serviço já está no ar sem ninguém logado no principal.
- [ ] **H-02.7** Suspender e retomar; hibernar e retomar o principal. *Esperado*: o serviço volta a responder em até 1 minuto, sem erro no `servidor.log`.
- [ ] **H-02.8** Defender (e outro antivírus, se houver): nenhum alerta ou quarentena do instalador, do `LocaControl.exe` ou da pasta de dados. Registrar qualquer alerta com o nome da detecção.

## 3. Estações (UX-P1E-03) — bloqueante

- [ ] **H-03.1** No principal: Gestão → Estações da rede → **Gerar código** (26 caracteres, 10 minutos). Anotar a hora.
- [ ] **H-03.2** **Estação A**, assistente gráfico: "Conectar à loja", endereço do principal (IP) e um código **errado**. *Esperado*: após a cópia, página "Não foi possível conectar…" com a mensagem exata ("NÃO confere com o código"); **nenhum** certificado em `certlm.msc` → Autoridades de Certificação Raiz Confiáveis.
- [ ] **H-03.3** Na mesma página, digitar o **código certo** e avançar. *Esperado*: segue para o final, que diz "certificado conferido e instalado… Falta um passo: dar nome à estação"; **não** diz "conectado".
- [ ] **H-03.4** Concluir com "Concluir o pareamento desta estação no navegador agora". *Esperado*: o navegador abre **como o usuário que iniciou o instalador** (não como o administrador que digitou a senha no UAC), em `https://<principal>:8443`, com o código preenchido e **sem aviso de certificado**.
- [ ] **H-03.5** Dar o nome "Balcão 1" e concluir. *Esperado*: a estação abre a Visão geral; rodapé "Estação Balcão 1 · rede da loja"; aparece na lista do principal.
- [ ] **H-03.6** **Estação B** (Windows 10): instalar com um código **expirado** (gerado há mais de 10 minutos). *Esperado*: mensagem clara; marcar "Concluir sem conectar". *Esperado*: final diz "NÃO está conectado"; código de saída do instalador 20 (ver `%TEMP%\Setup Log*.txt` ou executar com `/LOG=`).
- [ ] **H-03.7** Na Estação B, instalar de novo com código válido e parear como "Balcão 2".
- [ ] **H-03.8** Navegadores em cada estação: **Edge** e **Chrome** abrem `https://<principal>:8443` sem aviso. **Firefox** sem a política: aviso de certificado (anotar); com `security.enterprise_roots.enabled = true`: sem aviso.
- [ ] **H-03.9** No terceiro computador (sem conectar à loja): abrir `https://<principal>:8443`. *Esperado*: aviso de certificado do navegador; **não** continuar. Abrir `http://<principal>:8000`. *Esperado*: não conecta.
- [ ] **H-03.10** Acesso pelo **nome do computador** (`https://NOME-DO-PC:8443`) e por `NOME-DO-PC.local`: registrar se resolve e se abre sem aviso.
- [ ] **H-03.11** Perfil de rede do principal **Público** (Configurações → Rede): da estação, o acesso deve falhar (regra só Privado/Domínio). Voltar para **Privado**: volta a funcionar.

## 4. Uso simultâneo com duas estações

- [ ] **H-04.1** Balcão 1 e Balcão 2 editam o **mesmo cliente** ao mesmo tempo e salvam. *Esperado*: o segundo recebe aviso de conflito de versão; nenhum dado sobrescrito em silêncio.
- [ ] **H-04.2** As duas estações tentam retirar a **mesma unidade** no mesmo minuto. *Esperado*: só uma retirada é aceita; estoque e custódia corretos.
- [ ] **H-04.3** Backup manual no principal enquanto as estações gravam. *Esperado*: as gravações terminam; o backup conclui e verifica.
- [ ] **H-04.4** Com um orçamento aberto na estação, parar o serviço no principal (`parar`) e iniciar de novo. *Esperado*: o formulário continua na tela; o rascunho é salvo quando o principal volta; nenhum envio repetido sozinho.
- [ ] **H-04.5** Deixar as duas estações em uso por pelo menos **2 horas** (rotação de acesso a cada 15 min). *Esperado*: nenhuma revogação indevida ("reuso de credencial").
- [ ] **H-04.6** Copiar o perfil do navegador da Balcão 1 para outro computador da rede e usar os dois. *Esperado*: depois de uma rotação, a estação é revogada com o alerta de reuso no principal.

## 5. Backups e mídias

- [ ] **H-05.1** Backup automático de 20 minutos por **pelo menos 3 horas** com uso intermitente. *Esperado*: conjuntos a cada 20 min quando houve mudança, "sem alterações" quando não houve; retenção correta; nenhum aviso indevido. Anotar a duração típica de um backup.
- [ ] **H-05.2** Pasta de backup no **pendrive FAT32/exFAT**. *Esperado*: grava e verifica.
- [ ] **H-05.3** Pasta de backup no **HD externo NTFS** sem permissão para o serviço. *Esperado*: falha registrada no histórico com aviso. Conceder `icacls E:\Backups /grant "NT SERVICE\LocaControl:(OI)(CI)M"`. *Esperado*: grava.
- [ ] **H-05.4** Segunda cópia em `\\servidor\pasta` (permissão para a conta do computador) e numa **unidade mapeada** (Z:). *Esperado*: a UNC funciona; a mapeada falha com aviso claro (limite documentado).
- [ ] **H-05.5** Remover o pendrive durante um backup. *Esperado*: falha registrada, arquivo incompleto removido, sistema continua atendendo; nova tentativa depois.
- [ ] **H-05.6** Restaurar um backup **direto da pasta no HD externo**. *Esperado*: dados voltam; cópia `_pre-restore` criada; estações continuam pareadas.
- [ ] **H-05.7** Importar um `.zip` do pendrive (Gestão → Backups → importar) e restaurá-lo. *Esperado*: verificação aprovada e restauração concluída.

## 6. Encerramento, atualização e falhas (REL-P1E-02) — bloqueante

- [ ] **H-06.1** Atualizar (instalador 0.1.1) com as duas estações gravando. *Esperado*: atualização concluída; estações voltam sozinhas; nenhum cadastro confirmado se perde (conferir os últimos gravados).
- [ ] **H-06.2** Atualizar **durante um backup grande** (base de teste com vários PDFs). *Esperado*: o instalador espera o backup terminar; se não terminar em 10 min, cancela com o código 7 dizendo "nada foi alterado", e o programa antigo continua funcionando.
- [ ] **H-06.3** Desligar o Windows (Iniciar → Desligar) com um backup em andamento. *Esperado*: o desligamento espera ou o backup termina; no próximo início, nenhum aviso de banco danificado.
- [ ] **H-06.4** **Tirar o principal da tomada** com estações gravando. Ligar de novo. *Esperado*: `servidor.log` mostra "não foi encerrado normalmente… banco verificado e íntegro"; dados confirmados antes da queda presentes; backup incompleto removido.
- [ ] **H-06.5** Tirar da tomada **durante uma atualização** (logo depois de "Aplicando atualizações do banco" no log). Ligar de novo. *Esperado*: "a atualização anterior foi interrompida… voltou à cópia… sem perda"; a atualização é refeita e o sistema abre.
- [ ] **H-06.6** Ensaio da **restauração manual** (`docs/ADMIN_GUIDE.md` 4.1.1) numa cópia de teste: seguir os passos e conferir que o sistema volta com os dados do backup.

## 7. Troca de rede (SEC-P1E-04)

- [ ] **H-07.1** Mudar o IP do principal **na mesma rede** (outra reserva de DHCP no roteador) e reiniciar o serviço. *Esperado*: certificado reemitido para o IP novo; as estações acessam pelo IP novo (ajustar o endereço da estação: instalar de novo com "Conectar à loja").
- [ ] **H-07.2** Levar o principal para **outra faixa** (outro roteador ou outra VLAN). *Esperado*: Gestão → Estações da rede avisa que o endereço está fora das redes do certificado.
- [ ] **H-07.3** `LocaControl.exe nova-autoridade --confirmar`. *Esperado*: CA anterior guardada em `tls-anterior-<data>`; serviço reiniciado; nova CA com a /24 nova.
- [ ] **H-07.4** Reconectar as estações pelo instalador. *Esperado*: a CA antiga é removida e a nova instalada (conferir em `certlm.msc`); sem aviso no navegador.

## 8. Espaço em disco

- [ ] **H-08.1** Principal (ou VM física dedicada) com disco de **64 GB** e pouco espaço livre (menos de ~13 GB). *Esperado*: backup recusado com a mensagem de espaço, aviso no painel, nova tentativa a cada hora; atendimento normal.
- [ ] **H-08.2** Nesse disco, atualizar o programa para uma versão com mudança de banco. *Esperado*: se não houver espaço para a cópia prévia, o serviço não inicia, `servidor.log` mostra o código 5 "Nada foi alterado"; liberar espaço e iniciar: atualização concluída.

## 9. Recuperação e migração do principal

- [ ] **H-09.1** Simular perda do principal: instalar num **computador novo**, restaurar o backup do pendrive, reconectar as estações (`docs/INSTALLATION.md` 1.1). *Esperado*: dados restaurados; estações funcionam após "Conectar à loja" com código novo.
- [ ] **H-09.2** Migrar copiando `C:\ProgramData\LocaControl` inteira (como administrador, serviço parado). *Esperado*: dados e lista de estações vêm; a rede fica fechada ("senha das chaves não pôde ser lida"); `nova-autoridade --confirmar` e reconexão das estações resolvem.

## 10. Desinstalação e reinstalação

- [ ] **H-10.1** Desinstalar a Estação A (Configurações → Aplicativos). *Esperado*: CA da loja removida de `certlm.msc`; o ícone some.
- [ ] **H-10.2** Desinstalar o principal e responder **Não** à exclusão dos dados. *Esperado*: serviço e regra de firewall removidos; `C:\ProgramData\LocaControl` mantida.
- [ ] **H-10.3** Reinstalar o principal. *Esperado*: dados e estações pareadas de volta; permissões da pasta corretas (repetir H-02.1).
- [ ] **H-10.4** Só numa máquina de teste: desinstalar e responder **Sim** nas **duas** confirmações. *Esperado*: dados excluídos. Responder Sim e depois Não: dados mantidos.

## Critérios de aprovação

**Bloqueantes** (qualquer falha reprova): perda de dado confirmado; banco danificado servido; conta comum do principal lendo ou alterando arquivos da pasta de dados (H-02.1, H-02.2); estação aceita sem o código certo ou instalador dizendo "conectado" sem certificado e pareamento (H-03.2–H-03.6); navegador aceitando certificado da loja sem a CA instalada (H-03.9); atualização deixando o sistema sem iniciar (H-06.1, H-06.2, H-06.5); serviço não iniciando após reinício (H-02.6).

**Não bloqueantes** (registrar e decidir): aviso do SmartScreen; Firefox sem a política; nome `.local` não resolvendo; antivírus de terceiros com alerta; duração de backup acima do esperado.

## Registro

Ao final, acrescentar em `docs/VALIDATION.md` uma seção "Homologação física — SHA `<sha>`" com: data, máquinas (edição/build do Windows, cabo/Wi-Fi), navegadores e versões, resultado de cada ID, evidências dos itens ❌ e a decisão (aprovado / reprovado / aprovado com ressalvas, e quais).
