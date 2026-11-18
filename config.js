// PULSAR COMERCIAL - configuração por ambiente.
// O ambiente é escolhido pelo endereço da página:
//   .../dev/  ou  aberto no computador (localhost)  -> desenvolvimento
//   qualquer outro endereço                          -> produção
//
// Segurança: a URL do Apps Script e a chave NÃO ficam no repositório. Os marcadores abaixo são trocados na
// publicação (GitHub Actions) pelos segredos PULSAR_PLANILHA_URL e PULSAR_PLANILHA_CHAVE do repositório.
// Sem os segredos (ex.: painel aberto no computador), a planilha de ações fica desligada.
window.PULSAR_CONFIG = (function () {
  var dev = /\/dev(\/|$)/.test(location.pathname) || /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
  var url = '__PULSAR_PLANILHA_URL__', chave = '__PULSAR_PLANILHA_CHAVE__';
  if (url.indexOf('__') === 0) { url = ''; chave = ''; }
  var amb = dev ? 'desenvolvimento' : 'producao';
  return { ambiente: amb, nome: dev ? 'Desenvolvimento' : 'Produção', planilha: { url: url, chave: chave } };
})();
