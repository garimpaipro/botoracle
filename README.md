# 🤖 OCI Auto Instance Creator Bot (Oracle Cloud Always Free Retry)

Bot automatizado em Python para criação contínua de instâncias **Always Free** (ARM Ampere / AMD) na **Oracle Cloud Infrastructure (OCI)** com superação do erro `"Out of host capacity"`.

---

## ⚡ Recursos Principais
- 🔄 **Retry Automático 24/7:** Tentativas contínuas com tratamento do erro `OutOfCapacity` / `500` / `QuotaExceeded`.
- ☁️ **GitHub Actions Integrado:** Roda na nuvem 24h por dia gratuitamente sem precisar deixar o computador ligado.
- 📱 **Notificações em Tempo Real:** Alertas via **Telegram** e/ou **Discord Webhook** assim que a máquina for criada (ou em caso de credencial inválida).
- 🛡️ **Segurança Total:** Suporta credenciais via `.env` (local) ou GitHub Secrets (nuvem).
- 🧪 **Modo Dry-Run:** Teste a validação das chaves API e parâmetros sem criar recursos na nuvem.

---

## 📋 Pré-requisitos (Obtendo os Dados na Oracle Cloud)

Você precisará coletar as seguintes informações no painel da Oracle Cloud:

| Variável | Onde Encontrar na Oracle Cloud | Exemplo |
| :--- | :--- | :--- |
| `OCI_USER_OCID` | Perfil do Usuário -> `User OCID` | `ocid1.user.oc1..aaaa...` |
| `OCI_TENANCY_OCID` | Configurações da Conta -> `Tenancy OCID` | `ocid1.tenancy.oc1..aaaa...` |
| `OCI_COMPARTMENT_OCID` | Mesmo do Tenancy (ou em *Identity -> Compartments*) | `ocid1.tenancy.oc1..aaaa...` |
| `OCI_REGION` | Canto superior direito do painel Oracle | `sa-saopaulo-1` ou `us-ashburn-1` |
| `OCI_AVAILABILITY_DOMAIN` | Ao clicar em criar instância (ex: `XXXX:SA-SAOPAULO-1-AD-1`) | `pAKk:SA-SAOPAULO-1-AD-1` |
| `OCI_SUBNET_OCID` | Networking -> Virtual Cloud Networks -> Sua Subnet Pública | `ocid1.subnet.oc1.sa-saopaulo-1...` |
| `OCI_IMAGE_OCID` | Ao selecionar imagem (Ubuntu/Oracle Linux) -> Detalhes da Imagem | `ocid1.image.oc1.sa-saopaulo-1...` |
| `OCI_SSH_PUBLIC_KEY` | Sua chave pública SSH (conteúdo da `.pub` ou string `ssh-rsa ...`) | `ssh-rsa AAAAB3Nza...` |
| `OCI_FINGERPRINT` | Gerado ao adicionar API Key no usuário | `aa:bb:cc:dd:ee:...` |
| `OCI_KEY_CONTENT` | Conteúdo da chave privada RSA (arquivo `.pem`) | `-----BEGIN RSA PRIVATE KEY-----...` |

---

## 🔑 Como Gerar a API Key na Oracle Cloud

1. No painel da Oracle Cloud, clique no ícone de perfil no canto superior direito e selecione **My Profile** (ou **User Settings**).
2. No menu lateral esquerdo, clique em **API Keys**.
3. Clique em **Add API Key**.
4. Selecione **Generate API Key Pair** e clique em **Download Private Key** (salve o arquivo `.pem`).
5. Clique em **Add**.
6. Copie a caixa de texto **Configuration File Preview** contendo o `fingerprint`, `tenancy`, `user`, etc.

---

## 🚀 Modos de Execução

Você pode escolher a forma que for mais conveniente:

### 🌟 Opção 1: Direto no OCI Cloud Shell (Sem GitHub / Sem Chaves RSA)
Se você **não quer subir nada para o GitHub** nem precisa configurar API Keys/Secrets:
1. No painel da Oracle Cloud, abra o **Cloud Shell** (ícone `>_` no canto superior direito).
2. Crie o arquivo do script no terminal do Cloud Shell:
   ```bash
   nano cloudshell_bot.sh
   ```
3. Cole o conteúdo de [`cloudshell_bot.sh`](file:///d:/workspace/botoracle/cloudshell_bot.sh) e preencha suas variáveis (`COMPARTMENT_ID`, `SUBNET_ID`, `IMAGE_ID`, `AVAILABILITY_DOMAIN`).
4. Dê permissão e execute:
   ```bash
   chmod +x cloudshell_bot.sh
   ./cloudshell_bot.sh
   ```
*Nota: O Cloud Shell é autenticado automaticamente pela Oracle. Mantenha a aba aberta enquanto o bot estiver tentando.*

---

### ☁️ Opção 2: 24/7 via GitHub Actions (Roda na Nuvem sem Computador Ligado)
1. Faça um fork ou push deste repositório para o seu **GitHub**.
2. Vá em **Settings -> Secrets and variables -> Actions** do seu repositório.
3. Adicione as Secrets listadas abaixo:
   - `OCI_USER_OCID`, `OCI_TENANCY_OCID`, `OCI_COMPARTMENT_OCID`
   - `OCI_FINGERPRINT`, `OCI_REGION`, `OCI_KEY_CONTENT`
   - `OCI_AVAILABILITY_DOMAIN`, `OCI_SUBNET_OCID`, `OCI_IMAGE_OCID`, `OCI_SSH_PUBLIC_KEY`
4. Na aba **Actions**, execute o workflow **OCI Auto Instance Creator Bot**.

---

### 💻 Opção 3: Execução no seu Computador (Local)
1. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

2. Copie o modelo `.env.example` para `.env`:
   ```bash
   cp .env.example .env
   ```

3. Edite o arquivo `.env` preenchendo suas credenciais da Oracle Cloud.

4. Teste a conexão em modo Dry-Run:
   ```bash
   python oci_instance_bot.py --dry-run
   ```

5. Teste o envio de notificações:
   ```bash
   python oci_instance_bot.py --test-notify
   ```

6. Inicie o bot em loop continuo:
   ```bash
   python oci_instance_bot.py
   ```

---

## 📱 Configurando Notificações

### Telegram
1. Fale com o `@BotFather` no Telegram para criar um bot e obter o `TELEGRAM_BOT_TOKEN`.
2. Fale com o `@userinfobot` para obter o seu `TELEGRAM_CHAT_ID`.

### Discord
1. No seu servidor Discord, vá nas **Configurações do Canal -> Integrações -> Webhooks**.
2. Clique em **Novo Webhook** e copie o URL gerado para `DISCORD_WEBHOOK_URL`.

---

## 🛠️ Opções da Linha de Comando (CLI)

```bash
# Executar validação sem criar a VM
python oci_instance_bot.py --dry-run

# Executar apenas uma tentativa e sair
python oci_instance_bot.py --once

# Alterar o intervalo para 30 segundos
python oci_instance_bot.py --interval 30

# Definir tempo máximo da sessão para 10 minutos
python oci_instance_bot.py --timeout 10
```

---

## 📝 Licença
MIT License. Livre para uso e modificação.
