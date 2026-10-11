# LocaControl — Regras de negócio

O texto integral e os critérios de cada etapa estão em `DEVELOPMENT_PLAN.md`. As seções gerais abaixo são os requisitos do plano; as seções "confirmadas em 2026-10-11" descrevem o que o backend realmente faz e está coberto por testes. Onde as duas divergem, a diferença está indicada. Telas: ver `PROJECT_STATE.md`.

## Dados e histórico

- O Excel legado é a fonte inicial: preservar original, códigos e informações sempre que possível.
- Registros importantes terão ID interno, `created_at`, `updated_at` e `created_by` quando aplicável. Usar soft delete quando apropriado; não eliminar histórico comercial.
- Nunca usar `float` para dinheiro. Calcular com Decimal e persistir com representação exata validada para o banco utilizado.
- Preços, orçamentos e contratos guardam snapshots históricos. Atualizar tabela de preço não altera documentos anteriores.

## Cadastros e estoque — Etapa 3

- Cliente PF/PJ: razão social, fantasia, CPF/CNPJ, inscrição estadual aplicável, telefone, celular, e-mail, responsável, endereço, cidade, UF, CEP, observações e status. Validar duplicidades relevantes; preparar múltiplos endereços.
- Produto: código, nome, descrição, categoria, unidade, controle individual e ativo.
- Produto não é unidade física. Equipamentos: código interno, patrimônio, serial, marca, modelo, status e observações; permitir localização e histórico futuros.
- Suportar produto por quantidade e produto por unidade identificada.
- Estados: disponível, reservado, locado, manutenção, indisponível e baixado. Nunca permitir estoque negativo silenciosamente.
- Preços por produto e período: diária, semanal, quinzenal e mensal; manter histórico. Duração e arredondamento foram definidos em 11/10/2026 (ver regras de orçamento confirmadas).
- CRUD com permissões, filtros e auditoria.

## Importação — Etapa 4

Analisar o workbook real antes de definir o mapeamento: abas, cabeçalhos, fórmulas, mesclas, tipos, códigos, datas e referências. Não alterar o original. Fluxo: upload → análise → aba → mapeamento → preview → validações/avisos/conflitos → confirmação → importação.

Detectar duplicados, ausências, datas/valores inválidos e conflitos. Uma linha problemática não cancela indiscriminadamente as demais. DRY RUN não persiste alterações. Importação exige confirmação explícita e identificação de origem. ImportBatch registra filename, checksum, imported_at/by, total_rows, successful_rows, warning_rows e failed_rows; relatório exportável de erros e totais importados/ignorados/avisos/erros. Usar fixtures de teste isoladas.

## Orçamentos — Etapa 5

Cliente → produtos/quantidades → período → preços → desconto → total. Carregar preço automaticamente; alteração manual apenas com permissão. Registrar preço de tabela e negociado. Múltiplos itens, numeração própria (exemplo `ORC-2026-000123`), duplicação, edição de rascunho, PDF, aprovação, cancelamento e conversão em contrato. Mostrar disponibilidade sem reserva definitiva ao adicionar item.

Estados previstos: rascunho, enviado, aprovado, rejeitado, expirado e convertido. O fluxo de cancelamento deve ser conciliado formalmente com os estados na Etapa 5, pois o plano solicita a ação mas não lista seu estado. Testar cálculos com Decimal; não atualizar orçamento histórico pela tabela corrente.

### Regras de orçamento confirmadas em 2026-10-11

- Valor do item: quantidade × preço do período × número de períodos. Não há fração de período; o vendedor escolhe o período e quantos períodos.
- Duração: diária 1 dia, semanal 7, quinzenal 15, mensal 30 dias corridos. Devolução prevista = início + dias × número de períodos.
- Desconto: somente preço negociado por item, por usuário com permissão. O orçamento guarda preço de tabela e negociado e mostra a diferença; não há desconto separado no total.
- Arredondamento: cada item em centavos, meio centavo para cima; total é a soma dos itens.
- Estados persistidos: rascunho, enviado, aprovado, rejeitado, cancelado e convertido. Expirado é o enviado com validade vencida (classificação por data).
- Transições: enviar (rascunho → enviado); aprovar (rascunho ou enviado → aprovado); rejeitar (enviado → rejeitado, com motivo); cancelar (rascunho, enviado ou aprovado → cancelado, com motivo); reabrir (enviado, inclusive expirado → rascunho). Convertido é atribuído pela conversão em contrato (Etapa 6) e não pode ser cancelado.
- Rejeitado é recusa do cliente; cancelado é decisão da locadora. Só rascunho é editável; orçamento expirado pode ser reaberto, cancelado ou duplicado.
- Produto controlado por unidade exige quantidade inteira. O mesmo produto não se repete no mesmo período dentro de um orçamento.
- Rascunho já salvo mantém o preço de tabela registrado; reler a tabela é ação explícita. Duplicar usa a tabela atual e informa itens que não puderam ser copiados.
- Orçamento mostra o saldo disponível, mas não reserva estoque.

## Contratos e documentos — Etapa 6

Contrato direto ou a partir de orçamento aprovado. ID interno separado de `base_number` e `renewal_number`. Exibição `9193`, `9193.1`, `9193.2`; renovação sempre vinculada ao original. Numeração deve impedir colisões e preservar código importado.

ContractItems guardam produto, descrição, quantidade, período, preço, desconto, valor e datas. Estados: rascunho, aguardando retirada, ativo, vencendo, vencido, encerrado e cancelado. Regras de transição e limiar de vencendo serão definidos na etapa correspondente.

Usar modelo real fornecido pelo usuário, sem descaracterizá-lo. Templates com placeholders; PDF e DOCX se adequado. Vincular documentos ao contrato, permitir regeneração controlada e histórico; nunca substituir silenciosamente documento assinado. Tela reúne resumo, cliente, itens, datas, valores, documentos, histórico e auditoria.

## Ciclo operacional — Etapa 7

- Retirada após aprovação, com associação física quando necessária e atualização disponível → locado.
- Renovação recebe próximo número sem sobrescrever anterior. Pode incluir todos ou parte dos itens. Registrar opção explícita: preços anteriores, atuais ou negociados.
- Devolução total/parcial registra data, quantidade, unidade, observação e condição. Saldo não devolvido mantém contrato ativo. Equipamento volta como disponível ou manutenção conforme condição.
- Manter timeline completa de criação, retirada, renovações, devoluções e encerramento. Testar quantidades e estoque extensivamente.

### Regras de contrato confirmadas em 2026-10-11 (Etapa 6)

Decisões do usuário:
- Numeração: próximo número = maior existente + 1; o administrador pode definir o número inicial; sem configuração começa em 1.
- "Vencendo" e "vencido" são calculados pela data de devolução, não gravados. Antecedência de "vencendo": 3 dias (`LOCACONTROL_CONTRACT_DUE_SOON_DAYS`).
- Modelo de contrato PROVISÓRIO, identificado no documento, até o usuário fornecer o modelo real.

Comportamento implementado:
- Contrato nasce em rascunho, direto ou a partir de orçamento APROVADO. Cada orçamento converte uma única vez e passa a CONVERTIDO; o contrato copia cliente, itens e preços do orçamento, sem reler a tabela.
- Código exibido: `9193`; renovações `9193.1`, `9193.2`. O próximo número só pode ser configurado acima do maior já usado.
- Itens usam o mesmo cálculo do orçamento (quantidade × preço do período × nº de períodos; 1/7/15/30 dias corridos), com preço de tabela e negociado guardados. Preço diferente da tabela exige permissão própria de contrato.
- Estados gravados: rascunho, aguardando retirada, ativo, encerrado, cancelado. Vencendo = ativo com devolução prevista entre hoje e hoje + antecedência; vencido = ativo com devolução prevista anterior a hoje. A data considerada é a menor devolução prevista entre as linhas que ainda estão com o cliente.
- Transições: confirmar (rascunho → aguardando retirada); primeira retirada (→ ativo); cancelar (rascunho ou aguardando retirada → cancelado, com motivo de ao menos 5 caracteres); encerrar (ver encerramento). Só rascunho é editável; contrato com retirada registrada não pode ser cancelado.
- Confirmar o contrato NÃO reserva estoque (decisão técnica revisável): a disponibilidade é conferida e baixada na retirada.
- Documento: só PDF. Prévia no rascunho; geração após a confirmação. Cada geração é uma versão; a anterior apenas gerada vira "substituída". Documento marcado como assinado nunca é substituído, e nova versão depois dele exige motivo. "Assinado" é marcação com autor e data; não há upload do documento digitalizado nem geração de DOCX.

### Regras de operação confirmadas em 2026-10-11 (Etapa 7)

- Retirada: permitida com o contrato aguardando retirada ou ativo, total ou parcial, limitada ao saldo a retirar de cada item. Produto por unidade exige indicar um equipamento Disponível do mesmo produto para cada unidade; produto por quantidade exige saldo Disponível suficiente. Efeito: Disponível → Locado e contrato ativo.
- Devolução: somente em contrato ativo, total ou parcial, limitada ao que está com o cliente. Produto por unidade devolve uma unidade física por linha. Condição → destino: BOM → Disponível (ou Manutenção, se indicado); AVARIADO → Manutenção, obrigatoriamente. Efeito: Locado → destino. Saldo não devolvido mantém o contrato ativo.
- Renovação: somente de contrato ativo, de todos ou parte dos itens que estão com o cliente, limitada a essa quantidade. Recebe o próximo sufixo da mesma base e já nasce ativa. A opção de preço é obrigatória e fica registrada:
  - ANTERIORES — mantém preço de tabela e negociado do item original; exige o mesmo período.
  - ATUAIS — usa o preço de tabela vigente na data de início da renovação; sem preço vigente, a renovação é recusada.
  - NEGOCIADOS — preço informado por item; se diferir da tabela vigente, exige permissão de negociação.
- A renovação não movimenta estoque: os itens continuam Locados e a custódia passa para a nova linha. O contrato anterior é preservado e não é sobrescrito.
- Encerramento: automático quando nada resta com o cliente nem a retirar (por devolução total ou porque tudo foi renovado). Manual, com motivo, para contrato ativo cujo restante nunca foi retirado; não é permitido enquanto houver item com o cliente.
- Retirada e devolução repetidas com o mesmo identificador de operação não geram novo movimento.
- Ajuste manual de estoque não pode tirar de Locado quantidade ou unidade que está com cliente por contrato ativo; a devolução deve ser registrada no contrato.
- Manutenção: a devolução encaminha para Manutenção; o retorno a Disponível é feito pelos movimentos de estoque/situação do equipamento já existentes. Não há registro próprio de intervenção de manutenção.
- Timeline por cadeia (contrato original + renovações): criado, confirmado, retirada, devolução parcial/total, renovado, documento gerado/assinado, encerrado, cancelado.

## Usuários, autorização e auditoria — Etapa 2

Perfis iniciais: ADMINISTRADOR (completo), COMERCIAL (clientes/orçamentos/contratos/renovações), OPERAÇÃO (equipamentos/estoque/retirada/devolução/manutenção), FINANCEIRO (faturamento/valores/fiscal), CLIENTE (apenas dados próprios). Autorizar sempre na API. Matriz detalhada por ação deve ser definida nesta etapa.

Login, logout, usuário atual, alteração de senha, recuperação local segura, bootstrap administrativo sem senha fixa, perfil e gestão de usuários/permissões. Senhas somente com hash seguro. Não armazenar segredos no código. Validar uploads, extensão e nomes; nunca confiar no frontend.

Auditar mudanças importantes em clientes, preços, orçamentos, contratos, estoque, devoluções, usuários e permissões, com autor, horário, registro/campo e valores anteriores/novos, sem vazar segredos.

## Dashboard, relatórios e portal — Etapas 8 e 9

Dashboard real: contratos ativos/vencendo/vencidos, itens locados, equipamentos disponíveis/em manutenção, valor contratado e movimentos recentes. Filtros por código, cliente, documento, produto, equipamento, status, data e período. Cliente reúne contratos, itens, documentos e histórico.

Relatórios de locações, vencimentos, estoque, equipamentos por cliente, histórico de equipamento, renovações, devoluções, receita contratada e rankings de produtos/clientes; exportação Excel/PDF sem bloquear interface. Não apresentar receita contratada como pagamento efetivamente recebido.

Portal CLIENTE isola dados no backend; permite visualizar e baixar informações próprias e solicitar renovação. Solicitação exige aprovação do funcionário e não gera renovação definitiva. Operação local/LAN inicial; acesso remoto exige arquitetura posterior.

## Fiscal — Etapa 10

Abstração FiscalProvider com `emit`, `status`, `cancel`, `get_pdf`, `get_xml`, implementada por adapters. Documento ligado a cliente, contrato, período e valor; estados pendente, processando, emitido, erro e cancelado. Guardar número, série, chave aplicável, PDF, XML e retorno do provedor.

Não inventar regra tributária ou espécie fiscal da locação. Configuração validada com contabilidade. Primeiro sandbox claramente identificado; provedor real somente com credenciais de testes fornecidas. Nenhuma credencial no código.

### Regras de relatórios, portal e fiscal confirmadas em 2026-10-11 (Etapas 8–10)

Relatórios:
- Indicadores vêm de contratos, itens e estoque reais. "Valor contratado" soma os contratos ativos conforme pactuado e não é pagamento recebido; os relatórios de receita trazem essa ressalva.
- Relatórios existentes: locações ativas, contratos vencendo, contratos vencidos, produtos locados, produtos disponíveis, equipamentos por cliente, histórico de equipamento, renovações, devoluções, receita contratada por período, produtos mais locados e clientes com maior volume. Exportação em Excel ou PDF com os mesmos filtros.

Portal:
- A conta do cliente vê apenas o cliente a que está vinculada: contratos (exceto rascunhos), itens e saldos, equipamentos em seu poder, documentos vigentes (não os substituídos), orçamentos enviados/aprovados/rejeitados/convertidos e o próprio cadastro, somente leitura.
- Solicitação de renovação: apenas para contrato ativo e uma pendente por contrato; o cliente pode cancelá-la enquanto pendente. O funcionário aprova ou recusa (recusa exige motivo). A aprovação só registra a decisão: a renovação é feita depois, no contrato, pelo funcionário.

Fiscal:
- Documento fiscal liga cliente, contrato opcional (do mesmo cliente, nunca rascunho ou cancelado), período e valor positivo. Estados: pendente, processando, emitido, erro, cancelado. Envio só de pendente ou com erro; consulta só de processando; cancelamento de pendente, com erro ou emitido, sempre com motivo.
- Só existe o provedor de simulação: os documentos são marcados como simulação e não têm valor fiscal. Nenhuma regra tributária, alíquota ou espécie de documento foi definida; isso depende da contabilidade.

## Confiabilidade e aceite — Etapas 11 e 12

Backup automático configurável por ativação, horário, diretório e retenção; nomes com data/hora, verificação, exportação manual e restauração assistida com confirmação forte e cópia prévia. Logs, health checks, inicialização amigável no Windows e atualização sem apagar banco.

Confirmado em 2026-10-11 (Etapa 11, backend e scripts): o backup é um conjunto `.zip` com banco, importações, documentos, arquivos fiscais e manifesto; backup automático diário é opcional (desativado por padrão) com horário, pasta e retenção configuráveis; a restauração exige digitar `RESTAURAR <nome do backup>` e a senha do próprio usuário, cria cópia prévia e não apaga arquivos atuais. Detalhes na ADR-021.

Release 1.0 depende do fluxo completo cliente → produto/preço/estoque → orçamento aprovado → contrato → retirada → renovação → devolução parcial → nova renovação → devolução total → encerramento. Validar estoque, histórico, auditoria, backups/restauração, migrations de banco vazio e atualização, temas, resoluções e erros de entrada. Criar testes E2E e guias finais; não declarar pronta com base apenas em compilação.

## UX transversal

Aplicar `DESIGN_SYSTEM.md`: conforto, acessibilidade, feedback compreensível e confirmação de operações destrutivas. Preferências e estados nunca dependem somente de cores. Mocks somente em testes e na etapa visual explicitamente identificada, nunca misturados ao banco real.


## Importação via upload — decisão de 2026-10-08

O usuário envia o Excel pela interface; não solicitar caminho local. Analisar o arquivo em tempo de execução, sem layout definitivo presumido. Usar mapeamento explícito por aba/módulo, DRY RUN, digest da prévia e confirmação. Preservar original e origem. Informar colunas/abas sem destino. Contratos e renovações já têm entidades (Etapas 6/7), mas a conversão do histórico do Excel para elas não está implementada: depende do arquivo real para definir o mapeamento. Não declarar essa conversão realizada. Conflitos não sobrescrevem registros; estoque inicial não se soma a produto com movimentos anteriores. Detalhes e limites em EXCEL_IMPORT.md.
