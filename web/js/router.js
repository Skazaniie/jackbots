/**
 * Хеш-роутер: #/game, #/bots?new=1 …
 * Каркас (меню, фон) не перерисовывается — меняется только содержимое <main>,
 * поэтому анимации и состояние каркаса не сбрасываются при переходах.
 *
 * Страница — объект { id, mount(view, ctx) }, где mount может вернуть объект
 * { canLeave?: () => Promise<boolean> | boolean }. ctx.signal отменяется при уходе
 * со страницы: передавай его в addEventListener, и обработчики снимутся сами.
 * ctx.params — URLSearchParams из части адреса после «?».
 */

import { t } from './i18n.js';

export class Router {
  constructor({ view, pages, fallback, onChange }) {
    this.view = view;
    this.pages = new Map(pages.map(p => [p.id, p]));
    this.fallback = fallback;
    this.onChange = onChange;
    this.current = null;      // { id, hash, controller, instance }
    this._restoring = false;
  }

  start() {
    window.addEventListener('hashchange', () => this._go());
    this._go();
  }

  static parse(hash) {
    const [path, query = ''] = hash.replace(/^#\/?/, '').split('?');
    return { id: path || '', params: new URLSearchParams(query) };
  }

  async _go() {
    if (this._restoring) { this._restoring = false; return; }
    const { id, params } = Router.parse(location.hash);
    const page = this.pages.get(id);
    if (!page) { location.replace(`#/${this.fallback}`); return; }

    if (this.current?.instance?.canLeave && !(await this.current.instance.canLeave())) {
      this._restoring = true;              // вернуть адрес, не перерисовывая страницу
      location.hash = this.current.hash;
      return;
    }
    this.current?.controller.abort();

    const controller = new AbortController();
    // У каждой страницы свой корень: если старая страница допишет что-то после
    // асинхронной загрузки, это попадёт в уже отсоединённый элемент, а не на экран.
    const root = document.createElement('div');
    root.className = `page page--${id}`;
    this.view.replaceChildren(root);
    this.view.classList.remove('is-entering');
    void this.view.offsetWidth;            // перезапуск анимации входа только для <main>
    this.view.classList.add('is-entering');
    window.scrollTo({ top: 0, behavior: 'instant' });
    const current = { id, hash: location.hash, controller, instance: null };
    this.current = current;
    this.onChange?.(id);
    try {
      // replaceHash — поменять адрес без перехода (например, убрать ?new=1 после создания)
      const replaceHash = hash => { history.replaceState(null, '', hash); current.hash = hash; };
      current.instance = (await page.mount(root, { params, signal: controller.signal, replaceHash })) || null;
    } catch (error) {
      if (controller.signal.aborted) return;
      console.error(error);
      root.innerHTML = `<div class="empty">${t("Couldn't open the page. Details are in the browser console.")}</div>`;
    }
  }
}
