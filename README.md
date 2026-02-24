<div align="center">

# 🤖 Projeto Débora  
### Assistente Virtual de Comunicação via WhatsApp

Automação • n8n • WhatsApp Cloud API • Python • Excel • Templates com Mídia

<br>

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![n8n](https://img.shields.io/badge/n8n-Workflow%20Automation-orange)
![Meta API](https://img.shields.io/badge/WhatsApp-Cloud%20API-25D366?logo=whatsapp&logoColor=white)
![Status](https://img.shields.io/badge/status-estável-brightgreen)
![License](https://img.shields.io/badge/license-interno-lightgrey)

</div>

---

Projeto de automação para envio estruturado de mensagens ativas via WhatsApp, utilizando **n8n + WhatsApp Cloud API (Meta Graph API)**.

Este repositório contém:

- ✅ Workflows n8n (upload de mídia + envio de template)
- ✅ Script Python para carga em lote via Excel
- ✅ Controle de taxa (rate limit)
- ✅ Retry automático com backoff exponencial
- ✅ Relatório estruturado de rastreabilidade
- ✅ Configuração segura via variáveis de ambiente

---

# 📌 Visão Geral da Arquitetura
```text
Excel → carga.py → Webhook n8n → WhatsApp Cloud API → Destinatário
                                 ↓
                           Relatório de envio
```

---

## 📌 Sobre o Projeto

A **Débora** é a nova assistente virtual de comunicação via WhatsApp, criada para estruturar e modernizar o relacionamento digital.

Este projeto permite:

- 📤 Upload dinâmico de imagens
- 📩 Envio de templates aprovados
- 📊 Carga estruturada de contatos
- 📑 Registro e controle de erros
- 🔐 Versionamento seguro sem exposição de credenciais

---

### Fluxo detalhado

1. O script `carga.py` lê a planilha Excel.
2. Normaliza os telefones para padrão `wa_id`.
3. (Opcional) Faz upload da imagem 1x para obter `media_id`.
4. Dispara requisições para o workflow de envio.
5. Captura resposta do n8n / Meta.
6. Gera relatório consolidado com status e rastreabilidade.

---

## 🏗️ Estrutura do Repositório
```bash
.
├── workflows_n8n/
│ └── exemplos/
│ ├── PostImagem_EXEMPLO.json
│ └── MensageriaAtivaWA_EXEMPLO.json
│
├── samples/
│ ├── contatos_comercial_exemplo.xlsx
│ ├── relatorio_input_waid_mensageria.xlsx
│ └── erros_envio_n8n.csv
│
├── assets/
│ └── imagem_debora.png
│
├── carga.py
├── .env.example
├── .gitignore
└── README.md
```

---

## 🔐 Configuração de Ambiente

### 1️⃣ Copie o arquivo de exemplo:

```bash
cp .env.example .env
```

### 2️⃣ Configure as variáveis:
```bash
# =====================================================
# CONFIGURAÇÃO DO ARQUIVO EXCEL
# =====================================================
CAMINHO_ARQUIVO=.
ARQUIVO_EXCEL=contatos_comercial_exemplo.xlsx
COLUNA_CELULAR=Celular

# =====================================================
# CONFIGURAÇÃO N8N (Webhooks)
# =====================================================

# Workflow: MensageriaAtivaWA (produção - usar /webhook/)
URL_N8N=https://SEU_N8N_DOMINIO/webhook/SEU_ID_DO_WEBHOOK

# Workflow: PostImagem (produção - usar /webhook/)
URL_N8N_IMG_POST=https://SEU_N8N_DOMINIO/webhook/SEU_ID_DO_WEBHOOK_IMAGEM

# Auth Basic (caso o webhook use autenticação)
USUARIO_N8N=seu_usuario
SENHA_N8N=sua_senha

# =====================================================
# CONFIGURAÇÃO WHATSAPP CLOUD API (OPCIONAL)
# Não utilizada diretamente pelo carga.py.
# Usar apenas se integrar direto com a Meta API.
# =====================================================

# ID do número de telefone no Meta Business Manager
PHONE_NUMBER_ID=SEU_PHONE_NUMBER_ID_AQUI

# Token de acesso 
WHATSAPP_TOKEN=SEU_TOKEN_AQUI

# Endpoint base (normalmente não precisa alterar)
WHATSAPP_API_BASE=https://graph.facebook.com/v18.0

# =====================================================
# IMAGEM (LOCAL)
# =====================================================
FOTO=imagem_debora.png

# =====================================================
# CONTROLE DE TAXA
# =====================================================
DELAY_ENTRE_REQUESTS=0.5
```
> ⚠️ Nunca versionar o arquivo .env.

---

## 🔄 Fluxo de Funcionamento

### 1️⃣ Upload de Mídia

**Workflow n8n:** `PostImagem_EXEMPLO`
  PostImagem_EXEMPLO
- Recebe imagem via Webhook
- Realiza upload para a WhatsApp Cloud API
- Retorna media_id

---

## 2️⃣ Envio de Template com Mídia

**Workflow:** `MensageriaAtivaWA_EXEMPLO`
- Recebe wa_id e media_id
- Envia template aprovado
- Utiliza header com imagem dinâmica

Exemplo de payload:
```json
{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "5511999999999",
  "type": "template",
  "template": {
    "name": "nome_do_template",
    "language": {
      "code": "pt_BR"
    },
    "components": [
      {
        "type": "header",
        "parameters": [
          {
            "type": "image",
            "image": {
              "id": "MEDIA_ID_AQUI"
            }
          }
        ]
      }
    ]
  }
}
```

---

## 🐍 Script Python – Carga de Contatos

Arquivo: `carga.py`

Responsável por:
- 📖 Leitura do Excel
- 📱 Normalização de telefone
- 🖼 Upload único da imagem (quando configurado)
- 🔁 Retry automático em falhas
- ⏱ Controle de rate limit
- 📊 Geração de relatório consolidado

---

## 📞 Normalização de Telefone

A função normalizar_telefone():
- Remove caracteres não numéricos
- Adiciona DDI 55 quando necessário
- Retorna padrão:
> 5511999999999

---

## 🖼 Upload de Imagem (Opcional)

Se FOTO estiver definida:
1. O script envia a imagem para o workflow PostImagem
2. Obtém media_id
3. Reutiliza o mesmo media_id para todos os envios
Isso evita upload repetido e melhora performance.

---

## 🔁 Retry Automático

- Até 3 tentativas
- Backoff exponencial (2^tentativa)
- Tratamento especial para erro 429 (Rate Limit)

---

## 🚀 Execução

### Instalar dependências
```bash
pip install pandas requests openpyxl python-dotenv
```

### Executar script
```bash
python carga.py
```

---

## 📊 Relatório Gerado

Arquivo:
```bash
relatorio_input_waid_mensageria.xlsx
```

Colunas geradas:
- telefone_original
- wa_id_normalizado_enviado
- input_retorno
- wa_id_retorno
- match (Sim/Não)
- status_http
- message_status
- message_id
- erro

> Critério de Match
```bash
Sim → input_retorno == wa_id_retorno
Não → divergência ou erro
```
> Relatório é ordenado priorizando falhas.

---

## 🔄 Workflows n8n

### 1️⃣ PostImagem_EXEMPLO
- Recebe multipart file
- Faz upload na WhatsApp Cloud API
- Retorna:
```json
{
  "media_id": "XXXXXXXX"
}
```

---

## 2️⃣ MensageriaAtivaWA_EXEMPLO
Recebe:
```json
{
  "wa_id": "5511999999999",
  "media_id": "MEDIA_ID_AQUI"
}
```
> Envia template aprovado via Meta API.

---

## 🔒 Segurança

✔️ Tokens não versionados
✔️ `.env` ignorado pelo Git
✔️ Workflows de exemplo sem credenciais reais
✔️ Validação de variáveis obrigatórias
✔️ Bloqueio para uso de webhook-test em lote

---

## 📌 Boas Práticas

- Rotacionar credenciais periodicamente
- Monitorar limites de envio da Meta API
- Validar template antes de disparos em massa
- Testar com pequenos lotes antes de produção
- Monitorar status 429 (rate limit)

---

## 📈 Escalabilidade

Para grandes volumes:
- Ajustar DELAY_ENTRE_REQUESTS
- Implementar fila assíncrona
- Executar via scheduler (ex: Airflow / CRON)
- Logar envios em banco de dados
