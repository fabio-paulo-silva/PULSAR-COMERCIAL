@echo off
rem PULSAR COMERCIAL: processa as planilhas e abre o painel no navegador.
cd /d "%~dp0"
echo Processando planilhas...
python processar_dados.py
if errorlevel 1 (
  echo.
  echo Erro ao processar as planilhas. Veja a mensagem acima.
  pause
  exit /b 1
)
echo.
echo Abrindo o PULSAR em http://localhost:8744/  (feche esta janela para encerrar)
start "" http://localhost:8744/
python -m http.server 8744
