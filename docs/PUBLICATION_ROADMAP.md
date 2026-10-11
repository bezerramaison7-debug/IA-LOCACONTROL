# LocaControl — Roteiro até a publicação web

Data de referência: 2026-10-11.
Estado verificado: Etapas 0–3 concluídas; Etapa 4 PARCIAL (Excel real não enviado; conversão do histórico de contratos não implementada); Etapas 5–11 com backend e telas implementados e testados (commit `82e0845`); Etapa 12 com a entrega técnica feita (auditoria do backend corrigida, teste de aceite, E2E e guias) e aceite do usuário pendente; versão 1.0 não declarada. Nada foi publicado e nenhuma decisão de publicação (P1–P4) foi tomada.

Este documento organiza trabalho pendente, dependências e critérios de saída. Não substitui docs/DEVELOPMENT_PLAN.md nem autoriza execução das próximas etapas. Não contém estimativas de prazo ou percentuais sem base.

## 1. Ponto de partida real

| Área | Estado | Próximo passo |
| --- | --- | --- |
| Fundação/interface/identidade | Etapas 0–2 entregues e regressão aprovada | Preservar a base |
| Cadastros/estoque/preços | Etapa 3 concluída; cinco telas reais e invariantes testados | Não reimplementar |
| Banco local | 0010_backups, 5 perfis, 32 permissões, 1 usuário preservado, sem dados comerciais | Backup pelo sistema já inclui originais, documentos e fiscal |
| Importador | Upload, análise dinâmica, mapeamento, DRY RUN, confirmação, origem e relatório implementados | Homologar o arquivo real enviado pela interface |
| Contratos e renovações legados | Entidades de destino existem; conversão não implementada | Definir o mapeamento quando o Excel real for enviado |
| Orçamentos, contratos e operação | Backend e telas entregues em 11/10 | Validar com o usuário e substituir o modelo de contrato provisório |
| Dashboard, relatórios, portal, fiscal, backups | Backend e telas entregues em 11/10 (`82e0845`) | Validar com o usuário |
| Fiscal | Somente provedor de simulação | Regras da contabilidade, provedor e credenciais de sandbox |
| Código | Histórico Git local na branch `dev/etapas-4-12` (baseline `2b3d1d2` em `master`); nenhum remoto configurado | Definir remoto privado quando autorizado |
| Hospedagem | Sem deploy público | Preparar infraestrutura, persistência, HTTPS e operação |

## 2. Marco concluído e aceite restante

Etapa 3 concluída: CRUD, estados, histórico, precisão, concorrência, autorização, auditoria, frontend e migration local validados. Check oficial, 66 testes backend, 29 frontend, 16 visuais e 12 cenários de API/navegador aprovados. Backup anterior à migração preservado; banco íntegro sem drift.

Etapa 4 PARCIAL: mecanismo utilizável e testado com fixtures, sem pressupor formato do arquivo real. Usuário envia Excel em Gestão → Importações; não solicitar caminho. Homologar amostra e totais, resolver mapeamentos/conflitos e encaminhar contratos/renovações nas etapas correspondentes. Documentar exceções reais após upload; não declarar todo histórico convertido. Guia em EXCEL_IMPORT.md.

O acesso 127.0.0.1 é local e não constitui publicação pública.

Atualização de 11/10/2026: backends e telas das Etapas 5–11 implementados, com 141 testes de backend, 63 de frontend e 36 cenários de E2E real aprovados sobre o commit `82e0845`. Isso é evidência de testes automatizados com dados temporários, não homologação com dados da locadora nem aceite do usuário.

## 3. Etapas funcionais restantes do plano oficial

| Ordem | Etapa | O que falta implementar | Dependência / critério de saída |
| --- | --- | --- | --- |
| 4 | Importação do Excel legado — PARCIAL | Homologar Excel real via upload; conciliar totais e campos sem destino; implementar a conversão do histórico de contratos/renovações (IMP-04B) | Depende do arquivo real enviado pelo usuário |
| 5 | Orçamentos — backend e tela entregues | Validação pelo usuário | Regras confirmadas em 11/10 (ADR-014) |
| 6 | Contratos e documentos — backend e tela entregues; modelo PROVISÓRIO | Substituir o modelo provisório pelo real; decidir upload do assinado e DOCX | Modelo real de contrato e dados da locadora para o cabeçalho |
| 7 | Ciclo da locação — backend e tela entregues | Validação pelo usuário; decidir reserva na confirmação e registro de manutenção | Decisões de negócio (ADR-016) |
| 8 | Dashboard e relatórios — backend e telas entregues | Validação pelo usuário | Dados reais para conferir os indicadores |
| 9 | Portal do cliente — backend e telas entregues | Validação pelo usuário | Uso remoto depende de publicação |
| 10 | Faturamento/fiscal — backend e tela em simulação | Adapter de provedor real; homologação em sandbox | Regras da contabilidade, provedor escolhido e credenciais de teste |
| 11 | Operação e recuperação — backend, tela de backups e scripts entregues | Ensaio de restauração com dados reais; primeira execução de `update.ps1`; adaptar à infraestrutura web escolhida | Dados reais |
| 12 | QA e release 1.0 — entrega técnica feita (auditoria do backend corrigida, teste de aceite, E2E real e guias) | Aceite do usuário no navegador; auditoria não cobriu frontend, importação e identidade; teste de upgrade (`update.ps1`) e de restauração com dados reais | Usuário e insumos externos; não acrescentar funcionalidades |

Entregáveis oficiais de release: RELEASE_NOTES_1.0.md, INSTALLATION.md, USER_GUIDE.md e ADMIN_GUIDE.md — escritos em 11/10, ainda não commitados.

A entrega completa segue o plano oficial. Antecipar uma versão menor ou adiar importador/portal/fiscal exige definição explícita de escopo e aceite; não está aprovado neste roteiro.

## 4. Decisões necessárias para publicação pública

O plano original descreve local/LAN e reserva arquitetura remota para depois. Para atender uma publicação pública, estas decisões precisam ser tomadas e registradas antes de provisionar produção:

| Decisão | Definição necessária | Impacto |
| --- | --- | --- |
| Público | Equipe interna, clientes, ou ambos | Rede, portal, segurança e suporte |
| Empresas | Uma locadora nesta instalação ou várias empresas independentes | Multiempresa exige tenant_id, isolamento de dados/arquivos, permissões e testes; não existe hoje |
| Infraestrutura | Hospedagem que execute Python/API, sirva frontend e preserve dados | Publicar somente arquivos React não atende este projeto |
| Banco | SQLite em instância única/persistente ou migração validada para PostgreSQL | Não basta alterar URL; rever BEGIN IMMEDIATE, tipos, driver, locking, migrations e testes |
| Arquivos | Local persistente ou armazenamento próprio para contratos, anexos e fiscal | Permissões, downloads autenticados, backup e retenção |
| Acesso | Domínio/subdomínio e origem única ou origens separadas | DNS, HTTPS, cookies, CORS e CSRF |
| Capacidade | Usuários simultâneos, volume de registros/documentos e disponibilidade | Dimensionamento, custos e testes de carga |
| Recuperação | Perda de dados tolerável e tempo de restauração esperado | Frequência de backup, cópia externa e procedimento de recuperação |
| Versão inicial | Escopo oficial completo ou versão reduzida explicitamente autorizada | Critérios de aceite e cronograma real |

Multiempresa, planos de assinatura e cobrança recorrente do próprio SaaS não constam como funcionalidades entregues. Se esse for o objetivo comercial, precisam de escopo adicional; o nome da pasta não comprova uma arquitetura SaaS.

## 5. Frente adicional de publicação — fora da numeração oficial

### P1. Preparar produção

- [ ] Definir e documentar as decisões da seção 4.
- [ ] Criar histórico Git dos fontes revisados e rotina de entrega; definir remoto privado quando autorizado.
- [ ] Manter .env, credenciais, SQLite, backups e documentos privados fora de Git.
- [ ] Criar configuração reproduzível de deploy (container ou serviço do host, conforme escolha).
- [ ] Executar build do frontend e processo backend supervisionado, com reinício e configuração explícitos.
- [ ] Configurar banco/volumes/armazenamento persistentes e caminhos por ambiente.
- [ ] Preparar migrations como passo controlado de release, com backup prévio.
- [ ] Criar verificação automatizada de lint, testes, build e integridade de migrations.
- [ ] Definir rollback de código compatível com schema; evitar downgrade destrutivo de banco como solução padrão.

Critério: instalação reproduzível e dados preservados após reinício/atualização.

### P2. Configurar acesso web e segurança

- [ ] Configurar domínio/DNS, HTTPS e renovação de certificados.
- [ ] Configurar proxy reverso/encaminhamento para API e frontend.
- [ ] Configurar origens exatas, cookies Secure e política de sessão.
- [ ] Rever uso de IP remoto atrás do proxy; confiar somente no proxy autorizado para evitar contornar limites de tentativas.
- [ ] Rever exposição de documentação técnica, logs e mensagens de erro.
- [ ] Validar recuperação administrativa remota controlada e gestão de contas.
- [ ] Restringir acesso a banco, backups e arquivos; downloads devem passar pela autorização.
- [ ] Definir tratamento dos dados pessoais, acessos, retenção e canal de atendimento.
- [ ] Testar permissões contra acessos diretos por ID, incluindo documentos e portal.

Critério: login e fluxos protegidos funcionando no domínio HTTPS, sem acesso cruzado entre clientes/empresas.

### P3. Homologar e ensaiar recuperação

- [ ] Criar homologação isolada da produção, sem credenciais compartilhadas.
- [ ] Validar implantação em banco vazio e atualização de uma cópia controlada.
- [ ] Executar fluxo completo, concorrência e carga compatíveis com o uso esperado.
- [ ] Testar temas, responsividade, teclado, acessibilidade e downloads.
- [ ] Configurar monitoramento, logs sem segredos e alertas de indisponibilidade/backup.
- [ ] Fazer backup externo e ensaiar restauração completa de banco + documentos.
- [ ] Ensaiar rollback de aplicação e conferir compatibilidade de schema.
- [ ] Registrar falhas restantes e aceite da operação.

Critério: evidência de funcionamento e recuperação, com problemas críticos resolvidos.

### P4. Publicar e acompanhar

- [ ] Definir versão e janela de publicação.
- [ ] Obter aceite final da versão e autorização de publicação.
- [ ] Fazer backup, executar migration controlada e publicar os artefatos revisados.
- [ ] Criar/verificar administrador por procedimento seguro e validar acesso no domínio final.
- [ ] Executar smoke em produção sem modificar dados comerciais indevidamente.
- [ ] Confirmar monitoramento, backup, suporte e plano de retorno.
- [ ] Entregar guias de usuário/administração/instalação e notas de release.
- [ ] Acompanhar os primeiros usos e registrar incidentes/correções.

Critério: URL pública funcional e protegida, dados persistentes, recuperação comprovada e aceite registrado.

## 6. Insumos ainda necessários

- Excel legado enviado pelo cliente dentro do sistema para homologação da Etapa 4; não exigir caminho local.
- Modelo de contrato real da locadora (hoje há um provisório identificado no PDF).
- Dados da locadora para os documentos (`LOCACONTROL_COMPANY_*`; hoje o cabeçalho mostra "LocaControl").
- Duração dos períodos, arredondamento e cobrança: RESOLVIDO em 11/10 (ADR-014).
- Regras fiscais da contabilidade, provedor escolhido e credenciais de sandbox (hoje só existe o provedor de simulação).
- Definições de público, empresa única/multiempresa, infraestrutura, domínio, capacidade e recuperação antes da implantação pública.

Credenciais nunca devem ser coladas em documentos ou código. Custos e prazos dependem dessas escolhas; não foram estimados nem contratados.

## 7. Sequência e critérios de conclusão

Sequência funcional: concluir 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12.

A arquitetura da publicação pode ser decidida antes para evitar retrabalho; a liberação de produção depende do aceite da versão. P1–P3 podem avançar quando o escopo estiver autorizado e os módulos necessários forem estáveis. P4 ocorre após aceite e autorização final.

Fluxo de aceite obrigatório:
cliente → produto/preço/estoque → orçamento → aprovação → contrato → retirada → renovação → devolução parcial → nova renovação → devolução total → encerramento.

Ao final, validar saldos, snapshots, documentos, histórico, auditoria, permissões e restauração. Build aprovado isoladamente não significa sistema pronto para uso real.

## 8. Próxima ação imediata

Seguir o campo PRÓXIMA AÇÃO EXATA de docs/AI_HANDOFF.md: não há implementação desbloqueada; os próximos passos dependem do usuário (Excel real, modelo de contrato, dados da locadora, definições fiscais, aceite no navegador, decisões de publicação e de mesclagem da branch). Atualização: 2026-10-11.

Publicação: nenhuma ação de P1–P4 foi iniciada e este roteiro não autoriza deploy. As decisões da seção 4 continuam todas em aberto.

Não recriar o backend existente e não executar bootstrap: já existe um usuário local.

