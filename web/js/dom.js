/**
 * A tiny set of DOM utilities, no frameworks.
 *
 * html`...`   — template with automatic escaping of substitutions (XSS protection).
 * raw(str)    — insert a string as is (only for markup that is already safe).
 * syncList()  — update a list by keys: new elements get the .is-new class
 *               (CSS appear animations hang on it), old ones are updated in place,
 *               so animations don't restart on every data update.
 */

class SafeHTML {
  constructor(value) { this.value = value; }
  toString() { return this.value; }
}

const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ESCAPES[c]);
export const raw = value => new SafeHTML(String(value ?? ''));

function interpolate(value) {
  if (value instanceof SafeHTML) return value.value;
  if (Array.isArray(value)) return value.map(interpolate).join('');
  if (value === null || value === undefined || value === false) return '';
  return esc(value);
}

export function html(strings, ...values) {
  let out = strings[0];
  values.forEach((v, i) => { out += interpolate(v) + strings[i + 1]; });
  return new SafeHTML(out);
}

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

/** Create a single element from markup. */
export function toNode(markup) {
  const t = document.createElement('template');
  t.innerHTML = String(markup).trim();
  return t.content.firstElementChild;
}

/** Collect all elements with a data-ref attribute into an object { name: element }. */
export function refs(root) {
  return Object.fromEntries($$('[data-ref]', root).map(n => [n.dataset.ref, n]));
}

/** Mark an element as new so the CSS appear animation plays, and remove the mark after it. */
function markNew(node) {
  node.classList.add('is-new');
  const done = e => { if (e.target === node) { node.classList.remove('is-new'); node.removeEventListener('animationend', done); } };
  node.addEventListener('animationend', done);
  setTimeout(() => node.classList.remove('is-new'), 1200); // in case there is no animation (reduced motion)
}

/**
 * Sync a container's children with a data array.
 * @param {Element} container
 * @param {Array} items
 * @param {object} o
 * @param {(item) => string} o.key       unique element key
 * @param {(item) => SafeHTML} o.render  markup of one element (a single root tag)
 * @param {(node, item) => void} [o.update] targeted update of an existing node;
 *        if not set, the node is redrawn only when its markup changes
 * @param {SafeHTML} [o.empty]           what to show when the list is empty
 */
export function syncList(container, items, { key, render, update, empty }) {
  const existing = new Map();
  for (const node of [...container.children]) {
    if (node.dataset.key === undefined) node.remove();
    else existing.set(node.dataset.key, node);
  }
  let prev = null;
  for (const item of items) {
    const k = String(key(item));
    let node = existing.get(k);
    if (node) {
      existing.delete(k);
      if (update) update(node, item);
      else {
        const markup = String(render(item));
        if (node._markup !== markup) {
          const fresh = toNode(markup);
          fresh.dataset.key = k;
          fresh._markup = markup;
          node.replaceWith(fresh);
          node = fresh;
        }
      }
    } else {
      const markup = String(render(item));
      node = toNode(markup);
      node.dataset.key = k;
      node._markup = markup;
      if (update) update(node, item);
      markNew(node);
    }
    const expected = prev ? prev.nextElementSibling : container.firstElementChild;
    if (expected !== node) container.insertBefore(node, expected);
    prev = node;
  }
  existing.forEach(node => node.remove());
  if (!items.length && empty) container.innerHTML = String(empty);
}

/** A stable "random" tilt by key: the card doesn't jump on redraw. */
export function hash(seed) {
  let h = 0;
  for (const ch of String(seed)) h = (h * 31 + ch.charCodeAt(0)) | 0;
  return Math.abs(h);
}
export const tilt = (seed, max = 2) => ((hash(seed) % 1000) / 1000 * 2 - 1) * max;
/** Stably pick an array element by key (e.g. a sticker color). */
export const pick = (list, seed) => list[hash(seed) % list.length];

export function debounce(fn, ms = 300) {
  let timer;
  const wrapped = (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
  wrapped.cancel = () => clearTimeout(timer);
  return wrapped;
}

/** Deep copy of plain JSON data (configs). */
export const clone = data => JSON.parse(JSON.stringify(data));
export const sameJSON = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/** Short id for new records: p_x7k2m9 / b_4hq81z */
export const uid = prefix => `${prefix}_${Math.random().toString(36).slice(2, 8)}`;
