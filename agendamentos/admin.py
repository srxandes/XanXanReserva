# ─── Imports ──────────────────────────────────────────────────────────────────
from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta
from .models import Agendamento, Configuracao, EmailBloqueado, LogAtividade


# ─── Ações em lote ────────────────────────────────────────────────────────────
# Aparecem no dropdown "Ação" da listagem de agendamentos no admin.
# Só afetam agendamentos com status 'pendente' para evitar mudanças acidentais.

@admin.action(description="✅ Aprovar selecionados")
def aprovar_agendamentos(modeladmin, request, queryset):
    """Aprova todos os agendamentos pendentes selecionados.
    O save() do model dispara e-mail de confirmação e cria evento no Google Calendar."""
    for agendamento in queryset.filter(status='pendente'):
        agendamento.status = 'aprovado'
        agendamento.save()

@admin.action(description="❌ Rejeitar selecionados")
def rejeitar_agendamentos(modeladmin, request, queryset):
    """Rejeita todos os agendamentos pendentes selecionados.
    O save() do model dispara e-mail de rejeição."""
    for agendamento in queryset.filter(status='pendente'):
        agendamento.status = 'rejeitado'
        agendamento.save()

@admin.action(description="📦 Marcar selecionados como DEVOLVIDOS")
def marcar_como_devolvido(modeladmin, request, queryset):
    """Marca agendamentos como entregues/devolvidos em lote."""
    queryset.update(entregue=True)


# ─── Admin de Agendamento ─────────────────────────────────────────────────────
@admin.register(Agendamento)
class AgendamentoAdmin(admin.ModelAdmin):
    list_display  = ('nome', 'equipamento', 'quantidade', 'data_inicio', 'data_fim', 'status_colorido', 'entregue')
    list_filter   = ('status', 'entregue', 'equipamento')
    search_fields = ('nome', 'email', 'turma')
    actions       = [aprovar_agendamentos, rejeitar_agendamentos, marcar_como_devolvido]

    @admin.display(description='Status')
    def status_colorido(self, obj):
        """Renderiza a coluna Status com cores: verde=aprovado, amarelo=pendente, vermelho=rejeitado."""
        from django.utils.html import format_html
        cores = {
            'aprovado':  ('green',   '✅ Aprovado'),
            'pendente':  ('#d97706', '⏳ Pendente'),
            'rejeitado': ('red',     '❌ Rejeitado'),
        }
        cor, label = cores.get(obj.status, ('#000', obj.status))
        return format_html('<span style="color:{}; font-weight:600;">{}</span>', cor, label)


# ─── Admin de Configuração ────────────────────────────────────────────────────
# Registro simples — usa a interface padrão do Django
admin.site.register(Configuracao)


# ─── Admin de E-mails Bloqueados ──────────────────────────────────────────────
@admin.register(EmailBloqueado)
class EmailBloqueadoAdmin(admin.ModelAdmin):
    list_display  = ('email', 'motivo', 'criado_em')
    search_fields = ('email',)

    def save_model(self, request, obj, form, change):
        """Registra log quando um e-mail é adicionado à lista negra."""
        super().save_model(request, obj, form, change)
        LogAtividade.registrar(
            'email_bloqueado',
            f"E-mail '{obj.email}' bloqueado.",
            usuario=request.user.username,
        )

    def delete_model(self, request, obj):
        """Registra log quando um e-mail é removido da lista negra."""
        LogAtividade.registrar(
            'email_desbloqueado',
            f"E-mail '{obj.email}' removido da lista de bloqueados.",
            usuario=request.user.username,
        )
        super().delete_model(request, obj)


# ─── NTIAdminSite ─────────────────────────────────────────────────────────────
# Admin site customizado que substitui o Django admin padrão.
# Adiciona: menu de navegação, dashboard, página de logs.
class NTIAdminSite(admin.AdminSite):
    site_header = 'NTI — Painel de Administração'
    site_title  = 'NTI Admin'
    index_title = 'Administração do Site'

    def each_context(self, request):
        """Injeta links de navegação no contexto de TODAS as páginas do admin.
        Os links só aparecem após o login para não expor o menu na tela de login."""
        context = super().each_context(request)
        if request.user.is_authenticated:
            context['custom_links'] = [
                {'url': '/admin/dashboard/', 'label': '📊 Dashboard'},
                {'url': '/admin/logs/',      'label': '📋 Logs'},
                {'url': '/nti/cadastrar-admin/', 'label': '👤 Cadastrar Admin'},
                {'url': '/',        'label': '🏠 Site Principal'},
                {'url': '/agenda/', 'label': '📅 Agenda'},
            ]
        else:
            context['custom_links'] = []  # Menu vazio na tela de login
        return context

    def get_urls(self):
        """Registra URLs customizadas no admin: /admin/dashboard/ e /admin/logs/."""
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_view(self.dashboard_view), name='dashboard'),
            path('logs/',      self.admin_view(self.logs_view),      name='logs'),
        ]
        return custom_urls + urls

    # ── Dashboard ─────────────────────────────────────────────────────────────
    def dashboard_view(self, request):
        """Página /admin/dashboard/ com estatísticas do dia, semana,
        estoque atual, pendentes, próximos agendamentos e histórico filtrado."""
        agora        = timezone.now()
        hoje_inicio  = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        hoje_fim     = hoje_inicio + timedelta(days=1)
        semana_inicio = hoje_inicio - timedelta(days=agora.weekday())

        # Agendamentos de hoje
        hoje           = Agendamento.objects.filter(data_inicio__gte=hoje_inicio, data_inicio__lt=hoje_fim)
        total_hoje     = hoje.count()
        hoje_notebooks = hoje.filter(equipamento='notebook').aggregate(t=Sum('quantidade'))['t'] or 0
        hoje_tablets   = hoje.filter(equipamento='tablet').aggregate(t=Sum('quantidade'))['t'] or 0

        # Agendamentos desta semana (segunda até hoje)
        semana           = Agendamento.objects.filter(data_inicio__gte=semana_inicio)
        total_semana     = semana.count()
        semana_notebooks = semana.filter(equipamento='notebook').aggregate(t=Sum('quantidade'))['t'] or 0
        semana_tablets   = semana.filter(equipamento='tablet').aggregate(t=Sum('quantidade'))['t'] or 0

        # Pendentes aguardando aprovação
        pendentes       = Agendamento.objects.filter(status='pendente', entregue=False)
        total_pendentes = pendentes.count()

        # Estoque atual (em uso neste momento)
        config           = Configuracao.objects.first()
        limite_notebooks = config.limite_notebooks if config else 26
        limite_tablets   = config.limite_tablets   if config else 20

        em_uso_notebooks = Agendamento.objects.filter(
            equipamento='notebook', status__in=['aprovado', 'pendente'],
            entregue=False, data_inicio__lte=agora, data_fim__gte=agora,
        ).aggregate(t=Sum('quantidade'))['t'] or 0

        em_uso_tablets = Agendamento.objects.filter(
            equipamento='tablet', status='aprovado',
            entregue=False, data_inicio__lte=agora, data_fim__gte=agora,
        ).aggregate(t=Sum('quantidade'))['t'] or 0

        disponiveis_notebooks = max(0, limite_notebooks - em_uso_notebooks)
        disponiveis_tablets   = max(0, limite_tablets   - em_uso_tablets)
        # Percentual de uso para as barras de progresso
        pct_notebooks = round((em_uso_notebooks / limite_notebooks) * 100) if limite_notebooks else 0
        pct_tablets   = round((em_uso_tablets   / limite_tablets)   * 100) if limite_tablets   else 0

        # Próximos 10 agendamentos aprovados
        proximos = Agendamento.objects.filter(
            data_inicio__gte=agora, status='aprovado', entregue=False,
        ).order_by('data_inicio')[:10]

        # ── Histórico com filtros (GET params) ────────────────────────────────
        filtro_inicio = request.GET.get('data_inicio', '')
        filtro_fim    = request.GET.get('data_fim', '')
        filtro_equip  = request.GET.get('equipamento', '')
        filtro_status = request.GET.get('status', '')

        historico = Agendamento.objects.all().order_by('-data_inicio')
        if filtro_inicio: historico = historico.filter(data_inicio__date__gte=filtro_inicio)
        if filtro_fim:    historico = historico.filter(data_inicio__date__lte=filtro_fim)
        if filtro_equip:  historico = historico.filter(equipamento=filtro_equip)
        if filtro_status: historico = historico.filter(status=filtro_status)

        # Totais só aparecem quando há filtro ativo
        historico_totais = None
        if filtro_inicio or filtro_fim or filtro_equip or filtro_status:
            historico_totais = {
                'total':     historico.count(),
                'notebooks': historico.filter(equipamento='notebook').aggregate(t=Sum('quantidade'))['t'] or 0,
                'tablets':   historico.filter(equipamento='tablet').aggregate(t=Sum('quantidade'))['t'] or 0,
            }

        context = {
            **self.each_context(request),
            'total_hoje': total_hoje, 'hoje_notebooks': hoje_notebooks, 'hoje_tablets': hoje_tablets,
            'total_semana': total_semana, 'semana_notebooks': semana_notebooks, 'semana_tablets': semana_tablets,
            'total_pendentes': total_pendentes, 'pendentes': pendentes,
            'limite_notebooks': limite_notebooks, 'limite_tablets': limite_tablets,
            'em_uso_notebooks': em_uso_notebooks, 'em_uso_tablets': em_uso_tablets,
            'disponiveis_notebooks': disponiveis_notebooks, 'disponiveis_tablets': disponiveis_tablets,
            'pct_notebooks': pct_notebooks, 'pct_tablets': pct_tablets,
            'proximos': proximos,
            'historico': historico, 'historico_totais': historico_totais,
            'filtro_inicio': filtro_inicio, 'filtro_fim': filtro_fim,
            'filtro_equip': filtro_equip, 'filtro_status': filtro_status,
            'title': 'Dashboard NTI',
        }
        return render(request, 'admin/dashboard.html', context)

    # ── Logs ──────────────────────────────────────────────────────────────────
    def logs_view(self, request):
        """Página /admin/logs/ com histórico de atividades paginado (50 por página).
        Permite filtrar por tipo de evento."""
        from django.core.paginator import Paginator
        logs = LogAtividade.objects.all()

        filtro_tipo = request.GET.get('tipo', '')
        if filtro_tipo:
            logs = logs.filter(tipo=filtro_tipo)

        paginator = Paginator(logs, 50)
        page = paginator.get_page(request.GET.get('page', 1))

        context = {
            **self.each_context(request),
            'logs': page,
            'filtro_tipo': filtro_tipo,
            'tipos': LogAtividade.TIPOS,
            'title': 'Logs de Atividade',
        }
        return render(request, 'admin/logs.html', context)


# ─── Registro no NTIAdminSite ─────────────────────────────────────────────────
# Substitui o admin padrão do Django pelo customizado.
# Todos os models precisam ser registrados aqui para aparecer no painel.
admin_site = NTIAdminSite(name='admin')
admin_site.register(Agendamento,    AgendamentoAdmin)
admin_site.register(Configuracao)
admin_site.register(EmailBloqueado, EmailBloqueadoAdmin)
admin_site.register(LogAtividade)