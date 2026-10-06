// Tela de configuração do plugin (modal "Configurar" em Gerenciar Plugins), com 2 abas:
// "Agendamento" e "Retorno automático". Os campos vêm do JSON Schema de settings.py — cada
// um traz `group` ("agendamento" | "auto"), e é isso que decide a aba. Os dias da semana
// (`widget: "weekday"`) viram uma linha de checkboxes em vez de sete campos soltos.
// Visual igual ao formulário padrão de settings (título, descrição, campo).
import { h } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import htm from 'htm';
import { authHeaders, handleUnauthorized } from '/static/js/services/api.js';

const html = htm.bind(h);

const TABS = [
  { id: 'agendamento', label: 'Agendamento' },
  { id: 'auto', label: 'Retorno automático' },
];

const baseCls = 'w-full wa-field border border-wa-border rounded px-3 py-2 text-[14px] focus:outline-none focus:border-wa-teal';

async function api(url, init = {}) {
  const res = await fetch(url, { ...init, headers: authHeaders(init.headers || {}) });
  if (res.status === 401) { handleUnauthorized(); throw new Error('Não autenticado.'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) throw new Error(data.error || `Erro ${res.status}`);
  return data.data;
}

function Field({ prop, value, onChange }) {
  if (prop.type === 'boolean') {
    return html`
      <label class="inline-flex items-center gap-2">
        <input type="checkbox" checked=${!!value} onChange=${(e) => onChange(e.target.checked)} />
        <span class="text-[14px] text-wa-secondary">${value ? 'Ativado' : 'Desativado'}</span>
      </label>`;
  }
  if (prop.type === 'integer' || prop.type === 'number') {
    const int = prop.type === 'integer';
    return html`
      <input type="number" step=${int ? '1' : 'any'} class=${baseCls} value=${value ?? ''}
        min=${prop.minimum ?? undefined} max=${prop.maximum ?? undefined}
        onInput=${(e) => {
          const v = e.target.value;
          onChange(v === '' ? null : (int ? parseInt(v, 10) : parseFloat(v)));
        }} />`;
  }
  const long = (prop.description || '').length > 120 || String(value || '').length > 60;
  return long
    ? html`<textarea class=${baseCls + ' font-mono'} rows="4" value=${value ?? ''}
        onInput=${(e) => onChange(e.target.value)}></textarea>`
    : html`<input type="text" class=${baseCls} value=${value ?? ''}
        onInput=${(e) => onChange(e.target.value)} />`;
}

function FieldBlock({ name, prop, values, setValue }) {
  return html`
    <div key=${name}>
      <label class="block text-[14px] font-medium text-wa-text mb-1">${prop.title || name}</label>
      ${prop.description ? html`<div class="text-[12px] text-wa-secondary mb-1.5">${prop.description}</div>` : null}
      <${Field} prop=${prop} value=${values[name]} onChange=${(v) => setValue(name, v)} />
    </div>`;
}

function WeekdayRow({ days, values, setValue }) {
  return html`
    <div>
      <label class="block text-[14px] font-medium text-wa-text mb-1">Dias do expediente</label>
      <div class="text-[12px] text-wa-secondary mb-1.5">Notas só são postadas nos dias marcados.</div>
      <div style="display:flex;flex-wrap:wrap;gap:6px 16px">
        ${days.map(([name, prop]) => html`
          <label key=${name} class="inline-flex items-center gap-1.5 text-[14px] text-wa-text">
            <input type="checkbox" checked=${!!values[name]} onChange=${(e) => setValue(name, e.target.checked)} />
            ${prop.title}
          </label>`)}
      </div>
    </div>`;
}

export default function AgendamentoERetornoConfig({ apiBase = '/api/plugins/agendamento_e_retorno' } = {}) {
  const [tab, setTab] = useState('agendamento');
  const [schema, setSchema] = useState(null);
  const [values, setValues] = useState({});
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [feedback, setFeedback] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const d = await api(`${apiBase}/settings`);
        if (!alive) return;
        setSchema(d.schema);
        setValues(d.values || {});
        api(`${apiBase}/status`).then((s) => alive && setStatus(s)).catch(() => {});
      } catch (e) {
        if (alive) setError(String(e.message || e));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [apiBase]);

  function setValue(name, v) {
    setFeedback(null);
    setValues((prev) => ({ ...prev, [name]: v }));
  }

  async function save() {
    setSaving(true); setError(null); setFeedback(null);
    try {
      const d = await api(`${apiBase}/settings`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values),
      });
      setValues(d.values || values);
      setFeedback('Configurações salvas.');
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return html`<div class="text-wa-secondary">Carregando…</div>`;
  if (!schema) return html`<div class="text-red-600">${error || 'Sem schema disponível.'}</div>`;

  const props = Object.entries(schema.properties || {});
  const inTab = props.filter(([, p]) => p.group === tab);
  const days = inTab.filter(([, p]) => p.widget === 'weekday');
  const regular = inTab.filter(([, p]) => p.widget !== 'weekday');
  // Os dias entram logo depois do "Fim do expediente", que é onde fazem sentido.
  const endIdx = regular.findIndex(([n]) => n === 'auto_business_end');

  const blocks = regular.map(([name, prop]) => html`<${FieldBlock} name=${name} prop=${prop} values=${values} setValue=${setValue} />`);
  if (days.length) blocks.splice(endIdx >= 0 ? endIdx + 1 : blocks.length, 0,
    html`<${WeekdayRow} days=${days} values=${values} setValue=${setValue} />`);

  const tabCls = (id) => `flex-1 px-4 py-2.5 text-[14px] font-medium border-b-2 ${
    tab === id ? 'border-wa-teal text-wa-teal' : 'border-transparent text-wa-secondary hover:text-wa-text'}`;

  return html`
    <div class="space-y-4">
      ${status && status.auto_paused ? html`
        <div class="text-[13px] rounded p-3" style="background:rgba(245,158,11,.15);color:inherit;border:1px solid rgba(245,158,11,.5)">
          <strong>Retorno automático pausado.</strong> O plugin antigo “Retorno Automático (IA)” ainda está
          habilitado e varre os mesmos contatos — rodar os dois duplicaria a nota e a resposta da IA.
          Desabilite o antigo em <em>Gerenciar Plugins</em> para este assumir.
        </div>` : null}

      <div class="flex border-b border-wa-border" role="tablist">
        ${TABS.map((t) => html`
          <button key=${t.id} type="button" role="tab" aria-selected=${tab === t.id}
            class=${tabCls(t.id)} onClick=${() => setTab(t.id)}>${t.label}</button>`)}
      </div>

      ${blocks}

      ${error ? html`<div class="text-red-600 text-sm">${error}</div>` : null}
      ${feedback ? html`<div class="text-green-700 text-sm">${feedback}</div>` : null}

      <div class="flex gap-2">
        <button type="button" onClick=${save} disabled=${saving}
          class="px-4 py-2 bg-wa-teal text-white rounded text-[14px] disabled:opacity-50">${saving ? 'Salvando…' : 'Salvar'}</button>
      </div>
    </div>`;
}
