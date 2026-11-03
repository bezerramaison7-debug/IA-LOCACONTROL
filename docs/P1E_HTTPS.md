# LocaControl — Estudo do HTTPS local (P1-E)

Estudo pedido pela diretiva do arquiteto de 2026-11-03, que aprovou o HTTPS para o P1-E com **autoridade certificadora (CA) local por instalação**, certificados de servidor e provisionamento seguro das estações, **sem confiar na CA antes de uma verificação independente da sua identidade**. Nada disto está implementado; o P1-D continua em HTTP na rede privada, com o risco reafirmado na ADR-025.

## 1. Objetivo e limites

- **Protege contra**: captura e alteração do tráfego na rede da loja (cookies de estação e de sessão, dados comerciais em trânsito).
- **Não protege contra**: cópia do perfil do navegador ou de arquivos de uma estação (para isso existe a rotação com detecção de reuso, A1); programa malicioso no computador principal; quem tenha a chave privada da CA.
- Local-first: nada depende de internet, domínio público ou serviço externo.

## 2. Peças

| Peça | Onde fica | Validade | Observações |
| --- | --- | --- | --- |
| CA da loja (ECDSA P-256) | Pasta de dados do principal, chave cifrada com DPAPI de máquina e ACL só para SYSTEM e Administradores | 10 anos | **Name Constraints**: permite só o nome do computador, `nome.local` e os IPs privados — se vazar, não serve para outros sites |
| Certificado do servidor | Mesma pasta | 397 dias | SAN: nome do computador, `nome.local`, IPs privados atuais, `localhost`, `127.0.0.1` |
| Confiança na estação | Repositório "Autoridades de Certificação Raiz Confiáveis" do Windows | até a revogação | Máquina (exige administrador) ou usuário (aviso do Windows, vale só para aquele usuário) |

A chave da CA **não entra nos backups**: um backup copiado para outro lugar não deve permitir emitir certificados da loja. Reinstalar o principal sem a pasta de dados implica nova CA (seção 6).

## 3. Provisionamento seguro da estação

O ponto difícil é a CA ser baixada por HTTP antes de existir confiança: quem estiver no meio pode trocá-la. A identidade da CA precisa ser verificada por um canal independente.

**Proposta (pareamento + verificação da CA no mesmo passo):**

1. No principal, **Estações da rede → Gerar código** mostra um código de pareamento de **≥ 64 bits** (13 caracteres, `XXXX-XXXX-XXXX-X`, alfabeto sem 0/O/1/I) e a **impressão digital da CA** (SHA-256 abreviado em 4 grupos de 4 caracteres) para conferência visual opcional.
2. O instalador "Conectar à loja" da estação pede o código e baixa a CA por HTTP junto com `HMAC-SHA256(código, CA em DER)`.
3. A estação recalcula o HMAC com o código digitado. **Só se conferir** importa a CA e passa a falar HTTPS; o pareamento propriamente dito (troca do código pelo token) já é feito por HTTPS.
4. O código continua de uso único e vale 10 minutos; erros contam como hoje.

Por que ≥ 64 bits: um HMAC capturado permite força bruta **offline**. Com o código atual (~40 bits, cerca de 10¹² tentativas) isso leva minutos numa GPU; com 64 bits leva milhares de anos. A conferência visual da impressão digital é a alternativa para quem não usar o instalador (exige ≥ 64 bits exibidos; 32 bits podem ser falsificados com uma segunda pré-imagem por força bruta).

**Navegadores**: Edge e Chrome usam o repositório do Windows. Firefox usa o próprio, a menos que `security.enterprise_roots.enabled` esteja ligado (política `ImportEnterpriseRoots`) — **a confirmar na homologação**; a recomendação para as estações é Edge ou Chrome.

## 4. Operação

- O servidor passa a escutar **só HTTPS na rede** (por exemplo na porta 8443) e mantém HTTP apenas em `127.0.0.1` para o próprio principal, ou também usa HTTPS em `https://localhost` (o principal confia na própria CA).
- Cookies com `Secure`; `allowed_origins` e a verificação de `Origin` passam a usar `https://`.
- Firewall do Windows: regra só para a porta HTTPS e só para a sub-rede local (instalador).
- Dependência nova: `cryptography` para gerar chaves e certificados; o uvicorn já aceita `ssl_certfile`/`ssl_keyfile`.

## 5. Renovação

- **Certificado do servidor**: reemitido sozinho na partida e numa verificação diária quando faltarem 30 dias, ou quando o nome ou os IPs do computador mudarem (DHCP). Como é assinado pela CA já confiada, **as estações não fazem nada**.
- **CA**: 10 anos. Seis meses antes, a tela avisa; a troca é planejada (seção 6). Uma nova CA exige confiar de novo em cada estação.

## 6. Revogação e recuperação

| Situação | Procedimento |
| --- | --- |
| Estação perdida ou suspeita | Revogar a estação (já existe). Opcional: remover a CA dela (`certutil -delstore Root <impressão>`). O certificado não precisa ser revogado: ele é do servidor |
| Certificado do servidor comprometido | Reemitir (botão no principal); o antigo deixa de ser servido. Sem CRL/OCSP (não há infraestrutura); o dano fica limitado pelas Name Constraints |
| Chave da CA comprometida ou principal reinstalado do zero | Gerar nova CA; em cada estação remover a antiga, rodar "Conectar à loja" de novo e parear |
| Disco do principal perdido, com backup | Restaurar o backup num principal novo **não** traz a CA: nova CA e novo pareamento das estações |
| Troca planejada do principal (mesma loja) | Copiar a pasta de dados inteira (inclui CA cifrada por DPAPI de máquina — **não funciona em outra máquina**); por isso a troca de máquina também implica nova CA, salvo exportação explícita protegida por senha (a decidir) |

## 7. Riscos e decisões pendentes

1. Exportação protegida da CA para troca de máquina: permitir (com senha) ou exigir sempre nova CA?
2. Confiança por máquina × por usuário na estação (administrador disponível na instalação?).
3. Porta HTTPS e convivência com HTTP no principal.
4. Firefox nas estações: suportar via política ou recomendar outro navegador.
5. Validar no Windows: instalação com e sem administrador, troca de IP, renovação automática, Edge/Chrome/Firefox, antivírus inspecionando TLS.

## 8. Critérios de aceite para o P1-E

- A estação só confia na CA depois de o HMAC com o código conferir (teste com CA trocada no meio: deve recusar).
- Nenhum cookie trafega sem TLS na rede; HTTP na rede responde redirecionamento ou não escuta.
- Renovação do certificado sem ação nas estações (teste com relógio adiantado).
- Revogação de estação e troca de CA documentadas e ensaiadas no Windows.
