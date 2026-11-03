# LocaControl — P1-E: proposta técnica do instalador, do HTTPS local e do armazenamento

Diretiva arquitetural de 2026-11-03 (P1-E). Esta proposta orienta a branch `p1/e-instalador` (PR sobre `p1/d-rede`). Decisões marcadas "do implementador" são revisáveis. O estudo anterior está em `P1E_HTTPS.md`; quando divergirem, vale este documento.

## 1. Instalação

**Ferramentas**: PyInstaller (já provado no P1-B) gera a pasta do programa com o runtime Python, as dependências, as migrations e a interface compilada — o cliente não instala Python nem Node.js. **Inno Setup 6** (gratuito, scriptável, instalação e desinstalação silenciosas, `AppId` fixo para atualizar no lugar) gera um único `LocaControl-Setup-<versão>.exe`.

| Item | Decisão |
| --- | --- |
| Programa | `C:\Program Files\LocaControl` (somente leitura para usuários) |
| Dados | `C:\ProgramData\LocaControl` (banco, documentos, importações, fiscal, backups, logs, `.env`, `stations.json`, `tls\`) — padrão do executável congelado desde o P1-B |
| Opções | Página "Como este computador vai usar o LocaControl?": **Usar neste computador** (principal; caixa "Permitir que outros computadores da loja usem este") ou **Conectar à loja** (estação; endereço do principal e código de pareamento) |
| Configuração | O instalador grava só as chaves que escolhe (`LOCACONTROL_LOCAL_MODE`, `LOCACONTROL_NETWORK_MODE`) no `.env` da pasta de dados, preservando o resto; a escolha fica também em `HKLM\Software\LocaControl` para a atualização reapresentá-la |
| Início | Principal: atalho "LocaControl" (área de trabalho e menu Iniciar) que sobe o servidor se preciso e abre o navegador; início automático no logon (pasta Inicializar de todos os usuários). Estação: atalho para `https://<principal>:8443/` |
| Atualização | Mesmo `AppId`: substitui só o programa; o instalador fecha o LocaControl em execução (Restart Manager); a nova versão migra o banco ao iniciar, com cópia `pre-upgrade` (agora com conferência de espaço) |
| Desinstalação | Remove programa, atalhos, regra de firewall e, na estação, a CA que ela instalou. **Dados preservados por padrão**; excluí-los exige responder Sim a duas perguntas; a desinstalação silenciosa nunca exclui dados |
| Firewall | Só principal com rede: regra de entrada TCP 8443, `remoteip=localsubnet`, perfis privado e domínio, restrita ao executável |

Limitação aceita: o servidor roda na sessão do usuário (não é serviço do Windows); com o computador ligado mas sem ninguém logado, não há atendimento nem backup. Serviço do Windows fica como evolução.

## 2. HTTPS local e pareamento

**Autoridade certificadora por instalação** (criada no primeiro início do principal com rede, nunca copiada para backups):

- CA ECDSA P-256, 10 anos, `BasicConstraints(ca, pathlen=0)`, uso de chave só para assinar certificados, **Name Constraints** permitindo apenas: DNS `localhost`, nome do computador e `nome.local`; IP `127.0.0.0/8`, `10/8`, `172.16/12`, `192.168/16`, `::1`, `fc00::/7`, `fe80::/10`.
- Certificado do servidor ECDSA P-256, 397 dias, SAN com os mesmos nomes e os IPs privados atuais, EKU `serverAuth`; reemitido sozinho na partida quando faltarem 30 dias ou quando os IPs/nome mudarem.
- **Chaves privadas** em PEM cifrado (AES-256); a senha aleatória de 32 bytes é protegida pelo **DPAPI do Windows no escopo da máquina** (`CryptProtectData` com `CRYPTPROTECT_LOCAL_MACHINE`) — arquivos copiados para outra máquina não abrem. Fora do Windows (desenvolvimento e CI Linux) a senha fica em arquivo com permissão 0600, registrado como proteção mais fraca.

**Transporte**:

- HTTP só em `127.0.0.1:8000` (o próprio principal). Na rede, **só HTTPS** em `0.0.0.0:8443`; não há listener HTTP na rede, portanto nenhuma credencial trafega em HTTP na LAN.
- Requisição de estação (pareamento, sessão, escrita) exige `https`; cookies de estação e de sessão vindos por HTTPS levam `Secure`.
- `Origin` de estação = `https://<Host>`; continuam `X-LocaControl-Request` e CSRF.
- Sem TLS utilizável (chave ilegível, biblioteca ausente), o listener da rede **não sobe** (falha fechada); o principal continua.

**Código de pareamento**: 26 caracteres do alfabeto de 32 símbolos sem 0/O/1/I (**130 bits**), em grupos de 4, digitação tolerante. Configurável até o mínimo de 13 caracteres (65 bits) por `LOCACONTROL_PAIRING_CODE_LENGTH`. Decisão do implementador: 128 bits por padrão, porque a estação é pareada uma vez e o código é colado pelo instalador; reavaliar com o uso real.

**Verificação autenticada da CA antes de confiar** (instalador "Conectar à loja" → `LocaControl.exe conectar`):

1. Ao gerar o código, o principal guarda o hash do código e `prova = HMAC-SHA256(chave = código, mensagem = CA em DER)`.
2. A estação baixa `GET https://<principal>:8443/api/stations/ca` (CA em PEM + prova), **sem confiar** no TLS dessa conexão.
3. Recalcula o HMAC com o código digitado; **só se conferir** instala a CA em "Autoridades de Certificação Raiz Confiáveis" da máquina (`certutil -addstore Root`, o instalador já roda como administrador) e registra a impressão digital instalada.
4. Abre o navegador em `https://<principal>:8443/#/parear?codigo=…` (o fragmento não vai ao servidor nem aos logs; a página o apaga do histórico), onde o código já vem preenchido e o usuário dá nome à estação.
5. Um atacante no meio teria de quebrar a prova offline: 2¹³⁰ (padrão) ou 2⁶⁵ (mínimo) tentativas, inviável nos 10 minutos de validade do código.

Limite que não se resolve no navegador: quem ignorar o aviso de certificado do navegador e parear sem o instalador perde essa proteção. A tela de pareamento avisa e o caminho suportado é o instalador.

**Recuperação após perda do principal (sem depender da chave antiga)**: nova instalação = nova CA. Restaurar o backup traz os dados, não a CA nem as estações. Em cada estação, rodar "Conectar à loja" de novo: o `conectar` remove do repositório do Windows a CA anterior que ele mesmo registrou e instala a nova. Se a chave antiga tiver sido roubada (não só perdida), remover a CA antiga de todas as estações é obrigatório (o `conectar` faz; manualmente: `certutil -delstore Root <impressão>`); as Name Constraints limitam o dano até lá.

**Limitações reais de Name Constraints e da confiança no Windows** (a verificar, parte em CI Windows e parte em máquina física):

- As restrições valem para os nomes do SAN. Sem subárvore de um tipo, nomes daquele tipo **não** ficam restritos — por isso a CA declara DNS **e** IP.
- O CN do assunto não é usado por navegadores modernos, mas verificadores antigos podem tratá-lo como nome DNS.
- O Windows (CryptoAPI) aplica Name Constraints na construção da cadeia; a CI verifica com `X509Chain` do .NET. Edge e Chrome usam a confiança do Windows para raízes instaladas localmente; o Firefox só com `security.enterprise_roots.enabled` (política). Comportamento dos navegadores: homologação física.
- Raiz instalada no repositório da máquina é confiada para **qualquer** uso que ela permita; as Name Constraints e o uso de chave limitam isso a servidores da loja.

## 3. Armazenamento

**Reavaliação dos 15 %**: com 15 % um disco de 1 TB precisa de 150 GB livres e um de 252 GB com 29 GB livres (a máquina da nuvem) recusa todo backup — protege demais e acaba suspendendo a proteção. Proposta implementada:

- **Reserva mínima** `min_free_gb` (padrão 10 GB): piso absoluto livre depois do backup, para o Windows, o banco e os arquivos temporários do SQLite.
- **Margem operacional**: `margin_percent` do disco (padrão 5 %), nunca menos que 2 × o tamanho do banco (crescimento e cópia temporária) e nunca mais que `margin_max_gb` (padrão 20 GB).
- Espaço livre exigido depois de gravar = reserva mínima + margem.

| Disco | Banco | Exigido livre depois do backup |
| --- | --- | --- |
| 64 GB | 200 MB | 10 + 3,2 = 13,2 GB |
| 256 GB | 1 GB | 10 + 12,8 = 22,8 GB |
| 1 TB | 2 GB | 10 + 20 = 30 GB |
| 2 TB | 5 GB | 10 + 20 = 30 GB |

Uma configuração salva com o campo antigo `min_free_percent` passa a usá-lo como `margin_percent`. O teto da pasta (10 GB) não muda.

**Cópia pre-upgrade**: antes de migrar, confere se cabe na pasta de backups mantendo a reserva mínima; se não, tenta a pasta de dados; se nenhuma, **não migra e não sobe** (código de saída 5, mensagem clara), deixando o banco intacto — libere espaço e inicie de novo. Mantém as 3 cópias pre-upgrade mais recentes.

**Falha de backup não bloqueia a operação comercial**: o backup roda fora das transações comerciais, segura a trava só durante a cópia, a libera em qualquer falha, não deixa arquivos parciais e é tentado de novo depois; testes cobrem disco cheio no meio da gravação, falha do banco temporário e trava liberada.

## 4. Qualidade e CI

`.github/workflows/ci.yml` (manual e a cada push em `master` e `p1/**`; o repositório é privado e o Windows consome minutos em dobro). Três jobs independentes, para uma falha não esconder as outras: Linux; Windows — testes do backend; Windows — instalador (`windows-2022`). Resultados por SHA em `VALIDATION.md`:

- **Linux**: ruff, pytest, frontend (lint, formato, Vitest, build), E2E e smoke.
- **Windows** (`windows-2022`): pytest completo (inclui `msvcrt`, DPAPI e ACL), Name Constraints com o verificador do Windows (`scripts/ci/name-constraints.ps1`), PyInstaller, Inno Setup, **instalação silenciosa** como principal com rede (`scripts/ci/windows-install-test.ps1`), início, saúde em HTTP local, HTTP ausente na rede, HTTPS recusado antes da confiança, `conectar` com código errado (nada instalado) e certo (CA na Raiz da máquina, HTTPS validado pelo Windows), `desconectar`, **atualização** preservando os dados, **desinstalação** preservando os dados, e artefato com o instalador e os logs.

Exige máquina física (não substituível pela CI): Windows limpo sem ferramentas de desenvolvimento, duas estações reais na mesma rede, navegadores (Edge, Chrome, Firefox) diante da CA e das Name Constraints, antivírus, pendrive/HD externo, queda de energia, uso por horas. **A CI Windows não é homologação.**
