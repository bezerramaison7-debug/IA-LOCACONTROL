# LocaControl — Fluxo do aplicativo

Versão documental 1.0 — 2026-10-11. Responsáveis: negócio, UX e frontend.
Convenções: EXISTENTE = encontrado nos fontes/checkpoint; PARCIAL = homologação pendente; PROPOSTO = etapa futura. Fluxos não comprovam entrega.

## 1. Acesso e mapa de navegação
Login → consulta de sessão/permissões → troca obrigatória de senha, se exigida → destino permitido.
Sem sessão: login; sessão expirada: remover conteúdo privado; sem permissão: mensagem e navegação permitida.
Interno: Dashboard; Comercial (Clientes, Orçamentos, Contratos, Renovações); Operação (Produtos, Equipamentos, Estoque, Retiradas, Devoluções, Manutenção); Financeiro (Faturamento/Fiscal); Gestão (Relatórios, Importações, Usuários, Auditoria, Configurações).
Portal futuro: Dashboard, Meus contratos/equipamentos, Orçamentos, Renovações, Documentos e Meu cadastro.
Navegação visível não concede autorização; API é autoridade.

## 2. Contrato de documentação de cada fluxo
Campos obrigatórios: ID, requisito PRD, ator, gatilho, pré-condições, passos, alternativas, permissão, efeito persistido, resultado e evidência de aceite.
Nomes de permissões futuras serão definidos na implementação, sem tratá-los como grants existentes.

## 3. FL-ID — Identidade (EXISTENTE)
Ator: qualquer conta. Gatilho: acesso protegido.
Pré-condição: conta ativa e ambiente configurado.
Passos: login → sessão → verificação de troca de senha → área autorizada → logout.
Alternativas: credencial inválida, limite de tentativas, conta desativada, sessão revogada.
Efeito: sessão e eventos de segurança; nunca token em localStorage.
Aceite RF-ID-001: rotas diretas continuam protegidas; último administrador preservado.

## 4. FL-CAD — Preparar operação (EXISTENTE)
Ator: funcionário autorizado.
Cliente PF/PJ → endereços → produto e tipo de controle → equipamento quando individual → estoque → preço/período/vigência.
Produtos precedem equipamento/estoque/preço. Revisão usa versão.
Alternativas: documento/código duplicado, preço inválido, conflito de edição, saldo insuficiente e baixa bloqueada.
Efeito: cadastros, revisões/movimentos e auditoria conforme operação.
Aceite RF-CAD/PRO/EQP/EST/PRE: histórico íntegro e nenhuma baixa indevida.

## 5. FL-IMP — Excel (PARCIAL)
Ator: administrador ou usuário com permissões necessárias.
Pré-condição: usuário seleciona Excel na interface Gestão → Importações; não pedir caminho local.
Upload → análise → escolher aba/módulo → mapear → DRY RUN → revisar erros/avisos/conflitos → confirmar → relatório.
Uma aba/módulo por operação. Nova conversão pode reaproveitar original.
Prévia não grava registros comerciais, auditoria comercial ou origens; lote/original do upload já existem.
Alternativas: limites excedidos, fórmula sem cache, coluna sem destino, duplicação de origem, conflito, digest desatualizado.
Conteúdo inválido por linha é reportado; falha técnica inesperada reverte confirmação.
Efeito: válidos importados e rastreáveis; conflitos não sobrescritos.
Aceite RF-IMP: conferir amostra/totais reais e registrar histórico dependente das etapas 6/7.

## 6. FL-ORC — Orçamento (PROPOSTO, etapa 5)
Ator: Comercial autorizado. Cliente/produtos/preços disponíveis.
Selecionar cliente → itens/quantidades/período → preço automático → negociação autorizada → revisar total/validade → salvar rascunho → PDF/enviar → aprovar/rejeitar → converter em contrato.
Adicionar item apenas consulta disponibilidade, não reserva definitiva.
Alternativas: preço inexistente, desconto inválido, expiração, cancelamento e conflito.
Efeito: snapshots e histórico de transição.
Aceite RF-ORC: cálculo exato e histórico não alterado por preço novo.

## 7. FL-CON — Contrato (PROPOSTO, etapa 6)
Ator: Comercial autorizado. Modelo e condições aprovados.
Criar direto ou converter orçamento aprovado → revisar cliente/itens/datas → atribuir número → gerar documento → preparar retirada.
Conversão repetida deve impedir contratos duplicados indevidos.
Alternativas: número legado conflitante, datas inválidas, template incompleto.
Efeito: contrato/itens/snapshots/documentos versionados e auditoria.
Aceite RF-CON: documento coerente; versão assinada preservada.

## 8. FL-RET — Retirada (PROPOSTO, etapa 7)
Ator: Operação. Contrato liberado conforme transição aprovada.
Abrir contrato → selecionar itens/quantidades → associar unidades físicas → conferir disponibilidade → confirmar → comprovante/timeline.
Alternativas: outra operação consumiu saldo, equipamento indisponível, solicitação repetida.
Efeito atômico: retirada, movimentos, situação contratual e auditoria.
Aceite RF-RET: sem saldo negativo ou unidade em locações incompatíveis.

## 9. FL-REN — Renovação (PROPOSTO, etapa 7)
Ator: Comercial; solicitação pode vir do Cliente.
Selecionar contrato → selecionar itens pendentes → datas/período → escolher preços anteriores/atuais/negociados → revisar → confirmar próximo número → documento.
Alternativas: itens já devolvidos, quantidade excedida, colisão concorrente.
Efeito: vínculo estruturado à raiz e nova versão comercial; anterior preservado.
Aceite RF-REN: 9193 → 9193.1 → 9193.2 sem sobrescrever ou duplicar obrigações.

## 10. FL-DEV — Devolução e manutenção (PROPOSTO, etapa 7)
Ator: Operação. Existem quantidades retiradas pendentes.
Abrir contrato → informar data/itens/unidades/quantidades → registrar condição/observação → destino disponível/manutenção → conferir → confirmar.
Parcial: saldo restante segue pendente. Total: encerramento segundo regras aprovadas.
Alternativas: excesso de quantidade, equipamento incompatível, evento repetido.
Efeito: devolução, movimentos, timeline e auditoria na mesma transação.
Manutenção: registrar intervenção e liberar unidade por transição autorizada.
Aceite RF-DEV/MAN: saldos, condição e histórico reconciliados.

## 11. FL-REL — Indicadores e relatórios (PROPOSTO, etapa 8)
Ator: usuário autorizado. Filtrar → consultar dados reais → abrir origem → exportar Excel/PDF.
Alternativas: vazio, consulta extensa, erro de exportação.
Efeito: leitura e arquivo protegido; não confundir receita contratada com recebimento.
Aceite RF-REL: totais reconciliáveis e filtros mantidos na exportação.

## 12. FL-POR — Portal (PROPOSTO, etapa 9)
Ator: Cliente vinculado. Login → contratos/itens próprios → documento → solicitar renovação → acompanhar decisão.
Funcionário revisa solicitação antes de efetivar FL-REN.
Alternativas: acesso por ID de outro cliente ou download alheio é negado no backend.
Aceite RF-POR: isolamento testado em listas, detalhes e arquivos.

## 13. FL-FIS — Faturamento/fiscal (PROPOSTO, etapa 10)
Ator: Financeiro autorizado. Regras/provedor configurados.
Selecionar cliente/contrato/período/valor → validar → enviar sandbox → acompanhar → obter documento ou corrigir erro.
Cancelamento conforme regra/provedor. Repetição não deve gerar emissão duplicada.
Aceite RF-FIS: retornos rastreáveis e sandbox identificado; produção exige autorização específica.

## 14. FL-OPS — Recuperação (PROPOSTO, etapa 11)
Ator: Administrador. Configurar agenda/retenção → executar backup → verificar → exportar.
Restore: selecionar conjunto → validar → confirmação forte → cópia prévia → restauração assistida → verificar conta/dados/arquivos.
Aceite RF-OPS: ensaio isolado completo, sem restauração silenciosa.

## 15. Estados e decisões abertas
| Entidade | Estados conhecidos/previstos | Condição |
| --- | --- | --- |
| Equipamento/estoque | Disponível, reservado, locado, manutenção, indisponível, baixado | Existentes; ações comerciais integradas futuras |
| Orçamento | Rascunho, enviado, aprovado, rejeitado, expirado, convertido | Previstos; conciliar cancelamento |
| Contrato | Rascunho, aguardando retirada, ativo, vencendo, vencido, encerrado, cancelado | Previstos; definir matriz de transição e vencimento |
| Fiscal | Pendente, processando, emitido, erro, cancelado | Previstos; conciliação externa necessária |

Vencendo/vencido podem ser classificação por data ou estado persistido: decidir antes da modelagem. Não assumir transições apenas porque estados estão listados.

## 16. Aceite integral
Executar FL-CAD → FL-ORC → FL-CON → FL-RET → FL-REN → FL-DEV parcial → FL-REN → FL-DEV total → encerramento.
Conferir quantidade, dinheiro, documentos, auditoria e permissões; testar alternativas e FL-OPS.
