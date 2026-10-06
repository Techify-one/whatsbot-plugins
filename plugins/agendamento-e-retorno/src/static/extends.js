// Extensão de frontend (frontend_extends): o painel importa este arquivo UMA vez no boot e
// chama register(api). Adiciona o botão "Agendar" (ícone de calendário) na barra do contato,
// dentro da conversa (slot chat.header.actions). Ao clicar, abre o modal "Agendar retorno"
// já com o contato da conversa selecionado. Aditivo: desabilitar o plugin remove o botão no
// próximo boot; o core fica idêntico.
import { h, render } from 'preact';
import htm from 'htm';
import { ScheduleModal } from '/plugins/agendamento_e_retorno/static/ScheduleModal.js';

const html = htm.bind(h);

let _open = false; // um modal por vez (duplo clique no botão não empilha dois)

function openModal(scope) {
  if (_open) return;
  _open = true;
  const host = document.createElement('div');
  document.body.appendChild(host);
  const close = () => { render(null, host); host.remove(); _open = false; };
  // Só o "X" fecha (como no Pro): clicar fora não pode jogar fora o que foi digitado.
  render(html`<${ScheduleModal} scope=${scope} onClose=${close} />`, host);
}

function AgendarButton({ phone, contact, info, isGroup }) {
  if (!phone) return null;
  const name = isGroup
    ? ((contact && contact.group_name) || phone)
    : ((info && info.name) || phone);

  return html`
    <button type="button" title="Agendar retorno" aria-label="Agendar retorno"
      onClick=${() => openModal({ phone, name, contactId: contact && contact.id })}
      class="px-2 py-1 rounded-md text-wa-secondary hover:text-wa-teal hover:bg-wa-hover transition-colors flex items-center gap-1">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zm0-12H5V6h14v2zm-7 5h5v5h-5v-5z"/></svg>
      <span class="hidden sm:inline text-[12px]">Agendar</span>
    </button>`;
}

export default function register(api) {
  api.addSlot('chat.header.actions', AgendarButton);
}
