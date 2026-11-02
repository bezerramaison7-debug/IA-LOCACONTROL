# LocaControl — Fluxo do aplicativo

Versão documental 1.1 — 2026-10-11. Responsáveis: negócio, UX e frontend.
Convenções: EXISTENTE = API e tela nos fontes, com testes; PARCIAL = falta a parte indicada (tela, insumo externo ou homologação); PROPOSTO = não implementado. Em 11/10 (commit `82e0845`) todos os fluxos abaixo têm tela. Nenhum fluxo foi homologado com dados reais da locadora nem validado pelo usuário no navegador.

## 1. Acesso e mapa de navegação
Login → consulta de sessão/permissões → troca obrigatória de senha, se exigida → destino permitido.
Sem sessão: login; sessão expirada: remover conteúdo privado; sem permissão: mensagem e navegação permitida.
Interno: Dashboard; Comercial (Clientes, Orçamentos, Contratos, Renovações); Operação (Produtos, Equipamentos, Estoque, Retiradas, Devoluções, Manutenção); Financeiro (Faturamento/Fiscal); Gestão (Relatórios, Importações, Usuários, Perfis e permissões, Auditoria, Backups, Meu perfil, Configurações).
Rotas com tela em 11/10: Dashboard (dados reais, título "Visão geral"), Clientes, Orçamentos, Contratos, Renovações, Produtos, Equipamentos, Estoque, Preços, Retiradas, Devoluções, Manutenção, Faturamento e fiscal (`/faturamento`; `/fiscal` redireciona), Relatórios, Importações, Usuários, Perfis, Auditoria, Backups, Meu perfil e Configurações. Nenhum item de menu aponta para página provisória.
Portal (`/portal/*`, API e tela): Início, Meus contratos, Meus equipamentos, Orçamentos, Renovações, Documentos e Meu cadastro.
Navegação visível não concede autorização; API é autoridade.

## 2. Contrato de documentação de cada fluxo
Campos obrigatórios: ID, requisito PRD, ator, gatilho, pré-condições, passos, alternativas, permissão, efeito persistido, resultado e evidência de aceite.
Permissões reais de cada fluxo estão em SECURITY e BACKEND_SCHEMA.

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
Aceite RF-IMP: conferir amostra/totais reais. O histórico de contratos/renovações ainda não tem conversão: as entidades existem, o mapeamento depende do arquivo real.

## 6. FL-ORC — Orçamento (EXISTENTE: API e tela)
Ator: Comercial autorizado. Cliente/produtos/preços disponíveis.
Selecionar cliente → itens/quantidades/período → preço automático → negociação autorizada → revisar total/validade → salvar rascunho → PDF/enviar → aprovar/rejeitar → converter em contrato.
Adicionar item apenas consulta disponibilidade, não reserva definitiva.
Estados: rascunho → enviado → aprovado/rejeitado; cancelado com motivo; expirado é o enviado com validade vencida; reabrir devolve o enviado a rascunho; convertido ao virar contrato.
Alternativas: preço inexistente, negociação sem permissão, expiração, cancelamento e conflito de versão.
Efeito: snapshots e histórico de transição.
Aceite RF-ORC: cálculo exato e histórico não alterado por preço novo.

## 7. FL-CON — Contrato (PARCIAL: API e tela existentes; modelo de contrato provisório)
Ator: Comercial autorizado (contracts.write). Modelo em uso é PROVISÓRIO e identificado no PDF até o usuário fornecer o real.
Criar direto ou converter orçamento aprovado → rascunho com número já atribuído → revisar cliente/itens/datas → prévia em PDF → confirmar (aguardando retirada) → gerar documento versionado → marcar como assinado.
Conversão repetida é recusada: cada orçamento gera um único contrato.
Cancelar: só rascunho ou aguardando retirada, com motivo. Confirmar não reserva estoque.
Alternativas: orçamento não aprovado ou já convertido, conflito de versão, modelo com campo desconhecido, nova versão após documento assinado sem motivo.
Não existe: DOCX, upload do documento assinado, importação de número legado.
Efeito: contrato/itens/snapshots/documentos versionados e auditoria.
Aceite RF-CON: documento coerente; versão assinada preservada.

## 8. FL-RET — Retirada (EXISTENTE: API e tela)
Ator: Operação (operations.write). Contrato aguardando retirada ou ativo; retirada pode ser parcial.
Abrir contrato → selecionar itens/quantidades → associar unidades físicas → conferir disponibilidade → confirmar → comprovante/timeline.
Alternativas: outra operação consumiu saldo, equipamento indisponível, solicitação repetida.
Efeito atômico: retirada, movimentos, situação contratual e auditoria.
Aceite RF-RET: sem saldo negativo ou unidade em locações incompatíveis.

## 9. FL-REN — Renovação (EXISTENTE: API e tela)
Ator: Comercial (contracts.write); solicitação pode vir do Cliente pelo portal e aparece em Renovações para decisão. Somente contrato ativo; a renovação nasce ativa e não movimenta estoque.
Selecionar contrato → selecionar itens pendentes → datas/período → escolher preços anteriores/atuais/negociados → revisar → confirmar próximo número → documento.
Alternativas: itens já devolvidos, quantidade excedida, colisão concorrente.
Efeito: vínculo estruturado à raiz e nova versão comercial; anterior preservado e encerrado automaticamente quando nada resta nele.
Aceite RF-REN: 9193 → 9193.1 → 9193.2 sem sobrescrever ou duplicar obrigações.

## 10. FL-DEV — Devolução e manutenção (EXISTENTE: API e tela; manutenção PARCIAL)
Ator: Operação (operations.write). Existem quantidades com o cliente em contrato ativo.
Abrir contrato → informar data/itens/unidades/quantidades → registrar condição/observação → destino disponível/manutenção → conferir → confirmar.
Condição BOM → disponível (ou manutenção); AVARIADO → manutenção obrigatória.
Parcial: saldo restante segue pendente. Total: contrato encerra automaticamente quando nada resta com o cliente nem a retirar; encerramento manual com motivo quando o restante nunca foi retirado.
Alternativas: excesso de quantidade, equipamento incompatível, evento repetido.
Efeito: devolução, movimentos, timeline e auditoria na mesma transação.
Manutenção: a unidade/quantidade vai para o estado Manutenção e é liberada pelos movimentos de estoque; não há registro próprio de intervenção.
Aceite RF-DEV/MAN: saldos, condição e histórico reconciliados.

## 11. FL-REL — Indicadores e relatórios (EXISTENTE: API e tela)
Ator: usuário autorizado. Filtrar → consultar dados reais → abrir origem → exportar Excel/PDF.
Alternativas: vazio, consulta extensa, erro de exportação.
Efeito: leitura e arquivo protegido; não confundir receita contratada com recebimento.
Aceite RF-REL: totais reconciliáveis e filtros mantidos na exportação.

## 12. FL-POR — Portal (EXISTENTE: API e tela; acesso remoto depende de publicação)
Ator: Cliente com conta vinculada a um cliente por um administrador ("Vincular cliente" em Usuários). Login → contratos/itens próprios → documento → solicitar renovação → acompanhar decisão.
Funcionário aprova ou recusa; aprovar só registra a decisão, e a renovação é feita depois em FL-REN.
Alternativas: acesso por ID de outro cliente ou download alheio responde 404; conta sem vínculo responde 403; segunda solicitação pendente para o mesmo contrato é recusada.
Aceite RF-POR: isolamento testado em listas, detalhes e arquivos.

## 13. FL-FIS — Faturamento/fiscal (PARCIAL: API e tela EXISTENTES somente em simulação)
Ator: Financeiro (fiscal.write). Regras tributárias e provedor NÃO definidos; só o provedor de simulação existe e seus documentos não têm valor fiscal.
Selecionar cliente/contrato/período/valor → validar → enviar ao provedor (simulação) → acompanhar → obter PDF/XML ou corrigir erro e reenviar.
Cancelamento conforme regra/provedor. Repetição não deve gerar emissão duplicada.
Aceite RF-FIS: retornos rastreáveis e sandbox identificado; produção exige autorização específica.

## 14. FL-OPS — Recuperação (PARCIAL: API, tela de backups e scripts EXISTENTES; falta ensaio com dados reais)
Ator: Administrador (backups.manage). Configurar ativação/horário/pasta/retenção → executar backup → verificar → baixar.
Restore: selecionar conjunto → verificação → digitar RESTAURAR <nome> e a própria senha → cópia prévia automática → restauração → entrar novamente e verificar conta/dados/arquivos.
Uso diário: atalhos "Iniciar LocaControl" e "Parar LocaControl" na raiz do projeto.
Aceite RF-OPS: ensaio isolado completo, sem restauração silenciosa.

## 15. Estados e decisões abertas
| Entidade | Estados conhecidos/previstos | Condição |
| --- | --- | --- |
| Equipamento/estoque | Disponível, reservado, locado, manutenção, indisponível, baixado | Existentes; ações comerciais integradas futuras |
| Orçamento | Rascunho, enviado, aprovado, rejeitado, cancelado, convertido; expirado derivado da validade | Existentes |
| Contrato | Rascunho, aguardando retirada, ativo, encerrado, cancelado; vencendo e vencido derivados da data de devolução | Existentes |
| Documento de contrato | Gerado, assinado, substituído | Existentes |
| Solicitação de renovação | Pendente, aprovada, recusada, cancelada | Existentes |
| Fiscal | Pendente, processando, emitido, erro, cancelado | Existentes só em simulação; conciliação externa necessária |

Decidido em 11/10: vencendo/vencido são classificação por data, não estado gravado (ADR-015). Em aberto: reserva de estoque na confirmação do contrato, hoje inexistente.

## 16. Aceite integral
Executar FL-CAD → FL-ORC → FL-CON → FL-RET → FL-REN → FL-DEV parcial → FL-REN → FL-DEV total → encerramento.
Conferir quantidade, dinheiro, documentos, auditoria e permissões; testar alternativas e FL-OPS.
Esse percurso está coberto no backend por `test_operations.py` (ciclo completo com duas renovações e devolução parcial/total) e por `test_release_journey.py` (cenário oficial da versão 1.0 pela API). Pela interface, o E2E real (`scripts/e2e-auth.py`) cobre os módulos em nove roteiros separados (acesso, cadastros, importações, orçamentos, contratos e operação, relatórios, portal, fiscal e backups), 36 cenários aprovados em 11/10; o percurso por um usuário humano, com dados reais, ainda não foi feito.
