@echo off
rem PULSAR COMERCIAL: processa a venda parcial de hoje (Dados\Hoje) e abre o acompanhamento do dia no navegador.
cd /d "%~dp0"
echo Processando a venda de hoje...
python processar_hoje.py
if errorlevel 1 (
  echo.
  echo Erro ao processar a venda de hoje. Veja a mensagem acima.
  pause
  exit /b 1
)
echo.
echo Abrindo o acompanhamento do dia em http://localhost:8744/hoje.html  (feche esta janela para encerrar)
start "" http://localhost:8744/hoje.html
python -m http.server 8744
