# LocaControl — Notas da versão candidata 1.0 (entrega técnica das etapas 0–12)

Este documento descreve a **entrega técnica** das etapas 0 a 12 do LocaControl. **A versão 1.0 não está declarada concluída nem homologada.** O que foi construído está implementado e coberto por testes automatizados com dados de teste, mas a conclusão depende de cinco itens que só o usuário pode fornecer ou decidir:

1. **Importação com o Excel real.** O importador nunca recebeu a planilha da locadora; falta homologá-lo com o arquivo verdadeiro. A conversão do histórico de contratos e renovações da planilha **não está implementada**.
2. **Modelo real de contrato.** O modelo em uso é provisório, e todo PDF gerado com ele traz o aviso "MODELO PROVISÓRIO".
3. **Dados da locadora no `.env`.** Enquanto não forem preenchidos, os documentos saem com o nome "LocaControl" no cabeçalho.
4. **Regras fiscais, provedor e credenciais de teste.** Existe apenas a simulação, sem valor fiscal.
5. **Decisões de publicação na internet.** Nada foi publicado; o sistema roda no computador da locadora.

Data de referência: 11/10/2026. Branch `dev/etapas-4-12`. Nenhum dado comercial real foi lançado no banco local.

## 1. O que a versão entrega

| Módulo | Resumo |
| --- | --- |
| Acesso e segurança | Login com sessão revogável, troca obrigatória da senha temporária, cinco perfis (Administrador, Comercial, Operação, Financeiro, Cliente), permissões ajustáveis nos perfis internos, auditoria das ações |
| Cadastros | Clientes (PF/PJ, vários endereços), produtos (por quantidade ou por unidade identificada) e equipamentos, com desativação em vez de exclusão |
| Estoque | Saldos por situação (Disponível, Reservado, Locado, Manutenção, Indisponível, Baixado), movimentos com motivo e histórico, sem saldo negativo |
| Preços | Tabela por produto e período (diária, semanal, quinzenal, mensal), com vigência e histórico de versões |
| Importação do Excel | Envio pela tela, análise das abas, mapeamento de colunas, prévia sem gravação (DRY RUN), confirmação e relatório; clientes, produtos, equipamentos, preços e entradas de estoque |
| Orçamentos | Itens com preço de tabela e negociado, numeração `ORC-AAAA-NNNNNN`, enviar, aprovar, rejeitar, cancelar, reabrir, duplicar, validade com expiração, PDF e conversão única em contrato |
| Contratos | Diretos ou a partir de orçamento aprovado; número `N` e renovações `N.1`, `N.2`; próximo número configurável; confirmação, cancelamento e encerramento; filtros por origem, produto, equipamento, período e data |
| Documentos do contrato | Modelo com campos e blocos, PDF versionado e conferido por código de verificação, marcação de assinado, documento assinado nunca substituído |
| Operação | Retirada total ou parcial com escolha da unidade física; devolução total ou parcial com condição e destino; renovação total ou parcial com três opções de preço; encerramento automático; linha do tempo por cadeia de contratos |
| Manutenção | Lista do que está em manutenção e liberação para Disponível |
| Painel e relatórios | Indicadores calculados na hora, doze relatórios com filtros e exportação em Excel e PDF |
| Portal do cliente | Contratos, equipamentos, orçamentos, documentos e cadastro do próprio cliente; solicitação de renovação decidida pela locadora |
| Faturamento e fiscal | Registro e acompanhamento de documentos **somente em simulação**, sem valor fiscal |
| Backup e restauração | Conjunto `.zip` com banco e arquivos, verificação, backup diário opcional com retenção, download e restauração assistida com frase de confirmação e senha |
| Uso no Windows | Atalhos **Iniciar LocaControl.cmd** e **Parar LocaControl.cmd**, atualização que preserva `data\` e `.env` |

O uso de cada tela está em [USER_GUIDE.md](USER_GUIDE.md); a administração, em [ADMIN_GUIDE.md](ADMIN_GUIDE.md).

## 2. Regras e decisões

O registro completo está em [DECISIONS.md](DECISIONS.md) (ADR-014 a ADR-021) e em [BUSINESS_RULES.md](BUSINESS_RULES.md).

### Regras comerciais decididas pelo usuário em 11/10/2026

- Valor do item = quantidade × preço do período × número de períodos, sem fração de período.
- Períodos em dias corridos: diária 1, semanal 7, quinzenal 15, mensal 30. Devolução prevista = início + dias × número de períodos.
- Desconto somente como preço negociado por item; o sistema guarda o preço de tabela e o negociado.
- Cancelado (decisão da locadora, com motivo) é uma situação distinta de Rejeitado (recusa do cliente).
- Numeração de contratos: maior número existente + 1; o administrador pode definir o número inicial; sem configuração, começa em 1.
- "Vencendo" e "vencido" são calculados pela data de devolução, não gravados. Antecedência de "vencendo": 3 dias.
- Uso de um modelo de contrato provisório, identificado no documento, até o fornecimento do modelo real.

### Decisões técnicas do implementador (revisáveis)

- Arredondamento de cada item em centavos, meio centavo para cima; o total é a soma dos itens.
- "Expirado" não é gravado: é o orçamento enviado com validade vencida. A data comercial usa fuso fixo UTC−3.
- Um rascunho salvo mantém o preço de tabela registrado; reler a tabela é ação explícita.
- **A confirmação do contrato não reserva estoque**; a disponibilidade é conferida e baixada na retirada.
- A renovação nasce ativa, recebe o próximo sufixo da cadeia e não movimenta estoque.
- Devolução: bom estado vai para Disponível (ou Manutenção, se indicado); avariado vai obrigatoriamente para Manutenção.
- O ajuste manual de estoque não pode tirar de Locado o que está com cliente por contrato ativo.
- Documentos somente em PDF; "assinado" é uma marcação com autor e data.
- Relatórios calculados na consulta, sem tabela de totais. "Valor contratado" nunca é apresentado como valor recebido.
- Portal: uma conta vê exatamente um cliente; a aprovação de uma solicitação de renovação apenas registra a decisão.
- Fiscal desacoplado por provedor, com a simulação como único provedor existente. Nenhuma regra tributária foi definida.
- Backup em um único `.zip` com manifesto; restauração com frase exata e senha, cópia prévia e sem apagar arquivos.

## 3. Verificação

Resultados observados em 11/10/2026 sobre o código do commit `82e0845`. São verificações automatizadas com dados de teste: **nenhuma delas é homologação pelo usuário.**

| Verificação | Resultado |
| --- | --- |
| Testes do backend (`pytest backend/tests`) | 141 aprovados, 1 aviso (depreciação do Starlette/AnyIO, não bloqueante) |
| Lint do backend (`ruff check`) | Sem erros |
| Frontend: ESLint e Prettier (`format:check`) | Sem erros |
| Frontend: Vitest | 63 testes em 13 arquivos, todos aprovados |
| Frontend: build | Concluído, com aviso do Vite de arquivo principal acima de 500 kB |
| E2E real (`scripts/e2e-auth.py`, servidor e banco temporários) | 36 cenários aprovados: 9 roteiros (acesso, cadastros, importações, orçamentos, contratos, relatórios, portal, fiscal e backups) em 4 tamanhos de tela — 1366×768, 1920×1080 (Full HD), 820×1180 (tablet) e 390×844 (celular) —, com verificação de acessibilidade (Axe) e de rolagem horizontal nos temas claro e escuro conforme cada roteiro |
| Regressão visual (`npx playwright test`) | 16 aprovados |
| Smoke (`scripts/smoke.py`) | Aprovado |
| Teste de aceite pela API (`backend/tests/test_release_journey.py`) | Incluído nos 141: percorre o cenário oficial em 26 passos |
| Scripts do Windows | `launch.ps1` e `stop.ps1` exercitados em portas alternativas: subir, health, login recusado com 401, parar e PID inválido |

Ressalvas:

- Depois do E2E, duas frases de interface foram alteradas (telas de Perfis e de Importações). Lint, formatação, Vitest, build e smoke foram repetidos e passaram; **o E2E não foi repetido** depois dessa mudança de texto.
- Numa execução anterior, o roteiro de backups do E2E falhou uma vez (navegador fechado durante uma captura). A causa não foi identificada e a falha não se repetiu.
- `scripts\update.ps1` **não foi executado**.
- Nenhuma verificação foi feita com dados reais da locadora nem por um usuário humano percorrendo as telas. Não houve teste com leitor de tela; a verificação automática de acessibilidade não equivale a uma certificação.

Os testes automatizados usam bancos, pastas e planilhas temporários. Eles não comprovam nada sobre os dados reais da locadora, que ainda não existem no sistema.

## 4. Auditoria independente do backend

O backend passou por uma auditoria independente, que registrou 11 achados. Todos foram corrigidos no commit `b0d9ec4`. Entre as correções: a renovação recusa unidade física repetida; a verificação de backup exige manifesto completo, banco listado e ao menos um usuário; a restauração prepara os arquivos antes de tocar nos dados e informa a cópia de segurança se falhar; o portal não mostra motivos internos de cancelamento ou encerramento; repetir uma operação com a mesma chave e conteúdo diferente vira conflito; o modelo de contrato valida os blocos; a exportação não grava fórmulas; o backup manual do dia não suprime o automático.

**O que a auditoria não cobriu:** o frontend, a importação do Excel e as rotas de identidade (login, usuários, perfis). Essas partes têm testes próprios, mas não passaram por essa revisão independente.

## 5. Banco de dados e migrations

- Dez migrations, de `0001` a `0010`: fundação, identidade, cadastros, importações, orçamentos, contratos, relatórios, portal, fiscal e backups.
- O banco local foi atualizado até a `0010`, sempre com cópia prévia em `data\backups`.
- A atualização de estrutura é aplicada por **Iniciar LocaControl.cmd**, depois de copiar o banco para `data\backups\pre-upgrade-*.db`.
- O banco é SQLite em disco local. A troca para outro banco não foi validada.

## 6. Limites conhecidos

- **Sem reserva de estoque no contrato.** A confirmação não reserva; a disponibilidade é conferida na retirada.
- **Documento somente em PDF.** Não há geração em Word.
- **Sem envio do documento assinado digitalizado.** "Assinado" é uma marcação; a via física é arquivada fora do sistema.
- **Manutenção sem ordem de serviço.** Registra a ida e a volta do item, sem custo, descrição ou responsável pelo reparo.
- **O histórico de orçamentos e contratos mostra o número do usuário**, não o nome.
- **As listas de Retiradas e de Manutenção filtram no navegador.** Com muitos contratos ativos ou muitos produtos, essas telas ficam mais lentas e podem mostrar lista parcial.
- **A devolução por quantidade não divide bom e avariado na mesma operação.** São necessárias duas devoluções.
- **O download de backup carrega o arquivo na memória do navegador.** Conjuntos muito grandes devem ser copiados diretamente da pasta de backups.
- **Uso em rede exige HTTPS, que não foi homologado.** O atalho de início atende somente o próprio computador.
- **Uma empresa por instalação.** Não há multiempresa nem cobrança de assinatura.
- **Banco SQLite local.** Uso simultâneo intenso ou acesso pela internet exigem outra arquitetura.
- **Logs sem rotação.** Os arquivos em `data\logs` são sobrescritos a cada início.
- **Importação:** uma aba e um módulo por operação; `.xls` antigo não é aceito; o histórico de contratos e renovações da planilha não é convertido.
- **Fiscal:** apenas simulação; nenhum documento tem valor fiscal.
- **Sem controle de pagamentos.** Os valores exibidos são contratados, não recebidos.

## 7. Pendências e o que desbloqueia cada uma

| Pendência | Condição de desbloqueio |
| --- | --- |
| Homologação da importação | O usuário enviar o Excel real em **Gestão → Importações** e conferir a prévia com a planilha |
| Conversão do histórico de contratos e renovações | O Excel real, para definir o mapeamento; depois, implementação e teste dessa conversão |
| Modelo real de contrato | O usuário fornecer o texto; publicação em **Gestão → Configurações → Modelo de contrato** sem marcar "provisório" |
| Cabeçalho dos documentos | O usuário informar nome, CNPJ, endereço e contato da locadora para as linhas `LOCACONTROL_COMPANY_*` do `.env` |
| Emissão fiscal real | Regras definidas com a contabilidade, provedor escolhido e credenciais de teste; depois, implementação e homologação da integração |
| Acesso pela internet, inclusive do portal | Decisões de publicação (público, uma ou várias empresas, infraestrutura, banco, domínio) descritas em [PUBLICATION_ROADMAP.md](PUBLICATION_ROADMAP.md) |
| Uso por outros computadores da rede | Configuração e homologação de HTTPS na rede da locadora |
| Validação das telas pelo usuário | O usuário percorrer o fluxo completo com dados reais e apontar ajustes |
| Ensaio de restauração com dados reais | Existirem dados reais; restaurar um backup em um computador de teste |
| Declaração da versão 1.0 | Os itens acima resolvidos ou formalmente dispensados pelo usuário |

## 8. Como atualizar

Siga a seção 6 de [INSTALLATION.md](INSTALLATION.md): faça um backup, substitua os arquivos do sistema sem tocar em `data\` e `.env`, execute `scripts\update.ps1` e use **Iniciar LocaControl.cmd**. A atualização nunca apaga o banco.
