# ─── URLs do projeto ──────────────────────────────────────────────────────────
# Cada path() mapeia uma URL para uma view.
# O 'name' permite referenciar a URL nos templates com {% url 'nome' %}.

from django.urls import path
from agendamentos.admin import admin_site
from agendamentos.views import (
    fazer_agendamento,
    index,
    ver_agenda,
    cadastrar_admin,
    exportar_historico_excel,
    deletar_admin,
)

urlpatterns = [
    # Painel administrativo customizado (NTIAdminSite)
    path('admin/', admin_site.urls),

    # Área restrita — requer login de superusuário
    path('nti/cadastrar-admin/', cadastrar_admin, name='cadastrar_admin'),
    path('nti/deletar-admin/<int:user_id>/', deletar_admin, name='deletar_admin'),
    path('nti/exportar-historico/', exportar_historico_excel, name='exportar_historico'),

    # Área pública
    path('', index, name='index'),                      # Página inicial
    path('agendar/', fazer_agendamento, name='agendar'), # Formulário de agendamento
    path('agenda/', ver_agenda, name='ver_agenda'),      # Agenda pública (Google Calendar)
]