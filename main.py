import imaplib
import email
from datetime import datetime, timezone, timedelta
from email.header import decode_header
import re
import csv
import time

# Funções e configurações do Passo Anterior (enviar e-mail)
import smtplib
import ssl
from email.message import EmailMessage

# --- CONFIGURAÇÕES GERAIS ---
# E-mail que será monitorado e usado para enviar as notificações
MEU_EMAIL = "contageral0113@gmail.com"
SENHA_DE_APP_GMAIL = "pzhp kdzj vaag cbef"  # A mesma senha de app para IMAP e SMTP
IMAP_SERVER = "imap.gmail.com"

## --- FUNÇÕES 'enviar_notificacao_morador' e 'interpretar_email_multa' ---
# (Estas funções permanecem exatamente as mesmas do script anterior)
# ... cole as duas funções aqui ...
def enviar_notificacao_morador(dados_multa):
    NOME_CONDOMINIO = dados_multa['nome_condominio_origem']
    corpo_html = f"""
    <html><body><div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #ddd; padding: 20px;"><h1 style="color: #c0392b;">Notificação de Multa Condominial</h1><p>Prezado(a) <strong>{dados_multa['nome_morador']}</strong>,</p><p>A administração do seu condomínio nos repassou a notificação de uma multa por infração ao regulamento interno.</p><div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid #c0392b; margin-top: 20px;"><p><strong>Condomínio:</strong> {NOME_CONDOMINIO}</p><p><strong>Unidade:</strong> Apartamento {dados_multa['apartamento']}, Bloco {dados_multa['bloco']}</p><p><strong>Data da Ocorrência:</strong> {dados_multa['data_ocorrencia']}</p><p><strong>Valor da Multa:</strong> <strong style="color: #c0392b;">R$ {dados_multa['valor']}</strong></p><hr><p><strong>Motivo da Infração:</strong><br>{dados_multa['motivo']}</p></div><p>Este valor será incluído no seu próximo boleto.</p><div style="margin-top: 20px; font-size: 0.9em; color: #777;"><p>Atenciosamente,</p><p><strong>Sistema de Gestão Financeira</strong></p><p><em>Este é um e-mail automático gerado a partir da notificação do seu condomínio.</em></p></div></div></body></html>
    """
    msg = EmailMessage()
    msg['From'] = f"Gestão de Multas <{MEU_EMAIL}>"
    msg['To'] = dados_multa['email_morador']
    msg['Subject'] = f"Notificação de Multa Recebida - Condomínio {NOME_CONDOMINIO}"
    msg.add_alternative(corpo_html, subtype='html')
    contexto = ssl.create_default_context()
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as servidor:
            servidor.starttls(context=contexto)
            servidor.login(MEU_EMAIL, SENHA_DE_APP_GMAIL)
            servidor.send_message(msg)
            print(f"✅ Notificação enviada com sucesso para {dados_multa['email_morador']}")
            return True
    except Exception as e:
        print(f"❌ Falha ao enviar e-mail para {dados_multa['email_morador']}: {e}")
        return False

def interpretar_email_multa(corpo_email):
    dados_extraidos = {}
    try:
        padrao_bloco_apto = re.search(r"Unidade multada: Bloco (.*?), Apartamento (.*?)\n", corpo_email, re.IGNORECASE)
        padrao_valor = re.search(r"Valor: (.*?)\n", corpo_email, re.IGNORECASE)
        padrao_motivo = re.search(r"Motivo: (.*?)\n", corpo_email, re.IGNORECASE | re.DOTALL)
        padrao_data = re.search(r"Data: (.*?)\n", corpo_email, re.IGNORECASE)
        if all([padrao_bloco_apto, padrao_valor, padrao_motivo, padrao_data]):
            dados_extraidos['bloco'] = padrao_bloco_apto.group(1).strip()
            dados_extraidos['apartamento'] = padrao_bloco_apto.group(2).strip()
            dados_extraidos['valor'] = padrao_valor.group(1).strip()
            dados_extraidos['motivo'] = padrao_motivo.group(1).strip()
            dados_extraidos['data_ocorrencia'] = padrao_data.group(1).strip()
            return dados_extraidos
    except Exception as e:
        print(f"Erro ao interpretar e-mail com RegEx: {e}")
    return None

# --- FUNÇÃO PRINCIPAL DO ROBÔ (COM A LÓGICA DE TEMPO ATUALIZADA) ---
def monitorar_emails():
    print("Iniciando conexão com o servidor IMAP...")
    imap = imaplib.IMAP4_SSL(IMAP_SERVER)
    imap.login(MEU_EMAIL, SENHA_DE_APP_GMAIL)
    imap.select("inbox")
    print("Conexão estabelecida.")

    ### NOVO: Preparando o filtro de data para o IMAP ###
    # Formata a data de hoje para o padrão do IMAP (ex: 12-Aug-2025)
    date_str = datetime.now().strftime("%d-%b-%Y")
    search_criteria = f'(UNSEEN SINCE "{date_str}")'

    print(f"Buscando por e-mails não lidos de hoje ({date_str})...")
    status, messages = imap.search(None, search_criteria)

    email_ids = messages[0].split()

    if not email_ids:
        print("Nenhum e-mail novo encontrado hoje.")
        imap.logout()
        return

    print(f"Encontrados {len(email_ids)} novos e-mails hoje. Verificando o horário de cada um...")

    # Carrega a base de dados de moradores
    mapa_moradores = {}
    with open('moradores.csv', mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            chave = (row['apartamento'], row['bloco'])
            mapa_moradores[chave] = {'nome': row['nome_completo'], 'email': row['email_morador']}

    # ### NOVO: Define o tempo de agora (com fuso horário) e o limite de 1 hora ###
    agora_utc = datetime.now(timezone.utc)
    limite_de_tempo = timedelta(hours=1)

    for email_id in email_ids:
        status, msg_data = imap.fetch(email_id, "(RFC822)")
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])

                ### NOVO: Verificação do horário do e-mail ###
                date_header = msg['Date']
                if not date_header:
                    continue # Pula se o e-mail não tiver data

                # Converte a data do e-mail para um objeto datetime com fuso horário
                email_date = email.utils.parsedate_to_datetime(date_header)

                # Compara a data do e-mail com a hora atual
                if agora_utc - email_date.astimezone(timezone.utc) > limite_de_tempo:
                    print(f"  - Ignorando e-mail antigo (recebido em {email_date.strftime('%H:%M:%S')}).")
                    continue # Pula para o próximo e-mail se for mais antigo que 1 hora

                # Se o e-mail passou no teste de tempo, continua o processamento normal...
                print(f"\n✅ Processando e-mail recente (recebido em {email_date.strftime('%H:%M:%S')}).")

                from_ = msg.get("From")
                corpo_email = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            try:
                                corpo_email = part.get_payload(decode=True).decode()
                                break
                            except: pass
                else:
                    corpo_email = msg.get_payload(decode=True).decode()

                if not corpo_email:
                    print("Não foi possível extrair o corpo do e-mail. Pulando.")
                    continue

                dados_multa = interpretar_email_multa(corpo_email)

                if dados_multa:
                    print("  - Dados extraídos com sucesso:", dados_multa)
                    chave_busca = (dados_multa['apartamento'], dados_multa['bloco'])
                    if chave_busca in mapa_moradores:
                        info_morador = mapa_moradores[chave_busca]
                        dados_multa.update({
                            'nome_morador': info_morador['nome'],
                            'email_morador': info_morador['email'],
                            'nome_condominio_origem': from_
                        })
                        if enviar_notificacao_morador(dados_multa):
                            imap.store(email_id, '+FLAGS', '\\Seen')
                            print(f"  - E-mail {email_id} processado e marcado como lido.")
                    else:
                        print(f"  - ❌ ERRO: Morador para Apto {dados_multa['apartamento']}/Bloco {dados_multa['bloco']} não encontrado no CSV.")
                else:
                    print("  - Não foi possível interpretar os dados da multa neste e-mail.")

    imap.logout()


# --- LOOP PRINCIPAL DO ROBÔ ---
if __name__ == "__main__":
    while True:
        try:
            monitorar_emails()
        except Exception as e:
            print(f"Ocorreu um erro no ciclo principal: {e}")

        intervalo_segundos = 300 # 5 minutos
        print(f"\nAguardando {intervalo_segundos / 60:.0f} minutos para a próxima verificação...")
        time.sleep(intervalo_segundos)
