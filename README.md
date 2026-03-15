# SysAgen — Sistema de Agendamento de Equipamentos NTI

Sistema web desenvolvido em Django para gerenciamento de reservas de notebooks e tablets da Escola CAMB.

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

---

## Requisitos

- Python 3.10+
- Windows (para o servidor de produção com Waitress)

---

## Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/srxandes/SysAgen.git
cd SysAgen
```

### 2. Crie e ative o ambiente virtual

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

Copie o arquivo de exemplo e preencha com os valores reais:

```bash
copy .env.example .env
```

Edite o `.env` com suas configurações de e-mail e a chave secreta.

### 5. Configure as credenciais do Google Calendar

- Acesse o [Google Cloud Console](https://console.cloud.google.com)
- Crie um projeto e ative a **Google Calendar API**
- Crie uma **Service Account** e baixe o arquivo de chave JSON
- Renomeie o arquivo para `credentials.json` e coloque na raiz do projeto
- Compartilhe as agendas do Google Calendar com o e-mail da Service Account (permissão: *Fazer alterações em eventos*)

### 6. Execute as migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Crie o superusuário principal

```bash
python manage.py createsuperuser
```

> **Importante:** O usuário `tecno_camb` tem permissões exclusivas de remover outros admins. Crie-o primeiro.

### 8. Colete os arquivos estáticos

```bash
python manage.py collectstatic
```

### 9. Inicie o servidor

```bash
iniciar_servidor.bat
```

O sistema ficará disponível em:
- `http://10.17.108.77/`
- `http://agendamentosnti.escolacamb.br/`

---

## Configurar backup automático

Execute o arquivo abaixo **uma única vez como Administrador** para agendar o backup diário às 03:00:

```
configurar_backup.bat
```

Os backups são salvos em `backups/` com o nome `db_AAAA-MM-DD_HHmm.sqlite3`.

---

## Estrutura do projeto

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

## Variáveis de ambiente

| Variável | Descrição |
|----------|-----------|
| `SECRET_KEY` | Chave secreta do Django |
| `DEBUG` | Modo debug (`True` ou `False`) |
| `EMAIL_HOST` | Servidor SMTP |
| `EMAIL_PORT` | Porta SMTP |
| `EMAIL_USE_TLS` | Usar TLS (`True` ou `False`) |
| `EMAIL_HOST_USER` | E-mail remetente |
| `EMAIL_HOST_PASSWORD` | App Password do Google |
| `DEFAULT_FROM_EMAIL` | E-mail exibido como remetente |

---

## Desenvolvido por

xand3 — 2º ano Informática para Internet
