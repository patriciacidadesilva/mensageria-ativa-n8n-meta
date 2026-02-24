import os
import re
import time
import logging
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

# =========================
# Logger
# =========================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# =========================
# Env
# =========================
load_dotenv()

CAMINHO_ARQUIVO = os.getenv("CAMINHO_ARQUIVO")  # "." ou vazio ou absoluto
ARQUIVO_EXCEL = os.getenv("ARQUIVO_EXCEL", "contatos_comercial.xlsx")

URL_N8N = (os.getenv("URL_N8N") or "").strip()
USUARIO_N8N = (os.getenv("USUARIO_N8N") or "").strip()
SENHA_N8N = (os.getenv("SENHA_N8N") or "").strip()

# Workflow PostImagem (upload)
URL_N8N_IMG_POST = (os.getenv("URL_N8N_IMG_POST") or "").strip()
FOTO = (os.getenv("FOTO") or "").strip()  # ex: imagem_dexia.png

# Coluna do Excel
COLUNA_CELULAR = "Celular"

# Controle de taxa
DELAY_ENTRE_REQUESTS = float(os.getenv("DELAY_ENTRE_REQUESTS", "0.5"))


# =========================
# Utilitários
# =========================
def validar_variaveis():
    obrigatorias = {
        "URL_N8N": URL_N8N,
        "USUARIO_N8N": USUARIO_N8N,
        "SENHA_N8N": SENHA_N8N,
    }
    for nome, valor in obrigatorias.items():
        if not valor:
            raise ValueError(f"A variável de ambiente {nome} não está definida (ou está vazia) no .env")

    # Se quiser enviar imagem, precisa dessas duas
    if FOTO and not URL_N8N_IMG_POST:
        raise ValueError("FOTO foi definida, mas URL_N8N_IMG_POST não está definida no .env")

    # Webhook-test não serve para lote
    if URL_N8N_IMG_POST and "webhook-test" in URL_N8N_IMG_POST:
        raise ValueError(
            "URL_N8N_IMG_POST está apontando para webhook-test. "
            "Troque para a Production URL (/webhook/...) e ative o workflow PostImagem."
        )


def montar_caminho_excel() -> Path:
    """
    1) CAMINHO_ARQUIVO absoluto -> usa ele
    2) CAMINHO_ARQUIVO relativo -> relativo ao script
    3) vazio -> pasta do script
    """
    base_script = Path(__file__).resolve().parent

    if CAMINHO_ARQUIVO:
        p = Path(CAMINHO_ARQUIVO)
        pasta = p if p.is_absolute() else (base_script / p)
    else:
        pasta = base_script

    caminho_excel = (pasta / ARQUIVO_EXCEL).resolve()
    if not caminho_excel.exists():
        raise FileNotFoundError(f"Arquivo Excel não encontrado: {caminho_excel}")

    return caminho_excel


def normalizar_telefone(valor):
    """
    Normaliza telefone para wa_id:
    - remove tudo que não for dígito
    - adiciona DDI 55 se não existir
    Retorna string tipo: 5511999999999
    """
    if pd.isna(valor):
        return None

    somente = re.sub(r"\D", "", str(valor))
    if not somente:
        return None

    # Já tem DDI
    if somente.startswith("55"):
        # 55 + DDD + número
        if len(somente) in (12, 13):
            return somente
        # deixa passar (vai aparecer mismatch/erro no relatório)
        return somente

    # Sem DDI: DDD(2) + número (8/9) => 10/11
    if len(somente) in (10, 11):
        return "55" + somente

    return None


def guess_mime_type(p: Path) -> str:
    ext = p.suffix.lower()
    if ext in [".jpg", ".jpeg"]:
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".webp":
        return "image/webp"
    return "application/octet-stream"


# =========================
# PostImagem -> media_id
# =========================
def upload_imagem_n8n(caminho_imagem: str, max_retries=3) -> str:
    """
    Envia multipart com campo 'file' (porque o node Upload media está com mediaPropertyName='file')
    e espera resposta JSON: {"media_id":"..."}
    """
    img_path = Path(caminho_imagem).expanduser().resolve()
    if not img_path.exists():
        raise FileNotFoundError(f"Imagem não encontrada em: {img_path}")

    mime = guess_mime_type(img_path)

    for tentativa in range(max_retries):
        try:
            with open(img_path, "rb") as f:
                files = {"file": (img_path.name, f, mime)}
                resp = requests.post(
                    URL_N8N_IMG_POST,
                    auth=(USUARIO_N8N, SENHA_N8N),
                    files=files,
                    timeout=60,
                )

            if resp.status_code == 200:
                data = resp.json()
                media_id = data.get("media_id")
                if not media_id:
                    raise ValueError(f"Resposta 200 sem media_id. Body: {data}")
                return media_id

            logger.warning(f"Upload imagem falhou (status {resp.status_code}): {resp.text}")

        except requests.exceptions.RequestException as e:
            logger.warning(f"Tentativa {tentativa + 1}/{max_retries} upload imagem falhou: {e}")

        time.sleep(2 ** tentativa)

    raise RuntimeError("Máximo de tentativas excedidas no upload da imagem")


# =========================
# MensageriaAtivaWA_v01
# =========================
def chamar_workflow_mensagem(wa_id: str, media_id: str | None, max_retries=3):
    """
    POST JSON para o webhook do workflow de mensagem.
    Retorna dict com:
      - status_http
      - json (quando conseguir parsear)
      - raw_text
      - erro
    """
    payload = {"wa_id": wa_id}
    if media_id:
        payload["media_id"] = media_id

    last_text = None

    for tentativa in range(max_retries):
        try:
            resp = requests.post(
                URL_N8N,
                auth=(USUARIO_N8N, SENHA_N8N),
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=60,
            )

            last_text = resp.text

            # ok
            if resp.status_code == 200:
                try:
                    return {
                        "status_http": 200,
                        "json": resp.json(),
                        "raw_text": resp.text,
                        "erro": None,
                    }
                except Exception:
                    return {
                        "status_http": 200,
                        "json": None,
                        "raw_text": resp.text,
                        "erro": "Resposta 200, mas não foi possível parsear JSON",
                    }

            # rate limit
            if resp.status_code == 429:
                logger.warning("Rate limit (429). Aguardando 5s...")
                time.sleep(5)
                continue

            logger.warning(f"Erro {resp.status_code} para {wa_id}: {resp.text}")

        except requests.exceptions.RequestException as e:
            last_text = str(e)
            logger.warning(f"Tentativa {tentativa + 1}/{max_retries} falhou para {wa_id}: {e}")

        time.sleep(2 ** tentativa)

    return {
        "status_http": None,
        "json": None,
        "raw_text": last_text,
        "erro": "Máximo de tentativas excedidas",
    }


def _normalizar_resposta_n8n(obj):
    """
    O n8n pode responder de várias formas:
      - dict direto {contacts:..., messages:...}
      - dict full response {statusCode:..., body:{...}}
      - lista [ {...} ]
    Aqui devolvemos sempre o dict "útil" (onde estão contacts/messages).
    """
    if obj is None:
        return None

    # lista -> primeiro item
    if isinstance(obj, list) and obj:
        obj = obj[0]

    if not isinstance(obj, dict):
        return None

    # full response -> body
    if "body" in obj and isinstance(obj["body"], dict):
        return obj["body"]

    return obj


def extrair_input_waid(resposta_json):
    """
    Extrai:
      contacts[0].input / wa_id
      messages[0].id / message_status
    """
    obj = _normalizar_resposta_n8n(resposta_json)
    if not isinstance(obj, dict):
        return None, None, None, None

    input_ret = None
    wa_id_ret = None
    message_id = None
    message_status = None

    contacts = obj.get("contacts") or []
    if contacts and isinstance(contacts[0], dict):
        input_ret = contacts[0].get("input")
        wa_id_ret = contacts[0].get("wa_id")

    messages = obj.get("messages") or []
    if messages and isinstance(messages[0], dict):
        message_id = messages[0].get("id")
        message_status = messages[0].get("message_status")

    return input_ret, wa_id_ret, message_id, message_status


# =========================
# Main
# =========================
if __name__ == "__main__":
    validar_variaveis()

    caminho_excel = montar_caminho_excel()
    logger.info(f"URL_N8N: {URL_N8N}")
    logger.info(f"URL_N8N_IMG_POST: {URL_N8N_IMG_POST if URL_N8N_IMG_POST else '(sem upload)'}")
    logger.info(f"FOTO: {FOTO if FOTO else '(sem foto)'}")
    logger.info(f"Lendo Excel em: {caminho_excel}")

    dados = pd.read_excel(caminho_excel, engine="openpyxl")
    if COLUNA_CELULAR not in dados.columns:
        raise ValueError(f"Coluna '{COLUNA_CELULAR}' não existe no Excel. Colunas: {list(dados.columns)}")

    # Upload 1x e reutiliza media_id
    media_id_global = None
    if FOTO:
        logger.info("Fazendo upload da imagem (1x) para obter media_id...")
        media_id_global = upload_imagem_n8n(FOTO)
        logger.info(f"media_id obtido: {media_id_global}")

    logger.info(f"Carregadas {len(dados)} linhas do Excel. Iniciando processamento...")

    linhas_relatorio = []

    for idx, linha in dados.iterrows():
        telefone_original = linha[COLUNA_CELULAR]
        wa_id_enviado = normalizar_telefone(telefone_original)

        if not wa_id_enviado:
            linhas_relatorio.append({
                "telefone_original": telefone_original,
                "wa_id_normalizado_enviado": None,
                "input_retorno": None,
                "wa_id_retorno": None,
                "match": "Não",
                "status_http": None,
                "message_status": None,
                "message_id": None,
                "erro": "Telefone inválido / não normalizado",
            })
            continue

        logger.info(f"[{idx+1}/{len(dados)}] Enviando para wa_id={wa_id_enviado} ...")

        resp = chamar_workflow_mensagem(
            wa_id=wa_id_enviado,
            media_id=media_id_global,
            max_retries=3,
        )

        input_ret, wa_id_ret, message_id, message_status = extrair_input_waid(resp.get("json"))

        match = "Sim" if (
            input_ret is not None and wa_id_ret is not None and str(input_ret) == str(wa_id_ret)
        ) else "Não"

        linhas_relatorio.append({
            "telefone_original": telefone_original,
            "wa_id_normalizado_enviado": wa_id_enviado,
            "input_retorno": input_ret,
            "wa_id_retorno": wa_id_ret,
            "match": match,
            "status_http": resp.get("status_http"),
            "message_status": message_status,
            "message_id": message_id,
            "erro": resp.get("erro") if resp.get("erro") else None,
        })

        time.sleep(DELAY_ENTRE_REQUESTS)

    # Salvar relatório
    df_rel = pd.DataFrame(linhas_relatorio)

    # opcional: ordenar para ver primeiro os "Não"
    ordem = {"Não": 0, "Sim": 1}
    df_rel["_ord"] = df_rel["match"].map(ordem).fillna(2)
    df_rel = df_rel.sort_values(["_ord", "telefone_original"], ascending=[True, True]).drop(columns=["_ord"])

    saida_xlsx = caminho_excel.parent / "relatorio_input_waid_mensageria.xlsx"
    df_rel.to_excel(saida_xlsx, index=False)
    logger.info(f"Relatório salvo em: {saida_xlsx}")