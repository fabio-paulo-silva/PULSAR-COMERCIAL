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
- **Garantir (o número de hoje):** base = boletos do mesmo dia da semana da mesma semana do ano passado (364 dias antes: 14/10/2026, quarta = 15/10/2025, quarta). Boletos que a meta pede = meta de hoje ÷ BM alvo.
  - Se a meta pede até **+30%** de boletos sobre essa base: garantir esses boletos (no mínimo o mesmo do ano passado). Ação de fluxo: canal da loja ou item do ciclo.
  - Se pede mais de +30%: boletos ficam em +30% e o resto vem do **boleto médio** (BM = meta de hoje ÷ boletos com +30%, dividido entre IPB e PM na proporção atual). Ação: BT e BP no fechamento, combos presenteáveis e sarrafos do Compre e Ganhe do ciclo.
  - Sem base do ano passado (loja nova ou fim do mês): o indicador abaixo do alvo que mais tira receita.
- **Como:** canal da própria loja que mais rende contra o cluster (boletos) ou o item do ciclo; IPB sempre com BT e BP.
- **Registro:** a ação registrada pelo card leva o indicador (coluna gatilho) e a meta ("Meta: 82 boletos hoje" na descrição). O **placar de ontem** compara essa meta com o que a loja (ou o consultor) fez no dia.
- **A tela se adapta ao filtro:** com loja = visão do gerente (1 decisão, meta por consultor, ações da loja); com GVO = as lojas do GVO; sem loja nem GVO = rede, regional ou praça, com a tabela de GVOs fora do trilho.
- **Aba Entender:** árvore da perda, comparação com o ano passado, meta × realizado por dia, ciclo × lojas e ações do mês.

## Penetração de BT e BP
- **BT** = boletos com a tag Boleto Turbinado ÷ boletos com item pago (o brinde da Ação de Fluxo sem compra fica fora). Saudável: 32%.
- **BP** = boletos com a tag Boleto Promocional ÷ boletos elegíveis, a partir de R$ 120 (sarrafo). Saudável: 30%. O `processar_dados.py` grava os elegíveis por dia em `bpe`.

## Cards do topo
- **% da meta:** atingimento do mês, balão "Deveria estar" (verde acima, vermelho abaixo), meta do mês e variação contra o ano anterior.
- **Projeção:** % de fechamento e se fecha acima ou abaixo.
- **Meta de hoje = meta diarizada + gap**, com os boletos, BM e IPB necessários (mesma regra do "Garantir": boletos até +30% sobre o mesmo dia da semana do ano passado) e BT/BP necessários (32% e 30%) contra o atual.
- **BT e BP são sempre comparados com a meta de penetração** (32% e 30%), nunca com o cluster: card da loja, tabela de alavancas da loja e coluna "Maior oportunidade" da aba Lojas. Valor de chegar à meta = boletos que faltam × preço médio do item de BT ou BP do ciclo.
- **%B1 contra o melhor do cluster:** referência = menor %B1 entre as lojas do mesmo cluster com pelo menos 200 boletos no período (QDB fora). Valor de chegar lá = boletos de 1 item que viram 2 com o BT × preço do item de BT do ciclo. Aparece no "Por quê" e no "Como" do card da loja, na coluna %B1 e na comparação da loja (aba Lojas) e na linha de BT/BP dos consultores.

## Acompanhamento do dia (hoje.html)
- **Fonte:** o export de cupons de hoje, salvo em `Dados/Hoje` (pode ser trocado ao longo do dia). `processar_hoje.py` (ou `Atualizar hoje.bat`) grava `data/hoje.json`. A pasta `Dados/Hoje` fica fora do fechamento D-1 do `processar_dados.py`.
- **Meta de hoje** = meta diarizada + gap até ontem ÷ dias que faltam (a mesma do painel do mês); por isso o `data/pulsar.json` precisa estar fechado até ontem.
- **Esperado até agora** = meta de hoje × parte do dia que costuma estar vendida até a hora do último cupom. A curva por hora vem dos cupons do mês no mesmo dia da semana (metade a curva da loja, metade a da rede).
- **Ritmo agora** = vendido ÷ esperado (verde ≥ 100%, amarelo ≥ 90%, vermelho abaixo). **Projeção do dia** = vendido ÷ parte do dia já passada, comparada com o mesmo dia da semana do ano passado.
- **Boletos, BM, IPB e PM necessários:** regra do "Garantir" (boletos até +30% sobre o mesmo dia da semana do ano passado). BT e BP com as mesmas regras de elegibilidade do painel.
- **Consultores:** meta individual = meta de hoje da loja ÷ nº de consultores do time, em partes iguais (mesma regra da "Meta de hoje por consultor" do painel do mês). Time = quem vendeu nos últimos 7 dias e tem receita no mês de pelo menos 20% da mediana dos colegas da loja; abaixo disso é venda pontual (digital, apoio de outra loja) e o consultor aparece como "fora do time".
- A página busca o `data/hoje.json` de novo a cada 5 minutos. Filtros e `?loja=ID` iguais aos do painel do mês.

## Consultores digitais (WhatsApp)
- Lista em `processar_dados.py` (`DIGITAIS`, pelo código do Retaguarda): Allana Santos (1130) e João Barros (1413), de São Luís; Wanessa Menezes (1282) e Emilly Silva (795, Emilly Kailany Vicente da Silva), de Natal.
- No painel, cada digital é uma pessoa só, somando a venda de todas as lojas em que atende. É comparado com a média do grupo digital, fica fora do time da loja (média do time, meta por consultor, "puxam para baixo") e aparece em uma tabela própria na aba Consultores.
- Na hoje.html, os digitais aparecem como "digital (WhatsApp)", sem meta individual.

## Aba Consultores
Primeiro a tabela dos consultores de loja e a dos digitais, com receita/dia, boletos/dia, IPB, preço médio e %B1 contra o time (ou o grupo digital) e BT e BP contra a meta. Verde = no nível ou acima, amarelo = até 10% abaixo, vermelho = abaixo disso (no %B1, ao contrário). Embaixo, o card de cada consultor. Os botões de perfil filtram as tabelas e os cards.

## Qualidade do boleto e R$ em jogo (consultores)
- **Grupo de comparação:** consultores do mesmo cluster (shopping, rua, galeria, supermercado); QDB só com QDB; digitais só entre si.
- **Qualidade (0 a 100):** cada indicador vira percentil no grupo (0 = pior, 100 = melhor) e entra na média com os pesos **IPB 4**, **%B1 3** (menor é melhor), **BT + BP contra a meta 2** e **preço médio 1**. Quem tem menos de 100 boletos no período é puxado para a média do grupo na proporção do volume. Faixas: < 25 Crítica, 25–50 Abaixo, 50–75 Boa, ≥ 75 Ótima.
- **R$ em jogo por dia:** quanto o consultor perde, com os mesmos boletos/dia, por estar abaixo do grupo no IPB e no preço médio. Preço médio alto não compensa IPB baixo; IPB alto compensa preço médio baixo. É a ordem padrão da tabela.
- **Perfil = volume × qualidade:** receita/dia ≥ 95% do time e qualidade ≥ 50 → No nível do time (ou Destaque, se ≥ 115%); volume alto e qualidade < 50 → **Vende muito, boleto fraco** (1:1 de BT no boleto de 1 item); volume baixo e qualidade ≥ 50 → **Poucos boletos**; volume baixo e qualidade < 50 → **Crítico: volume e boleto**. "Sem venda nos últimos 3 dias" continua à parte.
- A tabela traz todos os consultores do filtro com rolagem (até 15 linhas, limitada a 80% da tela) e a linha "Total do filtro" fixa no rodapé, com o R$ em jogo somado e a qualidade média.
- Tabela de consultores enxuta: R$ em jogo, qualidade, boletos/dia, IPB, %B1, BT · BP, preço médio e boleto médio. A cor de cada indicador vem do percentil no grupo; a referência do grupo, o detalhe do R$ em jogo e o perfil ficam na dica ao passar o mouse.

## Uso do painel (quem acessa)
- **Identificação:** na primeira visita, o painel do mês e a hoje.html pedem o nome, com busca (todos os nomes distintos de GVO, GCVO/GPVO e GRVO do dCentros, o "TIME IAF" ou "Outro nome"). O TIME IAF (`USUARIOS_EXTRAS` em processar_dados.py) aparece na aba Uso como time interno, fora dos indicadores de gestores. Fica salvo no navegador; o selo "Usuário" no topo permite trocar. O autor do registro de ação vem preenchido com esse nome.
- **Registro (`uso.js`):** cada página, aba ou filtro aberto grava um acesso na aba `acessos` da planilha (data e hora, nome, papel, aparelho, página, aba, regional, praça, GVO, loja, ambiente). A mesma tela não é gravada de novo antes de 30 minutos. No computador local (localhost) nada é gravado.
- **Aba Uso:** "Telas mais usadas" (acessos e pessoas por página e aba) e "Últimos acessos" (hora, quem, tela e filtro; clique num gestor para ver só os dele). Por gestor, se acessou hoje, último acesso, dias com acesso no mês, acessos, uso do painel do mês e do acompanhamento do dia, lojas filtradas e ações registradas. Com filtro, mostra os gestores com loja no filtro.
- **Requer** o `apps-script/Codigo.gs` atualizado (op `acesso` e `?tipo=acessos`): republicar em Implantar > Gerenciar implantações > editar > Nova versão.
- A identificação é declarada pela própria pessoa (não há login).
