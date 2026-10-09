/**
 * UI reference data: game images, provider icons, presets.
 * To add a game to the panel, add it here (the game logic lives in app/games.py).
 */
import { lang, t } from './i18n.js';

const ART = '/assets/web/';
export const ICON_DIR = '/assets/icons/';

// titles: the name in the English and Russian game versions; title/about: in the UI language
const game = (tag, titles, about, players, art, logo) => ({
  tag, titles, players, art: ART + art, logo: ART + logo,
  get title() { return titles[lang()] || titles.en; },
  get about() { return t(about); },
});
export const GAMES = [
  game('quiplash2', { en: 'Quiplash 2', ru: 'Смехлыст 2' }, 'Bots write jokes and vote', '3–8', 'quip_mobile.png', 'quip_wordmark.png'),
  game('pollposition', { en: 'Guesspionage', ru: 'Нашшпионаж' }, 'They guess poll percentages', '2–8', 'guess_mobile.png', 'guess_wordmark.png'),
  game('triviadeath2', { en: 'Trivia Murder Party 2', ru: 'Смертельная вечеринка 2' }, 'They answer trivia and try to survive', '1–8',
    'tmp_tile_key.png', 'tmp_wordmark.png'),
  game('survivetheinternet', { en: 'Survive the Internet', ru: 'Выжить в интернете' }, 'They twist other players’ words and caption photos', '3–8',
    'sti_bg.jpg', 'sti_logo.png'),
];
export const gameByTag = tag => GAMES.find(g => g.tag === tag);

/** Icons from assets/icons: put your .svg there and add its name to the list. */
export const ICONS = ['openai.svg', 'claude-color.svg', 'anthropic.svg', 'gemini-color.svg', 'deepseek-color.svg',
  'openrouter.svg', 'ollama.svg', 'grok.svg', 'mistral-color.svg', 'qwen-color.svg', 'meta-color.svg'];

export const COLORS = ['#10a37f', '#d97757', '#4285f4', '#4d6bfe', '#e3172d', '#f5b400',
  '#a855f7', '#ec4899', '#22c55e', '#f97316', '#06b6d4', '#8a8f98'];

/** Quick presets for OpenAI-compatible providers. */
export const PROVIDER_PRESETS = [
  { name: 'Groq', base_url: 'https://api.groq.com/openai/v1', icon: 'meta-color.svg', color: '#f55036' },
  { name: 'LM Studio', base_url: 'http://localhost:1234/v1', icon: 'qwen-color.svg', color: '#7b61ff' },
  { name: 'Mistral', base_url: 'https://api.mistral.ai/v1', icon: 'mistral-color.svg', color: '#fa520f' },
  { name: 'xAI', base_url: 'https://api.x.ai/v1', icon: 'grok.svg', color: '#8a8f98' },
  { name: 'Together', base_url: 'https://api.together.xyz/v1', icon: 'meta-color.svg', color: '#0f6fff' },
  { name: 'Qwen (DashScope)', base_url: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', icon: 'qwen-color.svg', color: '#615ced' },
];

/** Empty provider: the fields match PROVIDER_FIELDS in app/store.py. */
export function newProvider(id, preset) {
  const p = preset || {};
  return {
    id, name: p.name || t('My provider'), base_url: p.base_url || '', icon: p.icon || 'openai.svg',
    color: p.color || '#8a8f98', api_key: '', models: [], timeout: 15, max_tokens: 0, stream: true, retry: true,
    extra_body: {}, headers: {}, status: 'new', last_ms: 0,
  };
}

/** Icon URL; an empty name -> the default icon. */
export const iconUrl = icon => ICON_DIR + (icon || 'openai.svg');
export const providerIcon = (providers, id) => iconUrl(providers.find(p => p.id === id)?.icon);

/** 1400 → «1.4s» */
export const secs = ms => (ms === null || ms === undefined ? '—' : t('{n}s', { n: (ms / 1000).toFixed(1) }));
/** Answer speed rating for the stamp color. */
export const speedKind = ms => (ms === null || ms === undefined ? 'wait' : ms < 1000 ? 'ok' : ms < 1800 ? 'gold' : 'bad');
