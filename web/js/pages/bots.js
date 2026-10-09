/**
 * Страница «Боты»: карточки ботов слева, редактор выбранного справа.
 *
 * Правки копятся в черновике `draft` и уходят на сервер кнопкой «Сохранить».
 * Карточки обновляются на лету (syncList + update), поэтому ничего не мигает.
 */
import { api } from '../api.js';
import { COLORS, GAMES, providerIcon, secs } from '../catalog.js';
import { clone, html, refs, sameJSON, syncList, tilt, uid } from '../dom.js';
import { t } from '../i18n.js';
import { confirmDialog, toast, toastError, withBusy } from '../ui.js';

const NEW_CARD = { id: '__new' };
// пример задания из app/prompts.py (SAMPLES) — на языке версии игры, которой ответил сервер
const SAMPLE_TASK = { en: 'The worst thing to say on a first date', ru: 'Худшее, что можно сказать на первом свидании' };

function newBot(index, providers) {
  const provider = providers.find(p => p.models.length) || providers[0];
  return {
    id: uid('b'), name: t('Rookie'), color: COLORS[index % COLORS.length],
    provider: provider?.id || '', model: provider?.models[0] || '',
    persona: t('an ordinary player with a sense of humor'), temperature: 1, enabled: true, vision: false,
    games: Object.fromEntries(GAMES.map(g => [g.tag, true])),
  };
}

const template = () => html`
  <header class="section-head">
    <h2><span>${t('Bots')}</span></h2><span class="hint">${t('who goes on stage')}</span><span class="spacer"></span>
    <button class="btn btn--small" data-ref="save" type="button">${t('saved ✓')}</button>
  </header>
  <div class="split">
    <div class="bot-cards" data-ref="cards"></div>
    <section class="sheet sheet--lined sheet--tilt-r editor paper-grain" data-ref="editor" aria-label="${t('Bot settings')}"></section>
  </div>`;

const cardTemplate = () => html`
  <button class="bot-card" type="button">
    <span class="avatar"><img alt=""></span>
    <b class="bot-card__name"></b>
    <small class="bot-card__model"></small>
    <span class="bot-card__persona"></span>
    <span class="stamp stamp--bad bot-card__off">${t('off')}</span>
  </button>`;

const newCardTemplate = () => html`<button class="bot-card bot-card--new" type="button"><b>${t('+ new bot')}</b></button>`;

export default {
  id: 'bots', icon: '🤖',
  get title() { return t('Bots'); },
  get short() { return t('Bots'); },

  async mount(root, { params, signal, replaceHash }) {
    root.innerHTML = String(template());
    const r = refs(root);
    const on = (el, type, fn) => el.addEventListener(type, fn, { signal });

    let saved = [];
    let draft = [];
    let providers = [];
    let currentId = null;
    const current = () => draft.find(b => b.id === currentId);
    const isDirty = () => !sameJSON(saved, draft);

    // ---------- карточки ----------
    function updateCard(node, bot) {
      if (bot === NEW_CARD) return;
      node.style.setProperty('--accent', bot.color);
      node.style.setProperty('--tilt', `${tilt(bot.id, 1.5)}deg`);
      node.querySelector('img').src = providerIcon(providers, bot.provider);
      node.querySelector('.bot-card__name').textContent = bot.name || t('No name');
      node.querySelector('.bot-card__model').textContent = bot.model || t('no model selected');
      node.querySelector('.bot-card__persona').textContent = bot.persona;
      node.classList.toggle('is-selected', bot.id === currentId);
      node.classList.toggle('is-off', !bot.enabled);
    }

    function renderCards() {
      syncList(r.cards, [...draft, NEW_CARD], {
        key: b => b.id,
        render: b => (b === NEW_CARD ? newCardTemplate() : cardTemplate()),
        update: updateCard,
      });
      r.save.textContent = isDirty() ? t('save *') : t('saved ✓');
      r.save.disabled = !isDirty();
      r.save.classList.toggle('btn--primary', isDirty());
    }

    on(r.cards, 'click', e => {
      const card = e.target.closest('.bot-card');
      if (!card) return;
      if (card.dataset.key === NEW_CARD.id) addBot();
      else select(card.dataset.key, true);
    });

    function select(id, scroll = false) {
      currentId = id;
      renderCards();
      renderEditor();
      if (scroll && matchMedia('(max-width: 900px)').matches) r.editor.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function addBot() {
      const bot = newBot(draft.length, providers);
      draft.push(bot);
      select(bot.id, true);
      r.editor.querySelector('[name="name"]')?.select();
    }

    // ---------- редактор ----------
    function modelOptions(bot) {
      const p = providers.find(x => x.id === bot.provider);
      return [...new Set([...(p?.models || []), bot.model].filter(Boolean))];
    }

    function renderEditor() {
      const bot = current();
      if (!bot) {
        r.editor.innerHTML = String(html`<div class="empty">${t('Pick a bot on the left or create a new one')}</div>`);
        return;
      }
      r.editor.innerHTML = String(html`
        <div class="tape"></div>
        <form class="form" data-ref="form" autocomplete="off">
          <div class="field">
            <label for="bot-name">${t('In-game name')}</label>
            <input class="input" id="bot-name" name="name" maxlength="12" value="${bot.name}" required>
            <small>${t('up to 12 characters — that’s how other players will see it')}</small>
          </div>

          <fieldset class="field">
            <legend class="label">${t('Color')}</legend>
            <div class="swatches">${COLORS.map(c => html`
              <label class="swatch" style="--swatch:${c}" title="${c}">
                <input type="radio" name="color" value="${c}" ${c === bot.color ? 'checked' : ''}><i></i>
              </label>`)}
            </div>
          </fieldset>

          <div class="grid-2">
            <div class="field">
              <label for="bot-provider">${t('Provider')}</label>
              <select class="input" id="bot-provider" name="provider">${providers.map(p => html`
                <option value="${p.id}" ${p.id === bot.provider ? 'selected' : ''}>${p.name}</option>`)}
              </select>
            </div>
            <div class="field">
              <label for="bot-model">${t('Model')}</label>
              <input class="input mono" id="bot-model" name="model" list="bot-models" value="${bot.model}" placeholder="${t('model name')}">
              <datalist id="bot-models" data-ref="models">${modelOptions(bot).map(m => html`<option value="${m}">`)}</datalist>
            </div>
          </div>

          <div class="field">
            <label for="bot-persona">${t('Personality')}</label>
            <textarea class="input" id="bot-persona" name="persona" rows="3">${bot.persona}</textarea>
            <small>${t('goes into the prompt in place of {persona}', { persona: '{persona}' })}</small>
          </div>

          <div class="field">
            <label for="bot-temp">${t('Imagination (temperature):')} <span data-ref="tempValue">${bot.temperature}</span></label>
            <input class="range" id="bot-temp" type="range" name="temperature" min="0" max="1.5" step="0.05" value="${bot.temperature}">
            <div class="range-legend"><span>${t('predictable')}</span><span>${t('crazy')}</span></div>
          </div>

          <fieldset class="field">
            <legend class="label">${t('Plays')}</legend>
            ${GAMES.map(g => html`
              <label class="check"><input type="checkbox" name="game:${g.tag}" ${(bot.games || {})[g.tag] !== false ? 'checked' : ''}><i></i><span>${g.title}</span></label>`)}
            <label class="check"><input type="checkbox" name="vision" ${bot.vision ? 'checked' : ''}><i></i>
              <span>${t('Sees pictures')}<small>${t('a vision model looks at the photos in “{game}”', { game: GAMES.find(g => g.tag === 'survivetheinternet').title })}</small></span></label>
            <label class="check"><input type="checkbox" name="enabled" ${bot.enabled ? 'checked' : ''}><i></i><span>${t('Bot enabled')}</span></label>
          </fieldset>

          <div class="form-actions">
            <button class="btn btn--small" type="button" data-action="try">${t('▶ try it')}</button>
            <span class="spacer"></span>
            <button class="link-btn link-btn--danger link-btn--plain" type="button" data-action="delete">${t('delete')}</button>
          </div>
          <div data-ref="result"></div>
        </form>`);
      Object.assign(r, refs(r.editor));
    }

    /** Перенести одно изменённое поле формы в черновик. */
    function applyField(input) {
      const bot = current();
      const { name } = input;
      if (!bot || !name) return;
      if (name.startsWith('game:')) bot.games = { ...bot.games, [name.slice(5)]: input.checked };
      else if (name === 'vision' || name === 'enabled') bot[name] = input.checked;
      else if (name === 'temperature') { bot.temperature = Number(input.value); r.tempValue.textContent = input.value; }
      else if (name === 'name') bot.name = input.value.trim().slice(0, 12);
      else if (name === 'persona') bot.persona = input.value.trim();
      else if (name === 'model') bot.model = input.value.trim();
      else if (name === 'color') bot.color = input.value;
      else if (name === 'provider') {
        bot.provider = input.value;
        const models = providers.find(p => p.id === bot.provider)?.models || [];
        if (models.length && !models.includes(bot.model)) {
          bot.model = models[0];
          r.form.elements.model.value = bot.model;
        }
        r.models.innerHTML = String(html`${modelOptions(bot).map(m => html`<option value="${m}">`)}`);
      }
      renderCards();
    }
    on(r.editor, 'input', e => applyField(e.target));
    on(r.editor, 'change', e => applyField(e.target));
    on(r.editor, 'submit', e => e.preventDefault());

    on(r.editor, 'click', e => {
      const action = e.target.closest('[data-action]')?.dataset.action;
      if (action === 'delete') removeCurrent();
      if (action === 'try') withBusy(e.target.closest('button'), tryBot);
    });

    async function removeCurrent() {
      const bot = current();
      if (!bot || !(await confirmDialog({ text: t('Delete the bot “{name}”?', { name: bot.name }), ok: t('Delete'), danger: true }))) return;
      draft = draft.filter(b => b.id !== bot.id);
      const wasSaved = saved.some(b => b.id === bot.id);
      if (wasSaved) await persist(saved.filter(b => b.id !== bot.id), false);
      select(draft[0]?.id ?? null);
      toast(t('Bot deleted'));
    }

    async function tryBot() {
      const bot = current();
      if (isDirty()) await persist(draft, true);
      r.result.innerHTML = String(html`<div class="note note--think"><div class="note__text dots-typing">${t('thinking')}</div></div>`);
      const res = await api.ask({ botId: bot.id, game: 'quiplash2', phase: 'answer' });
      r.result.innerHTML = String(res.ok
        ? html`<div class="note is-new" style="--accent:${bot.color}"><div class="note__who">${bot.name}:</div><div class="note__text">${res.text}</div><div class="note__meta"><span>${SAMPLE_TASK[res.lang] || SAMPLE_TASK.en}</span><span>${secs(res.ms)}</span></div></div>`
        : html`<div class="note note--error is-new"><div class="note__who">${t('Error')}</div><div class="note__text">${res.error}</div></div>`);
    }

    // ---------- сохранение ----------
    /**
     * Сохранить список на сервер.
     * keepDraftInSync=false — черновик не трогаем (так удаление не сохраняет чужие незаконченные правки).
     */
    async function persist(list, keepDraftInSync = true) {
      const result = await api.saveBots(list);
      saved = result;
      if (keepDraftInSync) draft = clone(result);
      renderCards();
    }

    on(r.save, 'click', () => withBusy(r.save, async () => {
      const bad = draft.find(b => !b.name);
      if (bad) { toast(t('The bot needs a name'), 'bad'); select(bad.id); return; }
      await persist(draft);
      toast(t('Saved'), 'ok');
    }));

    // ---------- старт ----------
    try {
      [saved, providers] = await Promise.all([api.bots(), api.providers()]);
    } catch (error) {
      toastError(error);
      return null;
    }
    if (signal.aborted) return null;
    draft = clone(saved);
    select(draft[0]?.id ?? null);
    if (params.get('new')) {
      replaceHash('#/bots');
      addBot();
    }

    return {
      canLeave: async () => !isDirty() || confirmDialog({ text: t('There are unsaved bot changes. Leave without saving?'), ok: t('Leave'), danger: true }),
    };
  },
};
