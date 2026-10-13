# PULSAR COMERCIAL

Painel diário do time comercial: % da meta, meta de hoje, onde está a perda (boletos × IPB × preço médio) e as prioridades de ação por loja e consultor.

## Como abrir
Dê dois cliques em **`Abrir PULSAR.bat`**. Ele roda `processar_dados.py` (lê as planilhas e gera `data/pulsar.json`) e abre o painel em http://localhost:8744.

## Pastas e arquivos
| Caminho | O que é |
|---|---|
| `Dados/<Mês>/cupom_venda_*.xlsx` | Vendas exportadas do Retaguarda GB (por cupom ou item a item) |
| `Metas/METAS <MÊS> VAREJO - VD.xlsx` | **Meta mensal** por loja do Canal Varejo (aba `VAREJO`) |
| `Metas/Metas_Canal_Loja.xlsx` | Meta **diarizada**, usada só para dar o formato de cada dia |
| `dCentros/dCentros.xlsx` | Cadastro de lojas e hierarquia (Regional, Praça, GVO) |
| `Plano BM/Plano_BM_2026.xlsx` | BM alvo (aba Acompanhamento), BM do cluster e meta de %B1 |
| `Ciclo/ciclo_atual.json` | Ações e agenda do ciclo vigente (trocar a cada ciclo) |
| `apps-script/` | Script e passo a passo da planilha Google onde ficam as ações registradas |

## Regra das metas
1. **Valor do mês:** vem da aba `VAREJO` do arquivo `METAS <MÊS> VAREJO...xlsx` do mês das vendas (ex.: `METAS OUTUBRO VAREJO - VD.xlsx`). O código `12175.1` (quiosque) soma na loja `12175`.
2. **Distribuição por dia:** a meta do dia = meta mensal × peso do dia na planilha diarizada (`Metas_Canal_Loja.xlsx`). Dias com meta zero na diarizada (loja fechada) continuam zero.
3. **Loja sem diarização** (em outubro: Ceará-Mirim 21270, Baraúna 23820 e Centro 7427): usa o formato médio das lojas da mesma praça.
4. **Sem o arquivo mensal do mês**, o painel usa a meta da própria planilha diarizada.
5. **Meta de hoje:** meta do dia + gap acumulado ÷ dias restantes com meta (contando hoje). Se a loja, ou o conjunto que está sendo visto, está acima do "deveria estar", fica só a meta do dia.

Para um novo mês: salve em `Metas/` o arquivo `METAS <MÊS> VAREJO - VD.xlsx` e mantenha a diarizada com as datas do mês.

## Outras regras de cálculo
- **Boletos de venda:** cupons "Efetivado" com receita ≥ R$ 1. Cupons de brinde (Ação de Fluxo) ficam à parte.
- **Itens:** sem a sacola. **IPB** = itens ÷ boletos; **preço médio** = receita ÷ itens; **BM** = receita ÷ boletos.
- **BM alvo da loja:** média do BM Alvo dos consultores da aba Acompanhamento do Plano BM (ponderada por boletos); sem consultor lá, o BM do cluster. Convertido para boleto de venda pela proporção de brindes da loja em jul–set.
- **Boletos que a meta pede** = meta ÷ BM alvo. **IPB e preço médio alvo** dividem o BM alvo na proporção de jul–set.
- **BT e BP:** % dos boletos com a tag "BOLETO TURBINADO" / "BOLETO PROMOCIONAL" na coluna Campanhas. Saudável: 32% e 30%.
