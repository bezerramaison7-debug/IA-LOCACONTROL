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

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\admin.ps1
```

Cria o primeiro administrador. O comando pergunta usuário, nome e senha no próprio terminal; a senha não aparece na tela nem fica gravada em arquivo. **Execute este passo somente em banco novo, sem nenhum usuário.**

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
