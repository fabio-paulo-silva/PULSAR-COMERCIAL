/** @OnlyCurrentDoc */
// Limita a permissão do script a esta planilha (sem acesso às outras planilhas da conta).

/**
 * PULSAR COMERCIAL - API das ações registradas e dos acessos (Google Apps Script ligado à planilha).
 *
 * GET  ?chave=...&mes=2026-10                -> ações ativas do mês em JSON
 * GET  ?chave=...&tipo=acessos&mes=2026-10   -> acessos ao painel no mês (aba Uso)
 * POST {chave, acao:{...}}                    -> adiciona uma ação (ignora se o id já existe)
 * POST {chave, op:'remover', id}              -> marca a ação como "removida" (o histórico fica na planilha)
 * POST {chave, op:'acesso', acesso:{...}}     -> registra um acesso ao painel (quem, página, aba e filtro)
 *
 * Publicar: Implantar > Gerenciar implantações > editar > Nova versão
 *   Executar como: Eu | Quem pode acessar: Qualquer pessoa
 */

// Troque por um texto só seu e use o mesmo valor no PULSAR (config.js, chave da planilha).
const CHAVE = 'troque-esta-chave';

const ABA = 'acoes';
const COLS = ['id', 'criado_em', 'autor', 'mes', 'dia', 'loja_id', 'loja', 'consultor_id', 'consultor',
              'tipo', 'gatilho', 'descricao', 'status'];
const ABA_ACESSOS = 'acessos';
const COLS_ACESSOS = ['quando', 'mes', 'dia', 'nome', 'papel', 'dispositivo', 'pagina', 'aba',
                      'regional', 'praca', 'gvo', 'loja_id', 'ambiente'];

function aba_(nome, cols) {
  nome = nome || ABA; cols = cols || COLS;
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(nome);
  if (!sh) {
    sh = ss.insertSheet(nome);
    // tudo como texto: evita que "2026-10" vire data ou que o código da loja perca formato
    sh.getRange(1, 1, sh.getMaxRows(), cols.length).setNumberFormat('@');
    sh.appendRow(cols);
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, cols.length).setFontWeight('bold');
  }
  return sh;
}

function resposta_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function ids_(sh) {
  const n = sh.getLastRow() - 1;
  return n > 0 ? sh.getRange(2, 1, n, 1).getValues().map(function (r) { return String(r[0]); }) : [];
}

// O Sheets converte textos como "2026-10" em data. Na leitura, datas voltam para o formato do PULSAR.
function texto_(coluna, v) {
  if (v === null || v === '') return '';
  if (Object.prototype.toString.call(v) === '[object Date]') {
    const fmt = coluna === 'mes' ? 'yyyy-MM' : coluna === 'dia' ? 'd' : 'yyyy-MM-dd HH:mm:ss';
    return Utilities.formatDate(v, Session.getScriptTimeZone(), fmt);
  }
  return String(v);
}

function linhas_(sh) {
  const valores = sh.getDataRange().getValues();
  const cab = valores.shift();
  return valores.map(function (r) {
    const o = {};
    cab.forEach(function (c, i) { o[c] = texto_(c, r[i]); });
    return o;
  });
}

// O apóstrofo no início força o Sheets a guardar como texto (não aparece na célula nem na leitura).
const comoTexto_ = function (v) { v = v === undefined || v === null ? '' : String(v); return v === '' ? '' : "'" + v; };

function doGet(e) {
  const p = (e && e.parameter) || {};
  if (p.chave !== CHAVE) return resposta_({ ok: false, erro: 'chave inválida' });
  if (p.tipo === 'acessos') {
    const acessos = linhas_(aba_(ABA_ACESSOS, COLS_ACESSOS)).filter(function (r) { return !p.mes || r.mes === p.mes; });
    return resposta_({ ok: true, acessos: acessos });
  }
  const linhas = linhas_(aba_()).filter(function (r) { return r.status !== 'removida' && (!p.mes || r.mes === p.mes); });
  return resposta_({ ok: true, acoes: linhas });
}

function doPost(e) {
  let d;
  try { d = JSON.parse(e.postData.contents || '{}'); } catch (err) { return resposta_({ ok: false, erro: 'JSON inválido' }); }
  if (d.chave !== CHAVE) return resposta_({ ok: false, erro: 'chave inválida' });

  const trava = LockService.getScriptLock();
  trava.waitLock(10000);
  try {
    const fuso = Session.getScriptTimeZone(), agora = new Date();

    if (d.op === 'acesso') {
      const a = d.acesso || {};
      if (!a.nome) return resposta_({ ok: false, erro: 'acesso sem nome' });
      aba_(ABA_ACESSOS, COLS_ACESSOS).appendRow(COLS_ACESSOS.map(function (c) {
        if (c === 'quando') return "'" + Utilities.formatDate(agora, fuso, 'yyyy-MM-dd HH:mm:ss');
        if (c === 'mes') return "'" + Utilities.formatDate(agora, fuso, 'yyyy-MM');
        if (c === 'dia') return "'" + Utilities.formatDate(agora, fuso, 'd');
        return comoTexto_(a[c]);
      }));
      return resposta_({ ok: true });
    }

    const sh = aba_();
    const ids = ids_(sh);

    if (d.op === 'remover') {
      const i = ids.indexOf(String(d.id));
      if (i >= 0) sh.getRange(i + 2, COLS.indexOf('status') + 1).setValue('removida');
      return resposta_({ ok: true });
    }

    const a = d.acao || {};
    if (!a.id || !a.loja_id || !a.tipo) return resposta_({ ok: false, erro: 'ação incompleta' });
    if (ids.indexOf(String(a.id)) >= 0) return resposta_({ ok: true, repetida: true });

    const quando = Utilities.formatDate(agora, fuso, 'yyyy-MM-dd HH:mm:ss');
    sh.appendRow(COLS.map(function (c) {
      if (c === 'criado_em') return "'" + quando;
      if (c === 'status') return 'ativa';
      return comoTexto_(a[c]);
    }));
    return resposta_({ ok: true });
  } finally {
    trava.releaseLock();
  }
}
