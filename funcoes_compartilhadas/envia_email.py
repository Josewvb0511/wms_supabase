# -*- coding: utf-8 -*-
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv


load_dotenv("credenciais/.env")


def enviar_email(destinatario: str, assunto: str, mensagem_html: str):
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASS", "").strip()
    smtp_from = os.getenv("SMTP_FROM", "").strip()

    if not smtp_host or not smtp_user or not smtp_pass or not smtp_from:
        raise ValueError("Configure SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS e SMTP_FROM no arquivo credenciais/.env")

    msg = MIMEMultipart()
    msg["From"] = smtp_from
    msg["To"] = destinatario
    msg["Subject"] = assunto

    msg.attach(MIMEText(mensagem_html, "html", "utf-8"))

    servidor = smtplib.SMTP(smtp_host, smtp_port)
    servidor.starttls()
    servidor.login(smtp_user, smtp_pass)
    servidor.sendmail(smtp_from, destinatario, msg.as_string())
    servidor.quit()