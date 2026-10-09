/**
 * Hash router: #/game, #/bots?new=1 ...
 * The layout (menu, background) is not redrawn; only the <main> content changes,
 * so animations and layout state are not reset on navigation.
 *
 * A page is an object { id, mount(view, ctx) }, where mount may return an object
 * { canLeave?: () => Promise<boolean> | boolean }. ctx.signal is aborted when leaving
 * the page: pass it to addEventListener and handlers are removed automatically.
 * ctx.params is URLSearchParams from the part of the URL after "?".
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
      this._restoring = true;              // restore the URL without redrawing the page
      location.hash = this.current.hash;
      return;
    }
    this.current?.controller.abort();

    const controller = new AbortController();
    // Each page has its own root: if an old page appends something after
    // an async load, it lands in a detached element, not on screen.
    const root = document.createElement('div');
    root.className = `page page--${id}`;
    this.view.replaceChildren(root);
    this.view.classList.remove('is-entering');
    void this.view.offsetWidth;            // restart the enter animation only for <main>
    this.view.classList.add('is-entering');
    window.scrollTo({ top: 0, behavior: 'instant' });
    const current = { id, hash: location.hash, controller, instance: null };
    this.current = current;
    this.onChange?.(id);
    try {
      // replaceHash: change the URL without navigating (e.g. drop ?new=1 after creating)
      const replaceHash = hash => { history.replaceState(null, '', hash); current.hash = hash; };
      current.instance = (await page.mount(root, { params, signal: controller.signal, replaceHash })) || null;
    } catch (error) {
      if (controller.signal.aborted) return;
      console.error(error);
      root.innerHTML = `<div class="empty">${t("Couldn't open the page. Details are in the browser console.")}</div>`;
    }
  }
}
