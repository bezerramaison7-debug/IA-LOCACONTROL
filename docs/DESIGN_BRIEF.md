# LocaControl — Briefing de design

Versão documental 1.0 — 2026-10-11. Responsáveis: design de produto, UX, acessibilidade e frontend.
Direção para evolução da interface existente. Tokens oficiais: [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) e frontend/src/styles.css.

## 1. Contexto e objetivos
Sistema utilizado durante muitas horas por equipe comercial, operacional e financeira. Favorecer leitura de dados, preenchimento rápido, identificação de pendências e prevenção de erros de estoque/dinheiro.
Preservar identidade e componentes existentes. Não redesenhar a base apenas pela introdução deste briefing.

## 2. Público e ambiente
Funcionários lidam com tabelas, códigos comerciais, equipamentos e documentos. Portal atende clientes com tarefas restritas.
Windows/navegador, desktop e telas estreitas. Familiaridade digital e dispositivo operacional preferido ainda precisam ser validados com usuários reais.
Viewports de revisão: 1366×768, Full HD e mobile; incluir os tamanhos dos testes existentes.

## 3. Princípios
Hierarquia clara; densidade confortável; ações previsíveis; feedback compreensível; baixo esforço repetitivo.
Texto/status nunca dependem apenas de cor. Não esconder efeitos financeiros/operacionais atrás de rótulos genéricos.
Confirmar ações destrutivas e restauração; informar consequências concretas.

## 4. Direção visual
Visual administrativo sóbrio, pouco ruído, espaços consistentes, bordas suaves, sombras principalmente em overlays.
Inter quando disponível, fallback system-ui/Segoe UI. Dados e texto principal com 14px ou mais.
Não usar preto puro no tema escuro nem saturação excessiva.

| Papel | Claro | Escuro |
| --- | --- | --- |
| Fundo | #F6F8FB | #0B1120 |
| Superfície | #FFFFFF | #111827 |
| Texto | #172033 | #E5E7EB |
| Primária | #2563EB | #60A5FA |

Tabela apenas orientativa; tokens completos e contraste de controles vêm de DESIGN_SYSTEM. Não copiar cores avulsas para novos componentes.

## 5. Temas
Claro, Escuro e Sistema; padrão Sistema. Reutilizar ThemeProvider e prevenção de flash inicial.
Validar campos, tabelas, erros, popovers e documentos de interface nos dois temas.
Preferência visual não interfere em autorização ou dados.

## 6. Estrutura
Sidebar recolhível em desktop e drawer em telas estreitas. Topbar com contexto/breadcrumbs e busca de páginas.
Conteúdo: título → contexto/resumo → filtros → tabela/formulário → ações.
Manter rolagem de tabelas dentro do componente quando necessária; evitar overflow global.

## 7. Padrões de interação
| Componente | Diretriz |
| --- | --- |
| Tabela | Busca, filtros, paginação, ações nomeadas, vazio/carregando/erro; ordenação quando aplicável |
| Formulário | Label explícito, ajuda próxima, obrigatório claro, erro por campo e resumo útil |
| Valores | Formatação pt-BR; edição conserva precisão; valores exatos trafegam como strings |
| Datas | Exibir contexto de período; não confundir data comercial e instante UTC |
| Modal | Foco inicial, teclado, retorno do foco e ação principal inequívoca |
| Status | Texto + ícone + cor; significado consistente entre módulos |
| Conflito | Mostrar necessidade de recarregar/revisar, sem sobrescrita silenciosa |
| Operação longa | Progresso verdadeiro quando disponível; impedir duplo envio indevido |

## 8. Estados obrigatórios
Carregando, vazio inicial, vazio filtrado, erro recuperável, sucesso, salvando, sem permissão e sessão expirada.
Estados específicos: prévia sem persistência, importação parcial, dados sem destino, saldo insuficiente, preço ausente e documento pendente.
Mocks/previews devem ser identificados enquanto existirem; produção comercial não usa dados fictícios.

## 9. Jornadas prioritárias
| Jornada | Informação essencial |
| --- | --- |
| Importação | Original/aba/módulo, mapeamento, válidos/erros/avisos e efeitos da confirmação |
| Orçamento | Cliente, itens, período, preço de tabela/negociado, desconto, total e validade |
| Contrato | Número/renovações, resumo, itens, datas, valores, documentos e timeline |
| Retirada/devolução | Quantidade pendente, unidade física, condição e destino de estoque |
| Portal | Apenas contexto do próprio cliente e estado de solicitação |
| Backup/restore | Conjunto, data, verificação e consequência da restauração |

## 10. Linguagem
Usar termos da locadora e mensagens acionáveis. Exemplo: “A quantidade devolvida supera a quantidade pendente.”
Não apresentar código HTTP como explicação principal. Não colocar detalhes de arquitetura no fluxo do operador.
Confirmar vocabulário e modelo documental com usuário.

## 11. Acessibilidade
Alvo WCAG AA: contraste, foco visível, teclado, ordem de leitura, nomes acessíveis e mensagens associadas.
Reutilizar Radix; testar dialogs/drawers, tabelas, filtros e feedback.
Axe ajuda na verificação automática; revisão manual de teclado/leitura permanece necessária. Não afirmar certificação completa por ausência de alertas.

## 12. Entregáveis e aceite
Entregar telas integradas ao backend e componentes reutilizados; wireframes para decisões ainda abertas, quando úteis.
Revisar temas, estados, viewports e teclado. Conferir fluxo real com usuário para homologação.
Documentar ajustes de tokens em DESIGN_SYSTEM e impactos em testes visuais.
Não gerar artefatos Figma ou imagens sem necessidade desta tarefa.

## 13. Questões abertas
Densidade compacta futura; dispositivo da equipe operacional; vocabulário comercial; template real; feedback de usuários; regras de vencimento.
Registrar decisões antes de transformar preferências provisórias em padrão.
