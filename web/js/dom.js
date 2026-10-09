/**
 * Мини-набор DOM-утилит без фреймворков.
 *
 * html`...`   — шаблон с автоматическим экранированием подстановок (защита от XSS).
 * raw(str)    — вставить строку как есть (только для уже безопасной разметки).
 * syncList()  — обновить список по ключам: новые элементы получают класс .is-new
 *               (на нём висят CSS-анимации появления), старые обновляются на месте,
 *               поэтому анимации не перезапускаются при каждом обновлении данных.
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

/** Создать один элемент из разметки. */
export function toNode(markup) {
  const t = document.createElement('template');
  t.innerHTML = String(markup).trim();
  return t.content.firstElementChild;
}

/** Собрать все элементы с атрибутом data-ref в объект { имя: элемент }. */
export function refs(root) {
  return Object.fromEntries($$('[data-ref]', root).map(n => [n.dataset.ref, n]));
}

/** Пометить элемент новым, чтобы сыграла CSS-анимация появления, и снять метку после неё. */
function markNew(node) {
  node.classList.add('is-new');
  const done = e => { if (e.target === node) { node.classList.remove('is-new'); node.removeEventListener('animationend', done); } };
  node.addEventListener('animationend', done);
  setTimeout(() => node.classList.remove('is-new'), 1200); // если анимации нет (reduced motion)
}

/**
 * Синхронизировать детей контейнера с массивом данных.
 * @param {Element} container
 * @param {Array} items
 * @param {object} o
 * @param {(item) => string} o.key       уникальный ключ элемента
 * @param {(item) => SafeHTML} o.render  разметка одного элемента (корень — один тег)
 * @param {(node, item) => void} [o.update] точечное обновление существующего узла;
 *        если не задано — узел перерисовывается только при изменении разметки
 * @param {SafeHTML} [o.empty]           что показать, когда список пуст
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

/** Стабильный «случайный» наклон по ключу: при перерисовке карточка не дёргается. */
export function hash(seed) {
  let h = 0;
  for (const ch of String(seed)) h = (h * 31 + ch.charCodeAt(0)) | 0;
  return Math.abs(h);
}
export const tilt = (seed, max = 2) => ((hash(seed) % 1000) / 1000 * 2 - 1) * max;
/** Стабильно выбрать элемент массива по ключу (например, цвет стикера). */
export const pick = (list, seed) => list[hash(seed) % list.length];

export function debounce(fn, ms = 300) {
  let timer;
  const wrapped = (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
  wrapped.cancel = () => clearTimeout(timer);
  return wrapped;
}

/** Глубокое копирование простых JSON-данных (конфиги). */
export const clone = data => JSON.parse(JSON.stringify(data));
export const sameJSON = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/** Короткий id для новых записей: p_x7k2m9 / b_4hq81z */
export const uid = prefix => `${prefix}_${Math.random().toString(36).slice(2, 8)}`;
