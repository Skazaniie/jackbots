/**
 * Страница «Промты»: системный промт + отдельный промт на каждую фазу каждой игры.
 * У английской (jackbox.tv) и русской версии игры свои промты: prompts_en.json и prompts.json.
 * Список переменных и примеры значений приходят с сервера (/api/meta).
 */
import { api } from '../api.js';
import { GAMES, gameByTag, providerIcon, secs } from '../catalog.js';
import { clone, debounce, html, refs, sameJSON, syncList, tilt } from '../dom.js';
import { lang as uiLang, t } from '../i18n.js';
import { confirmDialog, toast, toastError, withBusy } from '../ui.js';

const SYSTEM = 'system';
const FORMATS = { text: 'text', number: 'a number', choice: 'an option number', ranking: 'option numbers in order' };
const VERSIONS = ['en', 'ru'];
const VERSION_LABEL = { en: 'English game', ru: 'Russian game' };

const template = () => html`
  <header class="section-head">
    <h2><span>${t('Prompts')}</span></h2><span class="hint">${t('what we ask the model and how')}</span><span class="spacer"></span>
    <button class="btn btn--small" data-ref="save" type="button">${t('saved ✓')}</button>
  </header>
  <div class="prompts">
    <aside class="prompts__nav">
      <div class="seg prompts__versions" data-ref="versions" role="tablist" aria-label="${t('Game version')}">${VERSIONS.map(v => html`
        <button class="seg__btn" type="button" role="tab" data-version="${v}">${t(VERSION_LABEL[v])}</button>`)}</div>
      <div class="game-tabs" data-ref="games"></div>
      <div class="sheet sheet--torn phase-list" data-ref="phases" role="listbox" aria-label="${t('Game phases')}"></div>
    </aside>

    <section class="sheet sheet--lined editor prompts__editor paper-grain" aria-label="${t('Prompt text')}">
      <div class="tape"></div>
      <h3 class="editor-heading" data-ref="title"></h3>
      <p class="hint" data-ref="hint"></p>
      <textarea class="input prompt-text" data-ref="text" spellcheck="false" aria-label="${t('Prompt text')}"></textarea>
      <p class="label">${t('Variables — click to insert')}</p>
      <div class="chips" data-ref="vars"></div>
      <div class="prompt-settings">
        <div class="field"><label for="pr-max">${t('Max tokens')}</label><input class="input" id="pr-max" data-ref="maxTokens" type="number" min="1"></div>
        <div class="field"><label for="pr-mem">${t('Memory, events')}</label><input class="input" id="pr-mem" data-ref="memory" type="number" min="0" max="50"><small>${t('for all games')}</small></div>
        <div class="field"><label for="pr-delay">${t('Delay, ms')}</label><input class="input" id="pr-delay" data-ref="delay" placeholder="0-1500"><small>${t('random, before answering')}</small></div>
      </div>
      <div class="form-actions"><button class="link-btn link-btn--plain" type="button" data-ref="reset">${t('restore the default text')}</button></div>
    </section>

    <section class="sheet prompts__preview sheet--tilt-r" aria-label="${t('Request preview')}">
      <h3 class="editor-heading">${t('What the model will see')}</h3>
      <div class="who" data-ref="who" role="radiogroup" aria-label="${t('Which bot to test with')}"></div>
      <pre class="preview mono" data-ref="preview"></pre>
      <button class="btn btn--primary" data-ref="try" type="button">${t('▶ test the prompt')}</button>
      <div data-ref="result"></div>
    </section>
  </div>`;

/** «0-1500» → [0, 1500]; одно число → [n, n]. */
export function parseDelay(value) {
  const parts = String(value || '0').split(/[-–,\s]+/).filter(Boolean).map(x => Math.max(0, Number(x) || 0));
  return [parts[0] ?? 0, parts[1] ?? parts[0] ?? 0];
}

export default {
  id: 'prompts', icon: '✍️',
  get title() { return t('Prompts'); },
  get short() { return t('Prompts'); },

  async mount(root, { signal }) {
    root.innerHTML = String(template());
    const r = refs(root);
    const on = (el, type, fn) => el.addEventListener(type, fn, { signal });

    let meta, bots = [], providers = [];
    let saved = { prompts: null, settings: null };   // prompts: { en: {...}, ru: {...} }
    let draft = { prompts: null, settings: null };
    let version = 'en';                              // какую версию игры редактируем
    let game = GAMES[0].tag;
    let phase = SYSTEM;
    let botId = null;
    const isDirty = () => !sameJSON(saved, draft);
    const phasesOf = tag => draft.prompts[version][tag] || {};
    const gameTitle = tag => gameByTag(tag)?.titles[version] || tag;

    // ---------- версия игры ----------
    function renderVersions() {
      for (const b of r.versions.querySelectorAll('[data-version]')) {
        const selected = b.dataset.version === version;
        b.classList.toggle('is-selected', selected);
        b.setAttribute('aria-selected', String(selected));
      }
    }
    on(r.versions, 'click', e => {
      const b = e.target.closest('[data-version]');
      if (!b || b.dataset.version === version) return;
      version = b.dataset.version;
      if (phase !== SYSTEM && !phasesOf(game)[phase]) phase = firstPhase(game);
      renderVersions(); renderGames(); renderPhases(); loadEditor();
    });
    const firstPhase = tag => Object.keys(phasesOf(tag))[0];

    // ---------- навигация: игры и фазы ----------
    function renderGames() {
      syncList(r.games, GAMES, {
        key: g => g.tag,
        render: g => html`<button class="polaroid polaroid--small" type="button" style="--tilt:${tilt(g.tag, 3)}deg">
          <span class="polaroid__photo"><img class="polaroid__art" src="${g.art}" alt=""><img class="polaroid__logo" src="${g.logo}" alt=""></span>
          <span class="polaroid__caption"></span></button>`,
        update: (node, g) => {
          node.classList.toggle('is-selected', g.tag === game);
          node.querySelector('.polaroid__caption').textContent = g.titles[version];
        },
      });
    }

    function renderPhases() {
      const items = [{ id: SYSTEM, title: t('Character'), hint: t('system prompt shared by all games') },
        ...Object.entries(phasesOf(game)).map(([id, p]) => ({ id, title: p.title, hint: p.hint }))];
      syncList(r.phases, items, {
        key: p => `${version}/${game}/${p.id}`,
        render: p => html`<button class="phase" type="button" role="option" data-phase="${p.id}">
          <i aria-hidden="true"></i><span><b>${p.title}</b><small>${p.hint}</small></span></button>`,
        update: (node, p) => {
          node.classList.toggle('is-selected', p.id === phase);
          node.setAttribute('aria-selected', String(p.id === phase));
        },
      });
    }

    on(r.games, 'click', e => {
      const card = e.target.closest('.polaroid');
      if (!card) return;
      game = card.dataset.key;
      if (phase !== SYSTEM) phase = firstPhase(game);
      renderGames(); renderPhases(); loadEditor();
    });
    on(r.phases, 'click', e => {
      const item = e.target.closest('.phase');
      if (!item) return;
      phase = item.dataset.phase;
      renderPhases(); loadEditor();
    });

    // ---------- редактор ----------
    function loadEditor() {
      const isSystem = phase === SYSTEM;
      const ph = isSystem ? null : phasesOf(game)[phase];
      r.title.textContent = isSystem ? t('Character · system prompt') : `${gameTitle(game)} · ${ph.title}`;
      r.hint.textContent = isSystem
        ? t('goes first in every request')
        : `${ph.hint} · ${t('the model must answer with: {format}', { format: FORMATS[ph.format] ? t(FORMATS[ph.format]) : ph.format })}`;
      r.text.value = isSystem ? draft.prompts[version].system : ph.text;
      r.maxTokens.value = isSystem ? '' : ph.max_tokens;
      r.maxTokens.disabled = isSystem;
      const vars = (isSystem ? meta.vars[version].system : meta.vars[version][game]) || [];
      r.vars.innerHTML = String(html`${vars.map(v => html`<button class="chip chip--var" type="button">{${v}}</button>`)}`);
      renderPreview();
    }

    on(r.text, 'input', () => {
      if (phase === SYSTEM) draft.prompts[version].system = r.text.value;
      else phasesOf(game)[phase].text = r.text.value;
      changed();
    });
    on(r.maxTokens, 'input', () => {
      if (phase !== SYSTEM) phasesOf(game)[phase].max_tokens = Math.max(1, Number(r.maxTokens.value) || 1);
      changed();
    });
    on(r.memory, 'input', () => { draft.settings.memory_rounds = Math.max(0, Number(r.memory.value) || 0); changed(); });
    on(r.delay, 'input', () => { draft.settings.answer_delay_ms = parseDelay(r.delay.value); changed(); });

    on(r.vars, 'click', e => {
      const chip = e.target.closest('.chip');
      if (!chip) return;
      const t = r.text;
      t.setRangeText(chip.textContent, t.selectionStart, t.selectionEnd, 'end');
      t.focus();
      t.dispatchEvent(new Event('input'));
    });

    on(r.reset, 'click', async () => {
      if (!(await confirmDialog({ text: t('Restore the default text of this prompt?'), ok: t('Restore') }))) return;
      try {
        const fresh = await api.resetPrompt(version, game, phase);
        saved.prompts[version] = clone(fresh);
        if (phase === SYSTEM) draft.prompts[version].system = fresh.system;
        else phasesOf(game)[phase] = clone(fresh[game][phase]);
        loadEditor(); changed();
        toast(t('Default text restored'));
      } catch (error) { toastError(error); }
    });

    // ---------- превью ----------
    function renderWho() {
      syncList(r.who, bots, {
        key: b => b.id,
        render: b => html`<button class="avatar avatar--sm" type="button" role="radio" style="--accent:${b.color}" title="${b.name}">
          <img src="${providerIcon(providers, b.provider)}" alt="${b.name}"></button>`,
        update: (node, b) => {
          node.classList.toggle('is-selected', b.id === botId);
          node.setAttribute('aria-checked', String(b.id === botId));
        },
        empty: html`<p class="hint">${t('Create a bot to see the preview')}</p>`,
      });
    }
    on(r.who, 'click', e => {
      const a = e.target.closest('[data-key]');
      if (!a) return;
      botId = a.dataset.key;
      renderWho(); renderPreview();
    });

    /** Локальная подстановка переменных — превью обновляется без сохранения. */
    const renderPreview = debounce(() => {
      const bot = bots.find(b => b.id === botId);
      if (!bot) { r.preview.textContent = t('No bots — the preview is built for a sample bot.'); return; }
      const userPhase = phase === SYSTEM ? firstPhase(game) : phase;
      const ph = phasesOf(game)[userPhase];
      const base = { игра: gameTitle(game), имя: bot.name, персонаж: bot.persona, раунд: 1 };
      const values = { ...base, game: base.игра, name: base.имя, persona: base.персонаж, round: 1, ...(meta.samples[version][game] || {}) };
      const fill = s => s.replace(/\{([^{}\s]+)\}/g, (m, k) => (k in values ? values[k] : m));
      r.preview.innerHTML = String(html`<span class="preview__role">system:</span>
${fill(draft.prompts[version].system)}

<span class="preview__role">user:</span>
${fill(ph.text)}

<span class="preview__meta">${bot.model} · temperature ${bot.temperature} · max_tokens ${ph.max_tokens}</span>`);
    }, 120);

    on(r.try, 'click', () => withBusy(r.try, async () => {
      const bot = bots.find(b => b.id === botId);
      if (!bot) { toast(t('Create a bot first'), 'bad'); return; }
      if (isDirty()) await persist();
      r.result.innerHTML = String(html`<div class="note note--think"><div class="note__text dots-typing">${t('thinking')}</div></div>`);
      const res = await api.ask({ botId, game, phase: phase === SYSTEM ? firstPhase(game) : phase, lang: version });
      r.result.innerHTML = String(res.ok
        ? html`<div class="note is-new" style="--accent:${bot.color}"><div class="note__who">${bot.name}:</div><div class="note__text">${res.text || t('(empty)')}</div><div class="note__meta"><span>${t('first token {s}', { s: secs(res.ttft) })}</span><span>${secs(res.ms)}</span></div></div>`
        : html`<div class="note note--error is-new"><div class="note__who">${t('Error')}</div><div class="note__text">${res.error}</div></div>`);
    }));

    // ---------- сохранение ----------
    function changed() {
      r.save.textContent = isDirty() ? t('save *') : t('saved ✓');
      r.save.disabled = !isDirty();
      r.save.classList.toggle('btn--primary', isDirty());
      renderPreview();
    }
    async function persist() {
      // сохраняем только изменённые части: настройки могли поменять на другой странице
      const tasks = VERSIONS.map(v => (sameJSON(saved.prompts[v], draft.prompts[v]) ? saved.prompts[v] : api.savePrompts(v, draft.prompts[v])));
      const settingsTask = sameJSON(saved.settings, draft.settings) ? saved.settings : api.saveSettings(draft.settings);
      const [en, ru, settings] = await Promise.all([...tasks, settingsTask]);
      saved = { prompts: { en, ru }, settings };
      draft = clone(saved);
      changed();
    }
    on(r.save, 'click', () => withBusy(r.save, async () => { await persist(); toast(t('Saved'), 'ok'); }));

    // ---------- старт ----------
    let en, ru, settings;
    try {
      [en, ru, settings, meta, bots, providers] = await Promise.all([api.prompts('en'), api.prompts('ru'), api.settings(), api.meta(), api.bots(), api.providers()]);
    } catch (error) {
      toastError(error);
      return null;
    }
    if (signal.aborted) return null;
    saved = { prompts: { en, ru }, settings };
    draft = clone(saved);
    // по умолчанию — версия игры из настроек, а в режиме «авто» — язык интерфейса
    version = VERSIONS.includes(settings.game_language) ? settings.game_language : uiLang();
    botId = bots[0]?.id ?? null;
    phase = firstPhase(game);
    r.memory.value = settings.memory_rounds;
    r.delay.value = (settings.answer_delay_ms || [0, 0]).join('-');
    renderVersions(); renderGames(); renderPhases(); renderWho(); loadEditor(); changed();

    return {
      canLeave: async () => !isDirty() || confirmDialog({ text: t('There are unsaved prompt changes. Leave without saving?'), ok: t('Leave'), danger: true }),
    };
  },
};
