"""PULSAR COMERCIAL - processa as planilhas locais e gera dados/pulsar.json.

Entradas (relativas a esta pasta):
  Dados/<Mês>/cupom_venda_*.xlsx   cupons de venda exportados do Retaguarda GB
  Metas/Metas_Canal_Loja.xlsx      meta diarizada por loja (PDV x dia)
  dCentros/dCentros.xlsx           cadastro de lojas e hierarquia (GVO, GCVO/GPVO, GRVO...)

Saída:
  dados/pulsar.json   mês corrente (dia a dia por loja e por consultor) + período de referência

Uso:
  python processar_dados.py
"""
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
from datetime import date, datetime
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
PASTA_VENDAS = BASE / "Dados"
ARQ_METAS = BASE / "Metas" / "Metas_Canal_Loja.xlsx"          # meta diarizada: dá o formato (peso de cada dia)
PASTA_METAS = BASE / "Metas"                                    # metas mensais: "METAS <MÊS> VAREJO*.xlsx", aba VAREJO
MESES_PT = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO",
            "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
ARQ_CENTROS = BASE / "dCentros" / "dCentros.xlsx"
ARQ_PLANO = BASE / "Plano BM" / "Plano_BM_2026.xlsx"
PASTA_CACHE = BASE / ".cache"
ARQ_SAIDA = BASE / "data" / "pulsar.json"     # site publicado (não confundir com a pasta Dados, das vendas)

# Canais de venda (código do "Canal de vendas" do Retaguarda) e alavancas comparadas no cluster
CANAIS = {"cal": ["24"], "vfl": ["20"], "wpp": ["3", "4"], "exp": ["13", "14", "15", "16", "17", "18"],
          "par": ["11"], "vic": ["10", "25"]}
ALAVANCAS = list(CANAIS) + ["cl", "cb", "fc"]
RECEITA = "Receita liquida"   # mesma base da meta (receita líquida dos cupons efetivados)
# Consultores digitais (atendem pela carteira no WhatsApp, em várias lojas): comparados só entre si, fora do time das lojas.
# Código do Retaguarda -> nome. Para incluir alguém, acrescente o código aqui.
DIGITAIS = {
    "1130": "Allana Karoline Constantino dos Santos (São Luís)",
    "1413": "João Gabriel Carvalho Barros (São Luís)",
    "1282": "Wanessa Caroline dos Santos Menezes (Natal)",
    "795": "Emilly Kailany Vicente da Silva (Natal)",
}
SARRAFO_BP = 120.0            # boleto elegível ao Boleto Promocional: receita do cupom a partir de R$ 120
LIMITE_BRINDE = 1.0           # cupom com receita abaixo disso é brinde (ex.: Ação de Fluxo), não venda
MESES_REFERENCIA = 3          # IPB e preço médio "normais" de cada loja = média dos 3 meses anteriores


try:
    import python_calamine  # noqa: F401  leitor de Excel bem mais rápido, se instalado
    MOTOR = "calamine"
except ImportError:
    MOTOR = None


def ler_excel(caminho: Path, **kw) -> pd.DataFrame:
    """Lê um Excel; se estiver aberto (bloqueado), lê uma cópia temporária."""
    reserva = PASTA_CACHE / caminho.name
    try:
        df = pd.read_excel(caminho, engine=MOTOR, **kw)
        if caminho.stat().st_size < 5_000_000:  # guarda cópia dos arquivos pequenos (metas, cadastro)
            PASTA_CACHE.mkdir(exist_ok=True)
            shutil.copy2(caminho, reserva)
        return df
    except PermissionError:
        copia = Path(tempfile.gettempdir()) / f"pulsar_{caminho.name}"
        try:
            try:
                shutil.copy2(caminho, copia)
            except PermissionError:
                # o Excel bloqueia a leitura pelo Python, mas o Windows ainda consegue copiar o arquivo
                cmd = f"Copy-Item -LiteralPath '{caminho.resolve()}' -Destination '{copia}' -Force"
                if subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True).returncode != 0:
                    raise PermissionError(caminho)
        except PermissionError:
            if not reserva.exists():
                raise SystemExit(f"Feche o arquivo {caminho.name} no Excel e rode de novo.")
            print(f"  {caminho.name} está aberto no Excel; usando a última cópia salva.")
            copia = reserva
        return pd.read_excel(copia, engine=MOTOR, **kw)


def cod_loja(valor) -> str:
    # "12175.1" (quiosque) é somado à loja 12175, que é onde as vendas dele caem.
    return str(valor).strip().split(".")[0]


def nome_curto(texto: str) -> str:
    partes = [p for p in re.split(r"\s+", str(texto).strip()) if p]
    if not partes:
        return str(texto)
    nome = partes[0] if len(partes) == 1 else f"{partes[0]} {partes[-1]}"
    return nome.title()


# ---------------------------------------------------------------- vendas
def ler_cupons(arq: Path) -> pd.DataFrame:
    """Devolve um cupom efetivado por linha: Loja, Data, Qtd itens, receita, Consultores.

    Aceita os dois formatos exportados pelo Retaguarda:
      - por cupom (Qtd itens, Receita liquida, Consultores), usado a partir de setembro;
      - item a item (Quantidade, Receita liquida total, Consultor), usado até agosto.
    A sacola entra como item no Retaguarda e distorce IPB e %B1. No formato item a item ela é retirada
    pela descrição; no formato por cupom, desconta-se 1 item quando o cupom tem a campanha da sacola
    (testado em agosto: %B1 estimado a 0,3 p.p. do exato).
    """
    cab = list(ler_excel(arq, nrows=0).columns)
    if "Qtd itens" in cab:
        v = ler_excel(arq, usecols=["Loja", "Data", "Status cupom", "Qtd itens", RECEITA, "Consultores", "Campanhas",
                                    "Canal de vendas"])
        v = v[v["Status cupom"] == "Efetivado"].rename(columns={RECEITA: "receita"})
        sacola = v["Campanhas"].astype(str).str.upper().str.contains("SACOLA")
        v["Qtd itens"] = (v["Qtd itens"] - sacola.astype(int)).clip(lower=0)
        return v
    v = ler_excel(arq, usecols=["Loja", "Data", "Status cupom", "Status produto", "N. Doc", "Sequencial",
                                "Descricao produto", "Quantidade", "Receita liquida total", "Consultor", "Campanhas",
                                "Canal de vendas"])
    v = v[(v["Status cupom"] == "Efetivado") & (v["Status produto"].astype(str).str.upper() == "EFETIVADO")].copy()
    v.loc[v["Descricao produto"].astype(str).str.upper().str.contains("SACOLA"), "Quantidade"] = 0
    return (v.groupby(["Loja", "Data", "Sequencial", "N. Doc"], dropna=False)
              .agg(**{"Qtd itens": ("Quantidade", "sum"), "receita": ("Receita liquida total", "sum"),
                      "Consultores": ("Consultor", "first"),
                      "Campanhas": ("Campanhas", lambda x: " | ".join(x.dropna().astype(str))),
                      "Canal de vendas": ("Canal de vendas", "first")})
              .reset_index())


def agregar_arquivo(arq: Path) -> pd.DataFrame:
    """Cupons efetivados -> loja x consultor x dia. Guarda em cache até o arquivo mudar."""
    cache = PASTA_CACHE / f"{arq.stem}_v6.pkl"   # v6: + boletos elegíveis ao BP (a partir de R$ 120)
    if cache.exists() and cache.stat().st_mtime >= arq.stat().st_mtime:
        return pd.read_pickle(cache)
    print(f"  lendo {arq.relative_to(BASE)} ...", flush=True)
    v = ler_cupons(arq).copy()
    v["data"] = pd.to_datetime(v["Data"], format="%d/%m/%Y")
    v["loja"] = v["Loja"].astype(str).str.extract(r"^(\d+)")[0]
    v["loja_nome"] = v["Loja"].astype(str).str.replace(r"^\d+\s*-\s*", "", regex=True)
    v["consultor"] = v["Consultores"].fillna("").astype(str).str.strip().replace("", "0 - SEM CONSULTOR")
    # Brinde (ex.: Ação de Fluxo com receita de centavos) não é boleto de venda: fica fora de boletos, IPB, %B1 e BM.
    venda = v["receita"] >= LIMITE_BRINDE
    v["bol"] = venda.astype(int)
    v["it"] = v["Qtd itens"].where(venda, 0)
    v["b1"] = (venda & (v["Qtd itens"] <= 1)).astype(int)   # cupom de venda com 1 produto
    v["br"] = (~venda).astype(int)
    # Penetração: o cupom de venda tem a tag de Boleto Turbinado / Boleto Promocional na coluna Campanhas
    camp = v["Campanhas"].fillna("").astype(str).str.upper()
    v["bt"] = (venda & camp.str.contains("BOLETO TURBINADO")).astype(int)
    v["bp"] = (venda & camp.str.contains("BOLETO PROMOCIONAL")).astype(int)
    # Penetração = boletos com a tag ÷ boletos elegíveis. BT: todo boleto com item pago (o "bol").
    # BP: só o boleto que chegou ao sarrafo (receita a partir de R$ 120).
    v["bpe"] = (venda & (v["receita"] >= SARRAFO_BP)).astype(int)
    # Alavancas comparadas entre lojas do mesmo cluster (só cupons de venda)
    canal = v["Canal de vendas"].astype(str).str.extract(r"^(\d+)")[0]
    for col, codigos in CANAIS.items():
        v[col] = (venda & canal.isin(codigos)).astype(int)
    v["cl"] = (venda & camp.str.contains("COMPRE E LEVE")).astype(int)
    v["cb"] = (venda & camp.str.contains("CASHBACK")).astype(int)
    v["fc"] = (venda & camp.str.contains("FLUXO")).astype(int)        # cliente da Ação de Fluxo que comprou
    g = (v.groupby(["data", "loja", "loja_nome", "consultor"])
           .agg(rec=("receita", "sum"), bol=("bol", "sum"), it=("it", "sum"), b1=("b1", "sum"), br=("br", "sum"),
                bt=("bt", "sum"), bp=("bp", "sum"), bpe=("bpe", "sum"), **{c: (c, "sum") for c in ALAVANCAS})
           .reset_index())
    PASTA_CACHE.mkdir(exist_ok=True)
    g.to_pickle(cache)
    return g


def mes_do_arquivo(arq: Path):
    """(ano, mês) pelo nome: cupom_venda_2026_04 ou cupom_venda_2026-08-01_a_2026-08-13."""
    m = re.search(r"(\d{4})[_-](\d{2})", arq.stem)
    return (int(m.group(1)), int(m.group(2))) if m else None


def ler_vendas() -> pd.DataFrame:
    # Dados/Hoje é a venda parcial do dia (processar_hoje.py): fica fora do fechamento D-1
    # só os exports de cupons (cupom_venda_*.xlsx): outras planilhas salvas em Dados/ ficam de fora
    arquivos = sorted(a for a in PASTA_VENDAS.rglob("cupom_venda*.xlsx") if not a.name.startswith("~$") and "Hoje" not in a.parts)
    # só o mês atual e os meses de referência
    meses = [mes_do_arquivo(a) for a in arquivos]
    conhecidos = [m for m in meses if m]
    if conhecidos:
        ano, mes = max(conhecidos)
        corte = (ano * 12 + mes - 1) - MESES_REFERENCIA
        arquivos = [a for a, m in zip(arquivos, meses) if m is None or (m[0] * 12 + m[1] - 1) >= corte]
    partes = [agregar_arquivo(a) for a in arquivos]
    v = pd.concat(partes, ignore_index=True)
    # se dois arquivos cobrirem o mesmo dia, fica o último lido
    return v.drop_duplicates(["data", "loja", "consultor"], keep="last")


def ler_ano_anterior(ini_mes):
    """Mesmo mês do ano anterior (ex.: Dados/Outubro 2025/cupom_venda_2025-10-01_a_2025-10-31.xlsx).
    Mesmas regras do mês atual (só efetivados, brinde fora, sacola descontada). None se não houver arquivo."""
    alvo = (ini_mes.year - 1, ini_mes.month)
    arqs = sorted(a for a in PASTA_VENDAS.rglob("cupom_venda*.xlsx")
                  if not a.name.startswith("~$") and "Hoje" not in a.parts and mes_do_arquivo(a) == alvo)
    if not arqs:
        return None, []
    v = pd.concat([agregar_arquivo(a) for a in arqs], ignore_index=True)
    return v.drop_duplicates(["data", "loja", "consultor"], keep="last"), arqs


# ---------------------------------------------------------------- metas
def ler_metas(ano: int) -> pd.DataFrame:
    m = ler_excel(ARQ_METAS, header=None)
    cab_dia = m.iloc[2]
    linhas = m.iloc[4:]
    linhas = linhas[pd.to_numeric(linhas[0], errors="coerce").notna()]
    registros = []
    for col in range(4, m.shape[1]):
        rot = str(cab_dia[col]).strip()
        if not re.fullmatch(r"\d{2}/\d{2}", rot):
            continue
        dia, mes = map(int, rot.split("/"))
        valores = pd.to_numeric(linhas[col], errors="coerce").fillna(0)
        for pdv, nome, valor in zip(linhas[0], linhas[1], valores):
            registros.append((cod_loja(pdv), str(nome).strip(), pd.Timestamp(date(ano, mes, dia)), float(valor)))
    metas = pd.DataFrame(registros, columns=["loja", "loja_nome", "data", "meta"])
    return metas.groupby(["loja", "data"], as_index=False).agg(meta=("meta", "sum"), loja_nome=("loja_nome", "first"))


def ler_meta_mensal(mes: int):
    """Meta mensal do Canal Varejo (aba VAREJO) do mês, se houver o arquivo "METAS <MÊS> VAREJO...xlsx"."""
    arqs = [a for a in PASTA_METAS.glob("*.xlsx") if not a.name.startswith("~$")
            and MESES_PT[mes - 1] in a.name.upper() and "VAREJO" in a.name.upper()]
    if not arqs:
        return None, None, None
    arq = max(arqs, key=lambda a: a.stat().st_mtime)
    m = ler_excel(arq, sheet_name="VAREJO")
    m = m[pd.to_numeric(m["PDV"], errors="coerce").notna()].copy()
    m["loja"] = m["PDV"].map(cod_loja)   # 12175.1 (quiosque) soma na 12175
    m["META"] = pd.to_numeric(m["META"], errors="coerce").fillna(0)
    meta = m.groupby("loja")["META"].sum()
    info = m.groupby("loja").agg(nome=("LOJA", "first"), praca=("PRAÇA", "first"))
    return meta, info, arq


def diarizar(diaria: pd.DataFrame, mensal: pd.Series, info: pd.DataFrame) -> pd.DataFrame:
    """Distribui a meta mensal nova pelos dias com o mesmo formato da meta diarizada.

    Loja com diarização: meta do dia = meta mensal × (meta do dia ÷ meta do mês) da planilha diarizada.
    Loja sem diarização: usa o formato médio das lojas da mesma praça (ou da rede, se a praça não tiver).
    """
    tot = diaria.groupby("loja")["meta"].transform("sum")
    diaria = diaria.assign(peso=diaria["meta"] / tot.where(tot > 0))
    praca_da = info["praca"].to_dict()
    diaria["praca"] = diaria["loja"].map(praca_da)
    forma_praca = diaria.groupby(["praca", "data"])["meta"].sum()
    forma_praca = forma_praca / forma_praca.groupby(level=0).transform("sum")
    forma_rede = diaria.groupby("data")["meta"].sum()
    forma_rede = forma_rede / forma_rede.sum()
    linhas = []
    for loja, valor in mensal.items():
        d = diaria[(diaria["loja"] == loja) & diaria["peso"].notna()]
        if len(d):
            pesos = d.set_index("data")["peso"]
        elif praca_da.get(loja) in forma_praca.index.get_level_values(0):
            pesos = forma_praca.loc[praca_da[loja]]
        else:
            pesos = forma_rede
        nome = d["loja_nome"].iloc[0] if len(d) else str(info.loc[loja, "nome"])
        for data, w in pesos.items():
            linhas.append((loja, data, float(valor) * float(w), nome))
    return pd.DataFrame(linhas, columns=["loja", "data", "meta", "loja_nome"])


# ---------------------------------------------------------------- cadastro
def ler_centros() -> pd.DataFrame:
    c = ler_excel(ARQ_CENTROS)
    c["loja"] = c["BCPS"].map(cod_loja)
    return c.drop_duplicates("loja").set_index("loja")


def pessoas_do_cadastro(centros, ids_painel):
    """Nomes distintos de GVO, GCVO/GPVO e GRVO do dCentros (todos os canais), com os papéis e as lojas do painel.
    Usados na identificação de quem acessa o painel (aba Uso)."""
    pessoas = {}
    for loja, cad in centros.iterrows():
        for col in ("GVO", "GCVO/GPVO", "GRVO"):
            nome = txt(cad.get(col))
            if not nome:
                continue
            pe = pessoas.setdefault(nome, {"nome": nome, "papeis": [], "lojas": []})
            if col not in pe["papeis"]:
                pe["papeis"].append(col)
            if loja in ids_painel and loja not in pe["lojas"]:
                pe["lojas"].append(loja)
    ordem = {"GRVO": 0, "GCVO/GPVO": 1, "GVO": 2}
    for pe in pessoas.values():
        pe["papeis"].sort(key=ordem.get)
    return sorted(pessoas.values(), key=lambda x: x["nome"])


# ---------------------------------------------------------------- Plano de Ação de Boleto Médio
def normalizar(texto) -> str:
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().upper()


def num(v):
    try:
        f = float(v)
        return None if f != f else round(f, 4)
    except (TypeError, ValueError):
        return None


def txt(v):
    s = "" if v is None or (isinstance(v, float) and v != v) else str(v).strip()
    return "" if s in ("—", "-", "nan") else s


def ler_plano_bm():
    """Lê o Plano BM: BM saudável (mediana do cluster) e diagnóstico por loja; papel e alvos por consultor."""
    if not ARQ_PLANO.exists():
        print("  Plano BM não encontrado; seguindo sem ele.")
        return {}, {}, None
    lj = ler_excel(ARQ_PLANO, sheet_name="Lojas", header=2)
    lj = lj[pd.to_numeric(lj["BPCS"], errors="coerce").notna()]
    lojas = {}
    for _, r in lj.iterrows():
        lojas[cod_loja(int(r["BPCS"]))] = {
            "cluster": txt(r["Cluster"]), "categoria": txt(r["Categoria"]),
            "bmSaudavel": num(r["Mediana BM do cluster (R$)"]), "bm25": num(r["BM 2025 YTD (R$)"]), "bm26": num(r["BM 2026 YTD (R$)"]),
            "b1Loja": num(r["%B1 da loja, ponderado"]), "prioridade": txt(r["Prioridade estrutural"]),
            "grupo": txt(r["Grupo do teste"]), "diagnostico": txt(r["Diagnóstico"]), "acao": txt(r["Ação estrutural sugerida"]),
            "nUti": int(num(r["Nº consultores UTI"]) or 0),
        }
    cs = ler_excel(ARQ_PLANO, sheet_name="Consultores", header=2)
    cs = cs[pd.to_numeric(cs["BPCS"], errors="coerce").notna()]
    consultores = {}
    for _, r in cs.iterrows():
        consultores[(cod_loja(int(r["BPCS"])), normalizar(r["Consultor"]))] = {
            "papel": txt(r["Papel"]), "grupo": txt(r["Grupo do teste"]), "mult": txt(r["Multiplicador"]) == "Sim",
            "foco": txt(r["Foco da ficha"]), "bm26": num(r["BM 2026 (R$)"]), "b126": num(r["% B1"]),
            "bmAlvo": num(r["BM alvo (R$)"]), "b1Alvo": num(r["%B1 alvo"]), "receitaInc": num(r["Receita incremental estimada (R$)"]),
        }
    # BM alvo da loja: média do BM Alvo dos consultores da aba Acompanhamento, ponderada pelos boletos 2026
    # de cada um (aba Consultores). Lojas sem consultor no Acompanhamento ficam com o BM do cluster.
    loja_de = {normalizar(r["Consultor"]): (cod_loja(int(r["BPCS"])), num(r["Boletos 2026"]) or 0) for _, r in cs.iterrows()}
    ac = ler_excel(ARQ_PLANO, sheet_name="Acompanhamento", header=11)
    ac = ac[ac["Consultor"].notna() & pd.to_numeric(ac["BM alvo (R$)"], errors="coerce").notna()]
    soma = {}
    for _, r in ac.iterrows():
        loja, peso = loja_de.get(normalizar(r["Consultor"]), (None, 0))
        if loja and peso:
            t = soma.setdefault(loja, [0.0, 0.0, 0])
            t[0] += float(r["BM alvo (R$)"]) * peso; t[1] += peso; t[2] += 1
    for loja, d in lojas.items():
        if loja in soma:
            d["bmAlvo"], d["bmAlvoFonte"], d["bmAlvoN"] = round(soma[loja][0] / soma[loja][1], 2), "consultores", soma[loja][2]
        else:
            d["bmAlvo"], d["bmAlvoFonte"], d["bmAlvoN"] = d["bmSaudavel"], "cluster", 0
    # metas de %B1 do plano (aba Plano de Ação, bloco de indicadores)
    pa = ler_excel(ARQ_PLANO, sheet_name="Plano de Ação", header=None)
    rede = {}
    for _, r in pa.iterrows():
        rot = str(r[0])
        vals = [x for x in (num(v) for v in r.tolist()[1:]) if x is not None]  # [atual, meta]
        if rot.startswith("%B1 médio da rede") and len(vals) >= 2:
            rede["b1Atual"], rede["b1Meta"] = vals[0], vals[1]
        elif rot.startswith("%B1 médio do grupo UTI") and len(vals) >= 2:
            rede["b1UtiAtual"], rede["b1UtiMeta"] = vals[0], vals[1]
    return lojas, consultores, rede


def achar_plano(plano_cons, loja, nome):
    """Casa o consultor da venda com o do plano: nome igual na mesma loja, ou um nome começando pelo outro."""
    n = normalizar(nome)
    if (loja, n) in plano_cons:
        return plano_cons[(loja, n)]
    for (l, np_), dados in plano_cons.items():
        if l == loja and len(n) >= 10 and (np_.startswith(n) or n.startswith(np_)):
            return dados
    return None


def main():
    print("Lendo vendas...")
    vendas = ler_vendas()
    ontem = vendas["data"].max()
    ini_mes = ontem.replace(day=1)
    dias_mes = (ini_mes + pd.offsets.MonthEnd(0)).day
    ini_ref = ini_mes - pd.DateOffset(months=MESES_REFERENCIA)
    print(f"Vendas até {ontem:%d/%m/%Y}. Referência: {ini_ref:%d/%m/%Y} a {ini_mes - pd.Timedelta(days=1):%d/%m/%Y}")

    print("Lendo metas e cadastro...")
    metas = ler_metas(ontem.year)
    metas = metas[(metas["data"] >= ini_mes) & (metas["data"] <= ini_mes + pd.offsets.MonthEnd(0))]
    mensal = ler_meta_mensal(ini_mes.month)
    if mensal[0] is not None:
        meta_mes, info_mes, arq_mes = mensal
        sem_forma = sorted(set(meta_mes.index) - set(metas.loc[metas["meta"] > 0, "loja"]))
        metas = diarizar(metas, meta_mes, info_mes)
        print(f"  Metas: {arq_mes.name} (R$ {meta_mes.sum():,.0f}), diarizadas pelo formato de {ARQ_METAS.name}"
              + (f"; pela praça: {', '.join(sem_forma)}" if sem_forma else ""))
    centros = ler_centros()
    aa, arqs_aa = ler_ano_anterior(ini_mes)
    if aa is not None:
        print(f"  Ano anterior: {', '.join(a.name for a in arqs_aa)} (R$ {aa['rec'].sum():,.0f}, até {aa['data'].max():%d/%m/%Y})")
    else:
        print(f"  Ano anterior: sem arquivo de {ini_mes.month:02d}/{ini_mes.year - 1} em Dados/ (comparação desligada)")
    plano_lojas, plano_cons, plano_rede = ler_plano_bm()

    mes = vendas[vendas["data"] >= ini_mes]
    ref = vendas[(vendas["data"] >= ini_ref) & (vendas["data"] < ini_mes)]
    nomes_venda = mes.groupby("loja")["loja_nome"].first().to_dict()

    lojas_meta = set(metas.loc[metas["meta"] > 0, "loja"])
    sem_meta = sorted(set(mes["loja"]) - lojas_meta)
    lojas_out, cons_out = [], []

    def serie(df, campo):
        s = df.groupby(df["data"].dt.day)[campo].sum()
        return [round(float(s.get(d, 0)), 2) for d in range(1, ontem.day + 1)]

    def resumo_ref(df):
        if df.empty:
            return None
        return {"rec": round(float(df["rec"].sum()), 2), "bol": int(df["bol"].sum()), "it": int(df["it"].sum()),
                "b1": int(df["b1"].sum()), "br": int(df["br"].sum()),
                "bt": int(df["bt"].sum()), "bp": int(df["bp"].sum()), "bpe": int(df["bpe"].sum()), "dias": int(df["data"].nunique())}

    def serie_aa(loja):
        # mesmo dia do calendário do ano anterior (12/10 com 12/10): o mês inteiro, para comparar o período e o fechamento
        if aa is None:
            return None
        df = aa[aa["loja"] == loja]
        if df.empty or df["rec"].sum() <= 0:
            return None
        out = {}
        for campo in ("rec", "bol", "it", "b1", "br"):
            s = df.groupby(df["data"].dt.day)[campo].sum()
            out[campo] = [round(float(s.get(d, 0)), 2) for d in range(1, dias_mes + 1)]
        return out

    for loja in sorted(lojas_meta):
        cad = centros.loc[loja] if loja in centros.index else None
        ml = metas[metas["loja"] == loja]
        mt = ml.set_index(ml["data"].dt.day)["meta"]
        vl = mes[mes["loja"] == loja]
        nome = (cad["LOJA"] if cad is not None else None) or nomes_venda.get(loja) or metas.loc[metas["loja"] == loja, "loja_nome"].iloc[0]
        lojas_out.append({
            "id": loja,
            "nome": str(nome).strip().title(),
            "praca": str(cad["PRAÇA"]) if cad is not None else "",
            "gestor": str(cad["GVO"]) if cad is not None else "Sem gestor",
            "canal": str(cad["GCVO/GPVO"]) if cad is not None else "",
            "grvo": str(cad["GRVO"]) if cad is not None else "",
            "regional": str(cad["REGIONAL"]) if cad is not None else "",
            "cluster": str(cad["CLUSTER"]) if cad is not None else "",
            "meta": [round(float(mt.get(d, 0)), 2) for d in range(1, dias_mes + 1)],
            "rec": serie(vl, "rec"), "bol": serie(vl, "bol"), "it": serie(vl, "it"), "b1": serie(vl, "b1"), "br": serie(vl, "br"),
            "bt": serie(vl, "bt"), "bp": serie(vl, "bp"), "bpe": serie(vl, "bpe"),
            "alav": {c: serie(vl, c) for c in ALAVANCAS},
            "ref": resumo_ref(ref[ref["loja"] == loja]),
            "aa": serie_aa(loja),
            "plano": plano_lojas.get(loja),
        })
        for consultor, vc in vl.groupby("consultor"):
            codigo, _, nome_c = consultor.partition(" - ")
            if codigo.strip() in ("0", "") or "SEM CONSULTOR" in consultor.upper():
                continue
            rc = ref[(ref["loja"] == loja) & (ref["consultor"] == consultor)]
            cons_out.append({
                "id": f"{codigo.strip()}@{loja}", "nome": nome_curto(nome_c or consultor), "loja": loja,
                **({"digital": True} if codigo.strip() in DIGITAIS else {}),
                "rec": serie(vc, "rec"), "bol": serie(vc, "bol"), "it": serie(vc, "it"), "b1": serie(vc, "b1"), "br": serie(vc, "br"),
                "bt": serie(vc, "bt"), "bp": serie(vc, "bp"), "bpe": serie(vc, "bpe"),
                "ref": resumo_ref(rc),
                "plano": achar_plano(plano_cons, loja, nome_c),
            })

    saida = {
        "geradoEm": datetime.now().isoformat(timespec="minutes"),
        "ontem": ontem.strftime("%Y-%m-%d"),
        "diasMes": dias_mes,
        "referencia": {"inicio": ini_ref.strftime("%Y-%m-%d"), "fim": (ini_mes - pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                       "diasComVenda": int(ref["data"].nunique())},
        "lojasSemMeta": [{"id": l, "nome": nomes_venda.get(l, l)} for l in sem_meta],
        "planoBM": plano_rede,
        "pessoas": pessoas_do_cadastro(centros, {l["id"] for l in lojas_out}),
        "anoAnterior": None if aa is None else {"ano": ini_mes.year - 1, "ultimoDia": int(aa["data"].max().day),
                                                "arquivos": [a.name for a in arqs_aa]},
        "lojas": lojas_out,
        "consultores": cons_out,
    }
    ARQ_SAIDA.parent.mkdir(exist_ok=True)
    ARQ_SAIDA.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    rec = sum(sum(l["rec"]) for l in lojas_out)
    meta_ate = sum(sum(l["meta"][:ontem.day]) for l in lojas_out)
    print(f"OK: {len(lojas_out)} lojas, {len(cons_out)} consultores -> {ARQ_SAIDA.relative_to(BASE)}")
    print(f"Receita do mês até ontem R$ {rec:,.0f} | meta até ontem R$ {meta_ate:,.0f} | {rec / meta_ate:.1%}")
    if plano_lojas:
        n_l = sum(1 for l in lojas_out if l["plano"])
        n_c = sum(1 for c in cons_out if c["plano"])
        print(f"Plano BM: {n_l} de {len(lojas_out)} lojas e {n_c} consultores ligados ao plano ({len(plano_cons)} no plano).")
    if aa is not None:
        comp = [l for l in lojas_out if l["aa"]]
        r26 = sum(sum(l["rec"]) for l in comp)
        r25 = sum(sum(l["aa"]["rec"][:ontem.day]) for l in comp)
        print(f"Vs {ini_mes.year - 1}: {len(comp)} de {len(lojas_out)} lojas comparáveis | 01 a {ontem:%d/%m}: "
              f"R$ {r26:,.0f} vs R$ {r25:,.0f} ({r26 / r25 - 1:+.1%})")
    if sem_meta:
        print(f"Atenção: {len(sem_meta)} loja(s) com venda e sem meta, fora do painel: {', '.join(sem_meta)}")


if __name__ == "__main__":
    main()
