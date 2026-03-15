# ─── Formulário de agendamento ────────────────────────────────────────────────
# Define os campos, widgets e validações do formulário público de agendamento.
# O ModelForm gera automaticamente os campos a partir do model Agendamento.

from django import forms
from .models import Agendamento


class AgendamentoForm(forms.ModelForm):

    # Campo quantidade usa Select em vez do NumberInput padrão
    # As opções são preenchidas dinamicamente pelo JS conforme o horário selecionado
    quantidade = forms.IntegerField(
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_quantidade'}),
        label="Quantidade de Itens"
    )

    # Checkbox obrigatório de aceite dos termos
    aceitou_termos = forms.BooleanField(
        required=True,
        label="Li e concordo com os termos de uso e privacidade",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_aceitou_termos'})
    )

    class Meta:
        model  = Agendamento
        fields = [
            'nome', 'email', 'turma',
            'data_inicio', 'data_fim',
            'equipamento', 'quantidade',
            'software_especifico', 'perifericos',
            'aceitou_termos'
        ]

        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Digite seu nome completo'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'exemplo@escolacamb.com.br',
                'required': 'required'
            }),
            'turma': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 9º Ano A - EFAF'
            }),
            'software_especifico': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Liste os softwares necessários (opcional)'
            }),
            'perifericos': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Ex: fones de ouvido, adaptadores'
            }),
            # format='%Y-%m-%dT%H:%M' é obrigatório para o input datetime-local
            # funcionar corretamente — sem isso o Django usa espaço em vez de T
            'data_inicio': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'type': 'datetime-local', 'class': 'form-control', 'id': 'id_data_inicio'}
            ),
            'data_fim': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'type': 'datetime-local', 'class': 'form-control', 'id': 'id_data_fim'}
            ),
            'equipamento': forms.Select(
                attrs={'class': 'form-select', 'id': 'id_equipamento'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Inicializa o select de quantidade vazio — o JS popula conforme o horário
        self.fields['quantidade'].widget.choices = [('', 'Selecione o horário primeiro')]

        # Mostra no select de equipamento apenas os que têm saldo disponível agora,
        # com a capacidade máxima atual informada entre parênteses
        novas_opcoes_equip = []
        for valor, nome in Agendamento.TIPO_EQUIPAMENTO:
            saldo_geral = Agendamento.obter_saldo(valor)
            if saldo_geral > 0:
                novas_opcoes_equip.append((valor, f"{nome} (Capacidade máx: {saldo_geral})"))

        if novas_opcoes_equip:
            self.fields['equipamento'].choices = novas_opcoes_equip