/**
 * Panel HTTP API client (see app/main.py). All requests are JSON.
 * Server errors become ApiError with a readable message from the `detail` field.
 */
import { t } from './i18n.js';

export class ApiError extends Error {
  constructor(message, status) { super(message); this.name = 'ApiError'; this.status = status; }
}

async function request(method, path, body) {
  const init = { method, headers: {} };
  if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(`/api/${path}`, init);
  } catch {
    throw new ApiError(t('No connection to JackBOTS — is the server running?'), 0);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data && data.detail;
    throw new ApiError(typeof detail === 'string' ? detail : t('Server error (HTTP {status})', { status: response.status }), response.status);
  }
  return data;
}

const get = path => request('GET', path);
const put = (path, body) => request('PUT', path, body);
const post = (path, body = {}) => request('POST', path, body);

export const api = {
  meta: () => get('meta'),

  providers: () => get('providers'),
  saveProviders: list => put('providers', list),
  /** Check the connection; `draft` holds unsaved provider fields. */
  testProvider: (id, draft) => post(`providers/${encodeURIComponent(id)}/test`, draft ?? {}),

  bots: () => get('bots'),
  saveBots: list => put('bots', list),

  /** Prompts for a game version: lang 'ru' -> prompts.json, 'en' -> prompts_en.json. */
  prompts: lang => get(lang === 'en' ? 'prompts_en' : 'prompts'),
  savePrompts: (lang, data) => put(lang === 'en' ? 'prompts_en' : 'prompts', data),
  resetPrompt: (lang, game, phase) => post('prompts/reset', { lang, game, phase }),

  settings: () => get('settings'),
  saveSettings: data => put('settings', data),

  room: code => get(`room/${encodeURIComponent(code)}`),
  session: () => get('session'),
  startSession: (code, botIds) => post('session/start', { code, bot_ids: botIds }),
  stopSession: () => post('session/stop'),
  startGame: () => post('session/startgame'),

  /** One request to the bot's model. Returns { ok, text, ms, ttft } or { ok:false, error }. */
  ask: ({ botId, game, phase, vars, lang }) => post('ask', { bot_id: botId, game, phase, vars, lang }),
};
