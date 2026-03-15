# SysAgen — Sistema de Agendamento de Equipamentos NTI

Sistema web desenvolvido em Django para gerenciamento de reservas de notebooks e tablets.

---

## Funcionalidades

- Agendamento de notebooks e tablets por professores
- Aprovação automática ou manual (conforme limite configurável)
- Integração com Google Calendar
- Notificações por e-mail (confirmação, pendência, rejeição, lembrete)
- Painel administrativo customizado com dashboard
- Histórico de agendamentos com exportação para Excel
- Logs de atividade
- Lista negra de e-mails
- Backup automático do banco de dados
- Expiração automática de pendentes


### Configuração das credenciais do Google Calendar

- Acesse o [Google Cloud Console](https://console.cloud.google.com)
- Crie um projeto e ative a **Google Calendar API**
- Crie uma **Service Account** e baixe o arquivo de chave JSON
- Renomeie o arquivo para `credentials.json` e coloque na raiz do projeto
- Compartilhe as agendas do Google Calendar com o e-mail da Service Account (permissão: *Fazer alterações em eventos*)

### Criando o Superusuário

```bash
python manage.py createsuperuser
```

> **Importante:** O usuário `tecno_camb` tem permissões exclusivas de remover outros admins. Crie-o primeiro.

### Estrutura do projeto

```
SysAgen/
├── manage.py
├── .env                  # Variáveis de ambiente (não versionar)
├── .env.example          # Modelo do .env
├── .gitignore
├── requirements.txt
├── iniciar_servidor.bat
├── configurar_backup.bat
├── backup.bat
├── credentials.json      # Credenciais Google (não versionar)
├── db.sqlite3            # Banco de dados (não versionar)
├── staticfiles/          # Gerado pelo collectstatic (não versionar)
├── setup/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── agendamentos/
    ├── models.py
    ├── views.py
    ├── admin.py
    ├── forms.py
    ├── utils.py
    └── templates/
        ├── 404.html
        ├── 500.html
        ├── 403.html
        ├── admin/
        │   ├── base_site.html
        │   ├── dashboard.html
        │   └── logs.html
        └── agendamentos/
            ├── index.html
            ├── formulario.html
            ├── sucesso.html
            ├── agenda.html
            └── cadastro_admin.html
```

---

## URLs principais

| URL | Descrição |
|-----|-----------|
| `/` | Página inicial |
| `/agendar/` | Formulário de agendamento |
| `/agenda/` | Agenda pública (Google Calendar) |
| `/admin/` | Painel administrativo |
| `/admin/dashboard/` | Dashboard NTI |
| `/admin/logs/` | Logs de atividade |
| `/nti/cadastrar-admin/` | Cadastro de admins (requer login) |

---
## Desenvolvido por

xand3 — 2º ano Informática para Internet
