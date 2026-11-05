![IA](https://img.shields.io/badge/IA-Feito_por_IA-7F77DD)

> **Autoria:** eu defini a ideia, os requisitos e as regras de negócio. A arquitetura e o código foram feitos por IA, sob minha orientação.

# LocaControl

Sistema local para gestão de locação de equipamentos e materiais de construção civil.

**Estado em 11/10/2026.** Etapas 0–3 concluídas. Etapa 4 PARCIAL: upload e conversão do Excel funcionam, mas o arquivo real da locadora ainda não foi enviado e o histórico de contratos/renovações não tem conversão. Etapas 5–11: backend e telas implementados e testados (orçamentos, contratos, retirada, renovação, devolução, dashboard real, relatórios, portal do cliente, fiscal em simulação, backup e restauração); nenhum item de menu aponta para página provisória. Etapa 12: **entrega técnica feita** — auditoria independente do backend com 11 achados corrigidos, teste de aceite do cenário oficial pela API, E2E pela interface e guias de instalação, uso e administração. **A versão 1.0 não está declarada concluída:** falta o aceite do usuário no navegador e os insumos que só ele pode fornecer, listados em [RELEASE_NOTES_1.0](docs/RELEASE_NOTES_1.0.md).

Limites que não devem ser confundidos com entrega: o modelo de contrato é PROVISÓRIO e identificado no PDF; o fiscal é só simulação, sem valor fiscal; nada foi homologado com dados reais, validado pelo usuário nem publicado na internet. Guias: [Instalação](docs/INSTALLATION.md), [Uso](docs/USER_GUIDE.md), [Administração](docs/ADMIN_GUIDE.md) e [Importar Excel](docs/EXCEL_IMPORT.md). Estado: [PROJECT_STATE](docs/PROJECT_STATE.md) e [AI_HANDOFF](docs/AI_HANDOFF.md); roteiro: [PUBLICATION_ROADMAP](docs/PUBLICATION_ROADMAP.md).

## Requisitos

- Windows com PowerShell 5.1+.
- Python 3.12+ (ambiente validado: 3.12.14).
- Node.js 22.12+ e npm 10+ (ambiente validado: Node 24.13.0 e npm 11.6.2).
- Internet para a primeira instalação das dependências.

O projeto usa `.venv` próprio; não é necessário ativá-lo. Os scripts aceitam caminhos com espaços e retornam erro quando um comando falha. Não exigem alteração permanente da política do PowerShell.

## Instalar

Abra o PowerShell na raiz do projeto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

Se `python` não estiver no PATH, indique o executável de sua instalação:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -Python 'C:\caminho\para\python.exe'
```

O setup cria o ambiente virtual quando ausente, instala as versões de `backend/requirements-lock.txt` e `frontend/package-lock.json`, registra o backend em modo editável e copia `.env.example` para `.env` **somente se `.env` ainda não existir**. Não substitui seu banco ou suas configurações.

## Checkpoint atual

Banco local conferido em 11/10/2026: revisão `0010_backups`, cinco perfis, 32 permissões e uma conta existente preservada; sem dados comerciais (nenhum cliente, orçamento, contrato ou lote de importação). As migrations 0005–0010 foram aplicadas no dia, cada grupo depois de uma cópia do banco em `data/backups` (`pre-quotes-20261011-084445.db`, `pre-contracts-20261011-090635.db`, `pre-upgrade-20261011-092925.db`). Código na branch `dev/etapas-4-12`. Consultar [AI_HANDOFF](docs/AI_HANDOFF.md) antes de alterar código ou banco.

## Uso diário: iniciar pelo atalho

Depois da instalação e de uma primeira compilação da interface (`scripts\update.ps1` ou `npm.cmd --prefix frontend run build`), não é preciso terminal:

- **Iniciar LocaControl.cmd** (duplo clique, na raiz do projeto): confere se o sistema já está no ar, copia o banco para `data\backups\pre-upgrade-*.db` e aplica migrations se houver atualização de schema, sobe o servidor em segundo plano em <http://127.0.0.1:8000> e abre o navegador. A janela pode ser fechada.
- **Parar LocaControl.cmd**: encerra somente o servidor iniciado pelo atalho.
- **Atualizar** (`powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\update.ps1`): para o servidor, reinstala as dependências travadas e recompila a interface sem tocar em `data\`. O schema é atualizado no próximo "Iniciar".

Logs do servidor: `data\logs\web.stdout.log` e `web.stderr.log`. Outra porta: `scripts\launch.ps1 -Port 8080` (ajuste também `LOCACONTROL_ALLOWED_ORIGINS`). O atalho usa somente o endereço local 127.0.0.1.

## Preparar o banco

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\migrate.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\migrate.ps1 -Action current
```

Revisão local confirmada em 11/10/2026: `0010_backups`. Banco padrão: `data/locacontrol.db`. As migrations criam identidade, cadastros, estoque, preços, importação, orçamentos, contratos e operação, portal e fiscal. Seeds: cinco perfis, 32 permissões e um modelo de contrato provisório, sem usuários ou dados comerciais. A conta local existente foi preservada; não apagar o banco nem executar bootstrap novamente. Arquivos fora do banco: `data/imports` (originais do Excel), `data/documents` (PDFs de contrato) e `data/fiscal`; o backup do sistema (`.zip`) leva banco e as três pastas juntos.

## Primeiro acesso e recuperação

Após preparar o banco, crie o primeiro administrador em um terminal PowerShell interativo na raiz do projeto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\admin.ps1
```

Informe usuário, nome e senha de 12 a 128 caracteres. A senha e sua confirmação são digitadas de forma oculta. Não existe senha padrão. O comando só permite bootstrap enquanto não houver nenhum usuário e registra a operação na auditoria. O banco local auditado em 08/10/2026 já contém um usuário; preserve essa conta e não execute bootstrap novamente. O procedimento de primeiro acesso acima se destina a instalações novas, sem usuários.

Para recuperar uma conta pelo terminal do computador servidor:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\admin.ps1 -Action recover
```

A recuperação exige confirmação, revoga sessões e obriga a troca da senha no próximo login. Não reativa contas desativadas nem altera seus perfis. Consulte [Identidade e segurança](docs/SECURITY.md) para a matriz de acesso, API e limites do mecanismo local.

## Executar em desenvolvimento

Em um terminal:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1 -Reload
```

Em outro terminal:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

- Interface: <http://localhost:5173>.
- Saúde técnica: <http://localhost:8000/health>.
- Documentação OpenAPI: <http://localhost:8000/docs>.
- Parar: `Ctrl+C` em cada terminal.

O Vite encaminha `/health` e `/api` para o backend. Portas padrão 5173 e 8000. Para outra porta do backend, use `-Port` e ajuste `LOCACONTROL_PROXY_TARGET` no `.env`; reinicie o Vite. A porta do Vite é estrita: conflito gera erro, não troca silenciosa.

## Servir a interface compilada no backend

```powershell
npm.cmd --prefix frontend run build
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

Depois do build, inicie ou reinicie o backend e abra <http://localhost:8000/#/login>. Ele serve `frontend/dist` e mantém `/health`, `/docs` e `/openapi.json`. A navegação usa fragmentos; links diretos e atualização da página funcionam sem fallback adicional no servidor. Após autenticar, acesse Meu perfil e, como administrador, Usuários, Perfis e permissões e Auditoria pelo menu.

Para explorar a interface, use o seletor de tema no menu ou em Configurações. Todas as telas do menu, inclusive o Dashboard, leem e gravam dados reais; não há dados de demonstração. Faturamento e fiscal opera somente em simulação, sem valor fiscal.

## Configuração e LAN

Configurações na raiz, em `.env` (ignorado pelo Git):

| Variável | Finalidade |
| --- | --- |
| `LOCACONTROL_DATABASE_URL` | URL SQLAlchemy; padrão `sqlite:///./data/locacontrol.db`. Caminho relativo sempre parte da raiz. |
| `LOCACONTROL_CORS_ORIGINS` | Array JSON de origens permitidas para acesso direto à API. |
| `LOCACONTROL_PROXY_TARGET` | Destino do proxy de desenvolvimento, padrão `http://127.0.0.1:8000`. Não vai para o bundle do navegador. |
| `LOCACONTROL_ALLOWED_ORIGINS` | Array JSON de origens exatas autorizadas a enviar ações; validação de origem/CSRF, incluindo URLs do frontend. |
| `LOCACONTROL_COOKIE_SECURE` | `false` para HTTP de desenvolvimento em loopback; `true` quando servido por HTTPS. |
| `LOCACONTROL_SESSION_HOURS` | Prazo absoluto da sessão, padrão 8 horas, de 1 a 24. |
| `LOCACONTROL_COMPANY_NAME`, `_DOCUMENT`, `_ADDRESS`, `_CONTACT` | Dados da locadora impressos em orçamentos, contratos e relatórios. Sem configuração, o cabeçalho mostra "LocaControl". Presentes no `.env.example`. |
| `LOCACONTROL_CONTRACT_DUE_SOON_DAYS` | Dias de antecedência para um contrato ativo aparecer como "vencendo"; padrão 3, de 0 a 60. |
| `LOCACONTROL_IMPORT_DIRECTORY`, `LOCACONTROL_DOCUMENT_DIRECTORY`, `LOCACONTROL_FISCAL_DIRECTORY` | Pastas dos originais do Excel, dos PDFs de contrato e dos arquivos fiscais; padrão `data/imports`, `data/documents` e `data/fiscal`. |
| `LOCACONTROL_FISCAL_PROVIDER` | Provedor fiscal; o único valor aceito hoje é `fake` (simulação sem valor fiscal). |
| `LOCACONTROL_FISCAL_DOCUMENT_KIND` | Texto livre com a espécie do documento, a definir com a contabilidade; vazio por padrão. |
| `LOCACONTROL_BACKUP_DIRECTORY` | Pasta padrão dos conjuntos de backup; padrão `data/backups`. Horário, retenção e ativação do backup automático são configurados pela API de backups. |
| `LOCACONTROL_BACKUP_SCHEDULER` | `true` por padrão; `false` desliga a verificação em segundo plano do backup automático. |

Das variáveis novas de 11/10, o `.env.example` traz somente as quatro `LOCACONTROL_COMPANY_*`; as demais têm padrão em `backend/app/core/config.py` e só precisam ir ao `.env` para mudar o padrão.

Os scripts aceitam `-Lan` para bind em `0.0.0.0`; o padrão permanece somente local. Para uso autenticado entre computadores, configure HTTPS, `LOCACONTROL_COOKIE_SECURE=true` e a origem exata em `LOCACONTROL_ALLOWED_ORIGINS`. Firewall e política da rede precisam permitir a conexão. O parâmetro `-Lan` sozinho não configura HTTPS; instalação de rede pertence à etapa de operação. Ao mudar portas ou endereços, atualize também as origens autorizadas.

Não expor SQLite nem servidor de desenvolvimento à internet e não transmitir credenciais pela LAN em HTTP. Não usar arquivo SQLite em pasta compartilhada. Backup e restauração existem na API (`/api/backups`, permissão do administrador); a tela de backups ainda não foi construída. Inicialização sem terminal: ver "Uso diário".

## Qualidade e testes

```powershell
# Lint, formatação (somente checagem), TypeScript e build
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check.ps1

# Testes backend e frontend
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1

# Subir processos temporários e verificar HTTP real e proxy (requer build)
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke.ps1

# Checar divergência entre metadata e banco migrado
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\migrate.ps1 -Action check

# Aplicar formatação aos fontes
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\format.ps1
```

Backend usa pytest e bancos SQLite temporários. Verifica saúde, migrations, CORS, autenticação, autorização, CSRF, expiração/revogação, bootstrap/recuperação, auditoria, rollback e proteção concorrente do primeiro/último administrador. Frontend usa Vitest/Testing Library para temas, componentes, navegação, health e autenticação. Validação final da Etapa 2: 35 testes backend e 25 frontend aprovados. Em 11/10/2026, sobre o commit `82e0845`, a suíte de backend (`.\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider`) passou com 141 testes e 1 aviso, cobrindo também orçamentos, contratos, operação, relatórios, portal, fiscal, backups e o cenário oficial de aceite; o Vitest passou com 63 testes em 13 arquivos.

Para verificar renderização e acessibilidade no Chromium, após o build:

```powershell
Push-Location frontend
# Primeira utilização em uma máquina sem o navegador do Playwright
npx.cmd playwright install chromium
npm.cmd run test:e2e
Pop-Location
```

O teste inicia Vite preview na porta 4173 e verifica sete páginas, temas claro/escuro, teclado e responsividade em desktop, Full HD, tablet e celular. Relatório local: `frontend/playwright-report/index.html`; capturas: `frontend/test-results`. Se já houver um Chromium compatível instalado, a variável opcional `PLAYWRIGHT_CHROMIUM_EXECUTABLE` aceita o caminho completo. Nesta máquina foi usado `C:\Users\maiso\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe`. Em sandbox Windows restrito, o encerramento da árvore de processos do Playwright pode exigir permissão apropriada de execução; o teste final foi aprovado fora dessa restrição.

Essa regressão visual simula a identidade nos testes. Para verificar autenticação com API e banco reais, após o build e com Chromium disponível, execute na raiz:

```powershell
.\.venv\Scripts\python.exe scripts/e2e-auth.py
```

O script cria SQLite temporário, aplica migrations e usa um administrador exclusivamente de teste. Exercita, nos quatro viewports (1366×768, 1920×1080, 820×1180 e 390×844), nove roteiros: acesso (login, rota solicitada, criação/edição de usuário, troca obrigatória de senha, acesso negado, logout, desativação e auditoria), cadastros, importações, orçamentos, contratos e operação, relatórios, portal, fiscal e backups; encerra seu servidor e remove seu banco ao terminar. Relatório: `frontend/auth-playwright-report/index.html`; capturas: `frontend/auth-test-results`. Não cria contas no banco local.

Em 11/10/2026 as duas suítes passaram: 16 cenários visuais e 36 reais, com as verificações Axe e de rolagem horizontal previstas nos roteiros, nos temas claro e escuro. O E2E real não foi repetido depois de uma alteração posterior de duas frases de interface; ressalvas completas em [RELEASE_NOTES_1.0](docs/RELEASE_NOTES_1.0.md). Isso não equivale a uma certificação completa de acessibilidade nem a um aceite do usuário.

O smoke cria banco temporário, aplica migrations, inicia Uvicorn e Vite em portas livres, verifica HTML compilado e proxy `/health`, e encerra apenas os processos criados por ele. Não modifica o banco de desenvolvimento. A prova de renderização no navegador é registrada na documentação da etapa.

## Estrutura

```text
backend/
  app/
    api/              HTTP e schemas
    core/             Configurações e data comercial
    persistence/      SQLAlchemy e metadata
    services/         Casos de uso e saúde
    domain/           Reservado a regras comerciais
    auth/             Modelos, serviços, API, autorização e CLI de identidade
    masters/          Clientes, produtos, equipamentos, estoque e preços
    imports/          Upload, análise e conversão do Excel
    quotes/           Orçamentos, cálculo e PDF
    contracts/        Contratos, documentos, retirada, devolução e renovação
    reports/          Dashboard, relatórios e exportações
    portal/           Portal do cliente e solicitações de renovação
    fiscal/           Documentos fiscais, interface de provedor e simulação
    ops/              Backup e restauração
    documents/        Pacote reservado, vazio
    integrations/     Pacote reservado, vazio
  migrations/         Histórico Alembic
  tests/              Testes isolados
frontend/
  src/
    components/       Biblioteca visual acessível e health real
    layout/           Shell, menu e navegação
    pages/            Telas reais e página 404
    auth/             Sessão, cliente HTTP e proteção de rotas
    theme/            Tema, sistema operacional e persistência
    lib/              Cliente HTTP, validação Zod e preferências
    test/             Configuração dos testes
  e2e/                Playwright, responsividade e auditorias Axe
scripts/              Setup, execução, iniciar/parar/atualizar, migrations, administrador, testes e smoke
docs/                 Estado, regras, arquitetura e continuidade
data/                 Banco, importações, documentos, fiscal, backups e logs; fora do Git
Iniciar LocaControl.cmd / Parar LocaControl.cmd   Atalhos de uso diário
```

## Continuidade e decisões

Antes de alterar código, leia `docs/AI_HANDOFF.md`, `PROJECT_STATE.md`, `ARCHITECTURE.md`, `BUSINESS_RULES.md`, `DATABASE.md`, `DESIGN_SYSTEM.md`, `DECISIONS.md`, `CHANGELOG.md` e o prompt da etapa. As duas instruções originais estão preservadas em `docs/DEVELOPMENT_PLAN.md` e `docs/AI_CONTINUITY_PROTOCOL.md`.

Migrations são explícitas, sem `create_all` no startup. O health retorna 200 somente quando banco e revisão estão corretos; em falha retorna 503 sem caminho ou detalhes internos. React não concentra regras de negócio. Não usar float em dinheiro, não sobrescrever snapshots históricos e não antecipar módulos comerciais.

## Solução de problemas

- **“Virtual environment missing”**: executar setup, indicando `-Python` se necessário.
- **Conexão indisponível**: verificar backend, porta e `.env`; consultar `/health`. `schema: outdated` indica migration pendente ou revisão incompatível.
- **Porta ocupada**: encerrar sua instância anterior ou usar outra porta. Os scripts não encerram processos alheios.
- **Interface não aparece em :8000**: executar build e reiniciar backend.
- **Ainda não há conta para entrar**: executar `scripts/admin.ps1` no terminal interativo após as migrations.
- **Ação rejeitada por origem**: conferir a URL exata em `LOCACONTROL_ALLOWED_ORIGINS`; reiniciar o backend depois da alteração.
- **Senha esquecida**: executar `scripts/admin.ps1 -Action recover` no computador servidor.
- **Erro EACCES/esbuild em um agente com sandbox Windows**: foi observado bloqueio de leitura dos diretórios ancestrais; repetir o comando com a permissão de execução apropriada ao ambiente. Não é necessário editar fontes ou desabilitar segurança global.
- **Instalação sem rede**: primeira instalação requer acesso aos registros npm/PyPI; depois os caches podem reduzir downloads.


## Documentos estruturantes
- [PRD — requisitos do produto](docs/PRD.md)
- [TRD — requisitos técnicos](docs/TRD.md)
- [Fluxo do aplicativo](docs/APP_FLOW.md)
- [Briefing de design](docs/DESIGN_BRIEF.md)
- [Esquema do back-end](docs/BACKEND_SCHEMA.md)
- [Plano de implementação oficial](docs/DEVELOPMENT_PLAN.md)
- [Prompt de continuação até a conclusão](docs/CONTINUE_PROMPT.md)

## Guias da versão candidata 1.0
- [Instalação](docs/INSTALLATION.md)
- [Guia do usuário](docs/USER_GUIDE.md)
- [Guia do administrador](docs/ADMIN_GUIDE.md)
- [Notas da versão candidata 1.0](docs/RELEASE_NOTES_1.0.md)
- [Importar Excel](docs/EXCEL_IMPORT.md)

Documentos estruturados em 11/10/2026 e atualizados no mesmo dia após a implementação dos backends das etapas 5–11. Os guias de instalação, usuário e administração e as notas da versão 1.0 pertencem à etapa 12 e ainda não existem.
