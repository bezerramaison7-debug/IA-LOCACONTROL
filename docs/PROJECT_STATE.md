# LocaControl — Estado do projeto

Atualização: 2026-10-08 (America/Sao_Paulo).

Etapa 3: **CONCLUÍDA**, incluindo migrations locais e preservação da conta.
Etapa atual: **4 — Importador do Excel legado (PARCIAL: fluxo implementado, homologação real pendente)**.
Etapas 5–12: NÃO INICIADAS e sem autorização nesta execução.

## Entregas verificadas

- Etapas 0–2: fundação, interface responsiva, temas, identidade, permissões e auditoria.
- Etapa 3: clientes com endereços; produtos; equipamentos; seis saldos e movimentos; preços por período/vigência com histórico.
- Frontend comercial real em Masters.tsx, Stock.tsx e Prices.tsx, com busca/paginação, filtros, edição, conflitos, estados e permissões.
- Precisão: centavos e milésimos inteiros no banco, Decimal nos serviços e strings decimais na API.
- Estoque não negativo, deduplicação de solicitações, baixa definitiva e bloqueio de baixa de reservado/locado.
- Documentos PF/PJ: formato, normalização e unicidade; não declarar consulta externa ou verificação de dígitos implementadas.
- Excel: o usuário faz upload pela interface. Nenhuma busca por caminho local.
- Upload .xlsx/.xlsm, análise dinâmica de abas, amostra, fórmulas, mesclas, tipos/formatação de origem e valores salvos.
- Mapeamento por aba/módulo para clientes, produtos, equipamentos, entradas de estoque e preços.
- DRY RUN sem persistência comercial/auditoria/origens; confirmação com nova validação e digest da prévia.
- Linhas problemáticas reportadas individualmente; linhas válidas importadas na mesma operação.
- ImportBatch, checksum SHA-256, original preservado, origem por arquivo/aba/linha, relatório JSON e histórico.
- Nova conversão do mesmo original para outra aba ou módulo; origem já importada é ignorada.
- Permissões imports.read/write, inicialmente administrador; escrita também exige permissão do módulo de destino.

## Limites e aceite restante da Etapa 4

O Excel real não foi fornecido: o fluxo permite que o cliente o envie dentro do sistema. Não foi presumido layout definitivo. Homologar o arquivo real após upload, conferir cabeçalhos, fórmulas, códigos, referências, dados históricos e totais com o usuário.

Contratos e renovações dependem das Etapas 6/7 e não são convertidos para entidades comerciais ainda inexistentes. Abas/colunas sem destino ficam explicitamente pendentes no relatório e preservadas no original. Portanto não declarar conversão integral do histórico da empresa concluída.

Uma aba/módulo por operação. Produtos antes de equipamentos/estoque/preços. Não sobrescrever registros existentes: conflitos exigem revisão. Estoque inicial exige produto ainda sem movimentos; ajustes posteriores são manuais no módulo Estoque. Células mescladas não propagam valores automaticamente. Fórmula sem resultado salvo bloqueia a linha; valor salvo gera aviso de possível desatualização. Macros/fórmulas/referências externas não são executadas. .xls binário exige salvar como .xlsx. Limites: 10 MB, ZIP expandido 30 MB, 2.000 entradas ZIP, 10.000 linhas de dados/aba, 200 colunas e 200.000 células.

## Banco configurado

Estado após upgrade validado: SQLite 0004_imports, 5 perfis, 18 permissões e 1 usuário; identidade e hash preservados. Integridade ok e zero violações de FK. Tabelas comerciais/importação vazias.
Backup consistente criado: data/backups/pre-imports-20261008-214138.db; integrity_check ok.
Migrations 0003_masters e 0004_imports testadas em bancos temporários e APLICADAS ao banco local; Alembic check sem drift.
Nenhum fixture comercial ou usuário de teste é inserido na base real. Não executar bootstrap: há conta existente.

## Verificação desta execução

- Backend completo: 66 passed.
- Importador após nova conversão do original: 10 passed.
- Frontend: 29 passed.
- Check oficial: Ruff, formato, ESLint, Prettier e build PASSARAM.
- E2E comercial/autenticação anterior: 8 cenários PASSARAM, quatro tamanhos.
- Regressão visual: 16 cenários PASSARAM.
- E2E incluindo upload: 12 cenários PASSARAM (4 identidade, 4 comerciais, 4 importação), sem violações Axe detectadas nos estados testados. Ajustes visuais finais verificados separadamente nos quatro tamanhos.
- Smoke: PASSOU após build final, HTML/API/health/proxy em ambiente temporário.
- Falhas corrigidas: TypeScript de tipos comerciais, teste antigo de API inexistente, fixture de limite de colunas e seletor E2E exato do CPF/CNPJ.
- Uma rodada smoke coincidiu com limpeza de dist pelo build e recebeu 404; repetição após build PASSOU. Não executar smoke/E2E em paralelo com build.

Git: master sem commits, fontes untracked. Nenhum commit inventado ou criado nesta execução.
Avisos não bloqueantes: depreciação Starlette/AnyIO e anotações de tree shaking do Zod.

## Próximas etapas oficiais

| Etapa | Estado | Entrega |
| --- | --- | --- |
| 4 | PARCIAL | Homologar Excel real via upload e resolver dados pendentes sem perda |
| 5 | NÃO INICIADA | Orçamentos, cálculos, snapshots, estados e PDF |
| 6 | NÃO INICIADA | Contratos, numeração, templates e documentos históricos |
| 7 | NÃO INICIADA | Retiradas, renovações, devoluções e estoque integrado |
| 8 | NÃO INICIADA | Dashboard real, relatórios e exportações |
| 9 | NÃO INICIADA | Portal com isolamento por cliente |
| 10 | NÃO INICIADA | Faturamento e integração fiscal em sandbox |
| 11 | NÃO INICIADA | Backup, restauração, logs, instalação e atualização |
| 12 | NÃO INICIADA | QA, guias e release |

Dashboard, orçamentos e contratos ainda contêm prévias identificadas. Upload possui atalho inicial no dashboard para usuários autorizados. Guia em EXCEL_IMPORT.md. Continuidade em AI_HANDOFF.md e prompt em CONTINUE_PROMPT.md.

## Publicação web

Roteiro em PUBLICATION_ROADMAP.md. Arquitetura atual local/LAN, sem deploy público, multiempresa ou cobrança de assinatura. Definir infraestrutura, público, banco de produção, domínio/HTTPS, persistência, backup/restore, observabilidade e homologação antes de publicar.


## Documentação estruturante — 2026-10-11
Criados PRD, TRD, APP_FLOW, DESIGN_BRIEF e BACKEND_SCHEMA. DEVELOPMENT_PLAN é o sexto documento (plano de implementação), complementado com tarefas rastreáveis e responsabilidades.
CONTINUE_PROMPT agora referencia os seis, descreve especialistas e continuidade 4–12 quando acionado pelo usuário.
Estado funcional acima permanece o checkpoint de 08/10; banco, testes e servidor não revalidados nesta sessão. Nenhuma etapa funcional iniciada.