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

## Painel do início do dia (regras de leitura)
- **Dados D-1:** as vendas vão até ontem; não há parcial do dia.
- **Meta de hoje (ritmo):** meta do dia da planilha + gap acumulado diluído nos dias que faltam (com meta). **Fecha o mês:** média simples por dia que falta para chegar a 100% da meta do mês.
- **Chips de data:** filete verde (≥ 100% da meta do dia), amarelo (90 a 99%), vermelho (< 90%).
- **Meta × realizado por dia:** barras = meta do dia, linha = realizado, rótulo = % de atingimento do dia.
- **Cards de prioridade:** valor em R$ = perda (ou potencial) da loja no período filtrado. Ação de fluxo da própria loja quando um canal (Calçada, VFL, WhatsApp, conversão do brinde) vale ≥ R$ 1 mil contra o cluster no ritmo; senão, a ação do ciclo.
- **Link direto da loja:** `?loja=ID` (ou `?gvo=`, `?praca=`, `?reg=`). O último filtro fica lembrado no navegador. Com uma loja filtrada, a aba Hoje mostra a meta de hoje por consultor (pela participação na receita do período, só quem vendeu nos últimos 7 dias).

## Comparação com o ano anterior
- Fonte: o arquivo do mesmo mês do ano anterior em `Dados/` (ex.: `Dados/Outubro 2025/cupom_venda_2025-10-01_a_2025-10-31.xlsx`). Sem arquivo, a comparação some do painel.
- Mesmas regras de cupom do mês atual (só efetivados, brinde fora, sacola descontada; em 2025 não havia a campanha da sacola nem a sacola como item).
- Mesmo dia do calendário (12/10 com 12/10) e só lojas com venda nos dois anos.
- Variação da receita = efeito boletos ((boletos 2026 − boletos 2025) × BM 2025) + efeito boleto médio (boletos 2026 × diferença de BM).

## Boletos contra o cluster
O indicador de boletos é **% dos boletos que a meta pede**: boletos de venda ÷ (meta do período ÷ BM alvo de venda). Compara lojas de tamanhos diferentes; a referência é a mediana das lojas do mesmo cluster no ritmo.
- **Onde está a perda:** cada caixa mostra se o indicador está maior ou menor que o mesmo período do ano passado e quanto isso vale em R$ (boletos + IPB + preço médio somam a variação da receita).
- **Cards do topo:** % da meta mostra a variação contra o ano passado até ontem; Projeção mostra onde o mês fecha se repetir a curva do ano passado; Meta de hoje mostra quanto as mesmas lojas venderam no mesmo dia do ano passado.
- **Gatilho "Caindo vs ano passado":** receita da loja 5% ou mais abaixo do ano passado nos mesmos dias (crítico ≤ −15%, alto ≤ −8%). A ação vai para o indicador que mais tirou receita (boletos, IPB ou preço médio) e a meta do dia é superar a venda do mesmo dia do ano passado.

## Aba Hoje: uma decisão por loja
- **Régua única:** a meta. Cluster e ano passado aparecem só como evidência ("Por quê").
- **R$ em risco hoje** (ranking de todas as visões) = meta de hoje − venda esperada se a loja repetir o ritmo dos últimos 7 dias (realizado ÷ meta do dia). Loja sem risco contra a meta, mas 8% ou mais abaixo do ano passado: em risco = venda do mesmo dia do ano passado − esperada.
- **Indicador a mover:** entre boletos, IPB e preço médio que estão abaixo do alvo de hoje, o que mais tira receita (contra o alvo do Plano BM, ou contra o ano passado quando essa é a régua). Boletos: alvo = meta de hoje ÷ BM alvo, contra a média dos últimos 7 dias.
- **Como:** canal da própria loja que mais rende contra o cluster (boletos) ou o item do ciclo; IPB sempre com BT e BP.
- **Registro:** a ação registrada pelo card leva o indicador (coluna gatilho) e a meta ("Meta: 82 boletos hoje" na descrição). O **placar de ontem** compara essa meta com o que a loja (ou o consultor) fez no dia.
- **A tela se adapta ao filtro:** com loja = visão do gerente (1 decisão, meta por consultor, ações da loja); com GVO = as lojas do GVO; sem loja nem GVO = rede, regional ou praça, com a tabela de GVOs fora do trilho.
- **Aba Entender:** árvore da perda, comparação com o ano passado, meta × realizado por dia, ciclo × lojas e ações do mês.
