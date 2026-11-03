# LocaControl — Instalação

Guia para instalar o LocaControl em um computador Windows da locadora e deixá-lo pronto para uso diário, sem terminal. Para o dia a dia do administrador depois de instalado, veja [ADMIN_GUIDE.md](ADMIN_GUIDE.md); para o uso das telas, [USER_GUIDE.md](USER_GUIDE.md).

## 1. O que esta instalação é (e não é)

- O sistema roda **neste computador** e é aberto pelo navegador em `http://127.0.0.1:8000`.
- Os dados ficam na pasta `data\` da instalação: banco (`locacontrol.db`), planilhas importadas, contratos em PDF, arquivos fiscais de simulação, backups e logs.
- **Não é uma instalação na internet.** O atalho de início atende somente o próprio computador. Uso por outros computadores da rede exige HTTPS e ajustes descritos na seção 7; publicação na internet é uma etapa futura que não foi feita.

## 2. Requisitos

- Windows com PowerShell 5.1 ou mais novo.
- Python 3.12 ou mais novo.
- Node.js 22.12 ou mais novo, com npm 10 ou mais novo (necessário para compilar a interface).
- Internet na primeira instalação e nas atualizações, para baixar as dependências.

Não coloque a pasta do sistema em uma pasta de rede ou sincronizada (OneDrive, Google Drive): o banco SQLite precisa de disco local.

## 3. Instalar pela primeira vez

Abra o PowerShell na pasta do LocaControl e execute, um comando de cada vez:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

Cria o ambiente Python, instala as versões travadas das dependências e copia `.env.example` para `.env` se ele ainda não existir. Se o Python não estiver no PATH, acrescente `-Python 'C:\caminho\para\python.exe'`.

```powershell
npm.cmd --prefix frontend run build
```

Compila a interface. É obrigatório antes do primeiro início.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\migrate.ps1
```

Cria o banco e todas as tabelas.

### Primeiro acesso

Não é preciso criar usuário pelo terminal. Na primeira vez que **Iniciar LocaControl.cmd** encontra o banco sem nenhuma conta, ele cria o administrador inicial:

- usuário: `admin`
- senha: `admin`

Ao entrar com essa senha, o sistema exige imediatamente uma senha nova, com 12 caracteres ou mais, e não libera nenhuma tela antes da troca. Depois disso a senha `admin` deixa de funcionar. A conta inicial só é criada enquanto o banco não tem nenhum usuário; ela nunca é recriada.

**Faça o primeiro acesso e a troca de senha logo após instalar.** Até a troca, qualquer pessoa com acesso a este computador pode entrar como administrador.

Quem preferir definir usuário e senha próprios desde o início pode executar, antes do primeiro início e num PowerShell aberto pelo Windows, `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\admin.ps1`; nesse caso a conta `admin` não é criada.

## 4. Preencher os dados da locadora

Abra o arquivo `.env` na pasta do sistema e preencha as linhas abaixo. Elas aparecem no cabeçalho de orçamentos, contratos e relatórios:

```
LOCACONTROL_COMPANY_NAME=Nome da sua locadora
LOCACONTROL_COMPANY_DOCUMENT=CNPJ 00.000.000/0000-00
LOCACONTROL_COMPANY_ADDRESS=Rua, número — Cidade/UF
LOCACONTROL_COMPANY_CONTACT=(00) 0000-0000 · contato@exemplo.com.br
```

Enquanto não forem preenchidas, os documentos saem com o nome "LocaControl". O arquivo `.env` não deve conter senhas de usuários; nunca o envie a terceiros.

## 5. Iniciar e parar

- **Iniciar LocaControl.cmd** (duplo clique): confere o banco, aplica atualizações de estrutura quando existirem (sempre depois de copiar o banco para `data\backups\pre-upgrade-*.db`), sobe o sistema em segundo plano e abre o navegador. A janela preta pode ser fechada.
- **Parar LocaControl.cmd** (duplo clique): encerra o sistema iniciado pelo atalho.

Se o navegador não abrir, acesse `http://127.0.0.1:8000`. Se aparecer erro ao iniciar, consulte `data\logs\web.stderr.log`.

Para que o sistema inicie junto com o Windows, crie um atalho de **Iniciar LocaControl.cmd** na pasta que abre com `Win + R` → `shell:startup`.

## 6. Atualizar para uma versão nova

1. Faça um backup em **Gestão → Backups**, botão **Fazer backup agora** (ou, com o sistema parado, copie a pasta `data\` inteira para outro lugar).
2. Substitua os arquivos do sistema pelos da versão nova, **sem apagar nem substituir a pasta `data\` e o arquivo `.env`**.
3. Execute:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\update.ps1
```

4. Use **Iniciar LocaControl.cmd**. Ele copia o banco e aplica as mudanças de estrutura antes de subir.

A atualização nunca apaga o banco. Se algo falhar, o sistema não sobe e o banco anterior está em `data\backups\pre-upgrade-*.db`.

## 6.1 Programa e dados (P1-B)

O programa e os dados ficam em pastas separadas. Trocar, reinstalar ou remover o programa não toca nos dados.

| Pasta | Conteúdo | Quem escreve |
| --- | --- | --- |
| **Programa** (projeto; na edição instalada, `C:\Program Files\LocaControl`) | código, runtime Python, `frontend\dist`, `backend\migrations`, `backend\alembic.ini` | só a instalação ou a atualização; o servidor apenas lê |
| **Dados** (`data\` do projeto ou `LOCACONTROL_DATA_DIR`; na edição instalada, `%ProgramData%\LocaControl`) | `locacontrol.db`, `imports\`, `documents\`, `fiscal\`, `backups\` (com `pre-upgrade-*.db`), `logs\`, `.env`, `locacontrol.lock`, `locacontrol.pid`, `locacontrol.installed` | o servidor |

**Precedência dos caminhos**: uma variável específica (`LOCACONTROL_DATABASE_URL`, `LOCACONTROL_IMPORT_DIRECTORY`, `LOCACONTROL_DOCUMENT_DIRECTORY`, `LOCACONTROL_FISCAL_DIRECTORY`, `LOCACONTROL_BACKUP_DIRECTORY`) sempre vence. Sem ela, o caminho deriva de `LOCACONTROL_DATA_DIR`. Sem `LOCACONTROL_DATA_DIR`, vale a pasta `data\` do projeto, como antes. No executável empacotado, a falta da variável faz o servidor usar `%ProgramData%\LocaControl`. Com `LOCACONTROL_DATA_DIR` definido, o `.env` é lido de dentro da pasta de dados. A variável só é lida do ambiente do processo, nunca de um `.env`. Use caminho absoluto.

**Apontar para uma pasta existente** (por exemplo, a `data\` atual), sem mover nada:

```powershell
[Environment]::SetEnvironmentVariable('LOCACONTROL_DATA_DIR', 'C:\Users\<voce>\Documents\ChatGPT\SAAS LOCACAO\data', 'User')
```

Feche e reabra o terminal ou o atalho. Para voltar ao comportamento padrão, remova a variável. Copie o `.env` do projeto para a pasta de dados se ele tiver os dados da locadora.

**Início do servidor** (`python -m app.server [--port N] [--prepare]`, usado por `scripts\launch.ps1` e pelo executável). As etapas são:

1. Confere a pasta de dados.
2. Obtém o bloqueio de instância única.
3. Aplica as migrations com cópia prévia do banco em `backups\pre-upgrade-*.db`.
4. Cria `admin/admin` apenas na edição com login.
5. Sobe em `127.0.0.1`.

Com `--prepare`, o servidor só prepara o banco e encerra.

| Código de saída | Significado |
| --- | --- |
| 0 | encerrou normalmente |
| 3 | já há um LocaControl em execução com esta mesma pasta de dados (nada foi alterado) |
| 4 | pasta de dados indisponível ou banco desaparecido (nada foi criado) |

**Instância única**: o servidor trava um byte do arquivo `locacontrol.lock` (`msvcrt.locking`) antes de qualquer migration. A trava pertence ao processo: o Windows a solta quando ele termina, mesmo encerrado à força. Por isso o arquivo que sobra na pasta é inofensivo e não deve ser apagado à mão.

**Pasta de dados indisponível**: o servidor cria a pasta sozinho apenas na primeira instalação, e só quando a pasta-mãe já existe e aceita gravação. Ele encerra com o código 4, sem criar banco, quando:

- a pasta-mãe não existe (unidade ou compartilhamento ausente);
- não há permissão de gravação;
- existe um arquivo no lugar da pasta;
- o banco sumiu de uma pasta já usada, reconhecida pelo marcador `locacontrol.installed`, gravado depois da primeira preparação bem-sucedida. Nesse caso, restaure um backup ou corrija o caminho.

**Atualização, reinstalação e desinstalação**: `scripts\update.ps1` só escreve na pasta do programa (`.venv`, `backend`, `frontend\dist`). Na pasta de dados ele apenas para o servidor, que apaga o próprio registro de processo. O instalador (P1-E) deve preservar `%ProgramData%\LocaControl` ao atualizar e reinstalar, e **não removê-la na desinstalação por padrão**.

**Executável (prova de empacotamento)**: `scripts\package.ps1` gera `dist-app\LocaControl\LocaControl.exe` a partir de `packaging\locacontrol.spec`. A saída é uma pasta com `_internal\`, ignorada pelo Git, e o comando requer `pip install pyinstaller==6.22.3` no `.venv` e o `frontend\dist` compilado. O executável recebe `LOCACONTROL_DATA_DIR` e `LOCACONTROL_LOCAL_MODE` por variável de ambiente (ou pelo `.env` da pasta de dados, exceto `LOCACONTROL_DATA_DIR`) e a porta por `--port`. O instalador e o teste em Windows limpo ficam para o P1-E.

**Modo rede (P1-D, ADR-025)**: com `LOCACONTROL_LOCAL_MODE=true` e `LOCACONTROL_NETWORK_MODE=true` o servidor escuta em todas as interfaces (sem o modo rede, só em `127.0.0.1`) e aceita estações pareadas da rede privada. Opcionais: `LOCACONTROL_STATION_NETWORKS` (redes extras, por exemplo `["100.64.0.0/10"]`) e `LOCACONTROL_STATION_HOSTS` (nomes extras pelos quais as estações chegam ao servidor, além do IP e do nome do computador). A lista de estações fica em `stations.json` na pasta de dados, fora dos backups: copie a pasta de dados inteira para levar o principal para outro computador sem parear de novo. A regra de firewall do Windows limitada à rede local e a escolha "Usar neste computador" × "Conectar à loja" ficam para o instalador (P1-E).

## 7. Uso por outros computadores da rede

O atalho de início não libera acesso pela rede. Para isso é preciso, no mínimo:

- servir o sistema com HTTPS (as senhas não devem trafegar em HTTP pela rede);
- definir `LOCACONTROL_COOKIE_SECURE=true` e incluir o endereço exato usado pelos outros computadores em `LOCACONTROL_ALLOWED_ORIGINS`;
- liberar a porta no firewall somente para a rede interna.

Esse cenário não foi homologado nesta versão. O portal do cliente funciona na mesma instalação; acesso de clientes pela internet depende da publicação web, que não foi realizada.

## 8. Conferir se está tudo certo

- `http://127.0.0.1:8000/health` deve responder com `"status":"ok"`.
- Entre com o administrador criado e abra **Gestão → Configurações**: o cartão **Conexão do ambiente**, no fim da página, deve mostrar Servidor "Disponível", Banco de dados "Conectado" e Migrations "Atualizadas".
- Em **Gestão → Backups**, clique em **Fazer backup agora** e depois em **Verificar** no arquivo criado: o resultado deve ser "Backup íntegro: pode ser restaurado."

## 9. Problemas comuns

| Sintoma | O que fazer |
| --- | --- |
| "A interface ainda não foi compilada" | Execute `npm.cmd --prefix frontend run build` ou `scripts\update.ps1`. |
| "A porta 8000 está em uso por outro programa" | Feche o outro programa ou inicie com `scripts\launch.ps1 -Port 8080`. O script já libera a origem dessa porta (`http://127.0.0.1:8080` e `http://localhost:8080`); não é preciso editar `LOCACONTROL_ALLOWED_ORIGINS`. |
| Tela pede login a cada ação, ou "Origem da solicitação não permitida" | O endereço usado no navegador não está entre as origens aceitas. Use `http://127.0.0.1:8000` (ou a porta informada em `-Port`). Outros endereços, como o nome ou o IP do computador na rede, precisam constar em `LOCACONTROL_ALLOWED_ORIGINS` (seção 7). |
| `/health` responde "outdated" | A estrutura do banco está atrás da versão instalada: use **Iniciar LocaControl.cmd** ou `scripts\migrate.ps1`. |
| Esqueci a senha do administrador | `scripts\admin.ps1 -Action recover`, no próprio computador do sistema. |
