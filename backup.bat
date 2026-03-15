@echo off
title Backup NTI — Banco de Dados

:: Define o diretório do projeto (mesmo lugar que o backup.bat)
cd /d "%~dp0"

:: Cria a pasta de backups se não existir
if not exist "backups" mkdir backups

:: Gera o nome do arquivo com data e hora
set HORA=%time:~0,2%%time:~3,2%
set HORA=%HORA: =0%
set NOME_ARQUIVO=backups\db_%date:~6,4%-%date:~3,2%-%date:~0,2%_%HORA%.sqlite3

:: Copia o banco
copy /Y db.sqlite3 "%NOME_ARQUIVO%" > nul

if %errorlevel% == 0 (
    echo [%date% %time%] Backup criado: %NOME_ARQUIVO%
    echo [%date% %time%] Backup criado com sucesso. >> logs\backup.txt
) else (
    echo [%date% %time%] ERRO ao criar backup!
    echo [%date% %time%] ERRO ao criar backup. >> logs\backup.txt
)