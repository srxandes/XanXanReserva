# ─── Imports ──────────────────────────────────────────────────────────────────
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail  
from django.conf import settings          
from .utils import criar_eventos_google


# ─── Configuracao ─────────────────────────────────────────────────────────────
# Tabela de configurações globais do sistema. Só deve existir UM registro.
# Todos os valores são editáveis pelo admin sem precisar mexer no código.
class Configuracao(models.Model):
    limite_notebooks           = models.IntegerField(default=26,  verbose_name="Limite de Notebooks")
    limite_tablets             = models.IntegerField(default=20,  verbose_name="Limite de Tablets")
    limite_aprovacao_automatica= models.IntegerField(default=13,  verbose_name="Limite de Aprovação Automática (Notebooks)")
    antecedencia_minima        = models.IntegerField(default=30,  verbose_name="Antecedência Mínima para Agendamento (minutos)")
    prazo_expiracao_pendente   = models.IntegerField(default=5,   verbose_name="Prazo para Expiração de Pendentes (dias)")
    texto_instrucoes           = models.TextField(default="Preencha as informações abaixo.", verbose_name="instruções do Form")

    class Meta:
        verbose_name        = "Configuração"
        verbose_name_plural = "Configurações"


# ─── LogAtividade ─────────────────────────────────────────────────────────────
# Registra eventos importantes do sistema para auditoria.
# Visível em /admin/logs/ no painel NTI.
class LogAtividade(models.Model):
    TIPOS = [
        ('agendamento_criado',    'Agendamento Criado'),
        ('agendamento_aprovado',  'Agendamento Aprovado'),
        ('agendamento_rejeitado', 'Agendamento Rejeitado'),
        ('agendamento_expirado',  'Agendamento Expirado'),
        ('email_bloqueado',       'E-mail Bloqueado'),
        ('email_desbloqueado',    'E-mail Desbloqueado'),
        ('admin_criado',          'Admin Criado'),
    ]
    tipo      = models.CharField(max_length=30, choices=TIPOS, verbose_name="Evento")
    descricao = models.TextField(verbose_name="Descrição")
    usuario   = models.CharField(max_length=150, blank=True, verbose_name="Usuário")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Data/Hora")

    class Meta:
        verbose_name        = "Log de Atividade"
        verbose_name_plural = "Logs de Atividade"
        ordering            = ['-criado_em']  # Mais recentes primeiro

    def __str__(self):
        return f"[{self.get_tipo_display()}] {self.criado_em:%d/%m/%Y %H:%M}"

    @classmethod
    def registrar(cls, tipo, descricao, usuario='sistema'):
        """Atalho para criar um log. Uso: LogAtividade.registrar('tipo', 'descricao')"""
        cls.objects.create(tipo=tipo, descricao=descricao, usuario=usuario)


# ─── EmailBloqueado ───────────────────────────────────────────────────────────
# Lista negra de e-mails. Qualquer tentativa de agendamento com e-mail
# presente aqui recebe uma mensagem de erro genérica (sem revelar o bloqueio).
class EmailBloqueado(models.Model):
    email     = models.EmailField(unique=True, verbose_name="E-mail")
    motivo    = models.TextField(blank=True, verbose_name="Motivo (interno)")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Bloqueado em")

    class Meta:
        verbose_name        = "E-mail Bloqueado"
        verbose_name_plural = "E-mails Bloqueados"

    def __str__(self):
        return self.email


# ─── Agendamento ──────────────────────────────────────────────────────────────
# Model principal do sistema. Representa uma reserva de equipamento.
class Agendamento(models.Model):
    TIPO_EQUIPAMENTO = [
        ('notebook', 'Notebook'),
        ('tablet',   'Tablet'),
    ]
    STATUS_CHOICES = [
        ('aprovado',  'Aprovado'),
        ('pendente',  'Aguardando Aprovação'),
        ('rejeitado', 'Rejeitado'),
    ]

    # Dados do solicitante
    nome                = models.CharField(max_length=100)
    email               = models.EmailField()
    turma               = models.CharField(max_length=50)

    # Dados do equipamento
    equipamento         = models.CharField(max_length=10, choices=TIPO_EQUIPAMENTO, default='notebook')
    quantidade          = models.PositiveIntegerField()
    software_especifico = models.TextField(verbose_name="Precisa de algum software?", blank=True)
    perifericos         = models.TextField(verbose_name="Precisa de algum periférico?", blank=True)

    # Período da reserva
    data_inicio         = models.DateTimeField(verbose_name="Início do Agendamento", null=True)
    data_fim            = models.DateTimeField(verbose_name="Fim do Agendamento", null=True)

    # Controle interno
    entregue            = models.BooleanField(default=False)
    status              = models.CharField(max_length=10, choices=STATUS_CHOICES, default='aprovado')
    aceitou_termos      = models.BooleanField(default=False, verbose_name="Aceitou os Termos")
    lembrete_enviado    = models.BooleanField(default=False, verbose_name="Lembrete Enviado")

    # ── Saldo disponível ──────────────────────────────────────────────────────
    @classmethod
    def obter_saldo(cls, tipo):
        """Retorna quantos equipamentos do tipo ainda estão disponíveis AGORA."""
        config = Configuracao.objects.first()
        limite = config.limite_notebooks if (config and tipo == 'notebook') else 26
        if config and tipo == 'tablet':
            limite = config.limite_tablets

        agora = timezone.now()
        # Notebooks bloqueiam estoque mesmo quando pendentes; tablets só quando aprovados
        status_bloqueantes = ['aprovado', 'pendente'] if tipo == 'notebook' else ['aprovado']

        em_uso = cls.objects.filter(
            equipamento=tipo,
            status__in=status_bloqueantes,
            entregue=False,
            data_inicio__lte=agora,
            data_fim__gte=agora
        ).aggregate(Sum('quantidade'))['quantidade__sum'] or 0

        return max(0, limite - em_uso)

    # ── Helpers de e-mail ─────────────────────────────────────────────────────
    def _obter_emails_admins(self):
        """Retorna lista de e-mails de todos os usuários staff/admin cadastrados."""
        return list(User.objects.filter(is_staff=True).exclude(email='').values_list('email', flat=True))

    def enviar_email_confirmacao(self):
        """Envia comprovante de reserva aprovada ao professor e notifica os admins."""
        assunto = f"[APROVADO] Confirmacao de Reserva - {self.get_equipamento_display()}"
        corpo = f"""
Olá {self.nome},

Sua reserva de equipamento foi APROVADA e registrada com sucesso!

DETALHES DA RESERVA:
- Equipamento: {self.get_equipamento_display()}
- Quantidade: {self.quantidade}
- Período: {self.data_inicio.strftime('%d/%m/%Y às %H:%M')} até {self.data_fim.strftime('%H:%M')}

REQUISITOS ADICIONAIS:
- Softwares: {self.software_especifico or "Nenhum solicitado"}
- Periféricos: {self.perifericos or "Nenhum solicitado"}
        """
        self._disparar_email(assunto, corpo, [self.email])
        self._disparar_email(f"[NTI] Novo Agendamento: {self.nome}", corpo, self._obter_emails_admins())

    def enviar_email_pendente(self):
        """Avisa o professor que a reserva excedeu o limite e está em análise manual."""
        assunto = "[ANALISE] Solicitacao em Analise - NTI"
        corpo = f"""
Olá {self.nome},

Sua reserva de {self.quantidade} notebooks excedeu o limite de aprovação automática.
Sua solicitação foi encaminhada para análise manual da equipe NTI.
        """
        self._disparar_email(assunto, corpo, [self.email])
        assunto_admin = f"[PENDENTE] ACAO NECESSARIA: Nova Reserva Pendente ({self.nome})"
        self._disparar_email(assunto_admin, corpo, self._obter_emails_admins())

    def enviar_email_rejeicao(self):
        """Avisa o professor que a reserva foi rejeitada."""
        assunto = f"[INDEFERIDO] Reserva Indeferida - {self.get_equipamento_display()}"
        corpo = f"Olá {self.nome}, lamentamos informar que sua reserva de {self.get_equipamento_display()} não pôde ser aprovada por indisponibilidade técnica."
        self._disparar_email(assunto, corpo, [self.email])

    def _disparar_email(self, assunto, corpo, destinatarios):
        """Método auxiliar centralizado para envio de e-mails.
        Ignora silenciosamente se não houver destinatários.
        Codifica o assunto em ASCII para evitar erros no Windows (cp1252)."""
        if not destinatarios:
            return
        try:
            assunto_safe = assunto.encode('ascii', errors='ignore').decode('ascii')
            send_mail(assunto_safe, corpo, settings.EMAIL_HOST_USER, destinatarios, fail_silently=False)
        except Exception as e:
            print(f"Falha Critica ao enviar e-mail ({assunto}): {e}")

    # ── Validação ─────────────────────────────────────────────────────────────
    def clean(self):
        """Validações de negócio executadas antes de salvar.
        O Django chama clean() automaticamente via full_clean() no save()."""
        super().clean()
        agora = timezone.now()

        # Datas obrigatórias
        if not self.data_inicio or not self.data_fim:
            raise ValidationError("As datas de início e fim são obrigatórias para o processamento.")

        if self.quantidade <= 0:
            raise ValidationError({'quantidade': "A quantidade deve ser de pelo menos 1 equipamento."})

        # Antecedência mínima configurável
        config = Configuracao.objects.first()
        antecedencia = config.antecedencia_minima if config else 30
        minimo_permitido = agora + timedelta(minutes=antecedencia)
        if self.data_inicio < minimo_permitido:
            raise ValidationError({'data_inicio': f"O agendamento deve ser feito com pelo menos {antecedencia} minuto(s) de antecedência."})

        # Só permite agendamentos no ano corrente
        if self.data_inicio.year > agora.year:
            raise ValidationError({'data_inicio': f"Só é permitido realizar agendamentos para o ano de {agora.year}."})

        if self.data_fim <= self.data_inicio:
            raise ValidationError({'data_fim': "A data de fim deve ser posterior à data de início."})

        # Máximo de 24h por reserva
        duracao = self.data_fim - self.data_inicio
        if duracao > timedelta(hours=24):
            raise ValidationError({'data_fim': "A reserva não pode ultrapassar 24 horas consecutivas."})

        # Verifica conflito de estoque no período solicitado
        config = Configuracao.objects.first()
        limite_max = config.limite_notebooks if (config and self.equipamento == 'notebook') else 26
        if config and self.equipamento == 'tablet':
            limite_max = config.limite_tablets

        status_bloqueantes = ['aprovado', 'pendente'] if self.equipamento == 'notebook' else ['aprovado']

        # Busca agendamentos que se sobrepõem ao período solicitado
        conflitos = Agendamento.objects.filter(
            equipamento=self.equipamento,
            status__in=status_bloqueantes,
            entregue=False
        ).filter(
            Q(data_inicio__lt=self.data_fim) & Q(data_fim__gt=self.data_inicio)
        ).exclude(pk=self.pk)  # Exclui o próprio registro (para edições)

        ocupados = conflitos.aggregate(Sum('quantidade'))['quantidade__sum'] or 0
        if (ocupados + self.quantidade) > limite_max:
            disponivel = max(0, limite_max - ocupados)
            raise ValidationError(f"Conflito de Inventário: Restam apenas {disponivel} unidade(s) para este período.")

    # ── Save ──────────────────────────────────────────────────────────────────
    def save(self, *args, **kwargs):
        """Override do save para:
        1. Definir status como 'pendente' se notebooks excederem o limite automático
        2. Executar validações via full_clean()
        3. Criar evento no Google Calendar quando aprovado
        4. Disparar e-mails conforme o status
        5. Registrar logs de atividade
        """
        is_new = self.pk is None  # True se é um novo agendamento
        old_status = None

        # Guarda o status anterior para detectar mudanças (ex: pendente → aprovado)
        if not is_new:
            try:
                old_status = Agendamento.objects.get(pk=self.pk).status
            except Agendamento.DoesNotExist:
                old_status = None

        # Verifica se notebooks novos excedem o limite de aprovação automática
        if is_new and self.equipamento == 'notebook':
            config = Configuracao.objects.first()
            limite_pendente = config.limite_aprovacao_automatica if config else 13

            # Soma notebooks já aprovados no mesmo horário
            ja_aprovados = Agendamento.objects.filter(
                equipamento='notebook',
                status='aprovado',
                entregue=False,
            ).filter(
                Q(data_inicio__lt=self.data_fim) & Q(data_fim__gt=self.data_inicio)
            ).aggregate(Sum('quantidade'))['quantidade__sum'] or 0

            if (ja_aprovados + self.quantidade) > limite_pendente:
                self.status = 'pendente'  # Força análise manual

        # Executa as validações do clean() antes de salvar
        self.full_clean()
        super().save(*args, **kwargs)

        # ── Pós-save: e-mails e Google Calendar ───────────────────────────────
        # Aprovado (novo ou transitando de pendente → aprovado)
        if (is_new and self.status == 'aprovado') or (old_status == 'pendente' and self.status == 'aprovado'):
            try:
                if self.data_inicio and self.data_fim:
                    criar_eventos_google(self)  # Cria evento no Google Calendar
            except Exception as e:
                print(f"Aviso: Falha na integração com Google Calendar: {e}")
            self.enviar_email_confirmacao()

        elif old_status == 'pendente' and self.status == 'rejeitado':
            self.enviar_email_rejeicao()

        elif is_new and self.status == 'pendente':
            self.enviar_email_pendente()
            LogAtividade.registrar(
                'agendamento_criado',
                f"{self.nome} solicitou {self.quantidade} {self.get_equipamento_display()}(s) para {self.data_inicio:%d/%m/%Y %H:%M}."
            )

        # ── Logs de mudança de status ──────────────────────────────────────────
        if not is_new and old_status == 'pendente' and self.status == 'aprovado':
            LogAtividade.registrar(
                'agendamento_aprovado',
                f"Agendamento de {self.nome} ({self.quantidade} {self.get_equipamento_display()}(s) em {self.data_inicio:%d/%m/%Y %H:%M}) aprovado."
            )
        elif not is_new and old_status == 'pendente' and self.status == 'rejeitado':
            LogAtividade.registrar(
                'agendamento_rejeitado',
                f"Agendamento de {self.nome} ({self.quantidade} {self.get_equipamento_display()}(s) em {self.data_inicio:%d/%m/%Y %H:%M}) rejeitado."
            )

    def __str__(self):
        return f"{self.nome} - {self.quantidade} {self.equipamento}(s)"

    # ── Lembretes ─────────────────────────────────────────────────────────────
    def enviar_lembrete(self):
        """Envia e-mail de lembrete ao professor e aos admins 1 dia antes do agendamento."""
        from django.contrib.auth.models import User
        from django.conf import settings
        from django.core.mail import send_mail

        data_fmt = self.data_inicio.strftime("%d/%m/%Y")
        hora_fmt = self.data_inicio.strftime("%H:%M")

        # E-mail para o professor solicitante
        try:
            send_mail(
                subject=f"[NTI] Lembrete: Agendamento amanha — {data_fmt}",
                message=(
                    f"Olá, {self.nome}!\n\n"
                    f"Este é um lembrete do seu agendamento de {self.get_equipamento_display()} "
                    f"para amanhã, {data_fmt} às {hora_fmt}.\n"
                    f"Quantidade: {self.quantidade} unidade(s)\n\n"
                    f"Qualquer dúvida, entre em contato com o NTI.\n\nAtenciosamente,\nNTI"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Aviso: Erro ao enviar lembrete ao solicitante: {e}")

        # E-mail para todos os admins que têm e-mail cadastrado
        try:
            admins_emails = list(
                User.objects.filter(is_superuser=True, email__isnull=False)
                .exclude(email='')
                .values_list('email', flat=True)
            )
            if admins_emails:
                send_mail(
                    subject=f"[NTI] Lembrete: Agendamento amanha — {self.nome}",
                    message=(
                        f"Agendamento previsto para amanhã:\n\n"
                        f"Solicitante: {self.nome} ({self.turma})\n"
                        f"Equipamento: {self.get_equipamento_display()}\n"
                        f"Quantidade: {self.quantidade} unidade(s)\n"
                        f"Início: {data_fmt} às {hora_fmt}\n"
                        f"Fim: {self.data_fim.strftime('%d/%m/%Y %H:%M')}\n\n"
                        f"Acesse o painel para mais detalhes."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=admins_emails,
                    fail_silently=True,
                )
        except Exception as e:
            print(f"Aviso: Erro ao enviar lembrete aos admins: {e}")

        # Marca como enviado para não reenviar
        self.lembrete_enviado = True
        self.save(update_fields=['lembrete_enviado'])

    @classmethod
    def enviar_lembretes_do_dia(cls):
        """Verifica e envia lembretes para todos os agendamentos de amanhã.
        Chamado automaticamente a cada acesso ao formulário."""
        amanha_inicio = (timezone.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        amanha_fim    = amanha_inicio + timedelta(days=1)

        # Busca aprovados de amanhã que ainda não receberam lembrete
        pendentes_lembrete = cls.objects.filter(
            status='aprovado',
            entregue=False,
            lembrete_enviado=False,
            data_inicio__gte=amanha_inicio,
            data_inicio__lt=amanha_fim,
        )
        for ag in pendentes_lembrete:
            ag.enviar_lembrete()

    @classmethod
    def expirar_pendentes(cls):
        """Rejeita automaticamente pendentes que ultrapassaram o prazo configurado.
        Chamado automaticamente a cada acesso ao formulário."""
        config = Configuracao.objects.first()
        prazo_dias = config.prazo_expiracao_pendente if config else 5
        prazo_limite = timezone.now() - timedelta(days=prazo_dias)

        pendentes_expirados = cls.objects.filter(
            status='pendente',
            data_inicio__lte=prazo_limite,
        )

        for agendamento in pendentes_expirados:
            agendamento.status = 'rejeitado'
            agendamento.save()
            LogAtividade.registrar(
                'agendamento_expirado',
                f"Agendamento de {agendamento.nome} ({agendamento.quantidade} {agendamento.get_equipamento_display()}(s) em {agendamento.data_inicio:%d/%m/%Y %H:%M}) expirado automaticamente após {prazo_dias} dias."
            )