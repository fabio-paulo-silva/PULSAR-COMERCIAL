# PULSAR · Ligar o registro de ações ao Google Sheets

As ações registradas no PULSAR passam a ser gravadas numa planilha do Google, e todos que abrem o painel veem as mesmas ações.

## 1. Criar a planilha
1. Em sheets.google.com, crie uma planilha nova chamada **PULSAR · Ações**.
2. Não precisa criar abas nem cabeçalhos: o script cria a aba `acoes` sozinho no primeiro registro.

## 2. Colar o script
1. Na planilha: **Extensões > Apps Script**.
2. Apague o conteúdo do arquivo `Código.gs` e cole todo o conteúdo de `apps-script/Codigo.gs` (desta pasta).
3. Na linha `const CHAVE = 'troque-esta-chave';`, troque o texto por uma chave só sua (ex.: `pulsar-gn-2026-x7k`).
4. Clique no disquete (**Salvar**).

## 3. Publicar como App da Web
1. **Implantar > Nova implantação**.
2. Na engrenagem de "Selecionar tipo", escolha **App da Web**.
3. Preencha:
   - Descrição: `PULSAR ações`
   - Executar como: **Eu**
   - Quem pode acessar: **Qualquer pessoa**
4. **Implantar**. Na primeira vez, o Google pede autorização: escolha sua conta > **Avançado** > **Acessar PULSAR (não seguro)** > **Permitir**. O aviso aparece porque o script é seu e não passou por revisão do Google.
5. Copie a **URL do App da Web** (termina em `/exec`).

## 4. Testar a URL
Cole no navegador, trocando a chave:
```
https://script.google.com/macros/s/SEU_ID/exec?chave=SUA_CHAVE&mes=2026-10
```
A resposta deve ser `{"ok":true,"acoes":[]}`.

## 5. Configurar o PULSAR
No `index.html`, procure `const PLANILHA=` e preencha:
```js
const PLANILHA={
 url:'https://script.google.com/macros/s/SEU_ID/exec',
 chave:'SUA_CHAVE'
};
```
Salve e recarregue o painel. O selo no topo deve mostrar **"Ações: planilha conectada"**.

## Como funciona no dia a dia
- **Registrar ação:** grava uma linha na planilha com data/hora, autor, loja, consultor, tipo, gatilho e descrição.
- **Remover ação:** a linha fica na planilha com `status = removida` (o histórico não se perde).
- **Sem internet ou planilha fora do ar:** a ação fica guardada no navegador e é enviada na próxima sincronização (ao abrir o painel e a cada 2 minutos). O selo mostra "Ações: N para enviar".
- O painel lê só as ações do mês corrente.

## Se você alterar o script depois
Use **Implantar > Gerenciar implantações > lápis > Versão: Nova versão > Implantar**. Assim a URL continua a mesma. Uma "Nova implantação" gera outra URL, e aí é preciso trocar no `index.html`.

## Segurança
- A chave barra gravações por acaso ou por robôs, mas fica visível no código da página. Ela não é uma senha forte.
- Se o PULSAR for publicado em um site aberto (GitHub Pages público), qualquer pessoa com o link vê os dados e a URL da planilha. Prefira publicar com login (ex.: Cloudflare Pages + Cloudflare Access com os e-mails da empresa).
