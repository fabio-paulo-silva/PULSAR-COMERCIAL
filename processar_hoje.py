"""PULSAR COMERCIAL - acompanhamento do dia.

Lê a venda parcial de hoje em Dados/Hoje (mesmo export de cupons do Retaguarda) e grava data/hoje.json:
  - por loja e por consultor: receita, boletos, itens, B1, brindes, BT, BP e boletos elegíveis ao BP;
  - por loja: receita por hora de hoje e a curva de venda por hora (quanto do dia costuma estar vendido a cada hora),
    calculada com os cupons do mês atual no mesmo dia da semana (ou todos os dias, se houver poucos).

Mesmas regras do processar_dados.py: só cupom efetivado, brinde (< R$ 1) fora dos boletos, sacola descontada dos itens.
As metas, o gap e os alvos vêm do data/pulsar.json (rode o processar_dados.py antes, com as vendas até ontem).
"""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

import processar_dados as p

PASTA_HOJE = p.PASTA_VENDAS / "Hoje"
ARQ_SAIDA = p.BASE / "data" / "hoje.json"
COLS = ["Loja", "Data", "Hora", "Status cupom", "Qtd itens", p.RECEITA, "Consultores", "Campanhas"]
MIN_DIAS_MESMO_DIA = 2    # mínimo de dias iguais (ex.: duas quintas) para usar a curva do mesmo dia da semana


def ler_cupons_hora(arq: Path) -> pd.DataFrame:
    """Cupons efetivados com hora, já com as regras de brinde, sacola, BT e BP."""
    v = p.ler_excel(arq, usecols=COLS)
    v = v[v["Status cupom"] == "Efetivado"].rename(columns={p.RECEITA: "receita"}).copy()
    camp = v["Campanhas"].fillna("").astype(str).str.upper()
    v["Qtd itens"] = (v["Qtd itens"] - camp.str.contains("SACOLA").astype(int)).clip(lower=0)
    v["data"] = pd.to_datetime(v["Data"], format="%d/%m/%Y")
    v["hora"] = pd.to_numeric(v["Hora"].astype(str).str.slice(0, 2), errors="coerce").fillna(0).astype(int).clip(0, 23)
    v["minuto"] = v["Hora"].astype(str)
    v["loja"] = v["Loja"].astype(str).str.extract(r"^(\d+)")[0]
    v["consultor"] = v["Consultores"].fillna("").astype(str).str.strip()
    venda = v["receita"] >= p.LIMITE_BRINDE
    v["bol"] = venda.astype(int)
    v["it"] = v["Qtd itens"].where(venda, 0)
    v["b1"] = (venda & (v["Qtd itens"] <= 1)).astype(int)
    v["br"] = (~venda).astype(int)
    v["bt"] = (venda & camp.str.contains("BOLETO TURBINADO")).astype(int)
    v["bp"] = (venda & camp.str.contains("BOLETO PROMOCIONAL")).astype(int)
    v["bpe"] = (venda & (v["receita"] >= p.SARRAFO_BP)).astype(int)
    return v


def receita_por_hora(arq: Path) -> pd.DataFrame:
    """Receita por loja, dia e hora de um arquivo do mês (para a curva). Guarda em cache até o arquivo mudar."""
    cache = p.PASTA_CACHE / f"{arq.stem}_hora_v1.pkl"
    if cache.exists() and cache.stat().st_mtime >= arq.stat().st_mtime:
        return pd.read_pickle(cache)
    print(f"  lendo as horas de {arq.relative_to(p.BASE)} ...", flush=True)
    v = p.ler_excel(arq, usecols=["Loja", "Data", "Hora", "Status cupom", p.RECEITA])
    v = v[v["Status cupom"] == "Efetivado"]
    g = pd.DataFrame({
        "loja": v["Loja"].astype(str).str.extract(r"^(\d+)")[0],
        "data": pd.to_datetime(v["Data"], format="%d/%m/%Y"),
        "hora": pd.to_numeric(v["Hora"].astype(str).str.slice(0, 2), errors="coerce").fillna(0).astype(int).clip(0, 23),
        "rec": v[p.RECEITA].clip(lower=0),
    }).groupby(["loja", "data", "hora"], as_index=False)["rec"].sum()
    p.PASTA_CACHE.mkdir(exist_ok=True)
    g.to_pickle(cache)
    return g


def curvas(hoje: pd.Timestamp):
    """Participação de cada hora na venda do dia, por loja e da rede, no mesmo dia da semana de hoje."""
    arqs = [a for a in sorted(p.PASTA_VENDAS.rglob("*.xlsx"))
            if not a.name.startswith("~$") and "Hoje" not in a.parts and p.mes_do_arquivo(a) == (hoje.year, hoje.month)]
    if not arqs:
        return {}, None
    h = pd.concat([receita_por_hora(a) for a in arqs], ignore_index=True)
    h = h[h["data"] < hoje]
    mesmo = h[h["data"].dt.dayofweek == hoje.dayofweek]
    base = mesmo if mesmo["data"].nunique() >= MIN_DIAS_MESMO_DIA else h

    def forma(df):
        s = df.groupby("hora")["rec"].sum().reindex(range(24), fill_value=0)
        tot = s.sum()
        return [round(float(x / tot), 5) for x in s] if tot > 0 else None

    por_loja = {loja: forma(g) for loja, g in base.groupby("loja")}
    return por_loja, forma(base)


def main():
    arqs = sorted(a for a in PASTA_HOJE.glob("*.xlsx") if not a.name.startswith("~$")) if PASTA_HOJE.exists() else []
    if not arqs:
        print(f"Nenhum arquivo em {PASTA_HOJE.relative_to(p.BASE)}: salve lá o export de cupons de hoje.")
        return
    v = pd.concat([ler_cupons_hora(a) for a in arqs], ignore_index=True)
    dia = v["data"].max()
    v = v[v["data"] == dia]
    ate = v["minuto"].max()
    print(f"Venda de hoje: {dia:%d/%m/%Y} até {ate} ({len(v)} cupons)")
    por_loja, rede = curvas(dia)

    soma = ["rec", "bol", "it", "b1", "br", "bt", "bp", "bpe"]
    lojas = []
    for loja, g in v.rename(columns={"receita": "rec"}).groupby("loja"):
        t = g[soma].sum()
        h = g.groupby("hora")["rec"].sum().reindex(range(24), fill_value=0)
        lojas.append({"id": loja, **{k: round(float(t[k]), 2) for k in soma},
                      "h": [round(float(x), 2) for x in h], "curva": por_loja.get(loja)})
    cons = []
    for (loja, c), g in v.rename(columns={"receita": "rec"}).groupby(["loja", "consultor"]):
        codigo, _, nome = c.partition(" - ")
        if codigo.strip() in ("0", "") or "SEM CONSULTOR" in c.upper():
            continue
        t = g[soma].sum()
        cons.append({"id": f"{codigo.strip()}@{loja}", "loja": loja, "nome": p.nome_curto(nome or c),
                     **{k: round(float(t[k]), 2) for k in soma}})

    saida = {"geradoEm": datetime.now().isoformat(timespec="minutes"), "dia": dia.strftime("%Y-%m-%d"), "ate": ate,
             "arquivos": [a.name for a in arqs], "curvaRede": rede, "lojas": lojas, "consultores": cons}
    ARQ_SAIDA.parent.mkdir(exist_ok=True)
    ARQ_SAIDA.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    pul = json.loads((p.BASE / "data" / "pulsar.json").read_text(encoding="utf-8"))
    esperado = (pd.Timestamp(pul["ontem"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"OK: {len(lojas)} lojas, {len(cons)} consultores, R$ {sum(l['rec'] for l in lojas):,.0f} -> "
          f"{ARQ_SAIDA.relative_to(p.BASE)}")
    if saida["dia"] != esperado:
        print(f"Atenção: o data/pulsar.json vai até {pul['ontem']}; para a meta de hoje ({saida['dia']}) ele precisa "
              f"das vendas até a véspera. Rode o processar_dados.py com os arquivos até ontem.")


if __name__ == "__main__":
    main()
