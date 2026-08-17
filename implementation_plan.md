# OCI Auto Instance Creator Bot (Oracle Cloud 24/7 Capacity Retry)

## Overview

Na Oracle Cloud (especialmente na modalidade **Always Free** com as instâncias ARM Ampere `VM.Standard.A1.Flex`), a mensagem **"Out of host capacity"** (fora de capacidade de host) é muito comum. A Oracle libera capacidade aleatoriamente quando outros usuários liberam VMs ou novos servidores são adicionados ao datacenter.

Para obter a VM sem precisar ficar tentando manualmente no painel, criaremos um **Bot de Tentativas Automáticas** com suporte a:
1. **Execução Remota 24/7 via GitHub Actions** (Não precisa deixar o computador ligado!).
2. **Execução Local / Cloud Shell** (opção para rodar no seu PC ou no Cloud Shell da Oracle).
3. **Notificação via Telegram ou Discord** assim que a instância for criada com sucesso.
4. **Tentativas contínuas com controle de taxa** (Backoff/Intervalo ajustável) para evitar bloqueio da API.

---

## Estrutura das Opções de Execução

### Opção 1: GitHub Actions (Recomendado - 24/7 na Nuvem Grátis)
- Um workflow rodando periodicamente no GitHub Actions.
- Utiliza **Secrets do GitHub** para guardar suas chaves da Oracle com total segurança.
- Notifica seu celular via **Telegram / Discord Webhook** quando a VM for criada.

### Opção 2: Script Python Local / Cloud Shell
- Script em Python utilizando o SDK Oficial da Oracle (`oci`).
- Pode ser executado em segundo plano no seu PC ou dentro do **OCI Cloud Shell** na própria web console da Oracle Cloud.

---

## Arquivos Propostos

### 1. [NEW] [oci_instance_bot.py](file:///d:/workspace/botoracle/oci_instance_bot.py)
Script Python principal que se conecta à API do OCI usando o SDK `oci`:
- Autentica com API Key RSA + Fingerprint.
- Tenta criar a instância com as configurações informadas (`VM.Standard.A1.Flex` ou `VM.Standard.E2.1.Micro`, OCPUs, Memória, Boot Volume, SSH Key).
- Trata os erros de falta de capacidade (`OutOfCapacity` / `500` / `LimitExceeded`).
- Envia notificação por Telegram/Discord e encerra com sucesso ao conseguir.

### 2. [NEW] [requirements.txt](file:///d:/workspace/botoracle/requirements.txt)
Dependências do bot em Python (`oci`, `requests`, `python-dotenv`).

### 3. [NEW] [.env.example](file:///d:/workspace/botoracle/.env.example)
Modelo de configuração com as variáveis de ambiente necessárias (OCIDs, Chave SSH, Region, etc.).

### 4. [NEW] [oci-instance-bot.yml](file:///d:/workspace/botoracle/.github/workflows/oci-instance-bot.yml)
Workflow do GitHub Actions para rodar o bot automaticamente em loop na nuvem do GitHub 24/7.

### 5. [NEW] [README.md](file:///d:/workspace/botoracle/README.md)
Guia passo a passo em Português ensinando como obter todas as credenciais necessárias na Oracle Cloud (User OCID, Tenancy OCID, Fingerprint, Private Key, Subnet, Image ID).

---

## Informações Necessárias da Oracle Cloud (Prerequisites)

Para o Bot funcionar, você precisará dos seguintes dados do seu painel Oracle Cloud:
1. **User OCID** e **Tenancy OCID** (Em *Identity & Security -> Users / Tenancy*).
2. **Compartment OCID** (Geralmente o mesmo que o Tenancy OCID no plano free).
3. **Region** (ex: `sa-saopaulo-1`, `us-ashburn-1`, `eu-frankfurt-1`).
4. **Availability Domain** (ex: `XXXX:SA-SAOPAULO-1-AD-1`).
5. **Subnet OCID** (da sua VCN padrão/Subnet pública).
6. **Image OCID** (ID da imagem Ubuntu 22.04 / 24.04 ou Oracle Linux na sua região).
7. **API Signing Key (RSA Private Key + Fingerprint)** (Gerada no painel em *Users -> API Keys*).
8. **Chave Pública SSH** (Sua chave SSH para acessar o servidor depois de criado, como a `ssh-key-2026-08-17.key.pub` já existente no repositório).

---

## Plan de Verificação

### Teste Inicial
1. Executar o script `oci_instance_bot.py` localmente em modo `--dry-run` ou com validação de credenciais para garantir que a autenticação na API da Oracle funciona.
2. Confirmar captura de erro `OutOfCapacity` tratado adequadamente sem quebrar o loop.
3. Testar envio da notificação via Telegram/Discord Webhook.

---

## User Review Required

> [!IMPORTANT]
> **Você precisará gerar uma API Key no painel da Oracle Cloud** para o bot autenticar nas APIs de infraestrutura. O processo leva 2 minutos e explicaremos o passo a passo no guia.
> Além disso, confirme se deseja usar **GitHub Actions** para rodar 24/7 sem custos na nuvem ou prefere rodar localmente no seu computador / OCI Cloud Shell.
