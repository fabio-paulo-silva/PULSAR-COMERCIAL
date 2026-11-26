@echo off
rem PULSAR COMERCIAL: processa a pasta "Acompanhamento Beauty Week" e abre a página no navegador.
cd /d "%~dp0"
echo Processando a Beauty Week...
python processar_beauty.py
if errorlevel 1 (
  echo.
  echo Erro ao processar. Veja a mensagem acima.
  pause
  exit /b 1
)
echo.
echo Abrindo em http://localhost:8744/beauty.html  (feche esta janela para encerrar)
start "" http://localhost:8744/beauty.html
python -m http.server 8744
