/* PULSAR COMERCIAL - identificação de quem acessa e registro de uso (painel do mês e acompanhamento do dia).
 *
 * Na primeira visita a pessoa escolhe o nome (GVO, GCVO/GPVO ou GRVO do cadastro de lojas, ou outro nome).
 * A escolha fica neste navegador. A cada página, aba ou filtro aberto, grava um acesso na aba "acessos" da
 * planilha de ações (Apps Script), no máximo 1 vez a cada 30 minutos para a mesma tela.
 * No computador local (localhost) não grava nada, para os testes não contarem como uso.
 */
(function () {
  const KEY_USUARIO = 'pulsar-usuario', KEY_DISP = 'pulsar-dispositivo', KEY_ULT = 'pulsar-ultimo-acesso';
  const REPETE_MIN = 30;
  const local = /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
  let cfg = { pessoas: [], planilha: { url: '', chave: '' }, ambiente: '', pagina: '' };

  const ler = (k, d) => { try { const v = JSON.parse(localStorage.getItem(k)); return v == null ? d : v; } catch (e) { return d; } };
  const gravar = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const dispositivo = () => { let d = ler(KEY_DISP, ''); if (!d) { d = Math.random().toString(36).slice(2, 10); gravar(KEY_DISP, d); } return d; };

  function usuario() { return ler(KEY_USUARIO, null); }

  function selo() {
    const box = document.querySelector('.hero .chips');
    if (!box) return;
    let b = document.getElementById('hUsuario');
    if (!b) {
      b = document.createElement('button');
      b.id = 'hUsuario'; b.type = 'button'; b.className = 'glass'; b.title = 'Trocar quem está usando';
      b.style.border = '0'; b.style.cursor = 'pointer';
      b.addEventListener('click', () => perguntar(true));
      box.appendChild(b);
    }
    const u = usuario();
    b.innerHTML = `<span style="opacity:.75">Usuário:</span> <b>${esc(u ? u.nome : 'identificar')}</b>`;
  }

  // Janela de identificação (usa as cores do painel)
  function perguntar(trocar) {
    return new Promise(resolve => {
      const u = usuario();
      const grupos = { 'GRVO': [], 'GCVO/GPVO': [], 'GVO': [] };
      (cfg.pessoas || []).forEach(p => { const g = (p.papeis || ['GVO'])[0]; (grupos[g] = grupos[g] || []).push(p); });
      const opt = p => `<option value="${esc(p.nome)}" data-papel="${esc((p.papeis || []).join(', '))}" ${u && u.nome === p.nome ? 'selected' : ''}>${esc(p.nome)}${p.papeis && p.papeis.length > 1 ? ' · ' + esc(p.papeis.join(', ')) : ''}</option>`;
      const d = document.createElement('dialog');
      d.style.cssText = 'border:1px solid var(--border);border-radius:20px;background:var(--card);color:var(--foreground);padding:24px;max-width:440px;width:calc(100% - 32px);box-shadow:0 20px 40px -16px rgba(0,0,0,.4)';
      d.innerHTML = `<form method="dialog" style="display:flex;flex-direction:column;gap:14px">
        <h2 style="font-size:20px;margin:0">Quem está acessando?</h2>
        <p style="margin:0;color:var(--muted-fg);font-size:14px">Escolha seu nome para acompanharmos o uso do PULSAR. A escolha fica salva neste navegador.</p>
        <select id="usoNome" required style="height:40px;width:100%">
          <option value="">Selecione…</option>
          ${Object.entries(grupos).filter(([, l]) => l.length).map(([g, l]) => `<optgroup label="${g}">${l.map(opt).join('')}</optgroup>`).join('')}
          <option value="__outro">Outro nome…</option>
        </select>
        <input id="usoOutro" placeholder="Seu nome e função" style="height:40px;width:100%;display:none">
        <p style="margin:0;color:var(--muted-fg);font-size:12px">Seu acesso (nome, data e hora, página e filtros usados) fica registrado na planilha do PULSAR.</p>
        <div style="display:flex;justify-content:flex-end;gap:8px">
          ${trocar ? '<button type="button" id="usoCancelar" class="btn ghost">Cancelar</button>' : ''}
          <button type="submit" class="btn" style="background:var(--primary);color:var(--primary-fg);border:0;border-radius:10px;padding:9px 16px;font-weight:700">Entrar</button>
        </div></form>`;
      document.body.appendChild(d);
      const sel = d.querySelector('#usoNome'), outro = d.querySelector('#usoOutro');
      sel.addEventListener('change', () => { outro.style.display = sel.value === '__outro' ? 'block' : 'none'; outro.required = sel.value === '__outro'; });
      d.addEventListener('cancel', e => { if (!trocar) e.preventDefault(); });
      const can = d.querySelector('#usoCancelar'); if (can) can.onclick = () => { d.close(); d.remove(); resolve(u); };
      d.querySelector('form').addEventListener('submit', e => {
        const nome = sel.value === '__outro' ? outro.value.trim() : sel.value;
        if (!nome) { e.preventDefault(); return; }
        const papel = sel.value === '__outro' ? 'Outro' : (sel.selectedOptions[0].dataset.papel || '');
        gravar(KEY_USUARIO, { nome, papel });
        gravar(KEY_ULT, {});                 // pessoa nova: o próximo acesso é registrado
        d.remove(); selo(); resolve(usuario());
        if (window.PulsarUso.aoTrocar) window.PulsarUso.aoTrocar(usuario());
      });
      d.showModal();
    });
  }

  // Registra o acesso (página, aba e filtro). A mesma tela não é gravada de novo antes de 30 minutos.
  function registrar(tela) {
    const u = usuario();
    if (!u || !cfg.planilha || !cfg.planilha.url) return;
    const t = Object.assign({ pagina: cfg.pagina, aba: '', regional: '', praca: '', gvo: '', loja_id: '' }, tela || {});
    const chave = [u.nome, t.pagina, t.aba, t.regional, t.praca, t.gvo, t.loja_id].join('|');
    const ult = ler(KEY_ULT, {}), agora = Date.now();
    if (ult[chave] && agora - ult[chave] < REPETE_MIN * 60000) return;
    ult[chave] = agora; gravar(KEY_ULT, ult);
    if (local) return;
    const acesso = Object.assign({ nome: u.nome, papel: u.papel, dispositivo: dispositivo(), ambiente: cfg.ambiente }, t);
    fetch(cfg.planilha.url, { method: 'POST', keepalive: true, body: JSON.stringify({ chave: cfg.planilha.chave, op: 'acesso', acesso }) }).catch(() => {});
  }

  // Lê os acessos do mês (aba Uso). Se o Apps Script ainda for a versão antiga, devolve null.
  async function acessos(mes) {
    if (!cfg.planilha || !cfg.planilha.url) return null;
    const r = await fetch(`${cfg.planilha.url}?chave=${encodeURIComponent(cfg.planilha.chave)}&tipo=acessos&mes=${mes}`, { cache: 'no-store' }).then(x => x.json());
    return r && r.ok && Array.isArray(r.acessos) ? r.acessos : null;
  }

  async function iniciar(opcoes) {
    cfg = Object.assign(cfg, opcoes || {});
    selo();
    if (!usuario()) await perguntar(false);
    return usuario();
  }

  window.PulsarUso = { iniciar, usuario, registrar, acessos, trocar: () => perguntar(true), local };
})();
