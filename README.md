# LocaControl

Fundação de um sistema local para gestão de locação de equipamentos e materiais de construção civil.

**Etapas 0–3 concluídas; Etapa 4 PARCIAL (upload e conversão implementados, homologação do Excel real pendente).** Identidade, clientes, produtos, equipamentos, estoque e preços usam API e banco reais. O usuário envia o Excel em Gestão → Importações, analisa abas, mapeia campos, valida sem gravar e confirma a conversão. Original, origem de linhas e relatórios são preservados. Dashboard, orçamentos e contratos ainda têm prévias identificadas. Contratos/renovações históricos aguardam seus módulos e não são descartados silenciosamente. Guia: [Importar Excel](docs/EXCEL_IMPORT.md). Estado: [AI_HANDOFF](docs/AI_HANDOFF.md); roteiro: [PUBLICATION_ROADMAP](docs/PUBLICATION_ROADMAP.md).

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

Banco local validado em 08/10/2026: 0004_imports, cinco perfis, 18 permissões e uma conta existente preservada. Migrations 0003/0004 aplicadas após backup consistente. Integridade, FKs e Alembic check aprovados. Consultar [AI_HANDOFF](docs/AI_HANDOFF.md) antes de alterar código ou banco.

## Preparar o banco

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\migrate.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\migrate.ps1 -Action current
```

Revisão local confirmada em 08/10/2026: `0004_imports`. Banco padrão: `data/locacontrol.db`. As migrations criam identidade, cadastros comerciais, estoque, preços e lotes/origens de importação. Seeds: cinco perfis e 18 permissões, sem usuários ou dados comerciais. A conta local existente foi preservada; não apagar o banco nem executar bootstrap novamente. Originais enviados ficam em `data/imports`; incluir banco e arquivos juntos nos backups.

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

Para explorar a interface, use o seletor de tema no menu ou em Configurações. Nas listas comerciais demonstrativas, o seletor **Estado da prévia** mostra carregamento, vazio e erro; seus formulários validam exemplos e avisam que nada foi salvo. As telas de identidade salvam alterações reais. Itens de etapas futuras mostram uma página explicativa.

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

Os scripts aceitam `-Lan` para bind em `0.0.0.0`; o padrão permanece somente local. Para uso autenticado entre computadores, configure HTTPS, `LOCACONTROL_COOKIE_SECURE=true` e a origem exata em `LOCACONTROL_ALLOWED_ORIGINS`. Firewall e política da rede precisam permitir a conexão. O parâmetro `-Lan` sozinho não configura HTTPS; instalação de rede pertence à etapa de operação. Ao mudar portas ou endereços, atualize também as origens autorizadas.

Não expor SQLite nem servidor de desenvolvimento à internet e não transmitir credenciais pela LAN em HTTP. Não usar arquivo SQLite em pasta compartilhada. Backup automático e inicialização diária sem terminal pertencem à Etapa 11.

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

Backend usa pytest e bancos SQLite temporários. Verifica saúde, migrations, CORS, autenticação, autorização, CSRF, expiração/revogação, bootstrap/recuperação, auditoria, rollback e proteção concorrente do primeiro/último administrador. Frontend usa Vitest/Testing Library para temas, componentes, navegação, health e autenticação. Validação final da Etapa 2: 35 testes backend e 25 frontend aprovados.

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

O script cria SQLite temporário, aplica migrations e usa um administrador exclusivamente de teste. Exercita login, rota solicitada, criação/edição de usuário, troca obrigatória de senha, acesso negado, logout, desativação e auditoria nos quatro viewports; encerra seu servidor e remove seu banco ao terminar. Relatório: `frontend/auth-playwright-report/index.html`; capturas: `frontend/auth-test-results`. Não cria contas no banco local.

As duas suítes passaram: 16 cenários visuais e 4 reais, com 96 auditorias Axe sem violações detectadas. Isso não equivale a uma certificação completa de acessibilidade.

O smoke cria banco temporário, aplica migrations, inicia Uvicorn e Vite em portas livres, verifica HTML compilado e proxy `/health`, e encerra apenas os processos criados por ele. Não modifica o banco de desenvolvimento. A prova de renderização no navegador é registrada na documentação da etapa.

## Estrutura

```text
backend/
  app/
    api/              HTTP e schemas
    core/             Configurações
    persistence/      SQLAlchemy e metadata
    services/         Casos de uso e saúde
    domain/           Reservado a regras comerciais
    auth/             Modelos, serviços, API, autorização e CLI de identidade
    documents/        Reservado à geração de documentos
    imports/          Reservado ao importador
    integrations/     Reservado a adapters externos
  migrations/         Histórico Alembic
  tests/              Testes isolados
frontend/
  src/
    components/       Biblioteca visual acessível e health real
    demo/             Fixtures visuais identificadas, sem persistência
    layout/           Shell, menu e navegação
    pages/            Telas de identidade, prévias comerciais, placeholders e 404
    auth/             Sessão, cliente HTTP e proteção de rotas
    theme/            Tema, sistema operacional e persistência
    lib/              Cliente HTTP, validação Zod e preferências
    test/             Configuração dos testes
  e2e/                Playwright, responsividade e auditorias Axe
scripts/              Setup, execução, migrations, administrador, testes e smoke
docs/                 Estado, regras, arquitetura e continuidade
data/                 Banco local gerado; fora do Git
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

Documentos estruturados em 11/10/2026. Não representam novas funcionalidades ou revalidação dos testes/banco. O prompt integral autoriza execução quando enviado pelo usuário como instrução de retomada.