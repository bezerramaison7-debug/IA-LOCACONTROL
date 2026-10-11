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
Checkpoint de 08/10: etapas 0–3 concluídas; etapa 4 parcial; 5–12 não iniciadas. Fontes de cadastros/importação inspecionados em 11/10; banco e testes não reexecutados nesta sessão documental.
Fora do escopo confirmado: multiempresa, planos de assinatura, cobrança do próprio SaaS e implantação pública automática. Local/LAN é a arquitetura inicial. Preparação web segue [PUBLICATION_ROADMAP.md](PUBLICATION_ROADMAP.md).

## 4. Catálogo de requisitos e aceite
Estados: E = implementação existente, com evidências históricas; P = parcial; F = futuro. E não significa nova homologação nesta sessão.

| ID | Requisito | Estado | Dependência | Critério de aceite |
| --- | --- | --- | --- | --- |
| RF-ID-001 | Identidade, sessão, RBAC e auditoria | E | Etapa 2 | API rejeita acesso indevido; protege último administrador; não expõe segredos |
| RF-CAD-001 | Clientes PF/PJ e endereços | E | Identidade | Documento normalizado único; edição detecta conflito; desativação preserva referências |
| RF-PRO-001 | Produtos por quantidade ou unidade física | E | Cadastros | Código único e distinção produto/equipamento |
| RF-EQP-001 | Equipamentos identificados e estados | E | Produtos | Identificadores únicos aplicáveis; baixa de reservado/locado bloqueada |
| RF-EST-001 | Seis saldos e movimentos de estoque | E | Produtos/equipamentos | Sem saldo negativo; operação repetida não duplica movimento; auditoria atômica |
| RF-PRE-001 | Preços por período e vigência | E | Produtos | Valores exatos e revisões históricas preservadas |
| RF-IMP-001 | Upload, análise, mapeamento e DRY RUN | P | Cadastros | Excel real conciliado; prévia sem gravação comercial; confirmação revalidada |
| RF-IMP-002 | Migração de histórico de contratos/renovações | F | Etapas 6/7 e Excel real | Códigos/vínculos preservados; nenhuma informação descartada silenciosamente |
| RF-ORC-001 | Orçamentos com itens, preços e descontos | F | Preços e regras de cálculo | Cálculo exato, snapshots, numeração, estados, PDF, aprovação e duplicação |
| RF-CON-001 | Contrato direto ou de orçamento | F | Orçamentos/modelo real | Numeração sem colisão; snapshots e documento versionado |
| RF-RET-001 | Retirada e vínculo físico | F | Contratos/estoque | Apenas quantidade disponível; equipamento não fica em duas locações incompatíveis |
| RF-REN-001 | Renovação total/parcial numerada | F | Contrato/retirada | Próximo sufixo único; origem preservada; escolha de preço registrada |
| RF-DEV-001 | Devolução parcial/total | F | Retirada | Não excede pendente; registra condição; atualiza estoque e mantém saldo restante |
| RF-MAN-001 | Encaminhamento e retorno de manutenção | F | Equipamentos/estoque | Transições e histórico coerentes com condição da devolução |
| RF-REL-001 | Dashboard, filtros e exportações reais | F | Dados comerciais | Indicadores reconciliáveis; receita contratada distinta de pagamento recebido |
| RF-POR-001 | Portal com dados próprios | F | Cliente/contratos | Consultas por ID e downloads isolados; solicitação não cria renovação definitiva |
| RF-FIS-001 | Faturamento e integração fiscal | F | Regras contábeis/provedor | Estados e retornos rastreáveis; sandbox real homologado antes de produção |
| RF-OPS-001 | Backup, restore e atualização | F | Banco/documentos/importações | Restauração isolada recupera conjunto completo; atualização preserva conta/dados |
| RF-REL-002 | Release 1.0 e guias | F | Todos os critérios obrigatórios | Fluxo integral, segurança e recuperação comprovados |

## 5. Regras comerciais
- Dinheiro exato: Decimal e centavos; quantidades em milésimos no banco atual.
- Períodos: diária, semanal, quinzenal e mensal. Duração, arredondamento, frações e cobrança precisam de decisão antes da etapa 5.
- Produto não é equipamento físico. Estados de estoque: disponível, reservado, locado, manutenção, indisponível, baixado.
- Orçamento não reserva definitivamente ao adicionar item. Alteração de preço exige autorização.
- Contrato usa ID interno separado de número comercial; renovação mantém raiz e sequência (9193, 9193.1).
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
Excel real via interface; modelo contratual; regras de duração/cobrança; estado de cancelamento do orçamento; transições e limiar de vencimento; regras contábeis/provedor/sandbox; metas operacionais e destino de publicação.
Registrar decisões permanentes em DECISIONS e regras em BUSINESS_RULES.

## 10. Governança e rastreabilidade
PRD define necessidades; APP_FLOW descreve jornadas; DESIGN_BRIEF orienta experiência; TRD define solução; BACKEND_SCHEMA detalha contratos técnicos; DEVELOPMENT_PLAN organiza entrega.
Mudanças devem atualizar requisitos, aceite, plano e documentos afetados. PROJECT_STATE e AI_HANDOFF registram estado; CHANGELOG registra histórico.
