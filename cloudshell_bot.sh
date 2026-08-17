#!/bin/bash
# ==============================================================================
# OCI Cloud Shell Auto Instance Creator Bot (Com Detecção Automática)
# ==============================================================================

# --- CONFIGURAÇÃO DE RECURSOS (Always Free) ---
OCPUS=2                        # 2 OCPUs (Always Free permite até 4 no total)
MEMORY_IN_GBS=12               # 12 GB RAM (Always Free permite até 24 no total)
BOOT_VOLUME_SIZE=50            # Tamanho do disco em GB (Always Free permite até 200GB no total)
INSTANCE_NAME="Oracle-Free-ARM"
INTERVAL=60                    # Intervalo entre tentativas em segundos

# --- NOTIFICAÇÕES (OPCIONAL) ---
TELEGRAM_BOT_TOKEN=""
TELEGRAM_CHAT_ID=""
DISCORD_WEBHOOK_URL=""

# --- DADOS OCI (Preenchimento manual opcional caso queira fixar) ---
COMPARTMENT_ID=""              
AVAILABILITY_DOMAIN=""         
SUBNET_ID=""                   
IMAGE_ID=""                    
SSH_AUTHORIZED_KEYS_FILE="$HOME/.ssh/id_rsa.pub"

# ==============================================================================
echo "========================================================="
echo "🔍 Detectando configurações da sua conta Oracle Cloud..."
echo "========================================================="

# 1. Obter Tenancy / Compartment ID (Cloud Shell exporta $OCI_TENANCY nativamente)
if [ -z "$COMPARTMENT_ID" ]; then
    echo "• Buscando Tenancy OCID..."
    COMPARTMENT_ID="${OCI_TENANCY:-$TENANCY_OCID}"
    
    if [ -z "$COMPARTMENT_ID" ]; then
        # Tentar via OCI CLI sem silenciar erros críticos
        COMPARTMENT_ID=$(oci iam compartment list --query "data[0].\"compartment-id\"" --raw-output 2>/dev/null)
    fi
fi

if [ -z "$COMPARTMENT_ID" ] || [ "$COMPARTMENT_ID" = "None" ]; then
    echo "❌ Tenancy OCID não encontrado automaticamente."
    echo "Digite ou cole seu Tenancy OCID (Começa com ocid1.tenancy.oc1..):"
    read -r COMPARTMENT_ID
fi
echo "  -> Compartment/Tenancy: $COMPARTMENT_ID"

# 2. Obter Availability Domain (AD)
if [ -z "$AVAILABILITY_DOMAIN" ]; then
    echo "• Buscando Availability Domain..."
    AVAILABILITY_DOMAIN=$(oci iam availability-domain list --compartment-id "$COMPARTMENT_ID" --query "data[0].name" --raw-output 2>/dev/null)
fi

if [ -z "$AVAILABILITY_DOMAIN" ] || [ "$AVAILABILITY_DOMAIN" = "None" ]; then
    echo "⚠️ Não foi possível listar o AD. Digite o seu Availability Domain (Ex: pAKk:SA-SAOPAULO-1-AD-1):"
    read -r AVAILABILITY_DOMAIN
fi
echo "  -> Availability Domain: $AVAILABILITY_DOMAIN"

# 3. Obter Subnet Pública
if [ -z "$SUBNET_ID" ]; then
    echo "• Buscando Subnet da sua VCN..."
    SUBNET_ID=$(oci network subnet list --compartment-id "$COMPARTMENT_ID" --query "data[0].id" --raw-output 2>/dev/null)
fi

if [ -z "$SUBNET_ID" ] || [ "$SUBNET_ID" = "None" ]; then
    echo ""
    echo "⚠️ Nenhuma Subnet pública foi encontrada automaticamente."
    echo "Se você já criou uma VCN, cole o OCID da sua Subnet pública (ocid1.subnet...):"
    read -r SUBNET_ID
fi
echo "  -> Subnet OCID: $SUBNET_ID"

# 4. Obter Imagem Ubuntu ARM
if [ -z "$IMAGE_ID" ]; then
    echo "• Buscando imagem Ubuntu ARM (aarch64)..."
    IMAGE_ID=$(oci compute image list --compartment-id "$COMPARTMENT_ID" \
        --shape "VM.Standard.A1.Flex" \
        --operating-system "Canonical Ubuntu" \
        --sort-by TIMECREATED --sort-order DESC \
        --query "data[0].id" --raw-output 2>/dev/null)
    
    # Fallback para Oracle Linux caso Ubuntu não retorne
    if [ -z "$IMAGE_ID" ] || [ "$IMAGE_ID" = "None" ]; then
        IMAGE_ID=$(oci compute image list --compartment-id "$COMPARTMENT_ID" \
            --shape "VM.Standard.A1.Flex" \
            --operating-system "Oracle Linux" \
            --sort-by TIMECREATED --sort-order DESC \
            --query "data[0].id" --raw-output 2>/dev/null)
    fi
fi

if [ -z "$IMAGE_ID" ] || [ "$IMAGE_ID" = "None" ]; then
    echo "⚠️ Não foi possível auto-detectar a imagem. Cole o Image OCID:"
    read -r IMAGE_ID
fi
echo "  -> Image OCID: $IMAGE_ID"

# Validação Final
if [ -z "$COMPARTMENT_ID" ] || [ -z "$AVAILABILITY_DOMAIN" ] || [ -z "$SUBNET_ID" ] || [ -z "$IMAGE_ID" ]; then
    echo ""
    echo "❌ Faltam dados obrigatórios para iniciar. Verifique as configurações acima."
    exit 1
fi

# 5. Garantir Chave SSH
if [ ! -f "$SSH_AUTHORIZED_KEYS_FILE" ]; then
    echo "• Chave SSH não encontrada em $SSH_AUTHORIZED_KEYS_FILE. Gerando par de chaves..."
    mkdir -p ~/.ssh
    ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N "" -q
    echo "  -> Chave SSH gerada com sucesso em ~/.ssh/id_rsa.pub"
fi

echo ""
echo "========================================================="
echo "🚀 Iniciando Bot de Tentativas (Always Free ARM)"
echo "• Nome da Instância: $INSTANCE_NAME"
echo "• Shape: VM.Standard.A1.Flex ($OCPUS OCPUs / ${MEMORY_IN_GBS}GB RAM)"
echo "• Disco de Boot: ${BOOT_VOLUME_SIZE}GB"
echo "• Intervalo: ${INTERVAL}s"
echo "• Região: ${OCI_REGION:-sa-saopaulo-1}"
echo "========================================================="

notify() {
    local msg="$1"
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}&text=${msg}&parse_mode=Markdown" > /dev/null 2>&1
    fi
    if [ -n "$DISCORD_WEBHOOK_URL" ]; then
        curl -s -H "Content-Type: application/json" \
            -X POST -d "{\"content\": \"${msg}\"}" "${DISCORD_WEBHOOK_URL}" > /dev/null 2>&1
    fi
}

attempt=0

while true; do
    attempt=$((attempt+1))
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🔄 Tentativa #$attempt de criar '$INSTANCE_NAME'..."

    OUTPUT=$(oci compute instance launch \
        --compartment-id "$COMPARTMENT_ID" \
        --availability-domain "$AVAILABILITY_DOMAIN" \
        --shape "VM.Standard.A1.Flex" \
        --shape-config "{\"ocpus\": $OCPUS, \"memoryInGBs\": $MEMORY_IN_GBS}" \
        --subnet-id "$SUBNET_ID" \
        --image-id "$IMAGE_ID" \
        --display-name "$INSTANCE_NAME" \
        --assign-public-ip true \
        --boot-volume-size-in-gbs "$BOOT_VOLUME_SIZE" \
        --ssh-authorized-keys-file "$SSH_AUTHORIZED_KEYS_FILE" 2>&1)
    
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo "========================================================="
        echo "🎉 INSTÂNCIA CRIADA COM SUCESSO!"
        echo "========================================================="
        echo "$OUTPUT"
        
        SUCCESS_MSG="🎉 *INSTÂNCIA OCI CRIADA COM SUCESSO!* 🎉%0ANome: \`$INSTANCE_NAME\`%0AShape: \`VM.Standard.A1.Flex (${OCPUS} OCPU / ${MEMORY_IN_GBS}GB)\`"
        notify "$SUCCESS_MSG"
        break
    fi

    # Tratar falta de capacidade
    if echo "$OUTPUT" | grep -iqE "Out of host capacity|OutOfCapacity|TooManyRequests|LimitExceeded|500"; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️ Sem capacidade no momento (Out of host capacity). Tentando novamente em ${INTERVAL}s..."
    else
        echo "========================================================="
        echo "❌ ERRO NA CHAMADA DA API:"
        echo "$OUTPUT"
        echo "========================================================="
        break
    fi

    sleep "$INTERVAL"
done
