/**
 * "Keys" page (providers): any server with an OpenAI-compatible API
 * (POST {base_url}/chat/completions). Add as many of your own as you like.
 */
import { api } from '../api.js';
import { COLORS, ICONS, PROVIDER_PRESETS, iconUrl, newProvider } from '../catalog.js';
import { clone, html, refs, sameJSON, syncList, uid } from '../dom.js';
import { t } from '../i18n.js';
import { confirmDialog, toast, toastError, withBusy } from '../ui.js';

const STATUS_KIND = { ok: 'ok', new: 'wait', bad: 'bad' };
const STATUS_LABEL = { ok: 'connected', new: 'not checked', bad: 'no connection' };
/** [stamp kind, label] for a provider status */
const statusOf = status => (STATUS_KIND[status] ? [STATUS_KIND[status], t(STATUS_LABEL[status])] : ['wait', t('not checked')]);
const JSON_FIELDS = { extra_body: 'Extra request parameters', headers: 'Extra headers' };

const template = () => html`
  <header class="section-head">
    <h2><span>${t('Keys and providers')}</span></h2><span class="spacer"></span>
    <button class="btn btn--small" data-ref="save" type="button">${t('saved ✓')}</button>
  </header>
  <div class="split">
    <div>
      <div class="provider-list sheet sheet--torn" data-ref="list"></div>
      <div class="provider-add">
        <button class="btn btn--big" data-ref="addCustom" type="button">${t('+ OpenAI-compatible')}</button>
        <p class="hint">${t('any server with an OpenAI API: your own proxy, vLLM, LM Studio, Ollama…')}</p>
        <div class="chips" data-ref="presets">${PROVIDER_PRESETS.map((p, i) => html`
          <button class="chip chip--add" type="button" data-preset="${i}">+ ${p.name}</button>`)}
        </div>
      </div>
    </div>
    <section class="sheet sheet--lined sheet--tilt-r editor paper-grain" data-ref="editor" aria-label="${t('Provider settings')}"></section>
  </div>`;

const rowTemplate = () => html`
  <button class="provider-row" type="button">
    <span class="avatar"><img alt=""></span>
    <span class="provider-row__text"><b></b><small class="mono"></small></span>
    <span class="provider-row__state stamp"></span>
  </button>`;

const shortUrl = url => (url || t('no address')).replace(/^https?:\/\//, '');
const prettyJSON = obj => (obj && Object.keys(obj).length ? JSON.stringify(obj, null, 2) : '');

export default {
  id: 'providers', icon: '🔑',
  get title() { return t('Keys'); },
  get short() { return t('Keys'); },

  async mount(root, { signal }) {
    root.innerHTML = String(template());
    const r = refs(root);
    const on = (el, type, fn) => el.addEventListener(type, fn, { signal });

    let saved = [];
    let draft = [];
    let currentId = null;
    let found = [];                  // models the server returned during the check
    const jsonErrors = new Set();    // `${id}:${field}`: fields with invalid JSON
    const current = () => draft.find(p => p.id === currentId);
    const isDirty = () => !sameJSON(saved, draft);

    // ---------- list ----------
    function updateRow(node, p) {
      const [kind, label] = statusOf(p.status);
      node.style.setProperty('--accent', p.color);
      node.querySelector('img').src = iconUrl(p.icon);
      node.querySelector('b').textContent = p.name || t('No name');
      node.querySelector('small').textContent = shortUrl(p.base_url);
      const st = node.querySelector('.provider-row__state');
      st.className = `provider-row__state stamp stamp--${kind}`;
      st.textContent = `${label} · ${t('{n} models', { n: p.models.length })}`;
      node.classList.toggle('is-selected', p.id === currentId);
    }

    function renderList() {
      syncList(r.list, draft, {
        key: p => p.id, render: rowTemplate, update: updateRow,
        empty: html`<div class="empty">${t('No providers yet — add the first one below')}</div>`,
      });
      r.save.textContent = isDirty() ? t('save *') : t('saved ✓');
      r.save.disabled = !isDirty() || jsonErrors.size > 0;
      r.save.classList.toggle('btn--primary', isDirty());
    }

    on(r.list, 'click', e => {
      const row = e.target.closest('.provider-row');
      if (row) select(row.dataset.key, true);
    });

    function select(id, scroll = false) {
      currentId = id;
      found = [];
      renderList();
      renderEditor();
      if (scroll && matchMedia('(max-width: 900px)').matches) r.editor.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function add(preset) {
      const p = newProvider(uid('p'), preset);
      draft.push(p);
      select(p.id, true);
      r.editor.querySelector(preset ? '[name="api_key"]' : '[name="base_url"]')?.focus();
    }
    on(r.addCustom, 'click', () => add(null));
    on(r.presets, 'click', e => {
      const chip = e.target.closest('[data-preset]');
      if (chip) add(PROVIDER_PRESETS[Number(chip.dataset.preset)]);
    });

    // ---------- editor ----------
    function modelChips(p) {
      return html`${p.models.map(m => html`
        <span class="chip">${m}<button class="chip-x" type="button" data-remove-model="${m}" aria-label="${t('Remove {m}', { m })}">×</button></span>`)}`;
    }
    function foundChips(p) {
      const fresh = found.filter(m => !p.models.includes(m)).slice(0, 120);
      return fresh.length ? html`<p class="hint">${t('Found on the server — click to add:')}</p>
        <div class="chips">${fresh.map(m => html`<button class="chip chip--add" type="button" data-add-model="${m}">+ ${m}</button>`)}</div>` : '';
    }
    function renderModels() {
      const p = current();
      r.models.innerHTML = String(modelChips(p));
      r.found.innerHTML = String(foundChips(p));
    }

    function renderEditor() {
      const p = current();
      if (!p) {
        r.editor.innerHTML = String(html`<div class="empty">${t('Pick a provider or add a new one')}</div>`);
        return;
      }
      const [kind, label] = statusOf(p.status);
      const local = /localhost|127\.0\.0\.1/.test(p.base_url);
      r.editor.innerHTML = String(html`
        <div class="tape"></div>
        <form class="form" autocomplete="off">
          <div class="editor-title">
            <span class="avatar" style="--accent:${p.color}"><img src="${iconUrl(p.icon)}" alt="" data-ref="icon"></span>
            <input class="input editor-title__name" name="name" value="${p.name}" aria-label="${t('Name')}">
            <span class="stamp stamp--${kind}" data-ref="status">${label}</span>
          </div>

          <div class="field">
            <label for="prov-url">Base URL</label>
            <input class="input mono" id="prov-url" name="base_url" value="${p.base_url}" placeholder="https://example.com/v1" inputmode="url">
            <small>${t('the address before /chat/completions, usually ends with /v1')}</small>
          </div>

          <div class="field">
            <label for="prov-key">${t('API key')}</label>
            <div class="input-group">
              <input class="input mono" id="prov-key" name="api_key" type="password" value="${p.api_key}" placeholder="${local ? t('not needed for a local server') : 'sk-…'}" autocomplete="off">
              <button class="link-btn link-btn--plain" type="button" data-action="toggle-key">${t('show')}</button>
            </div>
            <small>${t('stored only on this device, in config/providers.json')}</small>
          </div>

          <div class="field">
            <div class="field-row"><span class="label">${t('Models')}</span><span class="spacer"></span>
              <button class="link-btn" type="button" data-action="test">${t('check and load the list')}</button></div>
            <p class="status-line" data-ref="testResult">${p.status === 'ok' ? t('✓ last check: {ms} ms', { ms: p.last_ms }) : ''}</p>
            <div class="chips" data-ref="models"></div>
            <input class="input mono model-add" name="new_model" placeholder="${t('+ your own model and Enter')}">
            <div data-ref="found"></div>
          </div>

          <details class="more">
            <summary class="label">${t('Advanced')}</summary>
            <div class="grid-2">
              <div class="field"><label for="prov-timeout">${t('Timeout, s')}</label><input class="input" id="prov-timeout" name="timeout" type="number" min="1" value="${p.timeout}"></div>
              <div class="field"><label for="prov-max">${t('Max tokens')}</label><input class="input" id="prov-max" name="max_tokens" type="number" min="0" value="${p.max_tokens}"><small>${t('0 — take from the prompt')}</small></div>
            </div>
            <label class="check"><input type="checkbox" name="stream" ${p.stream ? 'checked' : ''}><i></i><span>${t('Streaming')}<small>${t('cut the answer at the first line — faster')}</small></span></label>
            <label class="check"><input type="checkbox" name="retry" ${p.retry ? 'checked' : ''}><i></i><span>${t('Retry on error')}<small>${t('up to 2 times on a network failure or 429')}</small></span></label>
            ${Object.entries(JSON_FIELDS).map(([field, title]) => html`
              <div class="field"><label for="prov-${field}">${t(title)} (JSON)</label>
                <textarea class="input mono" id="prov-${field}" name="${field}" rows="3" placeholder="${field === 'headers' ? '{"HTTP-Referer": "http://localhost"}' : '{"reasoning_effort": "minimal"}'}">${prettyJSON(p[field])}</textarea>
                <small class="field-error" data-error="${field}"></small></div>`)}
            <fieldset class="field"><legend class="label">${t('Icon')}</legend>
              <div class="icon-pick">${ICONS.map(icon => html`
                <label title="${icon}"><input type="radio" name="icon" value="${icon}" ${icon === p.icon ? 'checked' : ''}><img src="${iconUrl(icon)}" alt="${icon}"></label>`)}</div></fieldset>
            <fieldset class="field"><legend class="label">${t('Color')}</legend>
              <div class="swatches">${COLORS.map(c => html`
                <label class="swatch" style="--swatch:${c}"><input type="radio" name="color" value="${c}" ${c === p.color ? 'checked' : ''}><i></i></label>`)}</div></fieldset>
          </details>

          <div class="form-actions">
            <span class="spacer"></span>
            <button class="link-btn link-btn--danger link-btn--plain" type="button" data-action="delete">${t('delete provider')}</button>
          </div>
        </form>`);
      Object.assign(r, refs(r.editor));
      renderModels();
    }

    function applyField(input) {
      const p = current();
      const { name } = input;
      if (!p || !name || name === 'new_model') return;
      if (name in JSON_FIELDS) {
        const key = `${p.id}:${name}`;
        const errorEl = r.editor.querySelector(`[data-error="${name}"]`);
        try {
          const value = input.value.trim() ? JSON.parse(input.value) : {};
          if (typeof value !== 'object' || Array.isArray(value) || value === null) throw new Error(t('an object { … } is needed'));
          p[name] = value;
          jsonErrors.delete(key);
          errorEl.textContent = '';
        } catch (error) {
          jsonErrors.add(key);
          errorEl.textContent = t('Invalid JSON: {e}', { e: error.message });
        }
      } else if (name === 'stream' || name === 'retry') p[name] = input.checked;
      else if (name === 'timeout') p.timeout = Number(input.value) || 15;
      else if (name === 'max_tokens') p.max_tokens = Number(input.value) || 0;
      else if (name === 'base_url') p.base_url = input.value.trim().replace(/\/+$/, '');
      else if (name === 'icon') { p.icon = input.value; r.icon.src = iconUrl(p.icon); }
      else if (name === 'color') { p.color = input.value; r.icon.parentElement.style.setProperty('--accent', p.color); }
      else p[name] = input.value.trim();
      renderList();
    }
    on(r.editor, 'input', e => applyField(e.target));
    on(r.editor, 'change', e => applyField(e.target));
    on(r.editor, 'submit', e => e.preventDefault());

    on(r.editor, 'keydown', e => {
      if (e.target.name !== 'new_model' || e.key !== 'Enter') return;
      e.preventDefault();
      addModel(e.target.value.trim());
      e.target.value = '';
    });

    function addModel(model) {
      const p = current();
      if (!model || p.models.includes(model)) return;
      p.models.push(model);
      renderModels(); renderList();
    }

    on(r.editor, 'click', e => {
      const target = e.target.closest('button');
      if (!target) return;
      if (target.dataset.addModel) addModel(target.dataset.addModel);
      if (target.dataset.removeModel) {
        current().models = current().models.filter(m => m !== target.dataset.removeModel);
        renderModels(); renderList();
      }
      const action = target.dataset.action;
      if (action === 'toggle-key') {
        const key = r.editor.querySelector('[name="api_key"]');
        key.type = key.type === 'password' ? 'text' : 'password';
        target.textContent = key.type === 'password' ? t('show') : t('hide');
      }
      if (action === 'test') withBusy(target, testConnection);
      if (action === 'delete') removeCurrent();
    });

    async function testConnection() {
      const p = current();
      if (!p.base_url) { toast(t('Enter the Base URL first'), 'bad'); return; }
      r.testResult.className = 'status-line';
      r.testResult.textContent = t('knocking…');
      const res = await api.testProvider(p.id, p);
      p.status = res.ok ? 'ok' : 'bad';
      p.last_ms = res.ms || 0;
      // the server has already saved the check status itself; sync it so it doesn't count as an "edit"
      const stored = saved.find(x => x.id === p.id);
      if (stored) Object.assign(stored, { status: p.status, last_ms: p.last_ms });
      const [kind, label] = statusOf(p.status);
      r.status.className = `stamp stamp--${kind}`;
      r.status.textContent = label;
      if (res.ok) {
        found = res.models;
        r.testResult.className = 'status-line is-ok';
        r.testResult.textContent = t('✓ answered in {ms} ms · models on the server: {n}', { ms: res.ms, n: res.models.length });
      } else {
        r.testResult.className = 'status-line is-bad';
        r.testResult.textContent = t('Error: {e}', { e: res.error });
      }
      renderModels(); renderList();
    }

    async function removeCurrent() {
      const p = current();
      if (!(await confirmDialog({ text: t('Delete the provider “{name}”? Bots using it will stop answering.', { name: p.name }), ok: t('Delete'), danger: true }))) return;
      draft = draft.filter(x => x.id !== p.id);
      if (saved.some(x => x.id === p.id)) saved = await api.saveProviders(saved.filter(x => x.id !== p.id));
      select(draft[0]?.id ?? null);
      toast(t('Provider deleted'));
    }

    on(r.save, 'click', () => withBusy(r.save, async () => {
      if (jsonErrors.size) { toast(t('Fix the JSON in the advanced settings'), 'bad'); return; }
      saved = await api.saveProviders(draft);
      draft = clone(saved);
      renderList();
      toast(t('Saved'), 'ok');
    }));

    // ---------- start ----------
    try {
      saved = await api.providers();
    } catch (error) {
      toastError(error);
      return null;
    }
    if (signal.aborted) return null;
    draft = clone(saved);
    select(draft[0]?.id ?? null);

    return {
      canLeave: async () => !isDirty() || confirmDialog({ text: t('There are unsaved provider changes. Leave without saving?'), ok: t('Leave'), danger: true }),
    };
  },
};
