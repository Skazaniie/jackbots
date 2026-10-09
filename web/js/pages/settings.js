/**
 * Страница «Настройки»: язык панели, версия игры (английская jackbox.tv / русская), сервер ecast, лог трафика.
 * Смена языка панели применяется перезагрузкой страницы — так все тексты гарантированно переводятся.
 */
import { api } from '../api.js';
import { clone, html, refs, sameJSON } from '../dom.js';
import { LANGS, lang as uiLang, setLang, t } from '../i18n.js';
import { confirmDialog, toast, toastError, withBusy } from '../ui.js';

const GAME_MODES = [
  ['auto', 'Auto — by the game text', 'Bots answer in the language of the game prompts.'],
  ['en', 'English (jackbox.tv)', 'Answers are Latin-only: the English game drops other characters.'],
  ['ru', 'Russian', 'For the Russian localization of the games.'],
];

const template = () => html`
  <header class="section-head">
    <h2><span>${t('Settings')}</span></h2><span class="hint">${t('language and connection')}</span><span class="spacer"></span>
    <button class="btn btn--small" data-ref="save" type="button">${t('saved ✓')}</button>
  </header>
  <section class="sheet sheet--lined editor settings paper-grain" aria-label="${t('Settings')}">
    <div class="tape"></div>
    <form class="form" data-ref="form" autocomplete="off">
      <div class="field">
        <label for="set-ui">${t('Interface language')}</label>
        <select class="input" id="set-ui" name="ui_language">${Object.entries(LANGS).map(([id, name]) => html`
          <option value="${id}">${name}</option>`)}</select>
      </div>
      <div class="field">
        <label for="set-game">${t('Game version')}</label>
        <select class="input" id="set-game" name="game_language">${GAME_MODES.map(([id, name]) => html`
          <option value="${id}">${t(name)}</option>`)}</select>
        <small data-ref="gameHint"></small>
      </div>
      <details class="more">
        <summary class="label">${t('Advanced')}</summary>
        <div class="field">
          <label for="set-host">${t('Jackbox server (ecast)')}</label>
          <input class="input mono" id="set-host" name="ecast_host" placeholder="ecast.jackboxgames.com" spellcheck="false">
          <small>${t('change it only if the game uses another server')}</small>
        </div>
        <label class="check"><input type="checkbox" name="log_traffic"><i></i>
          <span>${t('Log game traffic')}<small>${t('logs/traffic-*.jsonl — helps to debug a game')}</small></span></label>
      </details>
    </form>
  </section>`;

export default {
  id: 'settings', icon: '⚙️',
  get title() { return t('Settings'); },
  get short() { return uiLang() === 'ru' ? 'Опции' : t('Settings'); },   // короткая подпись нижнего меню

  async mount(root, { signal }) {
    root.innerHTML = String(template());
    const r = refs(root);
    const on = (el, type, fn) => el.addEventListener(type, fn, { signal });
    let saved = null;
    let draft = null;
    const isDirty = () => !sameJSON(saved, draft);

    function render() {
      const f = r.form.elements;
      f.ui_language.value = draft.ui_language;
      f.game_language.value = draft.game_language;
      f.ecast_host.value = draft.ecast_host;
      f.log_traffic.checked = Boolean(draft.log_traffic);
      renderState();
    }

    function renderState() {
      const mode = GAME_MODES.find(m => m[0] === draft.game_language) || GAME_MODES[0];
      r.gameHint.textContent = t(mode[2]);
      r.save.textContent = isDirty() ? t('save *') : t('saved ✓');
      r.save.disabled = !isDirty();
      r.save.classList.toggle('btn--primary', isDirty());
    }

    const apply = input => {
      if (!draft || !input.name) return;
      draft[input.name] = input.type === 'checkbox' ? input.checked : input.value.trim();
      renderState();
    };
    on(r.form, 'input', e => apply(e.target));
    on(r.form, 'change', e => apply(e.target));
    on(r.form, 'submit', e => e.preventDefault());

    on(r.save, 'click', () => withBusy(r.save, async () => {
      if (!draft.ecast_host) draft.ecast_host = 'ecast.jackboxgames.com';
      saved = await api.saveSettings(draft);
      draft = clone(saved);
      if (saved.ui_language !== uiLang()) {
        setLang(saved.ui_language);
        location.reload();               // перерисовать весь интерфейс на новом языке
        return;
      }
      render();
      toast(t('Saved'), 'ok');
    }));

    try {
      saved = await api.settings();
    } catch (error) {
      toastError(error);
      return null;
    }
    if (signal.aborted) return null;
    draft = clone(saved);
    render();

    return {
      canLeave: async () => !isDirty() || confirmDialog({ text: t('There are unsaved settings. Leave without saving?'), ok: t('Leave'), danger: true }),
    };
  },
};
