# ─── Integração com Google Calendar ──────────────────────────────────────────
# Usa uma Service Account (conta de serviço) para criar eventos nas agendas
# de notebooks e tablets automaticamente quando um agendamento é aprovado.
#
# Pré-requisitos:
# 1. credentials.json na raiz do projeto (baixado do Google Cloud Console)
# 2. Service Account compartilhada nas agendas com permissão "Fazer alterações em eventos"

import os
import traceback
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from django.conf import settings

# Caminho para o arquivo de credenciais da Service Account
SERVICE_ACCOUNT_FILE = os.path.join(settings.BASE_DIR, 'credentials.json')

# Escopo necessário para criar/editar eventos no Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar']


def criar_eventos_google(agendamento):
    """Cria um evento no Google Calendar da agenda correta (notebooks ou tablets).
    
    Retorna True se o evento foi criado com sucesso, False caso contrário.
    Nunca lança exceções — erros são apenas logados para não derrubar o servidor.
    """
    try:
        # Verifica se o arquivo de credenciais existe antes de tentar conectar
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            print("Erro: credentials.json não encontrado.")
            return False

        # Autentica com a Service Account
        creds   = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('calendar', 'v3', credentials=creds)

        # Seleciona a agenda correta pelo tipo de equipamento
        if agendamento.equipamento == 'notebook':
            calendar_id = '389efe1fd337bdd7427721c3ff77fbcc5fd89fb725969cb4464a875510c1c1d8@group.calendar.google.com'
        else:
            calendar_id = 'a979085c34567de2e46ddd4180c0249650a0843363028df4f89b89dad9184b1e@group.calendar.google.com'

        # Descrição do evento (visível ao abrir o evento na agenda)
        descricao = (
            f'Professor: {agendamento.nome}\n'
            f'Turma: {agendamento.turma}\n'
            f'Quantidade: {agendamento.quantidade}\n'
            f'Software/Obs: {agendamento.software_especifico or "Nenhuma"}\n'
            f'Periféricos Solicitados: {agendamento.perifericos or "Nenhum"}'
        )

        # Estrutura do evento conforme API do Google Calendar
        evento = {
            'summary': f'Reserva {agendamento.equipamento.capitalize()}: {agendamento.nome}',
            'description': descricao,
            'start': {
                'dateTime': agendamento.data_inicio.isoformat(),
                'timeZone': 'America/Sao_Paulo',
            },
            'end': {
                'dateTime': agendamento.data_fim.isoformat(),
                'timeZone': 'America/Sao_Paulo',
            },
        }

        service.events().insert(calendarId=calendar_id, body=evento).execute()
        print(f"Sucesso: Evento criado na agenda de {agendamento.equipamento}!")
        return True

    except Exception as e:
        # Loga o erro completo para facilitar diagnóstico sem derrubar o servidor
        print(f"ERRO Google Calendar: {type(e).__name__}: {e}")
        print(traceback.format_exc())
        return False