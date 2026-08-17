#!/usr/bin/env python3
"""
OCI Auto Instance Creator Bot
==============================
Bot para criação automática de instâncias na Oracle Cloud Infrastructure (OCI)
com retry contínuo em caso de erro 'OutOfCapacity' (Falta de capacidade do host).
"""

import os
import sys
import time
import argparse
import logging
import tempfile
import datetime
from pathlib import Path

# Carregar variáveis de ambiente do .env se disponível
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import requests

try:
    import oci
except ImportError:
    print("[ERRO CRÍTICO] Biblioteca 'oci' não encontrada. Instale executando: pip install -r requirements.txt")
    sys.exit(1)

# Configuração de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("oci_bot")

def send_telegram(token: str, chat_id: str, message: str) -> bool:
    """Envia uma mensagem via Telegram Bot API."""
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.ok
    except Exception as e:
        logger.warning(f"Falha ao enviar notificação para o Telegram: {e}")
        return False

def send_discord(webhook_url: str, message: str) -> bool:
    """Envia uma mensagem via Discord Webhook."""
    if not webhook_url:
        return False
    payload = {"content": message}
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        return resp.ok
    except Exception as e:
        logger.warning(f"Falha ao enviar notificação para o Discord: {e}")
        return False

def notify_all(message: str):
    """Envia notificação para todos os canais configurados (Telegram/Discord)."""
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    discord_url = os.getenv("DISCORD_WEBHOOK_URL")

    sent_any = False
    if telegram_token and telegram_chat_id:
        if send_telegram(telegram_token, telegram_chat_id, message):
            sent_any = True
            logger.info("Notificação enviada com sucesso para o Telegram.")
    
    if discord_url:
        if send_discord(discord_url, message):
            sent_any = True
            logger.info("Notificação enviada com sucesso para o Discord.")
    
    return sent_any

def get_oci_config():
    """
    Constrói o dicionário de configuração da OCI.
    Prioriza variáveis de ambiente e fallback para arquivo ~/.oci/config.
    """
    def clean_str(val):
        return val.strip().replace("\r", "").replace("\n", "") if val else ""

    user_ocid = clean_str(os.getenv("OCI_USER_OCID"))
    tenancy_ocid = clean_str(os.getenv("OCI_TENANCY_OCID"))
    fingerprint = clean_str(os.getenv("OCI_FINGERPRINT"))
    region = clean_str(os.getenv("OCI_REGION"))
    key_file = clean_str(os.getenv("OCI_KEY_FILE"))
    key_content = os.getenv("OCI_KEY_CONTENT")
    config_file = clean_str(os.getenv("OCI_CONFIG_FILE", "~/.oci/config"))

    # Se as variáveis de ambiente principais existirem, constrói config dinâmico
    if user_ocid and tenancy_ocid and fingerprint and region:
        logger.info("Usando credenciais OCI fornecidas via variáveis de ambiente.")
        
        # Tratar a chave privada
        key_path = None
        if key_file and os.path.exists(os.path.expanduser(key_file)):
            key_path = os.path.expanduser(key_file)
        elif key_content:
            # Caso a chave venha como string (ex: GitHub Secrets)
            key_text = key_content.strip()
            key_text = key_text.replace("\r\n", "\n").replace("\r", "\n")
            if "\\n" in key_text:
                key_text = key_text.replace("\\n", "\n")
            if not key_text.endswith("\n"):
                key_text += "\n"
            
            # Grava em um arquivo temporário seguro
            temp_key = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".pem")
            temp_key.write(key_text)
            temp_key.close()
            key_path = temp_key.name
        else:
            logger.error("Chave privada OCI não informada! Defina OCI_KEY_FILE ou OCI_KEY_CONTENT.")
            sys.exit(1)

        config = {
            "user": user_ocid,
            "fingerprint": fingerprint,
            "key_file": key_path,
            "tenancy": tenancy_ocid,
            "region": region
        }
    else:
        # Fallback para o arquivo de configuração padrão do OCI CLI
        expanded_config = os.path.expanduser(config_file)
        if os.path.exists(expanded_config):
            logger.info(f"Carregando configuração OCI do arquivo: {expanded_config}")
            profile = os.getenv("OCI_PROFILE", "DEFAULT")
            config = oci.config.from_file(expanded_config, profile_name=profile)
        else:
            logger.error("Credenciais OCI não encontradas! Defina as variáveis de ambiente ou o arquivo ~/.oci/config.")
            sys.exit(1)

    oci.config.validate_config(config)
    return config

def get_vnic_ip(compute_client, network_client, instance_id: str, compartment_id: str) -> str:
    """Busca o IP público associado à instância recém-criada."""
    try:
        vnic_attachments = compute_client.list_vnic_attachments(
            compartment_id=compartment_id,
            instance_id=instance_id
        ).data
        if vnic_attachments and len(vnic_attachments) > 0:
            vnic_id = vnic_attachments[0].vnic_id
            vnic = network_client.get_vnic(vnic_id=vnic_id).data
            return vnic.public_ip or "IP Público não atribuído"
    except Exception as e:
        logger.warning(f"Não foi possível obter o IP público automaticamente: {e}")
    return "N/A"

def create_instance_retry_loop(args):
    """Loop principal de tentativas de criação de instância."""
    config = get_oci_config()
    compute_client = oci.core.ComputeClient(config)
    network_client = oci.core.VirtualNetworkClient(config)

    def clean_str(val):
        return val.strip().replace("\r", "").replace("\n", "") if val else ""

    # Parâmetros da instância
    compartment_id = clean_str(os.getenv("OCI_COMPARTMENT_OCID") or config.get("tenancy"))
    availability_domain = clean_str(os.getenv("OCI_AVAILABILITY_DOMAIN"))
    subnet_id = clean_str(os.getenv("OCI_SUBNET_OCID"))
    image_id = clean_str(os.getenv("OCI_IMAGE_OCID"))
    shape = clean_str(os.getenv("OCI_SHAPE", "VM.Standard.A1.Flex")) or "VM.Standard.A1.Flex"
    instance_name = clean_str(os.getenv("OCI_INSTANCE_NAME", "Oracle-Free-ARM")) or "Oracle-Free-ARM"
    ocpus = float(os.getenv("OCI_OCPUS", "4"))
    memory_in_gbs = float(os.getenv("OCI_MEMORY_IN_GBS", "24"))
    boot_volume_size = int(os.getenv("OCI_BOOT_VOLUME_SIZE_IN_GBS", "50"))
    ssh_public_key = os.getenv("OCI_SSH_PUBLIC_KEY", "").strip()

    # Validação mínima dos parâmetros obrigatórios
    missing = []
    if not availability_domain: missing.append("OCI_AVAILABILITY_DOMAIN")
    if not subnet_id: missing.append("OCI_SUBNET_OCID")
    if not image_id: missing.append("OCI_IMAGE_OCID")
    if not ssh_public_key: missing.append("OCI_SSH_PUBLIC_KEY")

    if missing:
        logger.error(f"Parâmetros obrigatórios ausentes nas variáveis de ambiente: {', '.join(missing)}")
        logger.error("Verifique seu arquivo .env ou Secrets do GitHub.")
        sys.exit(1)

    # Configuração de Shape Flex vs Standard
    shape_config = None
    if "Flex" in shape:
        shape_config = oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=ocpus,
            memory_in_gbs=memory_in_gbs
        )

    launch_details = oci.core.models.LaunchInstanceDetails(
        display_name=instance_name,
        compartment_id=compartment_id,
        availability_domain=availability_domain,
        shape=shape,
        shape_config=shape_config,
        source_details=oci.core.models.InstanceSourceViaImageDetails(
            source_type="image",
            image_id=image_id,
            boot_volume_size_in_gbs=boot_volume_size
        ),
        create_vnic_details=oci.core.models.CreateVnicDetails(
            subnet_id=subnet_id,
            assign_public_ip=True
        ),
        metadata={
            "ssh_authorized_keys": ssh_public_key
        }
    )

    if args.dry_run:
        logger.info("=== Modo DRY-RUN ativado ===")
        logger.info(f"Conexão com OCI verificada com sucesso!")
        logger.info(f"Região: {config.get('region')}")
        logger.info(f"Compartment: {compartment_id}")
        logger.info(f"Availability Domain: {availability_domain}")
        logger.info(f"Shape: {shape} ({ocpus} OCPUs, {memory_in_gbs} GB RAM)")
        logger.info(f"Subnet ID: {subnet_id}")
        logger.info(f"Image ID: {image_id}")
        logger.info(f"Nome da Instância: {instance_name}")
        logger.info(f"SSH Key carregada: {ssh_public_key[:30]}... ({len(ssh_public_key)} caracteres)")
        
        # Testar listagem de ADs para validar autenticação real na API
        try:
            identity_client = oci.identity.IdentityClient(config)
            ads = identity_client.list_availability_domains(compartment_id).data
            ad_names = [ad.name for ad in ads]
            logger.info(f"Autenticação API Ok. ADs disponíveis na tenancy: {ad_names}")
        except Exception as e:
            logger.error(f"Erro ao testar chamada API OCI: {e}")
            return
            
        logger.info("Nenhuma instância foi criada (Dry-run concluído).")
        return

    interval = args.interval or int(os.getenv("RETRY_INTERVAL", "60"))
    max_retries = args.max_retries
    timeout_minutes = args.timeout

    logger.info("🚀 Iniciando OCI Auto Instance Creator Bot...")
    logger.info(f"Alvo: Instância '{instance_name}' | Shape: {shape} ({ocpus} OCPU, {memory_in_gbs} GB)")
    logger.info(f"Região: {config.get('region')} | AD: {availability_domain}")
    logger.info(f"Intervalo entre tentativas: {interval}s")

    attempt = 0
    start_time = time.time()

    while True:
        attempt += 1
        elapsed_minutes = (time.time() - start_time) / 60.0

        if max_retries > 0 and attempt > max_retries:
            logger.warning(f"Limite máximo de tentativas ({max_retries}) atingido. Encerrando.")
            break

        if timeout_minutes > 0 and elapsed_minutes >= timeout_minutes:
            logger.warning(f"Tempo limite total ({timeout_minutes} min) atingido. Encerrando esta sessão.")
            break

        try:
            logger.info(f"🔄 Tentativa #{attempt} de criar instância '{instance_name}'...")
            response = compute_client.launch_instance(launch_details)
            instance = response.data

            success_msg = (
                f"🎉 **INSTÂNCIA CRIADA COM SUCESSO!** 🎉\n\n"
                f"• **Nome:** `{instance.display_name}`\n"
                f"• **ID:** `{instance.id}`\n"
                f"• **Região:** `{config.get('region')}`\n"
                f"• **Shape:** `{instance.shape}`\n"
                f"• **Status:** `{instance.lifecycle_state}`\n"
            )
            
            logger.info(f"✅ SUCESSO! Instância {instance.display_name} criada com ID: {instance.id}")
            logger.info("Aguardando 10s para buscar o IP Público...")
            time.sleep(10)

            public_ip = get_vnic_ip(compute_client, network_client, instance.id, compartment_id)
            success_msg += f"• **IP Público:** `{public_ip}`\n"

            # Notificar via Telegram / Discord
            notify_all(success_msg)
            
            logger.info("Bot finalizado com sucesso!")
            sys.exit(0)

        except oci.exceptions.ServiceError as e:
            # Lista de erros comuns de capacidade indisponível
            is_capacity_error = (
                e.status in (500, 502, 503, 504, 429) or
                "OutOfCapacity" in str(e.code) or
                "OutOfCapacity" in str(e.message) or
                "LimitExceeded" in str(e.code) or
                "TooManyRequests" in str(e.code) or
                "QuotaExceeded" in str(e.code) or
                "InternalError" in str(e.code)
            )

            if is_capacity_error:
                logger.warning(
                    f"⚠️ Tentativa #{attempt}: Capacidade indisponível na Oracle Cloud ({e.code or e.status}). "
                    f"Aguardando {interval}s para tentar novamente..."
                )
            else:
                fatal_msg = (
                    f"❌ **ERRO FATAL NA API OCI** ❌\n"
                    f"Status: `{e.status}` | Código: `{e.code}`\n"
                    f"Mensagem: `{e.message}`\n\n"
                    f"Verifique se seus OCIDs, SSH Key e configurações do .env estão corretos."
                )
                logger.error(f"Erro fatal da API OCI (Status {e.status}): {e.code} - {e.message}")
                notify_all(fatal_msg)
                sys.exit(1)

        except Exception as e:
            logger.error(f"Erro inesperado durante a tentativa #{attempt}: {e}")

        if args.once:
            logger.info("Modo --once ativado. Encerrando após 1 tentativa.")
            break

        time.sleep(interval)

def main():
    parser = argparse.ArgumentParser(description="OCI Auto Instance Creator Bot")
    parser.add_argument("--dry-run", action="store_true", help="Valida as credenciais e parâmetros sem criar a instância")
    parser.add_argument("--once", action="store_true", help="Executa apenas uma tentativa e sai")
    parser.add_argument("--interval", type=int, default=None, help="Intervalo em segundos entre cada tentativa")
    parser.add_argument("--max-retries", type=int, default=0, help="Número máximo de tentativas (0 para ilimitado)")
    parser.add_argument("--timeout", type=float, default=0, help="Tempo limite em minutos para o bot rodar nesta sessão")
    parser.add_argument("--test-notify", action="store_true", help="Testa o envio de notificações (Telegram/Discord) e sai")

    args = parser.parse_args()

    if args.test_notify:
        logger.info("Testando envio de notificações Telegram / Discord...")
        sent = notify_all("🔔 **Teste de Notificação Bot OCI Oracle**: O sistema de notificação está funcionando corretamente!")
        if not sent:
            logger.warning("Nenhum serviço de notificação configurado ou envio falhou. Verifique TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID ou DISCORD_WEBHOOK_URL.")
        sys.exit(0)

    create_instance_retry_loop(args)

if __name__ == "__main__":
    main()
