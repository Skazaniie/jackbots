/**
 * Interface language. Strings are written in English right in the code: t('Bots are resting').
 * The Russian translation is looked up in RU by the English text; {name} placeholders are filled from vars.
 * The language comes from settings (ui_language); localStorage keeps it so the first paint is right.
 */
import { RU } from './i18n.ru.js';

const STORAGE = 'jackbots.lang';
export const LANGS = { en: 'English', ru: 'Русский' };
let current = LANGS[localStorage.getItem(STORAGE)] ? localStorage.getItem(STORAGE) : 'en';

export const lang = () => current;

/** Translate an English string and fill {placeholders}. */
export function t(text, vars) {
  const s = current === 'ru' ? (RU[text] ?? text) : text;
  return vars ? s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m)) : s;
}

/** Pick a word form for a number: plural(n, 'bot', 'bots') — Russian forms come from RU['bot|bots']. */
export function plural(n, one, many) {
  if (current !== 'ru') return n === 1 ? one : many;
  const [f1, f2, f5] = (RU[`${one}|${many}`] || `${one}|${many}|${many}`).split('|');
  const m10 = n % 10, m100 = n % 100;
  return m10 === 1 && m100 !== 11 ? f1 : m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14) ? f2 : f5;
}

export function setLang(value) {
  current = LANGS[value] ? value : 'en';
  localStorage.setItem(STORAGE, current);
  document.documentElement.lang = current;
}

/** Load the language from the server settings before the first render. */
export async function initLang() {
  try {
    const response = await fetch('/api/settings');
    if (response.ok) setLang((await response.json()).ui_language);
  } catch { /* offline: keep the saved language */ }
  setLang(current);
}
