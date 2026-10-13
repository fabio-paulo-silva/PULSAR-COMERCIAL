/** @OnlyCurrentDoc */
// Limita a permissão do script a esta planilha (sem acesso às outras planilhas da conta).

/**
 * PULSAR COMERCIAL - API das ações registradas (Google Apps Script ligado à planilha).
 *
 * GET  ?chave=...&mes=2026-10   -> devolve as ações ativas do mês em JSON
 * POST {chave, acao:{...}}       -> adiciona uma ação (ignora se o id já existe)
 * POST {chave, op:'remover', id} -> marca a ação como "removida" (o histórico fica na planilha)
 *
 * Publicar: Implantar > Nova implantação > App da Web
 *   Executar como: Eu | Quem pode acessar: Qualquer pessoa
 */

// Troque por um texto só seu e use o mesmo valor no PULSAR (index.html, constante PLANILHA.chave).
const CHAVE = 'troque-esta-chave';

const ABA = 'acoes';
const COLS = ['id', 'criado_em', 'autor', 'mes', 'dia', 'loja_id', 'loja', 'consultor_id', 'consultor',
              'tipo', 'gatilho', 'descricao', 'status'];

function aba_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(ABA);
  if (!sh) {
    sh = ss.insertSheet(ABA);
    // tudo como texto: evita que "2026-10" vire data ou que o código da loja perca formato
    sh.getRange(1, 1, sh.getMaxRows(), COLS.length).setNumberFormat('@');
    sh.appendRow(COLS);
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, COLS.length).setFontWeight('bold');
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

function doGet(e) {
  const p = (e && e.parameter) || {};
  if (p.chave !== CHAVE) return resposta_({ ok: false, erro: 'chave inválida' });
  const valores = aba_().getDataRange().getValues();
  const cab = valores.shift();
  let linhas = valores.map(function (r) {
    const o = {};
    cab.forEach(function (c, i) { o[c] = texto_(c, r[i]); });
    return o;
  });
  linhas = linhas.filter(function (r) { return r.status !== 'removida' && (!p.mes || r.mes === p.mes); });
  return resposta_({ ok: true, acoes: linhas });
}

function doPost(e) {
  let d;
  try { d = JSON.parse(e.postData.contents || '{}'); } catch (err) { return resposta_({ ok: false, erro: 'JSON inválido' }); }
  if (d.chave !== CHAVE) return resposta_({ ok: false, erro: 'chave inválida' });

  const trava = LockService.getScriptLock();
  trava.waitLock(10000);
  try {
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

    const agora = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');
    // O apóstrofo no início força o Sheets a guardar como texto (não aparece na célula nem na leitura).
    sh.appendRow(COLS.map(function (c) {
      if (c === 'criado_em') return "'" + agora;
      if (c === 'status') return 'ativa';
      const v = a[c] === undefined || a[c] === null ? '' : String(a[c]);
      return v === '' ? '' : "'" + v;
    }));
    return resposta_({ ok: true });
  } finally {
    trava.releaseLock();
  }
}
