"""PULSAR COMERCIAL - acompanhamento da Beauty Week (Varejo, VD e Total canais).

Lê a pasta "Acompanhamento Beauty Week" e grava data/beauty.json:
  METAS/METAS DIA.xlsx            abas VAREJO e VD: PDV, loja/ER, praça, GVO, META e DIA
  REALIZADOS/VAREJO/*.xlsx        export de cupons do Retaguarda (cupom_venda_...)
  REALIZADOS/VD/*.xlsx            export de pedidos com NF emitida (pedidos_nf_emitida_...)

Regras:
  Varejo: só cupons "Efetivado"; realizado = soma de "Receita liquida (-) trocas"; loja = código no início de "Loja".
  VD: fora os pedidos "Cancelado Pelo Usuário" (DetalheSituaçãoComercial); loja = código da "EstruturaPai"
      (pedido sem estrutura pai, como o Omnichannel, usa o código do CanalDistribuicao); realizado = soma de "ValorPedido";
      dia = DataFaturamento; hora = DataAutorizaçãoFaturamento.
  Regional: pela praça (dCentros). Varejo também leva boletos, itens e B1 de cada loja (mesmas regras do painel: brinde
      abaixo de R$ 1 fora dos boletos, sacola descontada dos itens) e o cluster, para comparar BM, IPB e % B1 com a média do cluster.
   Cluster da loja de varejo: dCentros (Shopping fecha às 22h; Rua, Galeria,
      Hipermercado e Cash & Carry às 19h). VD (ERs): funcionam das 8h às 19h.
  Ritmo ("horaização"): quanto do dia já deveria estar vendido até a hora do último cupom/pedido.
      Varejo: curva de venda por hora das lojas do mesmo tipo (shopping x demais) nas mesmas semanas do mês, no mesmo
      dia da semana, cortada no horário de fechamento. VD: distribuição uniforme das 8h às 19h.
"""
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

import processar_dados as p
from processar_hoje import receita_por_hora

PASTA = p.BASE / "Acompanhamento Beauty Week"
ARQ_METAS = PASTA / "METAS" / "METAS DIA.xlsx"
ARQ_SAIDA = p.BASE / "data" / "beauty.json"
FECHA_SHOPPING, FECHA_DEMAIS = 22, 19
VD_ABRE, VD_FECHA = 8, 19
CANCELADO_VD = "CANCELADO PELO USUÁRIO"

cod = lambda v: (re.match(r"\s*(\d+)", str(v)) or [None, None])[1]


def ler_metas(aba):
    m = pd.read_excel(ARQ_METAS, sheet_name=aba, engine="calamine")
    m.columns = [str(c).strip().upper() for c in m.columns]
    nome = next(c for c in m.columns if c in ("LOJA", "ER"))
    m = m[m["PDV"].notna() & m["META"].notna()].copy()
    m["id"] = m["PDV"].map(cod)
    m["dia"] = pd.to_datetime(m["DIA"]).dt.strftime("%Y-%m-%d")
    return m.rename(columns={nome: "nome", "PRAÇA": "praca", "GVO": "gvo", "META": "meta"})[["id", "nome", "praca", "gvo", "meta", "dia"]]


def arquivos(sub):
    pasta = PASTA / "REALIZADOS" / sub
    return sorted(a for a in pasta.glob("*.xlsx") if not a.name.startswith("~$")) if pasta.exists() else []


def realizado_varejo():
    fr = []
    for a in arquivos("VAREJO"):
        v = p.ler_excel(a, usecols=["Loja", "Data", "Hora", "Status cupom", "Qtd itens", "Campanhas", "Receita liquida (-) trocas"])
        v = v[v["Status cupom"] == "Efetivado"]
        camp = v["Campanhas"].fillna("").astype(str).str.upper()
        itens = (v["Qtd itens"] - camp.str.contains("SACOLA").astype(int)).clip(lower=0)
        venda = v["Receita liquida (-) trocas"] >= p.LIMITE_BRINDE
        fr.append(pd.DataFrame({"id": v["Loja"].map(cod), "dia": pd.to_datetime(v["Data"], format="%d/%m/%Y").dt.strftime("%Y-%m-%d"),
                                "hm": v["Hora"].astype(str).str.slice(0, 5), "valor": v["Receita liquida (-) trocas"],
                                "bol": venda.astype(int), "it": itens.where(venda, 0), "b1": (venda & (itens <= 1)).astype(int)}))
    return pd.concat(fr, ignore_index=True) if fr else pd.DataFrame(columns=["id", "dia", "hm", "valor", "bol", "it", "b1"])


def realizado_vd():
    fr = []
    for a in arquivos("VD"):
        v = p.ler_excel(a)
        v = v[v["DetalheSituaçãoComercial"].astype(str).str.strip().str.upper() != CANCELADO_VD]
        loja = v["EstruturaPai"].map(cod).fillna(v["CanalDistribuicao"].map(cod))
        aut = pd.to_datetime(v["DataAutorizaçãoFaturamento"], format="%d/%m/%Y %H:%M", errors="coerce")
        fr.append(pd.DataFrame({"id": loja, "dia": pd.to_datetime(v["DataFaturamento"], format="%d/%m/%Y").dt.strftime("%Y-%m-%d"),
                                "hm": aut.dt.strftime("%H:%M"), "valor": v["ValorPedido"]}))
    return pd.concat(fr, ignore_index=True) if fr else pd.DataFrame(columns=["id", "dia", "hm", "valor"])


def curva_varejo(dia: pd.Timestamp, shopping: set):
    """Participação de cada hora no dia: lojas de shopping x demais, mesmo dia da semana, no mês de referência."""
    arqs = [a for a in sorted(p.PASTA_VENDAS.rglob("cupom_venda*.xlsx"))
            if "Hoje" not in a.parts and p.mes_do_arquivo(a) == (dia.year, dia.month)]
    h = pd.concat([receita_por_hora(a) for a in arqs], ignore_index=True)
    h = h[h["data"] < dia]
    mesmo = h[h["data"].dt.dayofweek == dia.dayofweek]
    h = mesmo if mesmo["data"].nunique() >= 2 else h
    out = {}
    for nome, grupo, fecha in (("shopping", h[h["loja"].isin(shopping)], FECHA_SHOPPING), ("demais", h[~h["loja"].isin(shopping)], FECHA_DEMAIS)):
        s = grupo.groupby("hora")["rec"].sum().reindex(range(24), fill_value=0)
        s[s.index >= fecha] = 0
        out[nome] = [round(float(x / s.sum()), 5) for x in s]
    return out


def curva_vd():
    s = [1.0 if VD_ABRE <= hh < VD_FECHA else 0.0 for hh in range(24)]
    return [round(x / sum(s), 5) for x in s]


def montar(metas, real, centros, extra):
    """Uma linha por loja e dia (meta, realizado, realizado por hora) + o realizado de lojas sem meta."""
    reg = centros.groupby("PRAÇA")["REGIONAL"].first().to_dict()
    real = real.dropna(subset=["id"])
    tot = real.groupby(["id", "dia"])["valor"].sum()
    ind = real.groupby(["id", "dia"])[["bol", "it", "b1"]].sum() if "bol" in real else None
    hora = real.assign(h=pd.to_numeric(real["hm"].str.slice(0, 2), errors="coerce")).dropna(subset=["h"])
    hora = hora.groupby(["id", "dia", "h"])["valor"].sum()
    lojas = []
    for r in metas.itertuples():
        hs = [0.0] * 24
        if (r.id, r.dia) in tot.index:
            for hh, v in hora.loc[(r.id, r.dia)].items():
                hs[int(hh)] = round(float(v), 2)
        lojas.append({"id": r.id, "nome": str(r.nome).strip().title(), "praca": r.praca, "regional": reg.get(r.praca, "—"),
                      "gvo": str(r.gvo).strip(), "dia": r.dia, "meta": round(float(r.meta), 2),
                      "real": round(float(tot.get((r.id, r.dia), 0)), 2), "h": hs, **extra(r.id),
                      **({k: int(ind.loc[(r.id, r.dia), k]) if (r.id, r.dia) in ind.index else 0 for k in ("bol", "it", "b1")}
                         if ind is not None else {})})
    com_meta = set(zip(metas["id"], metas["dia"]))
    sem = [{"id": i, "dia": d, "real": round(float(v), 2)} for (i, d), v in tot.items() if (i, d) not in com_meta and v]
    ate = real.groupby("dia")["hm"].max().to_dict()
    return lojas, sem, ate


def main():
    centros = p.ler_centros()
    clu = centros["CLUSTER"].astype(str).str.strip().str.upper()
    shopping = set(clu[clu == "SHOPPING"].index)
    mv, md = ler_metas("VAREJO"), ler_metas("VD")
    rv, rd = realizado_varejo(), realizado_vd()
    lv, sv, av = montar(mv, rv, centros, lambda i: {"shopping": i in shopping, "fecha": FECHA_SHOPPING if i in shopping else FECHA_DEMAIS,
                                                    "cluster": str(centros["CLUSTER"].get(i, "Sem cluster")).strip()})
    ld, sd, ad = montar(md, rd, centros, lambda i: {"fecha": VD_FECHA})
    dias = sorted(set(mv["dia"]) | set(md["dia"]))
    curvas = {}
    for d in dias:
        try:
            curvas[d] = curva_varejo(pd.Timestamp(d), shopping)
        except ValueError:
            curvas[d] = None
    saida = {"geradoEm": datetime.now().isoformat(timespec="minutes"), "dias": dias,
             "varejo": {"ate": av, "lojas": lv, "semMeta": sv, "curvas": curvas},
             "vd": {"ate": ad, "lojas": ld, "semMeta": sd, "curva": curva_vd(), "abre": VD_ABRE, "fecha": VD_FECHA}}
    ARQ_SAIDA.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for canal, ls, sm, ate in (("Varejo", lv, sv, av), ("VD", ld, sd, ad)):
        for d in dias:
            m = sum(x["meta"] for x in ls if x["dia"] == d); r = sum(x["real"] for x in ls if x["dia"] == d)
            s = sum(x["real"] for x in sm if x["dia"] == d)
            print(f"{canal} {d}: meta R$ {m:,.0f} | realizado R$ {r:,.0f} ({r / m if m else 0:.1%}) até {ate.get(d, '—')}"
                  + (f" | sem meta: R$ {s:,.0f} ({', '.join(x['id'] for x in sm if x['dia'] == d)})" if s else ""))
    print(f"OK -> {ARQ_SAIDA.relative_to(p.BASE)}")


if __name__ == "__main__":
    main()
