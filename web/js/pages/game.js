/**
 * "Game" page: room code -> start bots, the gang, game choice, live feed.
 *
 * Page state is kept in the `state` object, rendering is split into small
 * render*() functions, each updates only its own block.
 */
import { api } from '../api.js';
import { GAMES, gameByTag, providerIcon, secs, speedKind } from '../catalog.js';
import { debounce, html, pick, refs, syncList, tilt } from '../dom.js';
import { t } from '../i18n.js';
import { live } from '../live.js';
import { toast, toastError, withBusy } from '../ui.js';

const STORAGE = { code: 'jackbots.code', benched: 'jackbots.benched' };
const FEED_VISIBLE = 40;
const NOTE_COLORS = ['var(--note-yellow)', 'var(--note-pink)', 'var(--note-green)', 'var(--note-blue)'];
// bot status codes from the server (app/games.py, app/jackbox.py) -> labels
const STATUS = () => ({ connecting: t('connecting'), joined: t('in the game'), error: t('connection error'),
  reconnect: t('reconnecting'), gone: t('left') });
const statusLabel = code => STATUS()[code] || code;

// Room codes are Latin only; if the Russian keyboard layout is on, map by keys.
const RU_KEYS = 'ЙЦУКЕНГШЩЗФЫВАПРОЛДЯЧСМИТЬ';
const EN_KEYS = 'QWERTYUIOPASDFGHJKLZXCVBNM';
export function normalizeCode(value) {
  return value.toUpperCase()
    .replace(/[А-ЯЁ]/g, c => EN_KEYS[RU_KEYS.indexOf(c)] || '')
    .replace(/[^A-Z]/g, '')
    .slice(0, 4);
}

const template = () => html`
  <p class="page-hello" data-ref="hello"></p>

  <div class="game-hero">
    <section class="sheet sheet--spiral sheet--tilt-l game-join paper-grain" aria-label="${t('Joining a room')}">
      <label class="label" for="room-code">${t('Enter the room code:')}</label>
      <div class="code" data-ref="code">
        <span class="code__cell"></span><span class="code__cell"></span><span class="code__cell"></span><span class="code__cell"></span>
        <input class="code__input" id="room-code" data-ref="codeInput" maxlength="8" autocomplete="off" autocorrect="off"
               autocapitalize="characters" spellcheck="false" enterkeyhint="go" inputmode="text">
      </div>
      <p class="status-line" data-ref="roomStatus" aria-live="polite"></p>
      <button class="btn btn--primary btn--big" data-ref="go" type="button"></button>
      <button class="btn btn--success btn--big game-join__vip" data-ref="vip" type="button" hidden>${t('★ everybody’s in — start')}</button>
    </section>

    <section class="game-cast">
      <header class="section-head">
        <h2><span>${t('The crew')}</span></h2><span class="spacer"></span>
        <a class="link-btn" href="#/bots?new=1">${t('+ one more bot')}</a>
      </header>
      <div class="sheet sheet--torn sheet--tilt-r cast" data-ref="cast"></div>
    </section>
  </div>

  <section class="game-section">
    <header class="section-head"><h2><span>${t('Games')}</span></h2><span class="hint">${t('the game is detected from the room code')}</span></header>
    <div class="games-row" data-ref="games"></div>
  </section>

  <section class="game-section">
    <header class="section-head"><h2><span>${t('What they write')}</span></h2><i class="live-dot" data-ref="liveDot"></i></header>
    <div class="feed" data-ref="feed" aria-live="polite"></div>
  </section>`;

export default {
  id: 'game', icon: '🎮',
  get title() { return t('Game'); },
  get short() { return t('Game'); },

  async mount(root, { signal }) {
    root.innerHTML = String(template());
    const r = refs(root);
    const cells = [...r.code.querySelectorAll('.code__cell')];
    const on = (el, type, fn) => el.addEventListener(type, fn, { signal });

    const state = {
      bots: [], providers: [],
      tag: GAMES[0].tag,                 // selected game: from the room or by clicking a card
      room: { kind: 'idle', text: '' },  // idle | checking | ok | bad
      benched: new Set(JSON.parse(localStorage.getItem(STORAGE.benched) || '[]')),
    };
    const session = () => live.session;

    // ---------- room code ----------
    function renderCode() {
      const value = r.codeInput.value;
      cells.forEach((cell, i) => {
        const ch = value[i] || '';
        if (cell.textContent !== ch) {
          cell.textContent = ch;
          cell.classList.toggle('is-filled', Boolean(ch));
        }
        cell.classList.toggle('is-caret', i === Math.min(value.length, 3) && value.length < 4);
      });
    }

    function renderRoomStatus() {
      const { kind, text } = state.room;
      r.roomStatus.className = `status-line ${kind === 'ok' ? 'is-ok' : kind === 'bad' ? 'is-bad' : ''}`;
      r.roomStatus.textContent = text || t('Four letters from the game screen');
    }

    let roomRequest = 0;
    const checkRoom = debounce(async code => {
      const id = ++roomRequest;
      state.room = { kind: 'checking', text: t('looking for the room…') };
      renderRoomStatus();
      try {
        const info = await api.room(code);
        if (id !== roomRequest || signal.aborted) return;   // the answer is for an outdated code
        if (info.supported) {
          state.tag = info.appTag;
          state.room = { kind: 'ok', text: `${t('✓ found it! {title}', { title: info.title })}${info.locked ? ` · ${t('the game has already started')}` : ''}` };
          renderGames(); renderCast();
        } else {
          state.room = { kind: 'bad', text: t('This is “{tag}” — the bots can’t play it yet', { tag: info.appTag }) };
        }
      } catch (error) {
        if (id !== roomRequest || signal.aborted) return;
        state.room = { kind: 'bad', text: error.message };
      }
      renderRoomStatus();
    }, 300);

    function onCodeInput() {
      const code = normalizeCode(r.codeInput.value);
      if (code !== r.codeInput.value) r.codeInput.value = code;
      renderCode();
      localStorage.setItem(STORAGE.code, code);
      if (code.length === 4) {
        r.codeInput.blur();              // hide the keyboard on phones
        checkRoom(code);
      } else {
        checkRoom.cancel(); roomRequest++;
        state.room = { kind: 'idle', text: '' };
        renderRoomStatus();
      }
    }
    on(r.codeInput, 'input', onCodeInput);
    on(r.codeInput, 'focus', renderCode);
    on(r.codeInput, 'keydown', e => { if (e.key === 'Enter') { e.preventDefault(); r.go.click(); } });

    // ---------- start / stop ----------
    function renderControls() {
      const s = session();
      r.go.textContent = s.running ? t('■ stop the bots') : t('start the bots →');
      r.go.classList.toggle('btn--primary', !s.running);
      r.vip.hidden = !(s.running && s.can_start && (!s.room_state || s.room_state === 'Lobby'));
      r.codeInput.disabled = s.running;
      r.hello.textContent = s.running
        ? `${t('Bots in room {code}', { code: s.code })}${s.game ? ` — ${s.game}` : ''}`
        : t('Hi! Start a game on your PC or TV and enter the room code.');
    }

    on(r.go, 'click', () => withBusy(r.go, async () => {
      if (session().running) {
        live.applySession(await api.stopSession());
        return;
      }
      const code = r.codeInput.value;
      if (code.length !== 4) { toast(t('Enter the 4-letter room code first'), 'bad'); r.codeInput.focus(); return; }
      const ids = eligibleBots().filter(b => !state.benched.has(b.id)).map(b => b.id);
      if (!ids.length) { toast(t('Pick at least one bot in the crew'), 'bad'); return; }
      live.applySession(await api.startSession(code, ids));
      toast(t('The bots are joining the room'), 'ok');
    }));

    on(r.vip, 'click', () => withBusy(r.vip, async () => { await api.startGame(); }));

    // ---------- gang ----------
    function eligibleBots() {
      const s = session();
      if (s.running) {
        const inRoom = new Set(s.bots.map(b => b.id));
        return state.bots.filter(b => inRoom.has(b.id));
      }
      return state.bots.filter(b => b.enabled && (b.games || {})[state.tag] !== false);
    }

    const castRow = bot => html`
      <label class="cast-row" style="--accent:${bot.color}">
        <input type="checkbox" data-bot="${bot.id}">
        <span class="avatar"><img src="${providerIcon(state.providers, bot.provider)}" alt=""></span>
        <span class="cast-row__text"><b class="cast-row__name"></b><small class="cast-row__sub"></small></span>
        <span class="cast-row__state"></span>
      </label>`;

    /** Updates a bot row in place: name, caption, mark and speed stamp. */
    function updateCastRow(node, bot) {
      const s = session();
      const liveBot = s.bots.find(b => b.id === bot.id);
      const checkbox = node.querySelector('input');
      checkbox.checked = s.running || !state.benched.has(bot.id);
      checkbox.disabled = s.running;
      node.classList.toggle('is-benched', !checkbox.checked);
      node.querySelector('.cast-row__name').textContent = bot.name;
      node.querySelector('.cast-row__sub').textContent = liveBot
        ? `${statusLabel(liveBot.status)}${liveBot.errors ? ` · ${t('errors: {n}', { n: liveBot.errors })}` : ''}`
        : `${bot.model} · ${providerName(bot.provider)}`;
      const stateEl = node.querySelector('.cast-row__state');
      const ms = liveBot ? (liveBot.avg_ms ?? liveBot.last_ms) : null;
      const thinking = Boolean(liveBot?.thinking);
      const label = thinking ? t('thinking…') : ms ? secs(ms) : liveBot ? t('in the game') : checkbox.checked ? t('ready') : t('on the bench');
      const kind = thinking ? 'wait' : ms ? speedKind(ms) : checkbox.checked ? 'ok' : 'wait';
      if (stateEl.textContent !== label) stateEl.textContent = label;
      stateEl.className = `cast-row__state stamp stamp--${kind}`;
    }

    const providerName = id => state.providers.find(p => p.id === id)?.name || id;

    function renderCast() {
      syncList(r.cast, eligibleBots(), {
        key: b => b.id, render: castRow, update: updateCastRow,
        empty: html`<div class="empty">${t('No enabled bots for this game.')}<br><a class="link-btn" href="#/bots?new=1">${t('+ create a bot')}</a></div>`,
      });
    }

    on(r.cast, 'change', e => {
      const id = e.target.dataset.bot;
      if (!id) return;
      if (e.target.checked) state.benched.delete(id); else state.benched.add(id);
      localStorage.setItem(STORAGE.benched, JSON.stringify([...state.benched]));
      renderCast();
    });

    // ---------- games ----------
    function renderGames() {
      syncList(r.games, GAMES, {
        key: g => g.tag,
        render: g => html`
          <button class="polaroid" type="button" style="--tilt:${tilt(g.tag)}deg" title="${g.about} · ${t('{n} players', { n: g.players })}">
            <span class="polaroid__photo"><img class="polaroid__art" src="${g.art}" alt="" loading="lazy"><img class="polaroid__logo" src="${g.logo}" alt=""></span>
            <span class="polaroid__caption">${g.title}</span>
          </button>`,
        update: (node, g) => {
          node.classList.toggle('is-selected', g.tag === state.tag);
          node.setAttribute('aria-pressed', String(g.tag === state.tag));
        },
      });
    }

    on(r.games, 'click', e => {
      const card = e.target.closest('.polaroid');
      if (!card || session().running) return;
      state.tag = card.dataset.key;
      renderGames(); renderCast();
    });

    // ---------- feed ----------
    /** Remove the "thinking" event as soon as this bot answers. */
    function visibleFeed() {
      const answered = new Set();
      const out = [];
      for (let i = live.feed.length - 1; i >= 0 && out.length < FEED_VISIBLE; i--) {
        const ev = live.feed[i];
        if (ev.type === 'session' || ev.type === 'hello') continue;
        if (['answer', 'vote', 'error'].includes(ev.type)) answered.add(ev.bot);
        if (ev.type === 'think' && answered.has(ev.bot)) continue;
        out.push(ev);
      }
      return out;
    }

    const botColor = id => state.bots.find(b => b.id === id)?.color || 'var(--ink)';
    const feedKey = ev => ev.id ?? `${ev.t}-${ev.type}-${ev.bot || ''}`;

    function feedItem(ev) {
      const color = botColor(ev.bot);
      if (ev.type === 'info') return html`<p class="feed-line feed-line--info">📌 ${ev.text}</p>`;
      if (ev.type === 'status') {
        const detail = ev.status !== 'joined' && ev.detail ? `: ${ev.detail}` : '';
        return html`<p class="feed-line" style="--accent:${color}"><b>${ev.name}</b> — ${statusLabel(ev.status)}${detail}</p>`;
      }
      if (ev.type === 'think') {
        return html`<article class="note note--think" style="--accent:${color};--tilt:${tilt(feedKey(ev))}deg">
          <div class="note__who">${ev.name}</div><div class="note__text dots-typing">${t('thinking')}</div><div class="note__meta">${ev.phase || ''}</div></article>`;
      }
      const isError = ev.type === 'error';
      const note = isError ? 'var(--note-pink)' : pick(NOTE_COLORS, feedKey(ev));
      const verb = ev.type === 'vote' ? ` ${t('votes')}` : isError ? ` ⚠ ${t('error')}` : '';
      return html`<article class="note ${isError ? 'note--error' : ''}" style="--accent:${color};--note:${note};--tilt:${tilt(feedKey(ev))}deg">
        <div class="note__who">${ev.name}${verb}:</div>
        <div class="note__text">${ev.text}</div>
        <div class="note__meta"><span>${ev.question || ''}</span><span>${ev.ms ? secs(ev.ms) : ''}</span></div>
      </article>`;
    }

    function renderFeed() {
      syncList(r.feed, visibleFeed(), {
        key: feedKey, render: feedItem,
        empty: html`<div class="empty feed__empty">${t('Bot answers and votes will show up here')}</div>`,
      });
      r.liveDot.className = `live-dot ${session().running ? 'is-on' : ''}`;
    }

    // ---------- live updates ----------
    function onSession() {
      const s = session();
      if (s.running && s.tag && s.tag !== state.tag) { state.tag = s.tag; renderGames(); }
      if (s.running && s.code && r.codeInput.value !== s.code) { r.codeInput.value = s.code; renderCode(); }
      renderControls(); renderCast(); renderFeed();
    }
    live.addEventListener('session', onSession, { signal });
    live.addEventListener('feed', renderFeed, { signal });

    // ---------- start ----------
    renderCode(); renderRoomStatus(); renderControls(); renderGames(); renderFeed();
    try {
      [state.bots, state.providers] = await Promise.all([api.bots(), api.providers()]);
    } catch (error) {
      toastError(error);
    }
    if (signal.aborted) return null;
    const saved = normalizeCode(localStorage.getItem(STORAGE.code) || '');
    if (!session().running && saved) { r.codeInput.value = saved; onCodeInput(); }
    onSession();
    return null;
  },
};
