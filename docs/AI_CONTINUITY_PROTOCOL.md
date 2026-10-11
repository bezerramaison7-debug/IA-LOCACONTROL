# LOCACONTROL — PROTOCOLO PERMANENTE DE CONTINUIDADE DA IA

Este prompt deve ser considerado obrigatório em TODAS as sessões de desenvolvimento do projeto LocaControl.

Sua função é garantir que nenhuma troca de sessão, limite de contexto, limite de execução, interrupção, reinício ou mudança de agente faça o projeto perder o estado atual.

---

# 1. ARQUIVO OFICIAL DE CONTINUIDADE

Existe um arquivo operacional obrigatório:

`/docs/AI_HANDOFF.md`

Esse arquivo representa a memória operacional de curto prazo do agente.

Ele deve informar com precisão:

* em qual etapa do projeto estamos;
* o que já foi concluído;
* o que está parcialmente concluído;
* o que ainda falta;
* quais arquivos foram modificados;
* quais migrations foram executadas;
* quais testes foram executados;
* quais testes falharam;
* quais problemas foram encontrados;
* quais decisões foram tomadas;
* qual deve ser EXATAMENTE a próxima ação.

O arquivo deve permitir que outra IA, sem memória da sessão anterior, continue o trabalho.

---

# 2. REGRA DE INICIALIZAÇÃO

ANTES de escrever ou alterar código:

1. localize a raiz do projeto;
2. verifique o estado atual do repositório;
3. procure:

`/docs/AI_HANDOFF.md`

Se existir:

LEIA-O INTEGRALMENTE ANTES DE CONTINUAR.

Se não existir:

CRIE-O antes de começar o desenvolvimento.

Depois leia, quando existentes:

`/docs/PROJECT_STATE.md`

`/docs/ARCHITECTURE.md`

`/docs/BUSINESS_RULES.md`

`/docs/DATABASE.md`

`/docs/DESIGN_SYSTEM.md`

`/docs/DECISIONS.md`

`/docs/CHANGELOG.md`

Também leia o prompt da etapa atualmente em execução.

---

# 3. NÃO CONFIE CEGAMENTE NO HANDOFF

O `AI_HANDOFF.md` ajuda a recuperar contexto, mas o código existente continua sendo a evidência técnica real.

Ao retomar uma sessão:

compare o conteúdo do AI_HANDOFF com:

* arquivos existentes;
* migrations;
* banco;
* testes;
* `git status`;
* `git diff`, quando disponível;
* estrutura atual do projeto.

Se houver divergência:

1. não invente qual estado é correto;
2. investigue o repositório;
3. use o estado real do código como referência técnica;
4. use BUSINESS_RULES/ARCHITECTURE como referência de regras;
5. corrija o AI_HANDOFF.

---

# 4. HIERARQUIA DE AUTORIDADE

Quando houver conflito, utilize esta prioridade:

1. instrução explícita atual do usuário;
2. prompt da etapa atual;
3. PROMPT MESTRE;
4. BUSINESS_RULES.md;
5. ARCHITECTURE.md;
6. DECISIONS.md;
7. demais documentos técnicos;
8. AI_HANDOFF.md.

O AI_HANDOFF registra ESTADO.

Ele não pode sobrescrever regras oficiais do projeto.

---

# 5. ATUALIZAÇÃO CONTÍNUA

NÃO espere atingir o limite da sessão para atualizar o AI_HANDOFF.

Atualize-o sempre que concluir uma unidade significativa de trabalho.

Exemplos:

* migration concluída;
* tabela criada;
* endpoint concluído;
* tela concluída;
* serviço concluído;
* grupo de testes concluído;
* bug importante corrigido;
* arquitetura alterada;
* decisão relevante tomada;
* dependência adicionada;
* integração concluída.

O objetivo é nunca haver uma diferença muito grande entre:

estado real do código

e

estado descrito no AI_HANDOFF.

---

# 6. QUANDO PERCEBER QUE A SESSÃO ESTÁ TERMINANDO

Se perceber qualquer risco de:

* limite de contexto;
* limite de tokens;
* limite de execução;
* limite de ferramentas;
* timeout;
* interrupção da sessão;
* necessidade de continuar em outra conversa;

INTERROMPA a criação de novas funcionalidades.

Priorize imediatamente:

1. salvar alterações válidas;
2. verificar se algum arquivo ficou parcialmente escrito;
3. executar testes relevantes, quando possível;
4. registrar erros;
5. atualizar `/docs/AI_HANDOFF.md`;
6. definir a próxima ação exata.

Não inicie uma grande nova alteração se houver risco de não conseguir documentá-la.

---

# 7. SE A INTERRUPÇÃO ACONTECER NO MEIO DE UMA IMPLEMENTAÇÃO

Nunca escreva no AI_HANDOFF que uma funcionalidade está concluída se não estiver.

Utilize explicitamente:

`PARCIAL`

ou:

`INCOMPLETO`

ou:

`BLOQUEADO`

Exemplo:

Status:

PARCIAL

Arquivos:

`backend/app/contracts/service.py`

Situação:

Método `create_contract()` implementado, porém a validação de estoque ainda não foi adicionada.

Próxima ação:

Abrir `backend/app/contracts/service.py` e implementar a validação de disponibilidade antes da criação dos ContractItems.

Isso é muito melhor do que simplesmente escrever:

“Continuar contratos.”

---

# 8. PRÓXIMA AÇÃO DEVE SER EXATA

Sempre deixar uma instrução de retomada extremamente objetiva.

RUIM:

“Continuar desenvolvimento.”

RUIM:

“Terminar backend.”

BOM:

“Implementar `PriceService.get_effective_price()` em `backend/app/pricing/service.py`, utilizando Decimal e selecionando a tabela ativa para product_id + rental_period + effective_date.”

MELHOR AINDA:

“Abra `backend/app/pricing/service.py`. O método `get_effective_price()` ainda contém TODO. Implemente seleção da tabela ativa por product_id, rental_period e effective_date; em seguida execute `pytest tests/pricing -q`.”

---

# 9. FORMATO OBRIGATÓRIO DO AI_HANDOFF.md

Utilize a seguinte estrutura:

# LocaControl — AI Handoff

## Identificação

Projeto: LocaControl

Etapa atual:

Exemplo:
ETAPA 3 — Clientes, Produtos, Equipamentos, Estoque e Preços

Status da etapa:

* NÃO INICIADA
* EM ANDAMENTO
* PARCIAL
* BLOQUEADA
* CONCLUÍDA

Última atualização:

Data/hora.

Branch atual:

Se Git estiver disponível.

Commit atual:

Se aplicável.

IMPORTANTE:

Não criar commits apenas para preencher este campo.

---

## Objetivo atual

Descrição curta do objetivo da etapa atual.

---

## Estado geral desta etapa

Exemplo:

* [x] Model Customer
* [x] Migration Customer
* [x] Repository Customer
* [x] API GET Customer
* [x] API POST Customer
* [ ] API PUT Customer
* [ ] API DELETE/disable Customer
* [ ] Frontend Customer
* [ ] Testes frontend

---

## Concluído nesta sessão

Lista objetiva.

Utilizar caminhos, classes e endpoints quando possível.

Exemplo:

* criado `backend/app/customers/models.py`;
* criado `CustomerService`;
* criada migration `20260912_01_create_customers`;
* criado `POST /api/customers`;
* criados 12 testes do módulo Customer.

---

## Trabalho parcialmente concluído

Para cada item parcial informar:

### Item

Status:

PARCIAL

Arquivos envolvidos:

Lista.

O que funciona:

Descrição.

O que ainda falta:

Descrição.

---

## Próximas tarefas

Manter em ordem de execução.

1.
2.
3.
4.

Não utilizar tarefas genéricas.

---

## PRÓXIMA AÇÃO EXATA

Este é o campo MAIS IMPORTANTE do documento.

Informar precisamente:

* arquivo a abrir;
* função/classe/tela;
* alteração necessária;
* comando/teste posterior.

Exemplo:

Abra:

`backend/app/customers/routes.py`

Implemente:

`PUT /customers/{customer_id}`

Depois execute:

`pytest tests/customers/test_update_customer.py -q`

---

## Arquivos criados nesta sessão

Lista completa dos arquivos relevantes criados.

---

## Arquivos alterados nesta sessão

Lista completa dos arquivos relevantes alterados.

---

## Banco de dados e migrations

Informar:

* migrations criadas;
* migrations executadas;
* migrations pendentes;
* estado esperado do banco.

Nunca afirmar que migration foi executada se não tiver sido executada.

---

## Dependências adicionadas

Backend:

Frontend:

Outras:

Informar motivo de dependências não óbvias.

---

## Testes executados

Para cada comando:

### Comando

`comando`

Resultado:

PASSOU / FALHOU

Resumo:

Exemplo:

47 passed, 0 failed.

---

## Testes ainda necessários

Lista.

---

## Erros conhecidos

Registrar:

* erro;
* arquivo;
* causa conhecida;
* tentativa realizada;
* situação atual.

Nunca esconder erro apenas porque há uma solução provável.

---

## Tentativas que NÃO funcionaram

Registrar abordagens relevantes que já foram tentadas.

Isso evita que o próximo agente repita a mesma abordagem.

Exemplo:

“Não utilizar X porque causou Y.”

---

## Decisões tomadas

Somente decisões tomadas durante o trabalho atual que ainda sejam importantes.

Decisões permanentes também devem ser registradas em:

`DECISIONS.md`

---

## Não refazer

Liste funcionalidades já concluídas e verificadas que não devem ser reimplementadas sem motivo.

---

## Dados temporários / mocks

Informar qualquer:

* mock;
* fixture;
* usuário de desenvolvimento;
* banco temporário;
* dado de demonstração.

Nunca fazer o próximo agente confundir mock com funcionalidade definitiva.

---

## Credenciais e segredos

NUNCA colocar:

* senha real;
* token;
* API key;
* certificado;
* segredo.

Somente informar:

“Variável X necessária no .env.”

---

## Critérios de aceite restantes

Lista do que ainda falta para considerar a etapa concluída.

---

## Estado para retomada

Uma síntese curta de 5 a 15 bullets destinada ao próximo agente.

Ela deve ser suficiente para que ele entenda rapidamente a situação.

---

# 10. NÃO TRANSFORMAR O HANDOFF EM LOG INFINITO

O arquivo deve mostrar principalmente o ESTADO ATUAL.

Não deixe o documento crescer indefinidamente.

Quando uma informação antiga deixar de ser útil:

resuma-a.

O histórico permanente pertence a:

`CHANGELOG.md`

O estado geral permanente pertence a:

`PROJECT_STATE.md`

O `AI_HANDOFF.md` é o checkpoint operacional.

---

# 11. HISTÓRICO CURTO DE SESSÕES

No final do arquivo poderá existir:

## Últimas sessões

Manter no máximo aproximadamente 5 registros resumidos.

Exemplo:

### Sessão 2026-09-12 A

Implementado Customer model/API.

### Sessão 2026-09-12 B

Implementado Customer frontend.

Remova/resuma sessões mais antigas quando não forem mais necessárias.

---

# 12. NÃO REFAZER CONTEXTO DESNECESSARIAMENTE

Ao iniciar uma nova sessão:

NÃO reanalise o projeto inteiro desde o zero se:

* AI_HANDOFF estiver atualizado;
* documentação estiver consistente;
* repositório confirmar o estado descrito.

Faça apenas a verificação necessária e continue.

Isso existe justamente para economizar contexto e capacidade da IA.

---

# 13. NÃO REPETIR TRABALHO CONCLUÍDO

Antes de implementar algo marcado como pendente:

verifique se a implementação já existe.

Uma sessão anterior pode ter terminado antes de atualizar completamente o Handoff.

Não recrie arquivos ou funcionalidades apenas porque uma checklist antiga indica pendência.

---

# 14. CHECKPOINT ANTES DE ALTERAÇÕES GRANDES

Antes de:

* migration complexa;
* refatoração ampla;
* alteração de arquitetura;
* mudança de banco;
* mudança significativa de dependência;

garanta que o AI_HANDOFF esteja atualizado.

Depois da alteração, atualize novamente.

---

# 15. DOCUMENTAÇÃO OFICIAL CONTINUA OBRIGATÓRIA

O uso do AI_HANDOFF NÃO substitui:

`PROJECT_STATE.md`

`CHANGELOG.md`

`DECISIONS.md`

`DATABASE.md`

etc.

Ao concluir um marco permanente, atualize a documentação correspondente.

Exemplo:

Uma nova decisão arquitetural deve entrar em:

`DECISIONS.md`

e não existir somente no AI_HANDOFF.

---

# 16. QUANDO A ETAPA FOR CONCLUÍDA

Quando TODOS os critérios da etapa forem atendidos:

1. execute os testes;
2. verifique migrations;
3. verifique frontend/backend;
4. atualize documentação;
5. marque a etapa como CONCLUÍDA no AI_HANDOFF;
6. atualize PROJECT_STATE;
7. atualize CHANGELOG;
8. registre a próxima etapa como NÃO INICIADA.

Depois:

PARE.

Não inicie automaticamente a próxima etapa.

Aguarde autorização do usuário.

---

# 17. PROIBIÇÕES

Nunca:

* apagar AI_HANDOFF sem recriá-lo;
* substituir informação válida por suposições;
* marcar testes como executados se não foram;
* dizer que funcionalidade está pronta porque “parece correta”;
* esconder código quebrado;
* perder registro de migration pendente;
* apagar TODOs importantes sem resolver;
* inventar commit;
* inventar arquivo;
* inventar resultado de teste;
* armazenar credenciais no arquivo;
* avançar automaticamente para a próxima etapa.

---

# 18. OBJETIVO FINAL DESTE PROTOCOLO

Se a sessão for interrompida AGORA, outra IA deverá conseguir:

1. abrir `/docs/AI_HANDOFF.md`;
2. entender a situação;
3. confirmar rapidamente o estado do repositório;
4. localizar o ponto exato onde o agente anterior parou;
5. executar a próxima ação;
6. continuar sem reconstruir todo o contexto desde o começo.

Se isso não for possível, o AI_HANDOFF está incompleto.

Este protocolo é obrigatório durante todo o desenvolvimento do LocaControl.
