/** Shared UI elements: toasts, confirm dialog, "busy" button. */
import { $, html, toNode } from './dom.js';
import { t } from './i18n.js';

/**
 * Show a sticker toast.
 * @param {string} text
 * @param {'ok'|'bad'|''} kind
 */
export function toast(text, kind = '') {
  const box = $('#toasts');
  const node = toNode(html`<div class="toast ${kind ? `toast--${kind}` : ''}" role="status">${text}</div>`);
  box.append(node);
  setTimeout(() => node.classList.add('is-leaving'), kind === 'bad' ? 5000 : 3000);
  node.addEventListener('transitionend', () => node.remove());
}

/** Show an error from an exception. */
export const toastError = error => toast(error?.message || String(error), 'bad');

/**
 * A paper confirm dialog instead of the system confirm().
 * @returns {Promise<boolean>}
 */
export function confirmDialog({ text, ok = t('Yes'), cancel = t('Cancel'), danger = false }) {
  const dialog = toNode(html`
    <dialog class="dialog">
      <form method="dialog" class="sheet sheet--lined">
        <div class="tape"></div>
        <p>${text}</p>
        <div class="dialog__actions">
          <button class="btn btn--small" value="cancel">${cancel}</button>
          <button class="btn btn--small ${danger ? 'btn--primary' : 'btn--success'}" value="ok" autofocus>${ok}</button>
        </div>
      </form>
    </dialog>`);
  document.body.append(dialog);
  dialog.showModal();
  return new Promise(resolve => {
    dialog.addEventListener('close', () => { resolve(dialog.returnValue === 'ok'); dialog.remove(); }, { once: true });
  });
}

/**
 * Run an action while blocking the button during the request (double-click protection).
 * The error is shown as a toast and not rethrown.
 */
export async function withBusy(button, action) {
  if (button.classList.contains('is-busy')) return undefined;
  button.classList.add('is-busy');
  button.disabled = true;
  try {
    return await action();
  } catch (error) {
    toastError(error);
    return undefined;
  } finally {
    button.classList.remove('is-busy');
    button.disabled = false;
  }
}
