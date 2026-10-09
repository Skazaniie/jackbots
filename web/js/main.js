/** Точка входа панели: меню, стикер состояния, роутер и живое соединение. */
import { $, html } from './dom.js';
import { initLang, plural, t } from './i18n.js';
import { live } from './live.js';
import { Router } from './router.js';
import gamePage from './pages/game.js';
import botsPage from './pages/bots.js';
import providersPage from './pages/providers.js';
import promptsPage from './pages/prompts.js';
import testPage from './pages/test.js';
import settingsPage from './pages/settings.js';

const PAGES = [gamePage, botsPage, providersPage, promptsPage, testPage, settingsPage];

/** Static texts of index.html — they are written in English and translated here. */
function translateShell() {
  $('.logo').setAttribute('aria-label', t('JackBOTS — home'));
  $('#menu').setAttribute('aria-label', t('Sections'));
  $('#offline').textContent = t('No connection to the server, reconnecting…');
}

function renderMenu() {
  $('#menu').innerHTML = String(html`${PAGES.map(p => html`
    <a class="menu__item" href="#/${p.id}" data-page="${p.id}">
      <span class="menu__icon" aria-hidden="true">${p.icon}</span>
      <span class="menu__label">${p.title}</span>
      <span class="menu__short">${p.short || p.title}</span>
    </a>`)}`);
}

function highlightMenu(id) {
  for (const a of document.querySelectorAll('.menu__item')) {
    const active = a.dataset.page === id;
    a.classList.toggle('is-active', active);
    if (active) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  }
}

/** Стикер внизу бокового меню: идёт ли игра прямо сейчас. */
function renderSideNote() {
  const s = live.session;
  const body = s.running
    ? html`<b><i class="live-dot is-on"></i>${t('Room {code}', { code: s.code })}</b>${s.game || ''} · ${s.bots.length} ${plural(s.bots.length, 'bot', 'bots')}`
    : html`<b><i class="live-dot ${live.online ? '' : 'is-off'}"></i>${t('Bots are resting')}</b>${t('Enter the room code on the “Game” page')}`;
  $('#side-note').innerHTML = `<div class="tape"></div>${body}`;
}

await initLang();
translateShell();
renderMenu();
renderSideNote();
live.addEventListener('session', renderSideNote);
live.addEventListener('connection', e => { $('#offline').hidden = e.detail.online; renderSideNote(); });
live.connect();

new Router({ view: $('#view'), pages: PAGES, fallback: 'game', onChange: highlightMenu }).start();
