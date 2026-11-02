# LocaControl — Guia do usuário

Este guia é para quem usa o LocaControl no dia a dia da locadora: atendimento comercial, operação e financeiro. A última seção é para o cliente que acessa o portal. Instalação está em [INSTALLATION.md](INSTALLATION.md); usuários, permissões, backup e modelo de contrato estão em [ADMIN_GUIDE.md](ADMIN_GUIDE.md).

Os nomes em **negrito** são os que aparecem na tela.

## 1. Entrar e trocar a senha

Na edição local (sem login) o LocaControl abre direto, sem usuário nem senha, e esta seção não se aplica: não há **Meu perfil**, **Sair**, **Usuários** nem **Perfis e permissões**. Se aparecer "Este computador não tem acesso ao LocaControl desta loja.", o navegador não está no computador principal.

1. Abra o endereço do sistema no navegador. No computador onde ele está instalado, o endereço é `http://127.0.0.1:8000`.
2. Em **Entrar na sua conta**, informe **Usuário** e **Senha** e clique em **Entrar**.
3. No primeiro acesso, ou depois de o administrador redefinir a sua senha, o sistema abre **Meu perfil** com o aviso "Para continuar, substitua a senha temporária por uma senha pessoal." Enquanto a senha não for trocada, nenhuma outra tela fica disponível.
4. No cartão **Alterar senha**, preencha **Senha atual**, **Nova senha** e **Confirmar nova senha** e clique em **Alterar senha**. A senha deve ter de 12 a 128 caracteres e ser diferente da atual.
5. O sistema encerra todas as suas sessões e pede que você entre de novo com a senha nova.

Para sair, use o botão **Sair** no menu lateral (em telas pequenas, **Sair da conta**).

Não existe "esqueci minha senha" por e-mail. Se você esqueceu a senha, peça ao administrador para usar **Redefinir senha** em **Gestão → Usuários**. Se quem esqueceu foi o próprio administrador, veja a seção 9 do [ADMIN_GUIDE.md](ADMIN_GUIDE.md).

Em **Meu perfil** você também corrige o seu **Nome completo** (**Salvar perfil**). O tema claro ou escuro é escolhido em **Gestão → Configurações**, no cartão **Aparência**, e vale só para o navegador em uso.

## 2. O menu e o que cada perfil vê

O menu lateral mostra somente as áreas liberadas para o seu perfil. Se um item citado neste guia não aparece para você, o seu perfil não tem aquela permissão: fale com o administrador.

| Grupo | Itens |
| --- | --- |
| Principal | Dashboard |
| Comercial | Clientes, Orçamentos, Contratos, Renovações |
| Operação | Produtos, Equipamentos, Estoque, Preços, Retiradas, Devoluções, Manutenção |
| Financeiro | Faturamento e fiscal |
| Gestão | Relatórios, Importações, Usuários, Perfis e permissões, Auditoria, Backups, Meu perfil, Configurações |

Com as permissões de fábrica, cada perfil trabalha assim (o administrador pode ajustar os perfis Comercial, Operação e Financeiro):

| Perfil | O que faz | O que só consulta |
| --- | --- | --- |
| Administrador | Tudo, inclusive Importações, Usuários, Perfis e permissões, Auditoria e Backups | — |
| Comercial | Clientes, orçamentos (criar, enviar, aprovar, converter), contratos (criar, confirmar, renovar, cancelar, gerar documento), solicitações de renovação, relatórios | Produtos, equipamentos, estoque, preços, manutenção. Vê Retiradas e Devoluções, mas não registra |
| Operação | Produtos, equipamentos, estoque, retiradas, devoluções, liberação da manutenção | Contratos e renovações |
| Financeiro | Preços, faturamento e fiscal, relatórios | Clientes, produtos, orçamentos, contratos |
| Cliente | Apenas o portal (seção 15) | — |

Dois pontos que costumam gerar dúvida:

- O perfil Comercial confirma e renova contratos, mas **não registra retirada nem devolução**. Isso é feito por quem tem o perfil Operação ou Administrador.
- Negociar preço (informar um valor diferente da tabela) é uma permissão separada, que de fábrica só o administrador tem.

## 3. Regras que você precisa conhecer

- **Valor do item = quantidade × preço do período × número de períodos.** Não existe fração de período: você escolhe o período e quantos períodos.
- **Períodos em dias corridos:** Diária = 1 dia, Semanal = 7, Quinzenal = 15, Mensal = 30. A devolução prevista é o início mais os dias do período multiplicados pelo número de períodos. Exemplo: início em 01/03, 2 × Semanal → devolução prevista em 15/03.
- **Desconto é preço negociado por item.** Não há campo de desconto no total. O sistema guarda o preço de tabela e o preço aplicado e mostra a diferença.
- **Orçamento não reserva estoque.** Ele mostra o saldo disponível no momento apenas como informação.
- **Contrato confirmado também não reserva estoque.** A disponibilidade é conferida e baixada somente na retirada. Dois contratos confirmados podem disputar o mesmo equipamento; quem retira primeiro leva.
- **"Vencendo"** é o contrato ativo com devolução prevista para hoje ou para os próximos 3 dias. **"Vencido"** é o contrato ativo cuja devolução prevista já passou. As duas situações são calculadas pela data; ninguém precisa marcá-las.
- **O estoque não tira de "Locado" o que está com cliente.** Enquanto um equipamento ou uma quantidade está com o cliente por contrato, a tela de Estoque e a situação do equipamento recusam a mudança. O caminho é registrar a devolução no contrato.
- **Preços, orçamentos e contratos antigos não mudam** quando a tabela de preços é atualizada.
- **Nada é apagado.** Cadastros são desativados; orçamentos e contratos são cancelados com motivo; o histórico fica.

## 4. Preparar a operação

Faça nesta ordem: clientes, produtos, equipamentos, estoque e preços. Se a locadora já tem esses dados em planilha, veja antes a seção 5.

### Clientes

1. Abra **Comercial → Clientes** e clique em **Novo cliente**.
2. Escolha o **Tipo de pessoa** e preencha pelo menos **Nome / razão social** e **CPF / CNPJ**.
3. Use **Adicionar endereço** para cada endereço. Um endereço informado exige identificação, endereço completo, cidade, UF (duas letras) e CEP.
4. Clique em **Salvar cliente**.

Na lista, **Detalhes** mostra o cadastro, **Editar** altera, **Desativar** tira o cliente de novos orçamentos sem apagar o histórico e **Contratos e documentos** reúne os contratos e os PDFs daquele cliente.

### Produtos

1. Abra **Operação → Produtos** e clique em **Novo produto**.
2. Preencha **Código**, **Nome do produto** e **Unidade de medida**.
3. Em **Controla equipamento individual**, escolha **Sim** para o que é locado por unidade identificada (uma betoneira com patrimônio, por exemplo) e **Não** para o que é locado por quantidade (andaimes, escoras).
4. Clique em **Salvar produto**.

Essa escolha não pode ser trocada depois que o produto tiver movimentação.

### Equipamentos (unidades físicas)

Somente para produtos com controle individual.

1. Abra **Operação → Equipamentos** e clique em **Novo equipamento**.
2. Selecione o produto e informe o **Código interno**. Patrimônio, número serial, marca e modelo são opcionais.
3. Clique em **Salvar equipamento**. A unidade nasce como **Disponível**.

Para mudar a situação de uma unidade (por exemplo, mandar para manutenção ou dar baixa), use **Alterar situação**, escolha a **Nova situação** e informe o **Motivo da alteração**. **Baixado** é definitivo.

### Estoque (produtos por quantidade)

1. Abra **Operação → Estoque**. A tabela mostra o saldo de cada produto em Disponível, Reservado, Locado, Manutenção, Indisponível e Baixado.
2. Para dar entrada, clique em **Movimentar** no produto, deixe **Origem** em **Entrada de estoque**, **Destino** em **Disponível**, informe **Quantidade** e **Motivo** e clique em **Confirmar movimentação**.
3. Para transferir entre situações (por exemplo, de Disponível para Manutenção), escolha a origem e o destino.

**Histórico** mostra todos os movimentos do produto. Em produtos com controle individual o botão é **Ver unidades**, que leva aos equipamentos. O sistema nunca deixa o saldo negativo.

### Preços

1. Abra **Operação → Preços** e clique em **Novo preço**.
2. Selecione o produto, o **Período** (Diária, Semanal, Quinzenal ou Mensal), o **Início da vigência**, o **Valor (R$)** e o **Motivo**.
3. Clique em **Publicar preço**.

Cada produto precisa de um preço para cada período que a locadora pratica. Para mudar um valor, use **Revisar**: o sistema publica uma nova versão e guarda a anterior. **Desativar** deixa o produto sem preço naquela vigência. **Consultar preço vigente** responde qual preço vale para um produto, período e data.

## 5. Importar a planilha Excel

Quem tem a permissão de importação (de fábrica, o administrador) pode trazer clientes, produtos, equipamentos, preços e entradas de estoque de uma planilha `.xlsx` ou `.xlsm`. O passo a passo completo, os limites e os cuidados estão em [EXCEL_IMPORT.md](EXCEL_IMPORT.md). Em resumo:

1. Abra **Gestão → Importações** (ou o atalho **Enviar Excel e converter dados** no painel inicial).
2. Em **1. Enviar arquivo**, escolha o arquivo e clique em **Enviar e analisar Excel**.
3. Em **2. Analisar e mapear**, escolha a aba, a linha do cabeçalho e o destino em **Converter para**; depois indique qual coluna alimenta cada campo.
4. Clique em **Validar e gerar prévia (DRY RUN)**. A prévia não grava nada.
5. Confira válidos, ignorados, avisos e erros. Marque "Revisei os avisos, os erros e as informações que ficaram sem destino." e clique em **Confirmar importação das linhas válidas**.
6. Use **Converter outra aba ou módulo deste arquivo** para continuar com a mesma planilha.

Importe produtos antes de equipamentos, estoque e preços. O arquivo original é preservado. **O histórico de contratos e renovações da planilha não é convertido nesta versão.**

## 6. Orçamentos

### Criar

1. Abra **Comercial → Orçamentos** e clique em **Novo orçamento** (o mesmo botão existe no painel inicial).
2. Em **Dados do orçamento**, busque e selecione o **Cliente**, confira o **Início previsto** e a **Validade do orçamento**.
3. Em **Itens**, para cada item: selecione o produto, informe a quantidade, o período e o número de períodos. O sistema mostra o **Preço de tabela**, o saldo "Disponível agora" e a prévia do item com a devolução prevista.
4. Use **Adicionar item** para incluir outros produtos. O mesmo produto não se repete no mesmo período.
5. Confira a **Prévia do total** e clique em **Salvar rascunho**.

O orçamento recebe um número no formato `ORC-2026-000123`. A prévia é uma estimativa; o valor oficial é calculado ao salvar.

### Preço de tabela e preço negociado

- Deixando **Preço negociado** em branco, vale o preço de tabela.
- Só quem tem a permissão de negociar consegue preencher esse campo. Para os demais, o campo fica bloqueado com o aviso "Seu perfil não permite alterar o preço de tabela."
- O detalhe do orçamento mostra **Total pela tabela**, a diferença (**Desconto negociado** ou **Acréscimo negociado**) e o **Total do orçamento**.
- Um rascunho já salvo mantém o preço de tabela que foi registrado. Para aplicar a tabela atual, marque **Atualizar preços de tabela dos itens já salvos** ao editar.

Se aparecer **Preço ausente**, não há preço vigente para aquele produto, período e data: cadastre o preço, mude o período ou remova o item.

### Situações e ações

Abra o orçamento pela lista (**Abrir**). As ações disponíveis dependem da situação:

| Situação | O que significa | Ações |
| --- | --- | --- |
| Rascunho | Em elaboração; é a única situação editável | Editar, Enviar, Aprovar, Cancelar orçamento |
| Enviado | Aguardando a resposta do cliente | Aprovar, Rejeitar, Reabrir, Cancelar orçamento |
| Expirado | Enviado cuja validade venceu | Reabrir, Cancelar orçamento |
| Aprovado | Cliente aceitou | Converter em contrato, Cancelar orçamento |
| Rejeitado | Cliente recusou | Nenhuma (só duplicar) |
| Cancelado | A locadora desistiu | Nenhuma (só duplicar) |
| Convertido | Já virou contrato | Nenhuma (só duplicar) |

- **Enviar**: o orçamento deixa de ser editável e passa a aguardar o cliente.
- **Aprovar**: registra o aceite. Exige a permissão de aprovar. Aprovar não reserva estoque.
- **Rejeitar** e **Cancelar orçamento**: exigem motivo com pelo menos 5 caracteres. Rejeitado é recusa do cliente; cancelado é decisão da locadora. Nenhum dos dois pode ser reaberto.
- **Reabrir**: volta a rascunho para corrigir itens ou a validade.
- **Duplicar**: cria um novo rascunho com os preços da tabela atual e avisa se algum item não pôde ser copiado. Funciona em qualquer situação.
- **Baixar PDF**: gera o PDF do orçamento para enviar ao cliente.

### Converter em contrato

1. Abra o orçamento **Aprovado** e clique em **Converter em contrato**.
2. Leia o aviso e clique em **Confirmar conversão**.
3. O sistema cria um contrato em **rascunho**, com o cliente, os itens e os preços do orçamento, usando o próximo número de contrato, e abre esse contrato.

A conversão só pode ser feita uma vez. O orçamento passa a **Convertido** e mostra o link **Abrir contrato**.

## 7. Contratos

### Criar

- **A partir de orçamento**: converta um orçamento aprovado (seção 6).
- **Contrato direto**: abra **Comercial → Contratos**, clique em **Novo contrato**, selecione o cliente, informe o **Início da locação**, monte os itens como no orçamento e clique em **Salvar rascunho**.

O número do contrato é definitivo desde o rascunho e não é reaproveitado. Enquanto estiver em rascunho, o contrato pode ser alterado em **Editar**.

### Confirmar

1. Abra o contrato em rascunho e clique em **Confirmar contrato**.
2. Confirme na janela. O contrato passa a **Aguardando retirada** e não pode mais ser editado.

Confirmar não baixa nem reserva o estoque: isso acontece na retirada.

### Gerar o documento e marcar como assinado

1. No cartão **Documentos** do contrato, use **Baixar prévia (PDF)** para conferir o texto. No rascunho só existe a prévia.
2. Depois de confirmar o contrato, clique em **Gerar documento** e confirme. O sistema cria e guarda a versão 1.
3. Baixe a versão (**Baixar**), imprima e colha a assinatura do cliente.
4. Com a via assinada em mãos, clique em **Marcar como assinado** e em **Confirmar assinatura**.

Cada nova geração cria uma nova versão; a anterior, se ainda não estava assinada, passa a **Substituído**. Um documento assinado nunca é substituído, e gerar outra versão depois dele exige informar o motivo. O sistema gera somente PDF e não guarda a via digitalizada: arquive a via assinada conforme a rotina da locadora.

Enquanto a locadora não publicar o seu contrato oficial, o PDF sai com o aviso **MODELO PROVISÓRIO**.

### Cancelar e encerrar

- **Cancelar contrato**: disponível em Rascunho e em Aguardando retirada, com motivo. Contrato que já teve retirada não pode ser cancelado: registre a devolução.
- **Encerramento automático**: acontece quando nada mais está com o cliente nem falta retirar.
- **Encerrar contrato** (manual): aparece no contrato ativo quando nada está com o cliente, mas ainda há saldo que nunca foi retirado. Exige motivo e não pode ser desfeito.

### Encontrar um contrato

Na lista, busque por cliente, documento ou número. Buscar `9193` traz o contrato e as renovações; `9193.1` traz só aquela renovação. **Filtros avançados** permitem filtrar por origem, produto, equipamento, período de locação e data de início.

A tela do contrato reúne: **Resumo**, **Cliente**, **Itens** (contratado, retirado, com o cliente, devolvido, renovado e a retirar), **Datas**, **Valores**, **Documentos**, **Cadeia de renovações**, **Retiradas e devoluções** e **Histórico**.

## 8. Retirada

1. Abra **Operação → Retiradas**. A tela lista os contratos **Aguardando retirada** e os **Ativos com saldo a retirar**. Clique em **Registrar retirada** (o mesmo botão existe dentro do contrato).
2. Confira a **Data da retirada**.
3. Em **Itens a retirar**, ajuste a quantidade de cada item. Deixe em branco ou zero o que não vai sair agora: a retirada pode ser parcial.
4. Para produto com controle individual, marque quais unidades físicas estão saindo — uma para cada unidade retirada. Só aparecem unidades **Disponíveis**.
5. Clique em **Revisar retirada**, confira o resumo e clique em **Confirmar retirada**.

Ao confirmar, os itens saem de Disponível para Locado e o contrato passa a **Ativo**. A partir daí o contrato não pode mais ser cancelado.

Se não houver saldo ou unidade disponível, a retirada é recusada. Libere o equipamento da manutenção, dê entrada no estoque ou aguarde uma devolução.

## 9. Renovação

A renovação prorroga a locação do que **está com o cliente**. Ela cria um novo contrato na mesma cadeia: o contrato `9193` renovado vira `9193.1`; renovado de novo, `9193.2`. O contrato anterior é preservado.

1. Abra **Comercial → Renovações**, localize o contrato em **Contratos que podem ser renovados** e clique em **Renovar** (ou use **Renovar** dentro do contrato ativo).
2. Confira o **Início da renovação**. A sugestão é a devolução prevista do contrato atual.
3. Escolha a **Opção de preço**, que é obrigatória e fica registrada:
   - **Manter os preços anteriores** — mesmo período e mesmo preço de cada item do contrato atual.
   - **Aplicar os preços atuais da tabela** — preço de tabela vigente na data de início da renovação. Se não houver preço vigente, a renovação é recusada.
   - **Informar preços negociados** — você informa o preço de cada item. Valor diferente da tabela exige a permissão de negociar.
4. Em **Itens com o cliente**, desmarque o que não será renovado e ajuste quantidade, período e número de períodos.
5. Clique em **Revisar renovação** e em **Confirmar renovação**.

O novo contrato já nasce **Ativo**. A renovação não movimenta o estoque, porque os itens não saíram do cliente, e não pode ser desfeita. Se todos os itens foram renovados e nada falta retirar, o contrato anterior é encerrado automaticamente; se a renovação foi parcial, os itens não renovados continuam pendentes no contrato anterior.

## 10. Devolução

1. Abra **Operação → Devoluções**. A lista traz primeiro os contratos vencidos, depois os que vencem em breve e os demais ativos. Clique em **Registrar devolução**.
2. Confira a **Data da devolução**.
3. Em **Itens com o cliente**, deixe marcado o que está voltando e desmarque o que continua com o cliente.
4. Para cada item devolvido, informe:
   - a quantidade (em produto por quantidade; produto por unidade devolve uma unidade física por linha);
   - a **Condição**: **Bom estado** ou **Avariado**;
   - o **Destino**: **Disponível** ou **Manutenção**. Item avariado vai obrigatoriamente para manutenção.
5. Clique em **Revisar devolução** e em **Confirmar devolução**.

- **Devolução parcial**: o restante continua com o cliente e o contrato segue ativo.
- **Devolução total**: quando nada fica com o cliente e nada falta retirar, o contrato é **encerrado automaticamente**.
- Para devolver parte de uma quantidade em bom estado e parte avariada, registre duas devoluções.
- A devolução não pode ser desfeita.

## 11. Manutenção

**Operação → Manutenção** mostra o que está fora de locação para reparo: **Unidades em manutenção** (equipamentos individuais) e **Saldos em manutenção** (produtos por quantidade). É aqui que chegam os itens devolvidos como avariados.

Para devolver um item à locação:

1. Clique em **Liberar** na unidade ou no saldo.
2. Em produto por quantidade, informe a **Quantidade a liberar**.
3. Informe o **Motivo da liberação** (por exemplo, "reparo concluído e testado") e clique em **Confirmar liberação**.

O item volta a **Disponível**. Esta versão registra a ida e a volta da manutenção, mas não tem ordem de serviço, custo ou descrição do reparo.

## 12. Solicitações de renovação dos clientes

O cliente pode pedir a renovação de um contrato pelo portal. O pedido aparece em **Comercial → Renovações**, no cartão **Solicitações de renovação dos clientes**.

1. Confira o contrato, o período pedido e as observações do cliente.
2. Clique em **Aprovar** ou em **Recusar**. A recusa exige motivo, que o cliente verá no portal.
3. **Aprovar não renova o contrato.** A aprovação apenas registra a decisão. Em seguida, clique em **Renovar contrato** e faça a renovação como na seção 9, com as condições combinadas.

## 13. Painel inicial e relatórios

### Painel inicial (Dashboard)

A tela **Visão geral** mostra indicadores calculados na hora: contratos ativos, aguardando retirada, vencendo em breve, vencidos, itens locados, equipamentos disponíveis, equipamentos em manutenção, orçamentos em aberto e valor contratado. Abaixo ficam **Contratos vencendo e vencidos**, **Movimentações recentes** e o **Acesso rápido**.

**"Valor contratado" não é valor recebido.** É a soma dos contratos ativos conforme o que foi pactuado. O LocaControl não controla pagamentos.

### Relatórios

1. Abra **Gestão → Relatórios** e escolha o relatório no campo **Relatório**.
2. Ajuste os filtros disponíveis para aquele relatório (período, cliente, produto ou busca).
3. Use **Exportar Excel** ou **Exportar PDF**. A exportação traz todas as linhas com os filtros escolhidos, não só a página exibida.

Relatórios disponíveis: Locações ativas, Contratos vencendo, Contratos vencidos, Produtos locados, Produtos disponíveis, Equipamentos por cliente, Histórico de equipamento, Renovações, Devoluções, Receita contratada por período, Produtos mais locados e Clientes com maior volume.

Os relatórios de valores trazem a nota "Valores contratados conforme os contratos; não representam pagamentos recebidos." Leia-os como o que foi contratado, não como o que entrou no caixa.

## 14. Faturamento e fiscal

**Atenção: esta tela é uma SIMULAÇÃO. Os documentos gerados aqui não têm valor fiscal e nada é transmitido à prefeitura, à Receita ou a qualquer provedor.** A tela mostra esse aviso o tempo todo. A nota fiscal ou o documento que a locação exigir continua sendo emitido fora do LocaControl, como a locadora faz hoje.

A tela serve para registrar o que será faturado e treinar o fluxo:

1. Abra **Financeiro → Faturamento e fiscal** e clique em **Novo documento**.
2. Selecione o **Cliente**, opcionalmente um contrato dele, o período, o **Valor (R$)** e a **Descrição do faturamento**. Clique em **Criar documento**. Ele nasce **Pendente**.
3. Abra o documento e clique em **Enviar ao provedor**. Na simulação, o documento passa direto a **Emitido**. Para treinar os outros caminhos, escreva `[PROCESSANDO]` na descrição (o documento fica **Processando** até você clicar em **Consultar situação**) ou `[ERRO]` (a simulação devolve uma rejeição, e o botão vira **Enviar novamente ao provedor**).
4. **Baixar PDF** e **Baixar XML** entregam arquivos marcados como simulação.
5. **Cancelar documento** exige motivo e não pode ser desfeito.

O cartão **Acompanhamento e retornos** lista cada chamada e a resposta recebida. A emissão real depende de a locadora definir as regras com a contabilidade, escolher um provedor e fornecer credenciais de teste.

## 15. Portal do cliente

Esta seção é para o cliente da locadora.

O portal funciona na rede local da locadora. O acesso pela internet ainda não está disponível.

### Entrar

1. A locadora entrega um usuário e uma senha provisória.
2. Entre no endereço informado pela locadora. No primeiro acesso o sistema pede a troca da senha (12 caracteres ou mais).
3. Se aparecer "Portal ainda não liberado para esta conta", a locadora ainda não associou a sua conta ao seu cadastro: fale com ela.

### O que você encontra

| Menu | O que mostra |
| --- | --- |
| Início | Contratos ativos, itens locados, solicitações em análise e as próximas devoluções |
| Meus contratos | Seus contratos confirmados, com itens, documentos, renovações e histórico |
| Meus equipamentos | O que está com você agora e a devolução prevista |
| Orçamentos | Orçamentos que a locadora enviou, com **Baixar PDF** |
| Renovações | Seus pedidos de renovação e a resposta da locadora |
| Documentos | Os PDFs dos seus contratos (**Baixar PDF**) |
| Meu cadastro | Os dados que a locadora tem sobre você, somente para leitura |
| Meu perfil | Seu nome e a troca de senha |

Você vê apenas os seus próprios dados. Para aprovar ou ajustar um orçamento, ou corrigir o cadastro, fale com a locadora.

### Pedir a renovação de um contrato

1. Abra **Renovações** e clique em **Solicitar renovação** (ou abra o contrato em **Meus contratos** e use o mesmo botão).
2. Escolha o contrato, o **Período desejado** e a **Quantidade de períodos**. Se quiser, escreva observações para a locadora.
3. Clique em **Enviar solicitação**.

**O pedido não renova o contrato.** A locadora analisa e responde; até lá, datas e valores continuam os mesmos, e os preços da renovação são confirmados por ela. Só é possível ter um pedido em análise por contrato. Enquanto o pedido estiver **Em análise**, você pode desistir em **Cancelar**. As respostas possíveis são **Aprovada** (a locadora fará a renovação) e **Recusada** (com o motivo).

## 16. Perguntas frequentes e mensagens de erro

| Mensagem ou situação | O que significa e o que fazer |
| --- | --- |
| "Usuário ou senha inválidos." | Confira o usuário e a senha. Se esqueceu, peça ao administrador para redefinir. |
| "Muitas tentativas. Aguarde 15 minutos." | Houve erros seguidos de senha. Aguarde e tente de novo. |
| "Sua sessão expirou. Entre novamente." | A sessão dura um tempo limitado. Entre de novo; o que já foi salvo não se perde. |
| "Altere sua senha antes de continuar." | A senha é temporária. Troque-a em **Meu perfil**. |
| "Você não tem permissão para esta ação." | O seu perfil não faz essa operação. Fale com o administrador. |
| "Você não tem permissão para alterar o preço de tabela." | Preço negociado exige permissão própria. Deixe o campo em branco ou peça a quem pode negociar. |
| "Preço ausente" / "Não há preço vigente para o produto, período e data." | Cadastre o preço em **Operação → Preços**, mude o período ou a data de início. |
| "Há item sem preço de tabela vigente. Ajuste ou remova o item para salvar." | O mesmo caso acima, ao salvar orçamento ou contrato. |
| "A validade não pode ser anterior a hoje." | Ajuste a **Validade do orçamento**. |
| "Somente rascunhos podem ser editados." | Reabra o orçamento enviado ou duplique-o. Contrato confirmado não volta a rascunho. |
| "Somente orçamento aprovado pode ser convertido em contrato." | Aprove o orçamento antes de converter. |
| "Este orçamento já foi convertido no contrato N." | A conversão é única. Abra o contrato indicado. |
| "... é controlado por unidade: use quantidade inteira." | Produto com controle individual não aceita quantidade fracionada. |
| "Saldo insuficiente. O estoque não pode ficar negativo." | Não há quantidade disponível. Confira o estoque, a manutenção e as devoluções pendentes. |
| "Equipamento X não está disponível." | A unidade escolhida saiu de Disponível depois que a tela foi aberta. Recarregue e escolha outra. |
| "Nenhuma unidade física disponível deste produto." | Libere uma unidade da manutenção ou cadastre um equipamento antes da retirada. |
| "Esta quantidade está com clientes por contrato. Registre a devolução no contrato em vez de movimentar o estoque manualmente." | Você tentou tirar de Locado, pelo Estoque, algo que está com cliente. Registre a devolução no contrato. |
| "Esta unidade está com o cliente no contrato N. Registre a devolução no contrato em vez de alterar a situação manualmente." | O mesmo caso, para um equipamento individual. |
| "Contrato com retirada registrada não pode ser cancelado; registre a devolução." | Depois da retirada não há cancelamento: devolva os itens e o contrato se encerra. |
| "Ainda há itens com o cliente. Registre a devolução antes de encerrar." | O encerramento manual só vale quando nada está com o cliente. |
| "Contrato alterado por outra operação. Atualize e tente novamente." (também para orçamento, documento e registro) | Outra pessoa alterou o mesmo registro enquanto você editava. Use o botão de recarregar e refaça a alteração. |
| "Libere a reserva ou locação antes da baixa." | Não se dá baixa em item reservado ou locado. |
| "Já existe uma solicitação em análise para este contrato." (portal) | Aguarde a resposta da locadora ou cancele o pedido anterior. |
| O contrato não aparece em Retiradas | Ele ainda está em rascunho (falta **Confirmar contrato**) ou já foi totalmente retirado. |
| O botão **Registrar retirada** ou **Registrar devolução** não aparece | O seu perfil não registra operações (caso do perfil Comercial de fábrica). |
| O histórico mostra "Usuário nº 3" em vez do nome | Limitação desta versão: o histórico de orçamentos e contratos mostra o número interno do usuário. **Gestão → Auditoria** mostra o nome de usuário do responsável por cada ação. |
| O PDF do contrato saiu com "MODELO PROVISÓRIO" | A locadora ainda não publicou o contrato oficial. Veja a seção 3 do [ADMIN_GUIDE.md](ADMIN_GUIDE.md). |
| O PDF saiu com o nome "LocaControl" no cabeçalho | Os dados da locadora ainda não foram preenchidos. Veja a seção 4 do [INSTALLATION.md](INSTALLATION.md). |
