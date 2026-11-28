"""PULSAR COMERCIAL - acompanhamento da Beauty Week (Varejo, VD e Total canais).

Lê a pasta "Acompanhamento Beauty Week" e grava data/beauty.json:
  METAS/METAS DIA.xlsx            abas VAREJO e VD: PDV, loja/ER, praça, GVO, META e DIA
  REALIZADOS/VAREJO/*.xlsx        export de cupons do Retaguarda (cupom_venda_...)
  REALIZADOS/VD/*.xlsx            export de pedidos com NF emitida de CPF (pedidos_nf_emitida_...)
  REALIZADOS/VD CNPJ/*.xlsx       export de pedidos com NF emitida de CNPJ (pedidos_nf_emitida_cnpj_...), somado ao VD

Regras:
  Varejo: só cupons "Efetivado"; realizado = soma de "Receita liquida (-) trocas"; loja = código no início de "Loja".
  VD: fora os pedidos "Cancelado Pelo Usuário" (DetalheSituaçãoComercial); loja = código da "EstruturaPai"
      (pedido sem estrutura pai, como o Omnichannel, usa o código do CanalDistribuicao); realizado = soma de "ValorPedido";
      dia = DataFaturamento; hora = DataAutorizaçãoFaturamento.
  Regional: pela praça (dCentros). Varejo também leva boletos, itens e B1 de cada loja (mesmas regras do painel: brinde
      abaixo de R$ 1 fora dos boletos, sacola descontada dos itens) e o cluster, para comparar BM, IPB e % B1 com a média do cluster.
   Cluster da loja de varejo: dCentros (Shopping fecha às 22h; Rua, Galeria,
      Hipermercado e Cash & Carry às 19h). VD (ERs): funcionam das 8h às 19h.
  HUB (aba HUB das metas): realizado da base do VD pelo código do CanalDistribuicao, sem os cancelados, somando ValorPedido.
      Linha sem DIA vale para o dia mais recente; linha sem META aparece sem meta. Fica fora do Total canais e do Ranking
      (os mesmos pedidos já estão nas ERs).
  Metas repetidas (mesmo PDV no mesmo dia na mesma aba): vale a primeira linha; as outras são avisadas no rodapé da página.
  Ritmo ("horaização"): quanto do dia já deveria estar vendido até a hora do último cupom/pedido, pela curva do dia.
  Curva de cada dia (quanto se vende em cada hora), na ordem de preferência:
      Cada canal tem a sua curva (Varejo ainda separa shopping x demais).
      1. média dos dias já fechados da campanha do mesmo tipo (dia útil, sábado ou domingo), pelo realizado de cada hora;
      2. o dia equivalente de 2025, contado a partir da Black Friday (ex.: 29/11/2026 = 30/11/2025);
         Varejo: Dados/NOVEMBRO 2025; VD: Acompanhamento Beauty Week/BASE 2025/VD;
      3. VD: média de todos os dias fechados da campanha;
      4. sem nada disso: Varejo = mesmo dia da semana do mês de referência; VD = uniforme das 8h às 19h.
  Projeção de fechamento (por canal): F = parte do dia já vendida pela curva; A = atingimento dos dias da campanha
      já fechados (realizado ÷ meta). Projeção = F × (realizado ÷ F) + (1 − F) × (meta × A): no começo do dia pesa o
      histórico da campanha; à medida que o dia anda, pesa o ritmo do próprio dia. Sem dia fechado: realizado ÷ F.
      Faixa provável: a mesma conta com as curvas alternativas (cada dia fechado da campanha e a curva padrão).
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
# Códigos cujo realizado soma em outro PDV (estrutura sem meta própria que pertence a outra loja/ER)
SOMAR_EM = {"25047": "20933"}   # 25047 -> Santa Luzia (20933)
AVISOS = []
VISTOS = set()   # códigos de pedido do VD já lidos (CPF + CNPJ)
# Detalhe VD: faixas de valor do pedido e ordem das segmentações (coluna Papel)
FAIXAS_VD = [(0, 150, "Até R$ 150"), (150, 300, "R$ 150 a 300"), (300, 500, "R$ 300 a 500"), (500, 1000, "R$ 500 a 1.000"),
             (1000, 2000, "R$ 1.000 a 2.000"), (2000, float("inf"), "Acima de R$ 2.000")]
ORDEM_PAPEL = ["Consumidor Final", "Revendedor", "Cobre", "Bronze", "Prata", "Ouro", "Platina", "Rubi", "Esmeralda GB", "Diamante GB"]
# Projeção: dia equivalente do ano anterior pela Black Friday e bases históricas
BLACK_FRIDAY = {2025: pd.Timestamp("2025-11-28"), 2026: pd.Timestamp("2026-11-27")}
PASTA_HIST_VAREJO = p.PASTA_VENDAS / "NOVEMBRO 2025"
PASTA_HIST_VD = PASTA / "BASE 2025" / "VD"

cod = lambda v: (re.match(r"\s*(\d+)", str(v)) or [None, None])[1]


def ler_metas(aba, dia_padrao=None, sem_meta_ok=False):
    """Metas de uma aba. HUB: linha sem DIA usa o dia_padrao e, com sem_meta_ok, linha sem META entra com meta 0."""
    try:
        m = pd.read_excel(ARQ_METAS, sheet_name=aba, engine="calamine")
    except ValueError:
        return pd.DataFrame(columns=["id", "nome", "praca", "gvo", "meta", "dia"])
    m.columns = [str(c).strip().upper() for c in m.columns]
    nome = next(c for c in m.columns if c in ("LOJA", "ER", "HUB"))
    m = m[m["PDV"].notna() & (sem_meta_ok or m["META"].notna())].copy()
    m["META"] = pd.to_numeric(m["META"], errors="coerce").fillna(0)
    m["id"] = m["PDV"].map(cod)
    m["dia"] = pd.to_datetime(m["DIA"], errors="coerce").dt.strftime("%Y-%m-%d")
    if dia_padrao:
        m["dia"] = m["dia"].fillna(dia_padrao)
    m = m[m["dia"].notna()]
    m["linha"] = m.index + 2   # linha no Excel (cabeçalho na 1)
    rep = m[m.duplicated(["id", "dia"], keep=False)]
    for (i, d), g in rep.groupby(["id", "dia"], sort=False):
        usadas = g.iloc[0]
        AVISOS.append({"aba": aba, "id": i, "dia": d, "usada": int(usadas["linha"]), "meta": round(float(usadas["META"]), 2),
                       "ignoradas": [{"linha": int(r["linha"]), "nome": str(r[nome]).strip(), "meta": round(float(r["META"]), 2)}
                                     for _, r in g.iloc[1:].iterrows()]})
    m = m.drop_duplicates(["id", "dia"], keep="first")
    return m.rename(columns={nome: "nome", "PRAÇA": "praca", "GVO": "gvo", "META": "meta"})[["id", "nome", "praca", "gvo", "meta", "dia"]]


def arquivos(sub):
    pasta = PASTA / "REALIZADOS" / sub
    return sorted(a for a in pasta.glob("*.xlsx") if not a.name.startswith("~$")) if pasta.exists() else []


def arquivos_varejo():
    """Cupons da pasta da Beauty Week e da pasta Dados/Hoje (mesmo export do acompanhamento do dia)."""
    hoje = p.PASTA_VENDAS / "Hoje"
    extra = [a for a in hoje.glob("cupom_venda*.xlsx") if not a.name.startswith("~$")] if hoje.exists() else []
    return sorted(arquivos("VAREJO") + extra, key=lambda a: a.stat().st_mtime)


def realizado_varejo():
    """Para cada dia vale o arquivo salvo por último que tem aquele dia (evita somar o mesmo cupom duas vezes)."""
    por_dia = {}
    for a in arquivos_varejo():
        v = p.ler_excel(a, usecols=["Loja", "Data", "Hora", "Status cupom", "Qtd itens", "Campanhas", "Receita liquida (-) trocas"])
        v = v[v["Status cupom"] == "Efetivado"]
        camp = v["Campanhas"].fillna("").astype(str).str.upper()
        itens = (v["Qtd itens"] - camp.str.contains("SACOLA").astype(int)).clip(lower=0)
        venda = v["Receita liquida (-) trocas"] >= p.LIMITE_BRINDE
        df = pd.DataFrame({"id": v["Loja"].map(cod).replace(SOMAR_EM), "dia": pd.to_datetime(v["Data"], format="%d/%m/%Y").dt.strftime("%Y-%m-%d"),
                           "hm": v["Hora"].astype(str).str.slice(0, 5), "valor": v["Receita liquida (-) trocas"],
                           "bol": venda.astype(int), "it": itens.where(venda, 0), "b1": (venda & (itens <= 1)).astype(int)})
        for d, g in df.groupby("dia"):
            por_dia[d] = (a, g)
    for d, (a, _) in sorted(por_dia.items()):
        print(f"  Varejo {d}: {a.relative_to(p.BASE)}")
    fr = [g for _, g in por_dia.values()]
    return pd.concat(fr, ignore_index=True) if fr else pd.DataFrame(columns=["id", "dia", "hm", "valor", "bol", "it", "b1"])


def realizado_vd():
    """Pedidos de CPF (REALIZADOS/VD) e de CNPJ (REALIZADOS/VD CNPJ); pedido repetido conta uma vez (vale o arquivo mais novo)."""
    fr = []
    for a in sorted(arquivos("VD") + arquivos("VD CNPJ"), key=lambda a: a.stat().st_mtime, reverse=True):
        v = p.ler_excel(a)
        v = v[~v["CodigoPedido"].astype(str).isin(VISTOS)]
        VISTOS.update(v["CodigoPedido"].astype(str))
        v = v[v["DetalheSituaçãoComercial"].astype(str).str.strip().str.upper() != CANCELADO_VD]
        loja = v["EstruturaPai"].map(cod).fillna(v["CanalDistribuicao"].map(cod)).replace(SOMAR_EM)
        aut = pd.to_datetime(v["DataAutorizaçãoFaturamento"], format="%d/%m/%Y %H:%M", errors="coerce")
        fr.append(pd.DataFrame({"id": loja, "hub": v["CanalDistribuicao"].map(cod),
                                "dia": pd.to_datetime(v["DataFaturamento"], format="%d/%m/%Y").dt.strftime("%Y-%m-%d"),
                                "hm": aut.dt.strftime("%H:%M"), "valor": v["ValorPedido"],
                                "papel": v["Papel"].fillna("Sem segmentação").astype(str).str.strip(),
                                "itens": pd.to_numeric(v["QtdeItens"], errors="coerce").fillna(0)}))
        fr[-1]["bol"], fr[-1]["it"], fr[-1]["b1"] = 1, fr[-1]["itens"], 0   # pedidos e itens por ER (pedido médio e itens/pedido)
    return pd.concat(fr, ignore_index=True) if fr else pd.DataFrame(columns=["id", "hub", "dia", "hm", "valor", "papel", "itens"])


def detalhe_vd(rd):
    """Pedidos do VD por dia, ER, segmentação e faixa de valor: [dia, id, papel, faixa, pedidos, valor, itens]."""
    d = rd.dropna(subset=["id", "dia"]).copy()
    lim = [f[0] for f in FAIXAS_VD] + [float("inf")]
    d["faixa"] = pd.cut(d["valor"], bins=lim, labels=False, right=False).fillna(0).astype(int)
    g = d.groupby(["dia", "id", "papel", "faixa"]).agg(n=("valor", "size"), valor=("valor", "sum"), itens=("itens", "sum")).reset_index()
    papeis = [x for x in ORDEM_PAPEL if x in set(g["papel"])] + sorted(set(g["papel"]) - set(ORDEM_PAPEL))
    return {"faixas": [f[2] for f in FAIXAS_VD], "papeis": papeis,
            "linhas": [[r.dia, r.id, r.papel, int(r.faixa), int(r.n), round(float(r.valor), 2), int(r.itens)] for r in g.itertuples()]}


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


def analogo(dia):
    """Dia equivalente do ano anterior, contado a partir da Black Friday."""
    d = pd.Timestamp(dia)
    if d.year in BLACK_FRIDAY and d.year - 1 in BLACK_FRIDAY:
        return (BLACK_FRIDAY[d.year - 1] + (d - BLACK_FRIDAY[d.year])).strftime("%Y-%m-%d")
    return None


def _hist(nome, pasta, padrao, ler):
    """Venda histórica por dia, loja e hora. Lê os arquivos uma vez e guarda em .cache (refaz se algum arquivo mudar)."""
    arqs = sorted(a for a in pasta.glob(padrao) if not a.name.startswith("~$")) if pasta.exists() else []
    if not arqs:
        return None
    chave = "|".join(f"{a.name}:{a.stat().st_size}:{int(a.stat().st_mtime)}" for a in arqs)
    cache = p.PASTA_CACHE / f"beauty_hist_{nome}.pkl"
    if cache.exists():
        try:
            k, df = pd.read_pickle(cache)
            if k == chave:
                return df
        except Exception:
            pass
    df = pd.concat([ler(a) for a in arqs], ignore_index=True).dropna(subset=["id", "d", "h"])
    df = df.groupby(["d", "id", "h"], as_index=False)["v"].sum()
    p.PASTA_CACHE.mkdir(exist_ok=True)
    pd.to_pickle((chave, df), cache)
    return df


def hist_varejo():
    def ler(a):
        v = pd.read_excel(a, engine="calamine", usecols=["Loja", "Data", "Hora", "Status cupom", "Receita liquida (-) trocas"])
        v = v[v["Status cupom"] == "Efetivado"]
        return pd.DataFrame({"id": v["Loja"].map(cod), "d": pd.to_datetime(v["Data"], format="%d/%m/%Y").dt.strftime("%Y-%m-%d"),
                             "h": pd.to_numeric(v["Hora"].astype(str).str.slice(0, 2), errors="coerce"),
                             "v": v["Receita liquida (-) trocas"]})
    return _hist("varejo", PASTA_HIST_VAREJO, "cupom_venda*.xlsx", ler)


def hist_vd():
    def ler(a):
        v = p.ler_excel(a)
        v = v[v["DetalheSituaçãoComercial"].astype(str).str.strip().str.upper() != CANCELADO_VD]
        aut = pd.to_datetime(v["DataAutorizaçãoFaturamento"], format="%d/%m/%Y %H:%M", errors="coerce")
        return pd.DataFrame({"id": v["EstruturaPai"].map(cod).fillna(v["CanalDistribuicao"].map(cod)),
                             "d": pd.to_datetime(v["DataFaturamento"], format="%d/%m/%Y").dt.strftime("%Y-%m-%d"),
                             "h": aut.dt.hour, "v": v["ValorPedido"]})
    return _hist("vd", PASTA_HIST_VD, "*.xlsx", ler)


def partes(df):
    """Participação de cada hora (0 a 23) na venda do conjunto."""
    s = df.groupby("h")["v"].sum().reindex(range(24), fill_value=0)
    return [round(float(x / s.sum()), 5) for x in s] if s.sum() > 0 else None


def por_hora(real):
    r = real.dropna(subset=["id", "dia"])
    return pd.DataFrame({"id": r["id"], "d": r["dia"], "h": pd.to_numeric(r["hm"].str.slice(0, 2), errors="coerce"),
                         "v": r["valor"]}).dropna(subset=["h"])


def projecao(dias, rv, rd, lv, ld, shopping, curvas_padrao):
    """Curva principal, curvas alternativas e atingimento dos dias fechados de cada dia, para Varejo e VD."""
    hv, hd = hist_varejo(), hist_vd()
    v26, d26 = por_hora(rv), por_hora(rd)
    com_dados = sorted(set(v26["d"]) | set(d26["d"]))
    hoje = com_dados[-1] if com_dados else None
    tipo = lambda df: {"shopping": partes(df[df["id"].isin(shopping)]), "demais": partes(df[~df["id"].isin(shopping)])}
    fmt = lambda d: f"{d[8:]}/{d[5:7]}/{d[:4]}"
    out = {c: {"curvas": {}, "refs": {}, "prior": {}, "base": {}} for c in ("varejo", "vd")}
    TIPO = ["dias úteis"] * 5 + ["sábados", "domingos"]
    tipo_dia = lambda x: TIPO[pd.Timestamp(x).dayofweek]
    media = lambda cs: [round(sum(c[i] for c in cs) / len(cs), 5) for i in range(24)] if cs else None
    lista = lambda xs: ", ".join(fmt(x)[:5] for x in xs)
    for d in dias:
        fech = [x for x in com_dados if x < d and x < hoje]
        mesmo = [x for x in fech if tipo_dia(x) == tipo_dia(d)]   # dias fechados da campanha do mesmo tipo (útil/sábado/domingo)
        an = analogo(d)
        # Varejo: 1) média dos dias fechados do mesmo tipo; 2) dia equivalente de 2025; 3) mesmo dia da semana do mês
        dia_v = {x: tipo(v26[v26["d"] == x]) for x in fech}
        g = hv[hv["d"] == an] if hv is not None and an else None
        c25 = tipo(g) if g is not None and len(g) else None
        if mesmo:
            out["varejo"]["curvas"][d] = {k: media([dia_v[x][k] for x in mesmo if dia_v[x][k]]) for k in ("shopping", "demais")}
            out["varejo"]["base"][d] = f"média dos {tipo_dia(d)} fechados da campanha ({lista(mesmo)})"
        elif c25:
            out["varejo"]["curvas"][d] = c25
            out["varejo"]["base"][d] = f"dia equivalente de 2025 ({fmt(an)})"
        else:
            out["varejo"]["curvas"][d] = curvas_padrao.get(d)
            out["varejo"]["base"][d] = "mesmo dia da semana do mês"
        refs = list(dia_v.values()) + [c25, curvas_padrao.get(d)]
        out["varejo"]["refs"][d] = [r for r in refs if r and r["shopping"] and r["demais"]]
        # VD: 1) média dos dias fechados do mesmo tipo; 2) dia equivalente de 2025; 3) média de todos os dias fechados; 4) uniforme
        dia_d = {x: partes(d26[d26["d"] == x]) for x in fech}
        g = hd[hd["d"] == an] if hd is not None and an else None
        c25 = partes(g) if g is not None and len(g) else None
        ok_mesmo = [dia_d[x] for x in mesmo if dia_d[x]]
        ok_todos = [c for c in dia_d.values() if c]
        if ok_mesmo:
            out["vd"]["curvas"][d] = media(ok_mesmo)
            out["vd"]["base"][d] = f"média dos {tipo_dia(d)} fechados da campanha ({lista(mesmo)})"
        elif c25:
            out["vd"]["curvas"][d] = c25
            out["vd"]["base"][d] = f"dia equivalente de 2025 ({fmt(an)})"
        elif ok_todos:
            out["vd"]["curvas"][d] = media(ok_todos)
            out["vd"]["base"][d] = f"média dos dias fechados da campanha ({lista(fech)})"
        else:
            out["vd"]["curvas"][d] = curva_vd()
            out["vd"]["base"][d] = "uniforme das 8h às 19h"
        out["vd"]["refs"][d] = [r for r in ok_todos + [c25, curva_vd()] if r]
        # atingimento dos dias fechados (só lojas/ERs com meta)
        for c, ls in (("varejo", lv), ("vd", ld)):
            m = sum(x["meta"] for x in ls if x["dia"] in fech)
            r = sum(x["real"] for x in ls if x["dia"] in fech)
            out[c]["prior"][d] = round(r / m, 4) if m else None
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
    # a aba VD da planilha de metas divide a praça em partes (OCE-1, OCE-2); no painel vale a praça do dCentros (OCE)
    base = lambda p: p if p in reg else re.sub(r"\s*-\s*\d+$", "", str(p)) if re.sub(r"\s*-\s*\d+$", "", str(p)) in reg else p
    metas = metas.assign(praca=metas["praca"].map(base))
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
    # HUB: mesma base do VD, mas pelo código do CanalDistribuicao (sem os cancelados, somando ValorPedido)
    dia_hub = max(set(mv["dia"]) | set(md["dia"]) | set(rd["dia"].dropna()), default=None)
    mh = ler_metas("HUB", dia_padrao=dia_hub, sem_meta_ok=True)
    rh = rd.drop(columns="id").rename(columns={"hub": "id"})
    lv, sv, av = montar(mv, rv, centros, lambda i: {"shopping": i in shopping, "fecha": FECHA_SHOPPING if i in shopping else FECHA_DEMAIS,
                                                    "cluster": str(centros["CLUSTER"].get(i, "Sem cluster")).strip()})
    ld, sd, ad = montar(md, rd, centros, lambda i: {"fecha": VD_FECHA})
    lh, _, ah = montar(mh, rh, centros, lambda i: {"fecha": VD_FECHA})
    for x in lh:
        x["temMeta"] = x["meta"] > 0
    dias = sorted(set(mv["dia"]) | set(md["dia"]) | set(mh["dia"]))
    curvas = {}
    for d in dias:
        try:
            curvas[d] = curva_varejo(pd.Timestamp(d), shopping)
        except ValueError:
            curvas[d] = None
    pj = projecao(dias, rv, rd, lv, ld, shopping, curvas)
    saida = {"geradoEm": datetime.now().isoformat(timespec="minutes"), "dias": dias,
             "varejo": {"ate": av, "lojas": lv, "semMeta": sv, **pj["varejo"]},
             "vd": {"ate": ad, "lojas": ld, "semMeta": sd, "curva": curva_vd(), "abre": VD_ABRE, "fecha": VD_FECHA,
                    "det": detalhe_vd(rd), **pj["vd"]},
             "hub": {"ate": ah, "lojas": lh, "semMeta": [], "curva": curva_vd()}, "avisos": AVISOS}
    ARQ_SAIDA.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for canal, ls, sm, ate in (("Varejo", lv, sv, av), ("VD", ld, sd, ad)):
        for d in dias:
            m = sum(x["meta"] for x in ls if x["dia"] == d); r = sum(x["real"] for x in ls if x["dia"] == d)
            s = sum(x["real"] for x in sm if x["dia"] == d)
            print(f"{canal} {d}: meta R$ {m:,.0f} | realizado R$ {r:,.0f} ({r / m if m else 0:.1%}) até {ate.get(d, '—')}"
                  + (f" | sem meta: R$ {s:,.0f} ({', '.join(x['id'] for x in sm if x['dia'] == d)})" if s else ""))
    for d in dias:
        print(f"Projeção {d}: Varejo pela curva do {pj['varejo']['base'][d]}; VD pela curva {pj['vd']['base'][d]}; "
              f"atingimento dos dias fechados: Varejo {pj['varejo']['prior'][d]}, VD {pj['vd']['prior'][d]}")
    for x in lh:
        print(f"HUB {x['dia']} {x['nome']}: meta {'R$ {:,.0f}'.format(x['meta']) if x['temMeta'] else 'sem meta'} | realizado R$ {x['real']:,.0f}")
    for a in AVISOS:
        print(f"ATENÇÃO aba {a['aba']}: PDV {a['id']} repetido em {a['dia']}. Usei a linha {a['usada']} (R$ {a['meta']:,.0f}); "
              + "ignorei " + ", ".join(f"linha {x['linha']} {x['nome']} (R$ {x['meta']:,.0f})" for x in a["ignoradas"]))
    print(f"OK -> {ARQ_SAIDA.relative_to(p.BASE)}")


if __name__ == "__main__":
    main()
