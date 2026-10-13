"""PULSAR - O que as lojas acima do ritmo fazem diferente (canais, campanhas, Ação de Fluxo).

Lê os cupons do mês corrente e o dados/pulsar.json (ritmo e metas) e gera
analises/boas_praticas_<mês>.xlsx com:
  - Indicadores: por loja, ritmo e alavancas (canais, campanhas, conversão do brinde, ID cliente)
  - Comparação: mediana das lojas acima x abaixo do ritmo e correlação com o ritmo
  - Oportunidades: para cada loja abaixo do ritmo, o ganho estimado ao chegar no nível
    das lojas acima do ritmo do mesmo cluster
Uso: python analises/boas_praticas.py
"""
import json
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
import processar_dados as p  # noqa: E402

CANAIS = {  # código do canal de vendas -> grupo
    "11": "Parcerias / venda externa", "24": "Calçada Perfumada", "20": "Venda fora de loja (VFL)",
    "10": "VIC", "25": "VIC", "3": "WhatsApp", "4": "WhatsApp", "6": "Drive thru",
    "13": "Experimentação", "14": "Experimentação", "15": "Experimentação", "16": "Experimentação",
    "17": "Experimentação", "18": "Experimentação", "8": "Live commerce", "22": "Estoque externo",
}
TAGS = {  # rótulo -> trecho procurado na coluna Campanhas
    "Boleto Turbinado": "BOLETO TURBINADO", "Boleto Promocional": "BOLETO PROMOCIONAL",
    "Compre e Leve": "COMPRE E LEVE", "Desconto sarrafo": "DESCONTO SARRAFO", "Cashback (resgate)": "CASHBACK",
    "Itens adicionais (Plano YTG)": "ITENS ADICIONAIS", "Desconto personalizado": "DESCONTO PERSONALIZADO",
}


def cupons_do_mes():
    arqs = sorted((BASE / "Dados").rglob("*.xlsx"))
    d = json.loads((BASE / "data" / "pulsar.json").read_text(encoding="utf-8"))
    ini = pd.Timestamp(d["ontem"]).replace(day=1)
    partes = []
    for a in arqs:
        mm = p.mes_do_arquivo(a)
        if mm and (mm[0], mm[1]) == (ini.year, ini.month):
            cab = list(p.ler_excel(a, nrows=0).columns)
            if "Qtd itens" not in cab:
                continue  # formato item a item: este estudo usa o formato por cupom
            partes.append(p.ler_excel(a, usecols=["Loja", "Data", "Status cupom", "Canal de vendas", "Qtd itens",
                                                  "Receita liquida", "Desconto fidelidade", "Campanhas", "Cliente",
                                                  "Cupom Marcadores"]))
    v = pd.concat(partes)
    v = v[v["Status cupom"] == "Efetivado"].copy()
    v["loja"] = v["Loja"].astype(str).str.extract(r"^(\d+)")[0]
    v["camp"] = v["Campanhas"].fillna("").astype(str).str.upper()
    # a sacola entra como item: desconta 1 quando o cupom tem a campanha da sacola (mesma regra do painel)
    v["Qtd itens"] = (v["Qtd itens"] - v["camp"].str.contains("SACOLA").astype(int)).clip(lower=0)
    v["canal"] = v["Canal de vendas"].astype(str).str.extract(r"^(\d+)")[0].map(CANAIS).fillna("Loja")
    v["venda"] = v["Receita liquida"] >= p.LIMITE_BRINDE
    v["fluxo"] = v["camp"].str.contains("FLUXO")
    v["cpf"] = v["Cliente"].astype(str).str.contains(r"\*")
    v["fidel"] = v["Desconto fidelidade"].fillna(0) > 0
    v["cr"] = v["Cupom Marcadores"].fillna("").astype(str).str.contains("CLIQUE")
    return v, d


def indicadores(v, d):
    lojas = {l["id"]: l for l in d["lojas"]}
    ontem = int(d["ontem"][8:])
    linhas = []
    for loja, g in v.groupby("loja"):
        if loja not in lojas:
            continue
        l = lojas[loja]
        meta_ate = sum(l["meta"][:ontem])
        venda = g[g["venda"]]
        bol, rec, it = len(venda), venda["Receita liquida"].sum(), venda["Qtd itens"].sum()
        brinde_so = (g["fluxo"] & ~g["venda"]).sum()
        rf, pl = l.get("ref") or {}, l.get("plano") or {}
        bm_ref = rf["rec"] / rf["bol"] if rf.get("bol") else None
        bm_alvo = pl["bmAlvo"] * (rf["bol"] + rf.get("br", 0)) / rf["bol"] if pl.get("bmAlvo") and rf.get("bol") else bm_ref
        bol_alvo = meta_ate / bm_alvo if bm_alvo else None
        fluxo_conv = (g["fluxo"] & g["venda"]).sum()
        r = {"loja": loja, "nome": l["nome"], "praca": l["praca"], "gvo": l["gestor"],
             "cluster": (l.get("plano") or {}).get("cluster", ""),
             "ritmo": rec / meta_ate if meta_ate else None, "receita": rec, "meta_ate": meta_ate,
             "meta_mes": sum(l["meta"]),
             "boletos": bol, "bm": rec / bol if bol else None, "ipb": it / bol if bol else None,
             # boletos feitos ÷ boletos que a meta pede com o BM alvo de venda (mesma régua do painel)
             "pct_boletos_da_meta": bol / bol_alvo if bol_alvo else None,
             "brindes_acao_fluxo": int(brinde_so),
             "conversao_acao_fluxo": fluxo_conv / (fluxo_conv + brinde_so) if (fluxo_conv + brinde_so) else None,
             "% com CPF": venda["cpf"].mean(), "% fidelidade": venda["fidel"].mean(),
             "% clique e retire": venda["cr"].mean()}
        for canal in sorted(set(CANAIS.values())):
            r[f"% {canal}"] = (venda["canal"] == canal).mean()
        r["% fora do balcão"] = (venda["canal"] != "Loja").mean()
        for rot, t in TAGS.items():
            r[f"% {rot}"] = venda["camp"].str.contains(t, regex=False).mean()
        linhas.append(r)
    return pd.DataFrame(linhas)


def main():
    v, d = cupons_do_mes()
    df = indicadores(v, d)
    df["grupo"] = pd.cut(df["ritmo"], [0, .96, 1.0, 9], labels=["abaixo", "atenção", "acima"], right=False)
    alav = [c for c in df.columns if c.startswith("%") or c in ("conversao_acao_fluxo", "pct_boletos_da_meta", "ipb", "bm")]
    comp = pd.DataFrame({
        "acima do ritmo (mediana)": df[df.grupo == "acima"][alav].median(),
        "abaixo do ritmo (mediana)": df[df.grupo == "abaixo"][alav].median(),
        "correlação com o ritmo": df[alav].rank().corrwith(df["ritmo"].rank()),  # Spearman sem scipy
    })
    comp["diferença"] = comp.iloc[:, 0] - comp.iloc[:, 1]
    comp = comp.sort_values("correlação com o ritmo", ascending=False)

    # Oportunidade por loja abaixo do ritmo: chegar à mediana das lojas acima do mesmo cluster
    ref = df[df.grupo == "acima"].groupby("cluster")[alav].median()
    ref_rede = df[df.grupo == "acima"][alav].median()
    pm = (v[v["venda"]].groupby("loja")["Receita liquida"].sum() / v[v["venda"]].groupby("loja")["Qtd itens"].sum())
    ops = []
    for _, r in df[df.grupo == "abaixo"].iterrows():
        rf = ref.loc[r.cluster] if r.cluster in ref.index else ref_rede
        bm, pmi = r.bm or 0, pm.get(r.loja, 0)
        g = {
            "Canais fora do balcão": max(0, rf["% fora do balcão"] - r["% fora do balcão"]) * r.boletos * bm,
            "Conversão da Ação de Fluxo": max(0, (rf["conversao_acao_fluxo"] or 0) - (r.conversao_acao_fluxo or 0)) * r.brindes_acao_fluxo / max(1e-9, 1 - (r.conversao_acao_fluxo or 0)) * bm if r.brindes_acao_fluxo else 0,
            "Boleto Turbinado": max(0, rf["% Boleto Turbinado"] - r["% Boleto Turbinado"]) * r.boletos * pmi,
            "Boleto Promocional": max(0, rf["% Boleto Promocional"] - r["% Boleto Promocional"]) * r.boletos * pmi * .5,
            "Compre e Leve": max(0, rf["% Compre e Leve"] - r["% Compre e Leve"]) * r.boletos * pmi,
        }
        top = sorted(g.items(), key=lambda x: -x[1])
        mes = r.meta_mes / r.meta_ate if r.meta_ate else 1   # do período até ontem para o mês inteiro
        ops.append({"loja": r.nome, "gvo": r.gvo, "cluster": r.cluster, "ritmo": r.ritmo,
                    **{f"ganho {k} (mês)": val * mes for k, val in g.items()},
                    "maior alavanca": top[0][0], "ganho total no mês": sum(g.values()) * mes})
    ops = pd.DataFrame(ops).sort_values("ganho total no mês", ascending=False)

    # Adoção dos canais e campanhas: quantas lojas usam e o ritmo de quem usa x quem não usa
    adoc = []
    for c in [f"% {x}" for x in sorted(set(CANAIS.values()))] + [f"% {x}" for x in TAGS]:
        usa = df[df[c] > 0]
        nao = df[df[c] == 0]
        adoc.append({"alavanca": c[2:], "lojas que usam": len(usa),
                     "% das lojas acima que usam": (df[df.grupo == "acima"][c] > 0).mean(),
                     "% das lojas abaixo que usam": (df[df.grupo == "abaixo"][c] > 0).mean(),
                     "ritmo de quem usa": usa["ritmo"].median(), "ritmo de quem não usa": nao["ritmo"].median()})
    adoc = pd.DataFrame(adoc).sort_values("lojas que usam", ascending=False)

    # Referências: as 3 lojas acima do ritmo que mais usam cada alavanca (exemplo para as outras)
    refs = []
    for c in ["% Calçada Perfumada", "% Venda fora de loja (VFL)", "% WhatsApp", "% VIC", "% Parcerias / venda externa",
              "% Experimentação", "% Boleto Turbinado", "% Boleto Promocional", "% Compre e Leve", "% Cashback (resgate)",
              "conversao_acao_fluxo"]:
        top3 = df[(df.grupo == "acima") & (df[c] > 0)].nlargest(3, c)
        for _, r in top3.iterrows():
            refs.append({"alavanca": c.replace("% ", "").replace("conversao_acao_fluxo", "Conversão da Ação de Fluxo"),
                         "loja": r.nome, "gvo": r.gvo, "praça": r.praca, "valor": r[c], "ritmo": r.ritmo})
    refs = pd.DataFrame(refs)

    saida = BASE / "analises" / f"boas_praticas_{d['ontem'][:7]}.xlsx"
    with pd.ExcelWriter(saida) as w:
        df.sort_values("ritmo", ascending=False).to_excel(w, sheet_name="Indicadores", index=False)
        comp.to_excel(w, sheet_name="Comparação")
        adoc.to_excel(w, sheet_name="Adoção", index=False)
        refs.to_excel(w, sheet_name="Referências", index=False)
        ops.to_excel(w, sheet_name="Oportunidades", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    print("Lojas por grupo:", df.grupo.value_counts().to_dict())
    print(comp.round(3).to_string())
    print(adoc.round(3).to_string(index=False))
    print(refs.round(3).to_string(index=False))
    print(ops.round(0).to_string(index=False))
    print("Ganho total estimado no mês (lojas abaixo):", round(ops["ganho total no mês"].sum()),
          {k: round(ops[k].sum()) for k in ops.columns if k.startswith("ganho ") and k != "ganho total no mês"})
    print("->", saida.relative_to(BASE))


if __name__ == "__main__":
    main()
