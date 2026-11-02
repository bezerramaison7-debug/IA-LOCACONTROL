@echo off
rem Duplo clique: inicia o LocaControl e abre o navegador. Nao e preciso manter esta janela.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch.ps1"
if errorlevel 1 pause
