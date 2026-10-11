# LocaControl — Regras de negócio

Estas regras são requisitos conhecidos, não funcionalidades já entregues. O texto integral e os critérios de cada etapa estão em `DEVELOPMENT_PLAN.md`. A Etapa 0 não implementa módulos comerciais.

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
- Preços por produto e período: diária, semanal, quinzenal e mensal; manter histórico. Duração exata, arredondamentos e regras de cobrança ainda precisam de definição antes dos cálculos comerciais.
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
- Transições: enviar (rascunho → enviado); aprovar (rascunho ou enviado → aprovado); rejeitar (enviado → rejeitado, com motivo); cancelar (rascunho, enviado ou aprovado → cancelado, com motivo); reabrir (enviado, inclusive expirado → rascunho). Convertido chega com a Etapa 6 e não pode ser cancelado.
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

## Confiabilidade e aceite — Etapas 11 e 12

Backup automático configurável por ativação, horário, diretório e retenção; nomes com data/hora, verificação, exportação manual e restauração assistida com confirmação forte e cópia prévia. Logs, health checks, inicialização amigável no Windows e atualização sem apagar banco.

Release 1.0 depende do fluxo completo cliente → produto/preço/estoque → orçamento aprovado → contrato → retirada → renovação → devolução parcial → nova renovação → devolução total → encerramento. Validar estoque, histórico, auditoria, backups/restauração, migrations de banco vazio e atualização, temas, resoluções e erros de entrada. Criar testes E2E e guias finais; não declarar pronta com base apenas em compilação.

## UX transversal

Aplicar `DESIGN_SYSTEM.md`: conforto, acessibilidade, feedback compreensível e confirmação de operações destrutivas. Preferências e estados nunca dependem somente de cores. Mocks somente em testes e na etapa visual explicitamente identificada, nunca misturados ao banco real.


## Importação via upload — decisão de 2026-10-08

O usuário envia o Excel pela interface; não solicitar caminho local. Analisar o arquivo em tempo de execução, sem layout definitivo presumido. Usar mapeamento explícito por aba/módulo, DRY RUN, digest da prévia e confirmação. Preservar original e origem. Informar colunas/abas sem destino. Contratos e renovações aguardam suas entidades; não declarar sua conversão realizada. Conflitos não sobrescrevem registros; estoque inicial não se soma a produto com movimentos anteriores. Detalhes e limites em EXCEL_IMPORT.md.
