@echo off
rem Duplo clique: encerra o servidor do LocaControl iniciado pelo atalho "Iniciar LocaControl".
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop.ps1"
if errorlevel 1 pause
