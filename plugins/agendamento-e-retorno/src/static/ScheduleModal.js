// Modal "Agendar retorno" — aberto pelo botão "Agendar" da barra do contato (extends.js).
// Duas abas: "Agendar Retorno" (formulário + próximos agendamentos do cliente) e
// "Lista de Agendamentos" (todos, manuais e da IA, com status ao vivo via /ws).
// Preact + HTM, sem build. Usa as classes wa-* do tema (claro/escuro) e um CSS próprio
// mínimo (prefixo aer-) para o layout responsivo — assim não depende de o Tailwind
// pré-compilado do core ter as utilitárias que um plugin instalado depois precisa.
import { h } from 'preact';
import { useState, useEffect, useRef, useCallback } from 'preact/hooks';
import htm from 'htm';
import { authHeaders, handleUnauthorized } from '/static/js/services/api.js';
import { createWebSocket } from '/static/js/services/websocket.js';

const html = htm.bind(h);

const API_BASE = '/api/plugins/agendamento_e_retorno';

const CSS = `
.aer-overlay{position:fixed;inset:0;z-index:70;background:rgba(0,0,0,.5);display:flex;align-items:flex-start;justify-content:center;padding:16px;overflow-y:auto}
.aer-dialog{width:100%;max-width:1100px;margin:24px 0}
.aer-grid{display:grid;grid-template-columns:minmax(0,1fr);gap:20px;align-items:start;padding:20px}
@media (min-width:860px){.aer-grid{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}}
.aer-row2{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px}
.aer-tabs{display:flex;border-bottom:1px solid rgb(var(--wa-border));margin-top:12px}
.aer-tab{flex:1;padding:12px 16px;font-size:14px;font-weight:500;border-bottom:2px solid transparent;color:rgb(var(--wa-secondary));background:none;cursor:pointer}
.aer-tab:hover{color:rgb(var(--wa-text))}
.aer-tab[aria-selected="true"]{border-bottom-color:rgb(var(--wa-teal));color:rgb(var(--wa-teal))}
.aer-card{border:1px solid rgb(var(--wa-border));background:rgb(var(--wa-bg));border-radius:12px;padding:16px}
.aer-item{border:1px solid rgb(var(--wa-border));border-left:4px solid rgb(var(--wa-teal));background:rgb(var(--wa-panel));border-radius:8px;padding:12px}
.aer-scroll{overflow-x:auto}
.aer-confirm{position:fixed;inset:0;z-index:80;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;padding:16px}
`;

function ensureStyle() {
  if (document.getElementById('aer-style')) return;
  const el = document.createElement('style');
  el.id = 'aer-style';
  el.textContent = CSS;
  document.head.appendChild(el);
}

const STATUS_META = {
  agendado:    { label: 'Ativo',     cls: 'bg-wa-teal/15 text-wa-teal' },
  processando: { label: 'Enviando…', cls: 'bg-blue-100 text-blue-700' },
  enviado:     { label: 'Enviado',   cls: 'bg-green-100 text-green-700' },
  expirado:    { label: 'Expirado',  cls: 'bg-red-100 text-red-700' },
  falhou:      { label: 'Falhou',    cls: 'bg-red-100 text-red-700' },
  cancelado:   { label: 'Cancelado', cls: 'bg-gray-100 text-gray-600' },
};

const REASON_LABEL = {
  ia_desligada: 'a IA está desligada neste contato',
  sem_resposta: 'a IA não respondeu',
  bloqueado_por_plugin: 'um plugin bloqueou o envio',
};

// Resultado do disparo (coluna `outcome`). Depende da origem: o lembrete do atendente vira
// nota privada por definição; no da IA a nota privada é só o plano B.
function outcomeOf(it) {
  if (!it.outcome) return null;
  if (!it.created_by_ia) {
    return it.outcome === 'nota_privada'
      ? { txt: 'Lembrete postado como nota privada', cls: 'text-green-700' } : null;
  }
  switch (it.outcome) {
    case 'enviado': return { txt: 'IA respondeu ao cliente', cls: 'text-green-700' };
    case 'nota_privada':
      return { txt: `Virou nota privada — ${REASON_LABEL[it.outcome_reason] || it.outcome_reason || 'motivo não registrado'}`, cls: 'text-amber-600' };
    case 'sem_resposta': return { txt: 'A IA não produziu resposta ao ser acionada', cls: 'text-red-600' };
    case 'substituido': return { txt: 'Substituído por um agendamento mais recente', cls: 'text-wa-secondary' };
    case 'cliente_respondeu': return { txt: 'Cancelado: o cliente voltou a falar antes da hora', cls: 'text-wa-secondary' };
    default: return null;
  }
}

const STATUS_FILTERS = [['ativos', 'Ativos'], ['todos', 'Todos'], ['enviado', 'Enviados'],
  ['expirado', 'Expirados'], ['falhou', 'Falhou'], ['cancelado', 'Cancelados']];
const ORIGEM_FILTERS = [['todos', 'Todas'], ['ia', 'Da IA'], ['humano', 'Manuais']];

const fieldCls = 'wa-field w-full rounded-lg px-3 py-2';

async function reqJson(url, init = {}) {
  const res = await fetch(url, { ...init, headers: authHeaders(init.headers || {}) });
  if (res.status === 401) { handleUnauthorized(); throw new Error('Não autenticado.'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) throw new Error(data.error || `Erro ${res.status}`);
  return data;
}

function fmtDateTime(epoch) {
  try { return new Date(epoch * 1000).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }); }
  catch { return ''; }
}

function todayLocal() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

const descOf = (it) => it.description || it.briefing || '';

const CalendarIcon = ({ size = 16 }) => html`<svg viewBox="0 0 24 24" width=${size} height=${size} fill="currentColor"><path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zm0-12H5V6h14v2zm-7 5h5v5h-5v-5z"/></svg>`;
const TrashIcon = ({ size = 16 }) => html`<svg viewBox="0 0 24 24" width=${size} height=${size} fill="currentColor"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>`;
const ChatIcon = ({ size = 16 }) => html`<svg viewBox="0 0 24 24" width=${size} height=${size} fill="currentColor"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>`;

function StatusBadge({ status }) {
  const m = STATUS_META[status] || { label: status, cls: 'bg-gray-100 text-gray-600' };
  return html`<span class=${`inline-block text-[11px] font-medium px-2 py-0.5 rounded-full ${m.cls}`}>${m.label}</span>`;
}

function OrigemBadge({ it }) {
  return it.created_by_ia
    ? html`<span class="shrink-0 px-1.5 py-0.5 rounded text-[11px] bg-indigo-100 text-indigo-700" title="Agendado pela própria IA">🤖 IA</span>`
    : html`<span class="shrink-0 px-1.5 py-0.5 rounded text-[11px] bg-gray-100 text-gray-600" title="Agendado por um atendente">Manual</span>`;
}

// Abre a conversa do contato (a mesma rota que o app usa: /contacts/<id>).
function goToConversation(it, onClose) {
  if (!it.contact_id) return;
  if (onClose) onClose();
  history.pushState(null, '', `/contacts/${it.contact_id}`);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

const sameContact = (it, picked) =>
  !!picked && ((picked.contactId && it.contact_id === picked.contactId) || it.phone === picked.phone);

export function ScheduleModal({ scope = null, onClose }) {
  useEffect(() => { ensureStyle(); }, []);
  ensureStyle();

  const [tab, setTab] = useState('agendar');
  const [items, setItems] = useState([]);
  const [loadErr, setLoadErr] = useState(null);

  const [dueDate, setDueDate] = useState('');
  const [dueTime, setDueTime] = useState('');
  const [description, setDescription] = useState('');
  const [saving, setSaving] = useState(false);
  const [formMsg, setFormMsg] = useState(null);
  const [confirmId, setConfirmId] = useState(null);

  // Busca de seleção única: vem com o contato da conversa, mas dá para escolher outro.
  const initial = scope && scope.phone
    ? { contactId: scope.contactId || null, name: scope.name || scope.phone, phone: scope.phone } : null;
  const [picked, setPicked] = useState(initial);
  const [query, setQuery] = useState(initial ? initial.name : '');
  const [results, setResults] = useState([]);
  const [showResults, setShowResults] = useState(false);
  const searchTimer = useRef(null);
  const blurTimer = useRef(null);

  const [fStatus, setFStatus] = useState('ativos');
  const [fOrigem, setFOrigem] = useState('todos');

  const load = useCallback(async () => {
    try {
      const d = await reqJson(`${API_BASE}/items`);
      setItems(d.data || []);
      setLoadErr(null);
    } catch (e) { setLoadErr(String(e.message || e)); }
  }, []);

  useEffect(() => {
    load();
    const ws = createWebSocket({ agendamento_e_retorno_changed: () => load() });
    return () => ws.close();
  }, [load]);

  useEffect(() => () => {
    clearTimeout(searchTimer.current);
    clearTimeout(blurTimer.current);
  }, []);

  function doSearch(term) {
    clearTimeout(searchTimer.current);
    if (!term || term.trim().length < 2) { setResults([]); return; }
    searchTimer.current = setTimeout(async () => {
      try {
        const d = await reqJson(`/api/contacts?q=${encodeURIComponent(term.trim())}`);
        setResults((d.data || []).slice(0, 8));
        setShowResults(true);
      } catch { setResults([]); }
    }, 250);
  }

  function onClientInput(e) {
    const v = e.target.value;
    setQuery(v);
    if (picked && v !== picked.name) setPicked(null); // digitar outra coisa desfaz a seleção
    doSearch(v);
  }

  function pickContact(c) {
    setPicked({ contactId: c.id, name: c.name || c.phone, phone: c.phone });
    setQuery(c.name || c.phone || '');
    setResults([]);
    setShowResults(false);
  }

  function clearForm() {
    setDueDate(''); setDueTime(''); setDescription(''); setFormMsg(null);
    setResults([]); setShowResults(false);
    setPicked(initial);
    setQuery(initial ? initial.name : '');
  }

  async function submit(e) {
    e.preventDefault();
    setFormMsg(null);
    if (!picked) { setFormMsg({ type: 'err', text: 'Busque e selecione o cliente (nome ou número).' }); return; }
    const t = (dueDate && dueTime) ? new Date(`${dueDate}T${dueTime}`).getTime() : NaN;
    if (!Number.isFinite(t)) { setFormMsg({ type: 'err', text: 'Informe a data e a hora do retorno.' }); return; }
    setSaving(true);
    try {
      await reqJson(`${API_BASE}/items`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone: picked.phone, contact_name: picked.name,
          due_at: Math.round(t / 1000), description,
        }),
      });
      setDueDate(''); setDueTime(''); setDescription('');
      setFormMsg({ type: 'ok', text: 'Retorno agendado com sucesso.' });
      load();
    } catch (err) {
      setFormMsg({ type: 'err', text: String(err.message || err) });
    } finally { setSaving(false); }
  }

  async function cancelItem(id) {
    try { await reqJson(`${API_BASE}/items/${id}/cancel`, { method: 'POST' }); load(); }
    catch (e) { setLoadErr(String(e.message || e)); }
  }

  async function removeItem(id) {
    try { await reqJson(`${API_BASE}/items/${id}`, { method: 'DELETE' }); load(); }
    catch (e) { setLoadErr(String(e.message || e)); }
  }

  // Próximos do cliente selecionado: ativos primeiro (o mais perto antes), depois o histórico.
  const clientItems = items.filter((it) => sameContact(it, picked)).sort((a, b) => {
    const aa = a.status === 'agendado', bb = b.status === 'agendado';
    if (aa !== bb) return aa ? -1 : 1;
    return aa ? a.due_at - b.due_at : b.due_at - a.due_at;
  });

  const tabBtn = (id, label) => html`
    <button type="button" role="tab" aria-selected=${tab === id} class="aer-tab" onClick=${() => setTab(id)}>${label}</button>`;

  function card(it) {
    const out = outcomeOf(it);
    return html`
      <div key=${it.id} class="aer-item">
        <div class="flex items-start justify-between gap-2">
          <div class="flex items-center gap-2 min-w-0">
            <span class="shrink-0 rounded-md bg-wa-teal/15 text-wa-teal p-1.5"><${CalendarIcon} /></span>
            <div class="font-medium text-wa-text truncate">${fmtDateTime(it.due_at)}</div>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <${OrigemBadge} it=${it} />
            <${StatusBadge} status=${it.status} />
            ${it.status === 'agendado' ? html`
              <button type="button" title="Cancelar" aria-label="Cancelar" onClick=${() => cancelItem(it.id)}
                class="text-wa-secondary hover:text-wa-text text-[12px] underline">cancelar</button>` : null}
            <button type="button" title="Excluir" aria-label="Excluir" onClick=${() => setConfirmId(it.id)}
              class="text-red-600 hover:opacity-80"><${TrashIcon} /></button>
          </div>
        </div>
        ${descOf(it) ? html`<div class="text-sm text-wa-secondary mt-2" style="white-space:pre-wrap">${descOf(it)}</div>` : null}
        ${out ? html`<div class=${`text-xs mt-1 ${out.cls}`}>${out.txt}</div>` : null}
        ${it.status === 'falhou' && it.last_error ? html`<div class="text-xs text-red-600 mt-1">${it.last_error}</div>` : null}
      </div>`;
  }

  function agendarTab() {
    return html`
      <div class="aer-grid">
        <section class="aer-card">
          <h3 class="text-wa-teal font-semibold mb-3">Novo agendamento</h3>
          <form onSubmit=${submit} class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-wa-text mb-1">Nome do Cliente</label>
              <div class="relative">
                <input class=${fieldCls} placeholder="Buscar cliente por nome ou número" autocomplete="off"
                  value=${query} onInput=${onClientInput}
                  onFocus=${() => { if (results.length) setShowResults(true); }}
                  onBlur=${() => { clearTimeout(blurTimer.current); blurTimer.current = setTimeout(() => setShowResults(false), 150); }} />
                ${showResults && results.length > 0 && html`
                  <ul class="absolute mt-1 w-full max-h-56 overflow-auto rounded-lg border border-wa-border bg-wa-panel shadow-lg" style="z-index:10;list-style:none;padding:0;margin:4px 0 0">
                    ${results.map((c) => html`
                      <li key=${c.id}>
                        <button type="button" onMouseDown=${(ev) => ev.preventDefault()} onClick=${() => pickContact(c)}
                          class="w-full text-left px-3 py-2 text-sm hover:bg-wa-hover flex justify-between gap-2">
                          <span class="text-wa-text truncate">${c.name || c.phone}</span>
                          <span class="text-wa-secondary text-xs shrink-0">${c.phone}</span>
                        </button>
                      </li>`)}
                  </ul>`}
              </div>
              ${picked
                ? html`<p class="text-xs text-wa-teal mt-1">Selecionado: ${picked.name} · ${picked.phone}</p>`
                : html`<p class="text-xs text-amber-600 mt-1">Busque e selecione o cliente (nome ou número).</p>`}
            </div>

            <div class="aer-row2">
              <div>
                <label class="block text-sm font-medium text-wa-text mb-1">Data</label>
                <input type="date" class=${fieldCls} min=${todayLocal()} value=${dueDate}
                  onInput=${(e) => setDueDate(e.target.value)} />
              </div>
              <div>
                <label class="block text-sm font-medium text-wa-text mb-1">Hora</label>
                <input type="time" class=${fieldCls} value=${dueTime} onInput=${(e) => setDueTime(e.target.value)} />
              </div>
            </div>

            <div>
              <label class="block text-sm font-medium text-wa-text mb-1">Descrição (opcional)</label>
              <textarea rows="3" maxlength="500" class=${fieldCls} style="resize:vertical"
                placeholder="Breve descrição sobre o retorno"
                value=${description} onInput=${(e) => setDescription(e.target.value)}></textarea>
            </div>

            ${formMsg && html`<div class=${formMsg.type === 'ok' ? 'text-sm text-green-600' : 'text-sm text-red-600'}>${formMsg.text}</div>`}

            <div class="flex gap-3">
              <button type="submit" disabled=${saving}
                class="flex-1 px-4 py-2.5 rounded-lg bg-wa-teal text-white font-medium disabled:opacity-50 transition-colors flex items-center justify-center gap-2">
                <${CalendarIcon} /> ${saving ? 'Agendando…' : 'Agendar Retorno'}
              </button>
              <button type="button" onClick=${clearForm}
                class="flex-1 px-4 py-2.5 rounded-lg bg-wa-hover text-wa-text font-medium transition-colors flex items-center justify-center gap-2">
                <${TrashIcon} /> Limpar
              </button>
            </div>
          </form>
        </section>

        <section class="aer-card">
          <h3 class="text-wa-teal font-semibold mb-3">
            ${picked ? `Próximos agendamentos de ${picked.name}` : 'Próximos agendamentos'}
          </h3>
          ${loadErr && html`<div class="text-red-600 text-sm mb-2">Erro: ${loadErr}</div>`}
          ${!picked
            ? html`<div class="text-wa-secondary text-sm py-4">Selecione um cliente para ver os agendamentos dele.</div>`
            : clientItems.length === 0
              ? html`<div class="text-wa-secondary text-sm py-4">Nenhum agendamento para este cliente.</div>`
              : html`<div class="space-y-2 overflow-y-auto" style="max-height:26rem">${clientItems.map(card)}</div>`}
        </section>
      </div>`;
  }

  function listaTab() {
    const filtered = items.filter((it) => {
      if (fStatus === 'ativos') { if (it.status !== 'agendado') return false; }
      else if (fStatus !== 'todos' && it.status !== fStatus) return false;
      if (fOrigem === 'ia' && !it.created_by_ia) return false;
      if (fOrigem === 'humano' && it.created_by_ia) return false;
      return true;
    });
    const th = 'text-left px-3 py-2';
    return html`
      <div class="p-5 space-y-3">
        <div class="flex flex-wrap items-center gap-3">
          <span class="text-wa-teal font-semibold mr-auto">Filtros</span>
          <label class="text-sm text-wa-secondary flex items-center gap-1">Status:
            <select class="wa-field rounded px-2 py-1" value=${fStatus} onChange=${(e) => setFStatus(e.target.value)}>
              ${STATUS_FILTERS.map(([v, l]) => html`<option value=${v}>${l}</option>`)}
            </select>
          </label>
          <label class="text-sm text-wa-secondary flex items-center gap-1">Origem:
            <select class="wa-field rounded px-2 py-1" value=${fOrigem} onChange=${(e) => setFOrigem(e.target.value)}>
              ${ORIGEM_FILTERS.map(([v, l]) => html`<option value=${v}>${l}</option>`)}
            </select>
          </label>
          <button type="button" title="Recarregar" aria-label="Recarregar" onClick=${load} class="text-wa-teal hover:opacity-80">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M17.65 6.35A8 8 0 1 0 19.73 14h-2.08A6 6 0 1 1 12 6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>
          </button>
        </div>
        ${loadErr && html`<div class="text-red-600 text-sm">Erro: ${loadErr}</div>`}
        <div class="aer-scroll">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-wa-teal text-white whitespace-nowrap">
                <th class=${th} style="border-radius:6px 0 0 6px">Data e Hora</th>
                <th class=${th}>Nome Cliente</th>
                <th class=${th}>Origem</th>
                <th class=${th}>Descrição</th>
                <th class=${th}>Status</th>
                <th class="px-3 py-2 text-center">Conversa</th>
                <th class="px-3 py-2 text-center" style="border-radius:0 6px 6px 0">Ações</th>
              </tr>
            </thead>
            <tbody>
              ${filtered.length === 0
                ? html`<tr><td colspan="7" class="text-center italic text-wa-secondary py-6">Não há agendamentos disponíveis com os filtros aplicados.</td></tr>`
                : filtered.map((it) => { const out = outcomeOf(it); return html`
                  <tr key=${it.id} class="border-b border-wa-border">
                    <td class="px-3 py-2 text-wa-text whitespace-nowrap">${fmtDateTime(it.due_at)}</td>
                    <td class="px-3 py-2 text-wa-text whitespace-nowrap">${it.contact_name || it.phone}</td>
                    <td class="px-3 py-2 whitespace-nowrap"><${OrigemBadge} it=${it} /></td>
                    <td class="px-3 py-2 text-wa-secondary truncate" style="max-width:22rem" title=${descOf(it)}>${descOf(it) || '—'}</td>
                    <td class="px-3 py-2 whitespace-nowrap">
                      <${StatusBadge} status=${it.status} />
                      ${out ? html`<div class=${`text-[11px] mt-0.5 ${out.cls}`}>${out.txt}</div>` : null}
                    </td>
                    <td class="px-3 py-2 text-center">
                      <button type="button" title="Abrir conversa" aria-label="Abrir conversa"
                        onClick=${() => goToConversation(it, onClose)} class="text-wa-teal hover:opacity-80"><${ChatIcon} /></button>
                    </td>
                    <td class="px-3 py-2 text-center whitespace-nowrap">
                      ${it.status === 'agendado' ? html`
                        <button type="button" title="Cancelar" aria-label="Cancelar" onClick=${() => cancelItem(it.id)}
                          class="text-wa-secondary hover:text-wa-text text-[12px] underline mr-2">cancelar</button>` : null}
                      <button type="button" title="Excluir" aria-label="Excluir" onClick=${() => setConfirmId(it.id)}
                        class="text-red-600 hover:opacity-80"><${TrashIcon} /></button>
                    </td>
                  </tr>`; })}
            </tbody>
          </table>
        </div>
      </div>`;
  }

  return html`
    <div class="aer-overlay" role="dialog" aria-modal="true" aria-label="Agendar retorno">
      <div class="aer-dialog">
        <div class="bg-wa-panel text-wa-text rounded-xl border border-wa-border shadow-sm overflow-hidden">
          <div class="flex items-center gap-3 px-5 pt-4">
            <h2 class="text-lg font-semibold text-wa-text mr-auto">Agendar retorno</h2>
            <button type="button" onClick=${onClose} class="text-wa-secondary hover:text-wa-text" aria-label="Fechar" title="Fechar">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
            </button>
          </div>
          <div class="aer-tabs" role="tablist">
            ${tabBtn('agendar', 'Agendar Retorno')}
            ${tabBtn('lista', 'Lista de Agendamentos')}
          </div>
          ${tab === 'agendar' ? agendarTab() : listaTab()}
        </div>
      </div>

      ${confirmId != null && html`
        <div class="aer-confirm" onClick=${() => setConfirmId(null)}>
          <div class="bg-wa-panel text-wa-text rounded-xl border border-wa-border shadow-lg w-full p-5" style="max-width:24rem" onClick=${(e) => e.stopPropagation()}>
            <h4 class="font-semibold text-wa-text mb-2">Excluir agendamento</h4>
            <p class="text-sm text-wa-secondary mb-4">Tem certeza que deseja excluir este agendamento? Esta ação não pode ser desfeita.</p>
            <div class="flex justify-end gap-2">
              <button type="button" onClick=${() => setConfirmId(null)} class="px-3 py-1.5 rounded-lg bg-wa-hover text-wa-text text-sm">Cancelar</button>
              <button type="button" onClick=${() => { const id = confirmId; setConfirmId(null); removeItem(id); }}
                class="px-3 py-1.5 rounded-lg bg-red-600 text-white text-sm">Excluir</button>
            </div>
          </div>
        </div>`}
    </div>`;
}

export default ScheduleModal;
