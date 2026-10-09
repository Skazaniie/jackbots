/**
 * Живое соединение с сервером (WebSocket /ws): лента событий и состояние сессии.
 * Одно соединение на всю вкладку — оно не рвётся при переходах между страницами.
 *
 * События (addEventListener):
 *   'session'    — изменилось состояние сессии (detail: session)
 *   'feed'       — изменилась лента (detail: { added: [...] } или { reset: true })
 *   'connection' — соединение появилось/пропало (detail: { online })
 */

const FEED_LIMIT = 300;            // столько событий держим в памяти (как на сервере)
const RECONNECT_MS = [500, 1000, 2000, 4000];

class Live extends EventTarget {
  constructor() {
    super();
    this.session = { running: false, bots: [] };
    this.feed = [];
    this.online = null;           // null — ещё не пробовали подключиться
    this._attempt = 0;
    this._sessionJSON = '';
  }

  connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.addEventListener('open', () => { this._attempt = 0; this._setOnline(true); });
    ws.addEventListener('message', m => this._handle(JSON.parse(m.data)));
    ws.addEventListener('close', () => {
      this._setOnline(false);
      const delay = RECONNECT_MS[Math.min(this._attempt++, RECONNECT_MS.length - 1)];
      setTimeout(() => this.connect(), delay);
    });
  }

  _handle(msg) {
    if (msg.type === 'hello') {
      this.feed = msg.feed;
      this._emit('feed', { reset: true });
      this._setSession(msg.session);
    } else if (msg.type === 'session') {
      this._setSession(msg.session);
    } else {
      this.feed.push(msg);
      if (this.feed.length > FEED_LIMIT) this.feed.splice(0, this.feed.length - FEED_LIMIT);
      this._emit('feed', { added: [msg] });
    }
  }

  /** Сервер шлёт состояние каждую секунду — оповещаем только при реальных изменениях. */
  _setSession(session) {
    const json = JSON.stringify(session);
    if (json === this._sessionJSON) return;
    this._sessionJSON = json;
    this.session = session;
    this._emit('session', session);
  }

  /** Локально обновить сессию после ответа API, не дожидаясь сокета. */
  applySession(session) { if (session) this._setSession(session); }

  _setOnline(online) {
    if (this.online === online) return;
    this.online = online;
    this._emit('connection', { online });
  }

  _emit(type, detail) { this.dispatchEvent(new CustomEvent(type, { detail })); }
}

export const live = new Live();
