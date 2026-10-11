# LocaControl — Prompt de continuação até a conclusão

Atualizado em 2026-10-11. Copie o bloco abaixo para a conversa de execução.
Criar/atualizar este arquivo não inicia desenvolvimento nem aplica migrations. A autorização de continuidade passa a valer quando o usuário enviar este prompt como instrução de execução.

---

Continue o LocaControl em C:\Users\maiso\Documents\ChatGPT\SAAS LOCACAO até a conclusão da versão 1.0 oficial.

## 1. Autorização e limites
Nesta execução, autorizo as etapas 4–12. Ao cumprir e documentar o aceite de uma etapa, avance para a próxima liberada. Esta instrução substitui a limitação histórica à etapa 4 e a parada entre etapas, preservando requisitos e critérios oficiais.
Não contrate serviços, assuma custos, publique na internet, emita fiscal real, envie mensagens a terceiros ou apague dados reais por inferência.
Multiempresa, assinatura e cobrança do próprio SaaS exigem escopo explícito. Prepare publicação, mas obtenha autorização final sobre versão/destino/custos concretos.
Persistir no trabalho autorizado; não entregar apenas plano quando houver implementação possível.

## 2. Leitura obrigatória e recuperação
Localize raiz, instruções AGENTS.md, git status e diff. Leia integralmente AI_HANDOFF e AI_CONTINUITY_PROTOCOL.
Leia os seis documentos estruturantes:
1. docs/PRD.md — necessidades, requisitos RF/RNF e aceite;
2. docs/TRD.md — arquitetura, requisitos RT, segurança e verificação;
3. docs/APP_FLOW.md — jornadas, estados, exceções e efeitos;
4. docs/DESIGN_BRIEF.md — direção visual, interação e acessibilidade;
5. docs/BACKEND_SCHEMA.md — entidades/APIs existentes e modelo proposto;
6. docs/DEVELOPMENT_PLAN.md — plano oficial e plano operacional por especialistas.
Leia também PROJECT_STATE, ARCHITECTURE, BUSINESS_RULES, DATABASE, DESIGN_SYSTEM, SECURITY, DECISIONS, CHANGELOG, EXCEL_IMPORT e PUBLICATION_ROADMAP.
Compare documentação com fontes, migrations, testes e banco mediante inspeção segura.
Checkpoint de 08/10: 0–3 concluídas; 4 parcial; 5–12 não iniciadas; banco 0004_imports com uma conta preservada. Isso é referência histórica, não verificação atual.
Não reinicie o projeto, recrie funcionalidade entregue, execute bootstrap ou invente commits.

## 3. Uso integrado dos seis documentos
Para cada entrega, vincule requisito PRD → fluxo APP_FLOW → padrão DESIGN_BRIEF/DESIGN_SYSTEM → requisito TRD → entidade/API BACKEND_SCHEMA → tarefa DEVELOPMENT_PLAN → teste/evidência.
PRD define o que/por quê; TRD define solução e restrições; APP_FLOW define sequência/alternativas; DESIGN_BRIEF define experiência; BACKEND_SCHEMA define dados/contratos; DEVELOPMENT_PLAN define responsáveis/dependências/aceite.
Distinga EXISTENTE, PARCIAL e PROPOSTO. Atualize documentos afetados junto com código, sem duplicar fontes de autoridade.
Regras detalhadas em BUSINESS_RULES, decisões permanentes em DECISIONS, estado em PROJECT_STATE e continuidade em AI_HANDOFF.
Em conflitos, a instrução explícita atual prevalece; investigue divergência técnica e registre correção.

## 4. Especialistas e coordenação
Este prompt autoriza subagentes quando disponíveis para trabalho independente. Caso indisponíveis, aplique os papéis sequencialmente. Não afirme revisão independente quando feita pelo autor.
- Coordenador/arquiteto: baseline, dependências, interfaces, integração e checkpoint.
- Negócio de locação: períodos, cobrança, estados, estoque, renovação/devolução e aceite comercial.
- Migração Excel: original, mapeamento, origem, conciliação e histórico.
- Backend Python/FastAPI: domínio, serviços, APIs, transações e auditoria.
- Dados/migrations: tipos exatos, constraints, concorrência e preservação de base.
- Frontend React/TypeScript: telas persistentes, formulários, API e permissões.
- UX/acessibilidade: tokens, temas, estados, responsividade, teclado e alvo WCAG AA.
- Documentos comerciais: templates, snapshots, PDFs e versões.
- Segurança: sessão, CSRF, RBAC, isolamento e downloads.
- Faturamento/fiscal: modelos, FiscalProvider, adapters e homologação de sandbox.
- Operação: backup/restore, Windows, atualização, logs e preparação web.
- QA: testes proporcionais, regressão, E2E, migrations e recuperação.
Coordenador define escopo/arquivos antes de delegar, evita edição concorrente incompatível, revisa resultados e valida integração.

## 5. Execução ordenada
Etapa 4: homologar Excel real enviado pelo usuário em Gestão → Importações. Não pedir caminho local nem upload nesta conversa. Analisar → mapear uma aba/módulo → DRY RUN → conciliar amostras/totais → confirmação. Preservar original/códigos/origem; não sobrescrever conflitos. Histórico de contratos/renovações aguarda 6/7. Sem Excel, manter aceite pendente e avançar tarefas independentes.
Etapa 5: orçamentos, cálculos, snapshots, numeração, negociação autorizada, estados, duplicação, PDF e preparação da conversão. Confirmar duração/arredondamento/cobrança e conciliar cancelamento antes de consolidar regras.
Etapa 6: contratos diretos/de orçamento, números, snapshots, estados, templates e documentos versionados. Obter modelo real; provisório permanece identificado. Retomar histórico importado.
Etapa 7: retirada/unidade física, estoque integrado, renovação numerada com preço explícito, devoluções parciais/totais, manutenção e encerramento. Testar concorrência e quantidades remanescentes.
Etapa 8: dashboard/relatórios/exportações reais. Remover mocks das capacidades entregues; receita contratada não é pagamento recebido.
Etapa 9: portal vinculado ao cliente, isolamento backend em listas/detalhes/downloads; solicitação de renovação requer aprovação interna.
Etapa 10: faturamento/FiscalProvider/adapters/estados/retornos. Confirmar regras contábeis e provedor; fake valida arquitetura, sandbox real valida integração. Sem credenciais, registrar homologação pendente e concluir trabalho independente. Não emitir em produção.
Etapa 11: backup completo de DB/originais/documentos, retenção/verificação, restore assistido com confirmação/cópia prévia, logs/health, inicialização Windows e atualização segura.
Etapa 12: auditoria e correções sem novas funcionalidades; fluxo integral, testes de upgrade/restore, guias INSTALLATION, USER_GUIDE, ADMIN_GUIDE e RELEASE_NOTES_1.0.
Preparação web: PUBLICATION_ROADMAP P1–P3 após decisões de infraestrutura/público/banco/arquivos/capacidade/recuperação. P4 somente com aceite/autorização final.

## 6. Invariantes
Decimal e inteiros escalados existentes; nunca float financeiro.
Produto separado de equipamento; impedir estoque negativo e operação duplicada.
Operação e auditoria atômicas. Permissão na API. Snapshots/revisões preservados.
Contrato usa ID interno, base_number/renewal_number e vínculo à raiz; 9193 → 9193.1 → 9193.2.
Não substituir documento assinado nem recalcular histórico com preço atual.
Dados de teste isolados; segredos fora de código/logs/documentação.

## 7. Verificação e continuidade
Conferir scripts/comandos reais. Executar checks e testes necessários conforme risco: regras, API, frontend, E2E, concorrência, segurança, migrations e restore.
Build → smoke/E2E em sequência; nunca limpar dist enquanto testes o utilizam.
Atualize AI_HANDOFF após unidade significativa; documentos permanentes em marcos. Registre somente comandos/resultados/migrations observados.
Pergunte quando decisão comercial, dado real ou ação externa exigir resposta; agrupe perguntas e continue tarefas independentes.
Registre bloqueio, impacto, trabalho liberado e condição de desbloqueio.
Antes de limite/interrupção, salve arquivos íntegros e próxima ação exata com arquivo/função/alteração/teste.

## 8. Conclusão
Validar: cliente → produto/preço/estoque → orçamento aprovado → contrato → retirada → renovação → devolução parcial → nova renovação → devolução total → encerramento.
Conferir dinheiro, saldos, documentos, snapshots, histórico, permissões, auditoria e recuperação.
Só declarar 1.0 concluída quando todos os critérios oficiais e homologações obrigatórias estiverem atendidos.
Sem insumo/aceite externo, informar entrega técnica e pendência exata; não mascarar como conclusão integral.
Relatório final: funcionalidades, arquivos relevantes, migrations criadas/aplicadas, testes/resultados, modo de execução, decisões, riscos/pendências e próxima ação.
Comece pela recuperação do contexto e retome o ponto real; avance no trabalho autorizado conforme dependências.

---
