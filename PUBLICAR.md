# Publicar o PULSAR no GitHub Pages (produção e desenvolvimento)

Repositório: https://github.com/fabio-paulo-silva/PULSAR-COMERCIAL

| Ambiente | Branch | Endereço |
|---|---|---|
| Produção | `main` | https://fabio-paulo-silva.github.io/PULSAR-COMERCIAL/ |
| Desenvolvimento | `develop` | https://fabio-paulo-silva.github.io/PULSAR-COMERCIAL/dev/ |

A cada `push` em `main` ou `develop`, o GitHub Actions (`.github/workflows/pages.yml`) monta os dois ambientes e publica. Os dados (`data/pulsar.json`) e o ciclo (`Ciclo/ciclo_atual.json`) saem da `main` e valem para os dois.

O que vai para o GitHub: `index.html`, `config.js`, `data/pulsar.json`, `Ciclo/`, `processar_dados.py`, `analises/*.py`, `apps-script/`, documentação. As planilhas brutas (vendas, metas, cadastro, Plano BM) ficam só no computador (`.gitignore`).

## Configuração única (uma vez)
1. No GitHub, abra o repositório > **Settings > Pages** > em **Source**, escolha **GitHub Actions**.
2. No computador, a pasta do projeto já está preparada como repositório Git, com as branches `main` e `develop`.
3. Envie as duas branches (o Windows abre o login do GitHub na primeira vez):
   ```
   git push -u origin main
   git push -u origin develop
   ```
4. Acompanhe em **Actions**; em 1 a 2 minutos os dois endereços acima ficam no ar.

## Dia a dia
**Atualizar os dados (produção e desenvolvimento):**
1. Salve as planilhas novas nas pastas de sempre e rode `Abrir PULSAR.bat` (ou `python processar_dados.py`).
2. Envie só os dados para a `main`:
   ```
   git checkout main
   git add data/pulsar.json Ciclo/ciclo_atual.json
   git commit -m "Dados até DD/MM"
   git push
   ```

**Atualizar o acompanhamento do dia (hoje.html), quantas vezes quiser ao longo do dia:**
1. Salve o export de cupons de hoje em `Dados/Hoje` (substitua o anterior).
2. Rode `Atualizar hoje.bat` (ou `python processar_hoje.py`).
3. Envie para a `main`:
   ```
   git checkout main
   git add data/hoje.json
   git commit -m "Venda de hoje até HH:MM"
   git push
   git checkout develop
   ```

**Testar uma mudança no painel:**
1. `git checkout develop`, faça a mudança, `git commit` e `git push`.
2. Confira em `/dev/` (aparece o selo amarelo **Desenvolvimento**).

**Levar a mudança para produção:**
```
git checkout main
git merge develop
git push
git checkout develop
```

## Ambientes e planilha de ações
O `config.js` escolhe o ambiente pelo endereço: `/dev/` e o computador local usam **desenvolvimento**; o resto usa **produção**. Cada um tem sua URL de planilha de ações. Hoje os dois ambientes usam a mesma planilha (todo mundo vê as mesmas ações, em `/dev/` e em produção); para separar, crie uma segunda planilha "PULSAR · Ações (dev)" seguindo `apps-script/PASSO_A_PASSO.md` e cole a URL e a chave no bloco `desenvolvimento` do `config.js`.

## Atenção: o site é público
No GitHub Pages do plano gratuito (e no Pro), o site fica aberto para qualquer pessoa com o link, mesmo com o repositório privado. Isso inclui `data/pulsar.json` (receita por loja e nomes de consultores) e a URL da planilha de ações. Para restringir a quem é da empresa, é preciso GitHub Enterprise Cloud (Pages privado) ou outra hospedagem com login, como Cloudflare Pages + Cloudflare Access.
