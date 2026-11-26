"""
Atualização automática da Beauty Week.

Fica vigiando as pastas de realizado (Varejo e VD). Quando um arquivo novo é salvo:
  1. espera o arquivo terminar de gravar;
  2. roda o processar_beauty.py;
  3. grava o data/beauty.json nas branches main e develop (sem trocar de branch nem mexer em outros arquivos);
  4. envia as duas para o GitHub (o site publica em 1 a 2 minutos).

Uso:
  python beauty_auto.py            vigia as pastas sem parar (dois cliques em "Beauty Week - atualizar sozinho.bat"; feche a janela para parar)
  python beauty_auto.py --uma-vez  roda uma vez e termina (para a tarefa agendada do Windows, de hora em hora).
                                   Só processa e publica se algum arquivo de realizado ou a planilha de metas mudou
                                   desde a última publicação. O que acontece fica em "Acompanhamento Beauty Week/atualizacao_automatica.log".
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
PASTAS = [BASE / "Acompanhamento Beauty Week" / "REALIZADOS" / "VAREJO",
          BASE / "Acompanhamento Beauty Week" / "REALIZADOS" / "VD"]
METAS = BASE / "Acompanhamento Beauty Week" / "METAS" / "METAS DIA.xlsx"
ESTADO = BASE / ".cache" / "beauty_auto_estado.json"   # arquivos da última publicação (modo --uma-vez)
LOG = BASE / "Acompanhamento Beauty Week" / "atualizacao_automatica.log"
DADOS = "data/beauty.json"
INTERVALO = 30      # segundos entre as checagens
ESTAVEL = 20        # segundos sem mudar de tamanho para considerar o arquivo pronto
BRANCHES = ["main", "develop"]


def log(msg):
    linha = f"{datetime.now():%d/%m %H:%M:%S}  {msg}"
    print(linha, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def git(*args, env=None):
    r = subprocess.run(["git", *args], cwd=BASE, capture_output=True, text=True, encoding="utf-8", env=env)
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


def assinatura():
    """Nome, tamanho e hora de cada arquivo de realizado (ignora temporários do Excel)."""
    arqs = sorted(a for p in PASTAS if p.exists() for a in p.glob("*.xlsx") if not a.name.startswith("~$"))
    return tuple((str(a), a.stat().st_size, a.stat().st_mtime) for a in arqs)


def assinatura_com_metas():
    m = ((str(METAS), METAS.stat().st_size, METAS.stat().st_mtime),) if METAS.exists() else ()
    return assinatura() + m


def pronto(sig, ler=assinatura):
    """Arquivo terminou de gravar: tamanho igual por ESTAVEL segundos e dá para abrir."""
    time.sleep(ESTAVEL)
    if ler() != sig:
        return False
    try:
        for nome, _, _ in sig:
            with open(nome, "rb"):
                pass
    except OSError:
        return False
    return True


def publicar(resumo):
    """Grava data/beauty.json como commit em main e develop sem trocar de branch."""
    blob = git("hash-object", "-w", DADOS)
    msg = f"Beauty Week: atualização automática ({resumo})\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
    atual = git("branch", "--show-current")
    mudou = False
    for b in BRANCHES:
        if git("rev-parse", f"{b}:{DADOS}") == blob:
            continue  # já está igual nessa branch
        idx = BASE / ".git" / f"beauty_auto_{b}.index"
        env = {**os.environ, "GIT_INDEX_FILE": str(idx)}
        try:
            git("read-tree", b, env=env)
            git("update-index", "--add", "--cacheinfo", f"100644,{blob},{DADOS}", env=env)
            arvore = git("write-tree", env=env)
        finally:
            idx.unlink(missing_ok=True)
        commit = git("commit-tree", arvore, "-p", b, "-m", msg)
        git("update-ref", f"refs/heads/{b}", commit)
        if b == atual:
            git("reset", "-q", "--", DADOS)  # deixa o índice da branch aberta em dia com o commit novo
        mudou = True
    if not mudou:
        log("Dados iguais aos já publicados; nada a enviar.")
        return
    for b in BRANCHES:  # uma de cada vez
        git("push", "-q", "origin", b)
    log(f"Publicado nas branches {' e '.join(BRANCHES)}: {resumo}")


def atualizar():
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, "processar_beauty.py"], cwd=BASE, capture_output=True, text=True, encoding="utf-8", env=env)
    if r.returncode:
        raise RuntimeError("processar_beauty.py falhou:\n" + (r.stderr or r.stdout)[-1500:])
    linhas = [l for l in r.stdout.splitlines() if l.startswith(("Varejo 20", "VD 20"))]
    for l in linhas:
        log("  " + l)
    resumo = " · ".join(l.split(" até ")[0].split(":")[0] + " até " + l.split(" até ")[1].split(" ")[0]
                        for l in linhas if " até " in l) or "dados novos"
    publicar(resumo)


def uma_vez():
    sig = assinatura_com_metas()
    try:
        antes = tuple(tuple(x) for x in json.loads(ESTADO.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        antes = None
    if sig == antes:
        log("Rodada agendada: nenhum arquivo novo de realizado ou de metas; nada a fazer.")
        return
    if not pronto(sig, assinatura_com_metas):
        log("Rodada agendada: arquivo ainda sendo gravado; fica para a próxima hora.")
        return
    log("Rodada agendada: arquivos novos, atualizando.")
    atualizar()
    ESTADO.parent.mkdir(exist_ok=True)
    ESTADO.write_text(json.dumps(sig), encoding="utf-8")


def main():
    log("Atualização automática ligada. Vigiando: " + ", ".join(str(p.relative_to(BASE)) for p in PASTAS))
    ultima = assinatura()
    while True:
        time.sleep(INTERVALO)
        sig = assinatura()
        if sig == ultima:
            continue
        if not pronto(sig):
            continue  # ainda gravando; tenta na próxima volta
        log("Arquivo de realizado novo: " + ", ".join(f"{Path(n).parent.name}/{Path(n).name} "
                                                       f"({datetime.fromtimestamp(m):%H:%M})" for n, _, m in sig))
        try:
            atualizar()
            ultima = sig
        except Exception as e:  # registra e tenta de novo na próxima volta
            log(f"ERRO: {e}")
            time.sleep(60)


if __name__ == "__main__":
    try:
        if "--uma-vez" in sys.argv:
            try:
                uma_vez()
            except Exception as e:
                log(f"ERRO na rodada agendada: {e}")
                sys.exit(1)
        else:
            main()
    except KeyboardInterrupt:
        log("Atualização automática desligada.")
