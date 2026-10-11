# LocaControl — Importar o Excel da empresa

O arquivo é enviado pelo usuário na tela **Gestão → Importações**, também acessível pelo atalho **Comece pelo seu Excel** no dashboard. Não informar caminho do computador ao servidor.

1. Entre com um usuário autorizado e envie .xlsx ou .xlsm.
2. Confira abas, amostra, fórmulas e mesclas. O sistema preserva o original.
3. Escolha a aba, linha de cabeçalho e módulo de destino.
4. Mapeie as colunas para os campos. Selecione separador decimal e formato de datas dos textos.
5. Gere a prévia DRY RUN. Confira linhas válidas, ignoradas, erros, avisos e colunas/abas sem destino.
6. Marque a confirmação de revisão e confirme somente quando os resultados estiverem corretos.
7. Baixe o relatório JSON. Corrija linhas com erro e envie o arquivo corrigido quando necessário.
8. Use **Converter outra aba ou módulo deste arquivo** para continuar sem novo upload.

Importe produtos antes de equipamentos, preços e estoque, que se vinculam pelo código do produto cadastrado. Clientes exigem tipo PF/PJ, nome e documento. Endereço informado exige rua, cidade, UF e CEP. Produtos exigem código, nome e unidade; controle individual usa sim/não. Preços exigem produto, período DIARIA/SEMANAL/QUINZENAL/MENSAL, vigência e valor. Quantidade inicial entra como disponível; produto com movimentos existentes exige revisão manual no Estoque. Equipamentos importados começam disponíveis; ajuste sua situação no módulo de operação após conferir a origem.

Dinheiro aceita até duas casas; quantidade até três. Valores textuais não aceitam separador de milhar ambíguo e não são arredondados silenciosamente. Datas textuais seguem formato selecionado; datas Excel reconhecidas são convertidas para ISO. Códigos numéricos com máscara de zeros preservam a máscara simples; zeros que não existem no arquivo não podem ser reconstruídos com segurança.

O DRY RUN não grava cadastros, movimentos, preços, auditoria ou origem de linhas. O upload já registra o arquivo e seu lote, antes da prévia. A confirmação revalida os dados e rejeita prévia desatualizada. Uma linha inválida não impede as válidas; uma falha técnica inesperada desfaz a confirmação inteira. A mesma origem arquivo+aba+linha+módulo não é importada duas vezes. Registros existentes não são sobrescritos automaticamente.

Fórmulas usam somente o resultado salvo no Excel e geram aviso. Sem resultado salvo, a linha exige recálculo/salvamento no Excel. Macros e referências externas não são executadas. Mesclas não preenchem células vazias automaticamente.

Contratos e renovações aguardam as etapas correspondentes. Informações sem campo de destino aparecem como pendentes e ficam preservadas no original. A análise real depende do arquivo que o cliente enviar; fixtures de teste não comprovam conversão integral do histórico da empresa.

Limites: 10 MB por upload; 30 MB expandido; 2.000 entradas ZIP; até 10.000 linhas de dados por aba, 200 colunas e 200.000 células no arquivo. .xls antigo deve ser salvo como .xlsx no Excel. Arquivos criptografados/protegidos ou inválidos são rejeitados.

Os originais ficam fora do Git em data/imports (configurável por LOCACONTROL_IMPORT_DIRECTORY). **Backups operacionais devem incluir o banco e essa pasta juntos**. Não remover os originais para liberar espaço sem política de retenção e cópia validada. Somente usuários com imports.read podem consultar o histórico/relatório/original; imports.write e a permissão de escrita do módulo são exigidas para conversão.
