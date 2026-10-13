// PULSAR COMERCIAL - configuração por ambiente.
// O ambiente é escolhido pelo endereço da página:
//   .../dev/  ou  aberto no computador (localhost)  -> desenvolvimento
//   qualquer outro endereço                          -> produção
// Cada ambiente pode gravar as ações numa planilha diferente (apps-script/PASSO_A_PASSO.md).
window.PULSAR_CONFIG = (function () {
  var dev = /\/dev(\/|$)/.test(location.pathname) || /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
  var ambientes = {
    producao: {
      nome: 'Produção',
      planilha: {
        url: 'https://script.google.com/macros/s/AKfycbxGdHjf5dv2LXH7d5HDwDH5KVuEFTkLenMEbZqFSLT8vbtIbPtpiNaO7xPTJ6quuAOp8g/exec',
        chave: 'pulsar-gn-2026'
      }
    },
    desenvolvimento: {
      nome: 'Desenvolvimento',
      // Usa a MESMA planilha de produção: quem abre /dev/ vê e registra as mesmas ações.
      // Para separar, crie a planilha "PULSAR · Ações (dev)" (apps-script/PASSO_A_PASSO.md) e troque a URL e a chave aqui.
      planilha: {
        url: 'https://script.google.com/macros/s/AKfycbxGdHjf5dv2LXH7d5HDwDH5KVuEFTkLenMEbZqFSLT8vbtIbPtpiNaO7xPTJ6quuAOp8g/exec',
        chave: 'pulsar-gn-2026'
      }
    }
  };
  var amb = dev ? 'desenvolvimento' : 'producao';
  return { ambiente: amb, nome: ambientes[amb].nome, planilha: ambientes[amb].planilha };
})();
