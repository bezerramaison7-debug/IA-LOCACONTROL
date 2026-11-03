# LocaControl — Edição local: briefing, decisões e ponto de retomada

Recebido em 2026-11-01. Este documento guarda o briefing da edição local (instalador único, sem login, proteção automática, rede local) e as decisões já tomadas, para que a execução continue em qualquer sessão. Ler junto com `AI_HANDOFF.md`.

## Objetivo
Sistema Windows instalado por um único executável, pronto para uso sem terminal, sem instalar dependências e sem login do aplicativo. Dados protegidos por gravação imediata, rascunhos recuperáveis e backups automáticos. Outros computadores da loja acessam a mesma base pela rede local.

## Decisões confirmadas pelo usuário
1. Sem senha, login, criação de administrador ou gestão de perfis no uso local.
2. Instalação por um único executável que inclui tudo; uso local sem internet.
3. Dados protegidos automaticamente; a mesma solução instalável em computadores diferentes.
4. Vários computadores da loja acessam os mesmos dados pela rede local.
5. Ordem de execução: começar pelo P0 (validação e integridade), depois P1, um PR por tema.
6. **Estações da rede autorizadas por código de pareamento**: o computador principal mostra um código; cada estação o digita uma única vez na instalação e passa a ser aceita; o principal pode revogar estações. O login do Windows não conta como autenticação perante a API.
7. **Portal do cliente desativado na edição local** (fora do menu e das rotas; o código permanece para uma futura edição web).
8. **Autorizada a instalação de PyInstaller e Inno Setup** nesta máquina, apenas para gerar o instalador.
9. **Rede local em HTTP restrito à rede privada** (2026-11-02): o servidor só aceita estações de endereços privados (192.168.x, 10.x, 172.16–31.x); o risco de captura da credencial na rede da loja fica documentado, com revogação disponível. Sem certificado próprio por enquanto.
10. **Estações fazem todo o atendimento, exceto funções sensíveis** (2026-11-02): restaurar backup, alterar a configuração de backup, baixar ou importar o `.zip` e parear ou revogar estações só no computador principal.
11. **Pareamentos não mudam com a restauração** (2026-11-02): a lista de estações fica no servidor, fora da base; restaurar um backup antigo não reativa estação revogada nem desconecta as pareadas depois dele.
12. **Rascunhos no servidor, 7 dias** (2026-11-02): tabela própria, separada dos dados definitivos, por computador/estação, nos backups, expiração 7 dias após a última alteração.
13. **Diretiva do arquiteto (2026-11-03)**: confirmação da importação do Excel só no computador principal (estações consultam conforme autorização; sem importação concorrente de histórico nesta fase); HTTPS aprovado para o P1-E com CA local por instalação, sem confiar na CA antes de verificação independente da identidade; rotação de tokens de estação com detecção de reuso, revogação e auditoria, sem depender só de IP e sem afirmar impossibilidade de clonagem; limites de backup com padrão de 10 GB para a pasta e reserva livre de 10 GB ou 15 % (o maior). Correções autorizadas: A1, A2, A3, M2, M4, M5; M1 e M3 só investigação e proposta (sem WAL automático). Desenvolvimento só na nuvem; homologação Windows pendente, sem bloquear correções validáveis remotamente.

## Arquitetura adotada
Monólito modular existente (frontend compilado + FastAPI + SQLite). Uma instalação principal executa o servidor e guarda os dados; as estações acessam a mesma API pela rede e nunca abrem o arquivo SQLite. Sem sincronização entre bancos independentes.

## Estado
| Item | Situação | Onde |
| --- | --- | --- |
| P0 Validação do SHA `af0474f` | Concluída; 142 backend, 63 frontend, 36 E2E, 16 visual, smoke | `docs/VALIDATION.md`, PR #2 |
| PR #1 (etapas 4–12) | Mesclado na `master` (`866c67b`) após a validação | — |
| P0 Integridade e recuperação | Implementado: modo manutenção, desfazer automático da restauração, 10 testes de falha | branch `p0/integridade`, PR #3 |
| P1 Remover login | Implementado atrás de `LOCACONTROL_LOCAL_MODE` (padrão `false` até o instalador ligar): sessão automática só para o próprio computador, operador local auditado, rotas de login/usuários/perfis/portal com 404, restauração sem senha | branch `p1/a-sem-login`, ADR-023 |
| P1-B Base de instalação (programa × dados, `LOCACONTROL_DATA_DIR`, ponto de entrada `app.server`, instância única, prova PyInstaller) | Implementado; instalador e teste em Windows limpo seguem pendentes (P1-E) | branch `p1/b-instalacao`, `docs/INSTALLATION.md` 6.1 |
| P1 Instalador único | Pendente | — |
| P1-C Proteção automática (backup 20/60 min, histórico e aviso, segunda cópia, importação e restauração de outro disco, rascunhos, sessão local preservada; limites de espaço e verificação após gravação) | Implementado com as correções A3 e M2 da auditoria; validado no Linux da nuvem; homologação Windows pendente (seção abaixo) | branch `p1/c-protecao`, ADR-024 |
| P1 Rede local | Pendente | — |
| P1 Importação Excel (continuidade) | Pendente; histórico depende do Excel real | — |

## Requisitos do P1 (resumo fiel do briefing)
**Sem login.** Remover tela de login, primeiro acesso admin/admin, troca obrigatória, configuração de administrador e gestão de usuários/perfis do uso normal. Criar contexto interno de operador local sem credenciais, compatível com a auditoria e as referências existentes; registrar a origem das operações sem afirmar identidade individual. Adaptar rota a rota — não liberar todos os endpoints indiscriminadamente; manter a proteção contra solicitações de outros sites (origem/CSRF). Na restauração, trocar a senha por confirmação explícita, modo manutenção (já existe) e cópia prévia (já existe).

**Instalador único.** Executável com aplicação, runtime, frontend compilado, migrations, atalhos e inicialização. Programa separado dos dados (sugestão: programa em `Arquivos de Programas`, dados em `%ProgramData%\LocaControl`). Atualização/reinstalação preservam dados; desinstalação preserva por padrão. Duas opções: "Usar neste computador" (principal) e "Conectar à loja" (estação). Rede só habilitada no modo escolhido, com regra de firewall limitada à rede local. Comprovar instalação e uso sem internet em máquina Windows limpa.

**Proteção automática.** (A) gravação definitiva — sucesso só depois do commit (comprovado no P0); (B) rascunho automático de formulários longos, separado dos dados definitivos, sem movimentar estoque nem emitir documento, com recuperação após reabertura, expiração e descarte; (C) backup automático a cada 20 min (opção 60), com banco + originais Excel + documentos, retenção, verificação, registro de sucesso/falha, indicação da última cópia, sem sobreposição, aviso de que depende do computador ligado, segunda cópia em outro dispositivo e ensaio de recuperação.

**Rede local.** Instalação principal concentra dados e processamento; estações usam a mesma API. Tratar concorrência e conflito de edição (já há versão por registro e `BEGIN IMMEDIATE`). Testar com duas estações: alteração de cadastro, retirada concorrente da mesma unidade, confirmação de contrato, backup durante uso, queda e retorno do principal.

**Excel.** Preservar original, checksum, prévia, confirmação e rastreabilidade; documentar campos canônicos; perfis de transformação, staging e conciliação; separar histórico encerrado de contratos ativos na data de corte; não reproduzir retiradas históricas sobre estoque inicial conciliado. Depende do Excel real e de regras aprovadas.

## Critérios de conclusão
Um instalador prepara máquina limpa sem downloads; o atalho abre sem login; operações confirmadas sobrevivem à reinicialização; formulários suportados recuperam rascunho; backups seguem o intervalo e restauram; atualizações preservam dados; duas estações não violam estoque e custódia; documentação corresponde ao comportamento e ao SHA validado.

## Entrega
Um PR por tema (validação, integridade, sem login, empacotamento, proteção automática, rede), cada um com problema, comportamento final, decisões, testes executados, limitações e procedimento de recuperação. O GitHub CLI está autenticado nesta máquina (`gh`), e o Git usa essa credencial.

## Critérios adicionais para as próximas frentes (registrados em 2026-11-01)
- **P1-A/C:** expiração e renovação da sessão local preservam o formulário em edição; nenhuma escrita é repetida automaticamente sem idempotência. *Atendido no P1-C* (ADR-024): renovação sem desmontar a tela, leitura repetida uma vez, escrita nunca repetida.
- **P1-C/E:** existe procedimento utilizável e verificado para recuperar backups guardados em outro disco. *Atendido no P1-C*: restauração com a pasta de backups em outro disco (teste com sistema de arquivos distinto) e importação verificada do `.zip` (`ADMIN_GUIDE.md` 4); falta repetir no Windows com pendrive/HD externo.
- **P1-D:** distinguir identidade da base/loja, do servidor e das estações; definir o efeito da restauração sobre pareamentos e revogações.
- **Demonstração (pendente):** pacote de demonstração a partir do empacotamento do P1-B — executável sem login, pasta de dados exclusiva, dados fictícios cobrindo cliente, produto, preço, orçamento, contrato, retirada, renovação e devolução, marcação visível de DEMONSTRAÇÃO, sem dados reais/.env/backups, validado pelo próprio executável (interface e PDFs de orçamento e contrato), entregue com caminho, SHA de origem, checksum e instruções; distinguir "testado nesta máquina" de "validado em Windows limpo".

## P1-C — o que falta validar no Windows
- Limites de espaço com discos reais (pequeno e grande), aviso de "não cabe", recusa e retomada.
- `fsync` no NTFS e verificação após gravação em pendrive/HD externo.
- Backup automático real de 20 minutos com o servidor empacotado rodando por algumas horas (retenção, "sem alterações", aviso no dashboard).
- Pasta de backups e segunda cópia em pendrive/HD externo (letras de unidade diferentes): backup, desconexão do disco (aviso), restauração direto da pasta em outro disco e importação do `.zip`.
- Restauração com arquivos abertos por outros programas (antivírus, Explorer) na pasta de dados.
- Rascunhos: fechar o navegador e reiniciar o Windows no meio de um orçamento e de uma retirada; recuperar.
