# LocaControl — Roteiro do guia visual

Cada passo corresponde a uma imagem da pasta img, com o mesmo nome.

## Começando

### 1. Entrar no sistema

Imagem: img/01-login.png

Narração:

Bem-vindo ao LocaControl. Para abrir o sistema, dê dois cliques em Iniciar LocaControl. O navegador abre nesta tela de acesso. No primeiro uso, entre com o usuário admin e a senha admin. O sistema vai pedir uma senha nova, com pelo menos doze caracteres, antes de liberar as telas.

Destaques na tela:

- Atalho: Iniciar LocaControl.cmd
- Primeiro acesso: admin / admin
- A troca de senha é obrigatória

### 2. Visão geral

Imagem: img/02-dashboard.png

Narração:

Esta é a visão geral. Os cartões mostram quantos contratos estão ativos, quantos aguardam retirada, os que estão vencendo e os vencidos, os itens locados e os equipamentos disponíveis ou em manutenção. O valor contratado é a soma dos contratos ativos. Ele não representa dinheiro recebido. O menu à esquerda dá acesso a todas as áreas.

Destaques na tela:

- Valor contratado não é valor recebido
- Vencendo: devolução em até 3 dias
- Menu lateral com todas as áreas

## Preparar a operação

### 3. Clientes

Imagem: img/03-clientes.png

Narração:

Comece pelos cadastros. Em Comercial, Clientes, cadastre pessoas físicas e jurídicas com documento, contato e endereço. O sistema não aceita dois clientes com o mesmo CPF ou CNPJ. O botão Contratos e documentos mostra o histórico de cada cliente.

Destaques na tela:

- CPF ou CNPJ não se repete
- Desativar preserva o histórico
- Resumo: contratos e documentos do cliente

### 4. Produtos e equipamentos

Imagem: img/04-produtos.png

Narração:

Em Operação, Produtos, cadastre o que a locadora aluga. Há dois tipos de controle. Por quantidade, como andaimes, em que basta saber quantos existem. E por unidade física, como uma betoneira, em que cada equipamento tem código próprio e é cadastrado na tela Equipamentos.

Destaques na tela:

- Por quantidade: andaimes, escoras
- Por unidade: cada equipamento tem código
- Unidades ficam em Equipamentos

### 5. Estoque

Imagem: img/05-estoque.png

Narração:

A tela de Estoque mostra o saldo de cada produto por situação: disponível, reservado, locado, manutenção, indisponível e baixado. Use Movimentar para dar entrada no estoque inicial. Depois, as retiradas e devoluções dos contratos atualizam esses saldos sozinhas. O estoque nunca fica negativo.

Destaques na tela:

- Entrada inicial pelo botão de movimento
- Contratos atualizam o saldo automaticamente
- O que está com cliente só volta pela devolução

### 6. Preços

Imagem: img/06-precos.png

Narração:

Em Preços, defina o valor de cada produto por período: diária, semanal, quinzenal e mensal, com a data de início de vigência. Ao reajustar, o preço antigo fica guardado no histórico. Orçamentos e contratos já feitos não mudam quando a tabela muda.

Destaques na tela:

- Diária, semanal, quinzenal e mensal
- Reajuste preserva o histórico
- Documentos antigos não são recalculados

## Orçamento

### 7. Lista de orçamentos

Imagem: img/07-orcamentos.png

Narração:

Com os cadastros prontos, vamos ao orçamento. A lista mostra número, cliente, validade, total e situação. Você pode buscar pelo nome do cliente, pelo documento ou pelo número do orçamento, e filtrar pela situação.

Destaques na tela:

- Número no formato ORC-ano-sequência
- Busca por cliente, documento ou número
- Situação sempre com texto e ícone

### 8. Criar um orçamento

Imagem: img/08-orcamento-novo.png

Narração:

Para criar, escolha o cliente, a data de início e a validade. Em cada item, selecione o produto, a quantidade, o período e o número de períodos. O preço de tabela é preenchido automaticamente e a tela mostra quanto há disponível. O valor do item é a quantidade, vezes o preço do período, vezes o número de períodos. O orçamento não reserva estoque.

Destaques na tela:

- Valor = quantidade × preço × nº de períodos
- Preço negociado exige permissão
- Orçamento não reserva estoque

### 9. Enviar, aprovar e converter

Imagem: img/09-orcamento-detalhe.png

Narração:

No detalhe do orçamento ficam as ações. Enviar marca que o cliente recebeu a proposta. Aprovar registra o aceite. Rejeitar e cancelar pedem o motivo. Você pode baixar o PDF, duplicar o orçamento e, depois de aprovado, usar Converter em contrato. Os preços do orçamento aprovado seguem para o contrato sem alteração.

Destaques na tela:

- Enviar → Aprovar → Converter em contrato
- Rejeitar e cancelar pedem motivo
- PDF e duplicação a qualquer momento

## Contrato

### 10. Lista de contratos

Imagem: img/10-contratos.png

Narração:

Em Contratos estão todas as locações. A busca aceita número, cliente e documento. Os filtros avançados localizam por produto, equipamento, período e datas. Cada contrato recebe um número, e as renovações usam o mesmo número com um sufixo: nove mil cento e noventa e três, ponto um, ponto dois, e assim por diante.

Destaques na tela:

- Renovações: 9193.1, 9193.2
- Filtros por produto, equipamento e datas
- Vencendo e vencido calculados pela data

### 11. O contrato por dentro

Imagem: img/11-contrato-detalhe.png

Narração:

O detalhe reúne resumo, cliente, itens, datas, valores, documentos e histórico. Em cada item você vê o que foi retirado, o que está com o cliente, o que foi devolvido e o que foi renovado. Em Documentos, gere o PDF do contrato e marque como assinado a via que o cliente assinou. Um documento assinado nunca é substituído.

Destaques na tela:

- Confirmar libera a retirada
- Gerar documento em PDF
- Assinado nunca é substituído

## Operação

### 12. Registrar a retirada

Imagem: img/12-retirada.png

Narração:

Quando o cliente vem buscar, abra o contrato e escolha Registrar retirada. Informe a quantidade de cada item. Para produtos controlados por unidade, marque qual equipamento está saindo. Ao confirmar, o estoque passa de disponível para locado e o contrato fica ativo. A retirada pode ser parcial.

Destaques na tela:

- Disponível → Locado
- Escolha a unidade física quando houver
- Retirada pode ser parcial

### 13. Renovar

Imagem: img/13-renovacao.png

Narração:

Para renovar, escolha os itens que continuam com o cliente, o novo período e a opção de preço: manter os preços anteriores, usar a tabela atual, ou negociar novos valores. A escolha fica registrada. O sistema cria o próximo número, e o contrato anterior é preservado. Renovar não mexe no estoque, porque o equipamento continua com o cliente.

Destaques na tela:

- Preços: anteriores, atuais ou negociados
- Pode renovar só parte dos itens
- O contrato anterior é preservado

### 14. Registrar a devolução

Imagem: img/14-devolucao.png

Narração:

Na devolução, informe o que voltou e em que condição. Item em bom estado volta para disponível. Item avariado vai para manutenção. A devolução pode ser parcial: o que não voltou continua pendente no contrato. Quando tudo é devolvido, o contrato é encerrado automaticamente.

Destaques na tela:

- Bom → Disponível; Avariado → Manutenção
- Parcial mantém o saldo pendente
- Tudo devolvido encerra o contrato

### 15. Renovações e pedidos dos clientes

Imagem: img/15-renovacoes.png

Narração:

A tela Renovações lista as renovações feitas e os pedidos enviados pelos clientes pelo portal. Aprovar um pedido apenas registra a decisão. A renovação em si é feita pelo funcionário, pelo botão Renovar contrato.

Destaques na tela:

- Pedido do cliente precisa de decisão
- Aprovar não cria a renovação
- Recusar pede o motivo

### 16. Manutenção

Imagem: img/16-manutencao.png

Narração:

Em Manutenção aparecem os equipamentos e as quantidades que voltaram avariados. Depois do reparo, use Liberar para devolver o item ao estoque disponível.

Destaques na tela:

- Recebe os itens avariados
- Liberar devolve ao disponível

## Gestão

### 17. Relatórios

Imagem: img/17-relatorios.png

Narração:

Em Relatórios há doze consultas prontas: locações ativas, contratos vencendo e vencidos, produtos locados e disponíveis, equipamentos por cliente, histórico de equipamento, renovações, devoluções, receita contratada por período, produtos mais locados e clientes com maior volume. Todas podem ser exportadas para Excel ou PDF.

Destaques na tela:

- 12 relatórios com filtros
- Exportação em Excel e PDF
- Receita contratada não é recebimento

### 18. Faturamento e fiscal

Imagem: img/18-fiscal.png

Narração:

A tela de faturamento e fiscal funciona, nesta versão, apenas em modo de simulação. Os documentos saem marcados como simulação, sem valor fiscal, e nada é transmitido. A emissão real depende das regras definidas com a contabilidade e da contratação de um provedor.

Destaques na tela:

- SIMULAÇÃO: sem valor fiscal
- Nada é transmitido
- Emissão real segue fora do sistema

### 19. Backups

Imagem: img/19-backups.png

Narração:

Em Gestão, Backups, o administrador ativa o backup automático diário, escolhe o horário e quantas cópias manter. Fazer backup agora cria uma cópia na hora. Cada backup guarda o banco, as planilhas importadas e os contratos em PDF. Baixe cópias com frequência e guarde fora deste computador. Para restaurar, o sistema pede uma frase de confirmação e a sua senha, e antes faz uma cópia de segurança do estado atual.

Destaques na tela:

- Ative o backup automático
- Guarde cópias fora do computador
- Restaurar exige frase e senha

### 20. Usuários e perfis

Imagem: img/20-usuarios.png

Narração:

Em Usuários, o administrador cria as contas da equipe e escolhe o perfil: administrador, comercial, operação, financeiro ou cliente. Cada perfil vê apenas o que precisa. A senha criada é provisória, e o sistema obriga a troca no primeiro acesso. Para dar acesso ao portal, crie uma conta com perfil Cliente e use Vincular cliente.

Destaques na tela:

- Perfis: Administrador, Comercial, Operação, Financeiro, Cliente
- Senha provisória com troca obrigatória
- Vincular cliente libera o portal

### 21. Configurações

Imagem: img/21-configuracoes.png

Narração:

Em Configurações, o administrador define o próximo número de contrato, para continuar a sequência que a locadora já usava, e publica o modelo de contrato. O sistema vem com um modelo provisório, identificado no documento. Publique o texto da sua locadora antes de usar com clientes.

Destaques na tela:

- Próximo número de contrato
- Modelo de contrato da locadora
- Tema claro ou escuro

## Portal do cliente

### 22. Portal do cliente

Imagem: img/22-portal.png

Narração:

O cliente com acesso ao portal vê apenas os próprios contratos, equipamentos, orçamentos e documentos. Ele pode baixar o contrato e pedir uma renovação, que fica aguardando a decisão da locadora. Nesta versão o portal funciona no computador e na rede local da locadora.

Destaques na tela:

- Cada cliente vê só os próprios dados
- Pedido de renovação aguarda aprovação
- Funciona na rede local

### 23. Contrato visto pelo cliente

Imagem: img/23-portal-contrato.png

Narração:

No detalhe, o cliente acompanha os itens, as datas de devolução e o histórico da locação, e baixa os documentos. Com isso concluímos o percurso: cadastro, orçamento, contrato, retirada, renovação e devolução. Para mais detalhes, consulte o guia do usuário. Bom trabalho.

Destaques na tela:

- Itens, datas e documentos
- Histórico da locação
- Mais detalhes no guia do usuário
