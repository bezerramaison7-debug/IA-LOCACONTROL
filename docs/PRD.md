# LocaControl — PRD: requisitos do produto

Versão: 1.0 documental. Data: 2026-10-11 (America/Sao_Paulo).
Responsáveis: produto e especialista de negócio de locação.
Status: especificação baseada no plano oficial; não representa homologação da versão 1.0.

## 1. Visão e problema
Substituir o processo da locadora baseado em Excel por gestão integrada de clientes, equipamentos, estoque, preços, orçamentos, contratos, renovações, devoluções e documentos. Preservar dados e histórico, reduzir digitação repetida e tornar saldos e decisões comerciais rastreáveis.

## 2. Usuários
| Perfil | Necessidade principal |
| --- | --- |
| Administrador | Configurar acesso, acompanhar operação, auditar e recuperar dados |
| Comercial | Cadastrar clientes, negociar, orçar, contratar e renovar |
| Operação | Identificar equipamentos, retirar, devolver e controlar manutenção/estoque |
| Financeiro | Consultar valores e administrar faturamento/documentação fiscal |
| Cliente | Consultar seus dados/documentos e solicitar renovação |

Permissões efetivas são verificadas no backend. Necessidade de negócio não equivale a grant já implementado.

## 3. Escopo e baseline
Entrega oficial: etapas 0–12 de [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md).
Checkpoint de 11/10/2026: etapas 0–3 concluídas; etapa 4 parcial (Excel real não enviado); etapas 5–11 com backend e telas implementados e testados (141 testes de backend, 63 de frontend e 36 cenários de E2E real aprovados sobre o commit `82e0845`); etapa 12 com a entrega técnica feita (auditoria independente do backend corrigida, teste de aceite pela API, E2E pela interface e guias) e aceite do usuário pendente. A versão 1.0 não está declarada concluída. Nada foi homologado com dados reais da locadora nem validado pelo usuário no navegador.
Fora do escopo confirmado: multiempresa, planos de assinatura, cobrança do próprio SaaS e implantação pública automática. Local/LAN é a arquitetura inicial. Preparação web segue [PUBLICATION_ROADMAP.md](PUBLICATION_ROADMAP.md).

## 4. Catálogo de requisitos e aceite
Estados: E = implementado e coberto por testes automatizados; P = parcial (a coluna diz o que falta); F = futuro. E não significa homologação com dados reais nem aceite do usuário.

| ID | Requisito | Estado | Dependência | Critério de aceite |
| --- | --- | --- | --- | --- |
| RF-ID-001 | Identidade, sessão, RBAC e auditoria | E | Etapa 2 | API rejeita acesso indevido; protege último administrador; não expõe segredos |
| RF-CAD-001 | Clientes PF/PJ e endereços | E | Identidade | Documento normalizado único; edição detecta conflito; desativação preserva referências |
| RF-PRO-001 | Produtos por quantidade ou unidade física | E | Cadastros | Código único e distinção produto/equipamento |
| RF-EQP-001 | Equipamentos identificados e estados | E | Produtos | Identificadores únicos aplicáveis; baixa de reservado/locado bloqueada |
| RF-EST-001 | Seis saldos e movimentos de estoque | E | Produtos/equipamentos | Sem saldo negativo; operação repetida não duplica movimento; auditoria atômica |
| RF-PRE-001 | Preços por período e vigência | E | Produtos | Valores exatos e revisões históricas preservadas |
| RF-IMP-001 | Upload, análise, mapeamento e DRY RUN | P | Cadastros | Excel real conciliado; prévia sem gravação comercial; confirmação revalidada |
| RF-IMP-002 | Migração de histórico de contratos/renovações | F — entidades de destino existem; mapeamento não implementado | Excel real | Códigos/vínculos preservados; nenhuma informação descartada silenciosamente |
| RF-ORC-001 | Orçamentos com itens, preços e descontos | E — API e tela | Preços e regras de cálculo | Cálculo exato, snapshots, numeração, estados, PDF, aprovação e duplicação |
| RF-CON-001 | Contrato direto ou de orçamento | P — API e tela entregues; modelo de contrato é provisório, só PDF, sem upload do assinado | Modelo real do usuário | Numeração sem colisão; snapshots e documento versionado |
| RF-RET-001 | Retirada e vínculo físico | E — API e tela; sem reserva na confirmação | Contratos/estoque | Apenas quantidade disponível; equipamento não fica em duas locações incompatíveis |
| RF-REN-001 | Renovação total/parcial numerada | E — API e tela | Contrato/retirada | Próximo sufixo único; origem preservada; escolha de preço registrada |
| RF-DEV-001 | Devolução parcial/total | E — API e tela | Retirada | Não excede pendente; registra condição; atualiza estoque e mantém saldo restante |
| RF-MAN-001 | Encaminhamento e retorno de manutenção | P — devolução encaminha à manutenção e o retorno usa os movimentos de estoque; sem registro próprio de intervenção | Definição de escopo | Transições e histórico coerentes com condição da devolução |
| RF-REL-001 | Dashboard, filtros e exportações reais | E — API e telas (Dashboard real, Relatórios e resumo do cliente) | Contratos | Indicadores reconciliáveis; receita contratada distinta de pagamento recebido |
| RF-POR-001 | Portal com dados próprios | E — API e telas; isolamento testado; uso fora do computador da locadora depende de publicação | Vínculo conta–cliente | Consultas por ID e downloads isolados; solicitação não cria renovação definitiva |
| RF-FIS-001 | Faturamento e integração fiscal | P — API e tela com provedor de simulação; sem provedor real, sem regra tributária | Contabilidade, provedor e sandbox | Estados e retornos rastreáveis; sandbox real homologado antes de produção |
| RF-OPS-001 | Backup, restore e atualização | P — API, tela de backups e scripts Windows entregues e testados; falta ensaio de restauração com dados reais e `update.ps1` nunca foi executado | Dados reais | Restauração isolada recupera conjunto completo; atualização preserva conta/dados |
| RF-REL-002 | Release 1.0 e guias | P — guias escritos e verificação automatizada feita; falta o aceite do usuário e os insumos externos | Todos os critérios obrigatórios | Fluxo integral, segurança e recuperação comprovados |

## 5. Regras comerciais
- Dinheiro exato: Decimal e centavos; quantidades em milésimos no banco atual.
- Períodos: diária 1, semanal 7, quinzenal 15 e mensal 30 dias corridos. Valor do item = quantidade × preço do período × nº de períodos, sem fração; arredondamento por item (decisões de 11/10, ADR-014).
- Produto não é equipamento físico. Estados de estoque: disponível, reservado, locado, manutenção, indisponível, baixado.
- Orçamento não reserva definitivamente ao adicionar item. Alteração de preço exige autorização.
- Contrato usa ID interno separado de número comercial; renovação mantém raiz e sequência (9193, 9193.1). Próximo número = maior existente + 1, com inicial configurável. Vencendo/vencido são calculados pela data de devolução (antecedência padrão de 3 dias).
- Preços novos não alteram snapshots antigos.
- Devolução parcial mantém quantidades pendentes e histórico.
- Original Excel, códigos, origem, conflitos e campos sem destino são preservados.
Referência detalhada: [BUSINESS_RULES.md](BUSINESS_RULES.md).

## 6. Qualidade do produto
| ID | Objetivo | Evidência exigida |
| --- | --- | --- |
| RNF-SEG-001 | Autorização e confidencialidade | Testes por perfil, cliente e download |
| RNF-DAD-001 | Integridade e histórico | Constraints, transações, concorrência e snapshots testados |
| RNF-UX-001 | Uso prolongado e acessível | Temas, teclado, contraste e viewports; alvo WCAG AA |
| RNF-OPS-001 | Recuperação e continuidade | Ensaio de restore e atualização de cópia controlada |
| RNF-PER-001 | Resposta compatível com a operação | Definir volume/concorrência e metas antes de medir; não inventar SLA |

## 7. Jornada de aceite integral
Cliente → produto/preço/estoque → orçamento aprovado → contrato → retirada → renovação → devolução parcial → nova renovação → devolução total → encerramento.
Conferir saldo, cálculos, documentos, snapshots, permissões e auditoria. Depois comprovar recuperação.

## 8. Indicadores de sucesso
Medir divergências de estoque, erros de importação, tempo para emitir orçamento/contrato, tarefas concluídas sem retrabalho e sucesso de restauração. Baseline, metas, período e responsáveis ainda devem ser acordados; não existem números validados.

## 9. Decisões e insumos pendentes
Resolvidos em 11/10/2026: duração/cobrança, cancelamento do orçamento, transições de contrato e limiar de vencimento (ADR-014 a ADR-016).
Ainda pendentes: Excel real via interface; modelo contratual real (em uso um provisório); dados da locadora para o cabeçalho dos documentos; regras contábeis, provedor fiscal e credenciais de sandbox; metas operacionais; destino de publicação.
Registrar decisões permanentes em DECISIONS e regras em BUSINESS_RULES.

## 10. Governança e rastreabilidade
PRD define necessidades; APP_FLOW descreve jornadas; DESIGN_BRIEF orienta experiência; TRD define solução; BACKEND_SCHEMA detalha contratos técnicos; DEVELOPMENT_PLAN organiza entrega.
Mudanças devem atualizar requisitos, aceite, plano e documentos afetados. PROJECT_STATE e AI_HANDOFF registram estado; CHANGELOG registra histórico.
