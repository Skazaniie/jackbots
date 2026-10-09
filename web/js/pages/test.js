/**
 * "Test" page: one task for all enabled bots, real API requests.
 * Lanes show who manages to answer before the limit (the red finish line).
 */
import { api } from '../api.js';
import { providerIcon, secs } from '../catalog.js';
import { $, $$, html, refs } from '../dom.js';
import { lang as uiLang, t } from '../i18n.js';
import { toastError, withBusy } from '../ui.js';

const SCALE_OVER_LIMIT = 1.35;   // the lane scale is a bit longer than the limit so late bots are visible

const template = () => html`
  <header class="section-head"><h2><span>${t('Model test')}</span></h2><span class="hint">${t('who answers in time')}</span></header>
  <form class="sheet sheet--spiral test-controls paper-grain" data-ref="form">
    <div class="field"><label for="t-phase">${t('Game and phase')}</label><select class="input" id="t-phase" data-ref="phase"></select></div>
    <div class="field test-controls__task"><label for="t-task">${t('Task · fills {question}', { question: '{question}' })}</label><input class="input" id="t-task" data-ref="task"></div>
    <div class="field"><label for="t-limit">${t('Limit, s')}</label><input class="input" id="t-limit" data-ref="limit" type="number" step="0.5" min="0.5" value="3"></div>
    <button class="btn btn--primary" data-ref="go" type="submit">${t('▶ everyone!')}</button>
  </form>
  <section class="sheet sheet--lined race paper-grain" aria-label="${t('Model race')}">
    <div class="tape"></div>
    <div class="lanes" data-ref="lanes"></div>
    <div class="race-summary" data-ref="summary"></div>
  </section>`;

export default {
  id: 'test', icon: '⏱️',
  get title() { return t('Model test'); },
  get short() { return t('Test'); },

  async mount(root, { signal }) {
    root.innerHTML = String(template());
    const r = refs(root);
    const on = (el, type, fn) => el.addEventListener(type, fn, { signal });
    let meta, bots = [], providers = [];
    let version = 'en';   // game version: prompts and the sample task are taken for it
    const limitMs = () => (Number(r.limit.value) || 3) * 1000;

    function renderLanes() {
      r.lanes.innerHTML = String(bots.length ? html`${bots.map(b => html`
        <div class="lane" data-bot="${b.id}" style="--accent:${b.color}">
          <div class="lane__who"><span class="avatar avatar--sm"><img src="${providerIcon(providers, b.provider)}" alt=""></span>
            <span><b>${b.name}</b><small class="mono">${b.model}</small></span></div>
          <div class="lane__track"><div class="lane__fill"></div><div class="lane__finish"></div>
            <span class="lane__runner avatar avatar--sm"><img src="${providerIcon(providers, b.provider)}" alt=""></span></div>
          <div class="lane__time">—</div>
          <div class="lane__answer"></div>
        </div>`)}` : html`<div class="empty">${t('No enabled bots — turn them on on the “Bots” page')}</div>`);
      placeFinish(limitMs() * SCALE_OVER_LIMIT);
    }

    const pct = (ms, scale) => `${Math.min(100, (ms / scale) * 100)}%`;
    function placeFinish(scale) {
      $$('.lane__finish', r.lanes).forEach(f => { f.style.left = pct(limitMs(), scale); });
    }

    on(r.phase, 'change', () => {
      const [tag] = r.phase.value.split('/');
      r.task.value = meta.samples[version][tag]?.question || '';
    });
    on(r.limit, 'input', () => placeFinish(limitMs() * SCALE_OVER_LIMIT));

    on(r.form, 'submit', e => {
      e.preventDefault();
      if (bots.length) withBusy(r.go, race);
    });

    async function race() {
      renderLanes();
      r.summary.innerHTML = '';
      const [game, phase] = r.phase.value.split('/');
      const limit = limitMs();
      const results = new Map();
      const lanes = new Map($$('.lane', r.lanes).map(l => [l.dataset.bot, l]));
      const t0 = performance.now();

      // Running animation: move the runners every frame until everyone finishes.
      const frame = () => {
        if (signal.aborted) return;
        const now = performance.now() - t0;
        const scale = Math.max(limit * SCALE_OVER_LIMIT, now * 1.05, ...[...results.values()].map(x => x.ms));
        placeFinish(scale);
        for (const b of bots) {
          const lane = lanes.get(b.id);
          const ms = results.get(b.id)?.ms ?? now;
          $('.lane__fill', lane).style.width = pct(ms, scale);
          $('.lane__runner', lane).style.left = pct(ms, scale);
          $('.lane__time', lane).textContent = secs(ms);
        }
        if (results.size < bots.length) requestAnimationFrame(frame);
      };
      requestAnimationFrame(frame);

      await Promise.all(bots.map(async b => {
        let res;
        try { res = await api.ask({ botId: b.id, game, phase, vars: { question: r.task.value }, lang: version }); }
        catch (error) { res = { ok: false, error: error.message }; }
        res.ms = res.ms || Math.round(performance.now() - t0);
        results.set(b.id, res);
        const lane = lanes.get(b.id);
        lane.classList.add('is-done');
        const answer = $('.lane__answer', lane);
        answer.textContent = res.ok ? `“${res.text}”` : t('Error: {e}', { e: res.error });
        answer.classList.toggle('is-error', !res.ok);
      }));
      if (signal.aborted) return;

      const ok = bots.filter(b => results.get(b.id).ok);
      const best = ok.length ? Math.min(...ok.map(b => results.get(b.id).ms)) : null;
      for (const b of bots) {
        const res = results.get(b.id);
        const late = !res.ok || res.ms > limit;
        const win = res.ok && res.ms === best;
        const stamp = document.createElement('span');
        stamp.className = `stamp ${late ? 'stamp--bad' : win ? 'stamp--gold' : 'stamp--ok'} lane__stamp`;
        stamp.textContent = !res.ok ? t('error') : late ? t('too slow') : win ? t('★ fastest') : t('in time');
        lanes.get(b.id).append(stamp);
      }
      const inTime = ok.filter(b => results.get(b.id).ms <= limit).length;
      const avg = ok.length ? ok.reduce((sum, b) => sum + results.get(b.id).ms, 0) / ok.length : null;
      const winner = best !== null ? bots.find(b => results.get(b.id).ms === best && results.get(b.id).ok) : null;
      r.summary.innerHTML = String(html`
        <div class="note" style="--note:var(--note-green);--tilt:-1.5deg"><div class="note__meta">${t('answer in time')}</div><div class="note__text">${t('{n} of {total}', { n: inTime, total: bots.length })}</div></div>
        <div class="note" style="--note:var(--note-blue);--tilt:1deg"><div class="note__meta">${t('average time')}</div><div class="note__text">${secs(avg)}</div></div>
        <div class="note" style="--note:var(--note-yellow);--tilt:-.5deg"><div class="note__meta">${t('fastest')}</div><div class="note__text">${winner ? winner.name : '—'}</div></div>`);
    }

    try {
      [meta, bots, providers] = await Promise.all([api.meta(), api.bots(), api.providers()]);
    } catch (error) {
      toastError(error);
      return null;
    }
    if (signal.aborted) return null;
    bots = bots.filter(b => b.enabled);
    const settings = await api.settings().catch(() => ({}));
    if (signal.aborted) return null;
    version = ['en', 'ru'].includes(settings.game_language) ? settings.game_language : uiLang();
    r.phase.innerHTML = String(html`${meta.games.map(g => html`<optgroup label="${g.titles[version]}">${g.phases_by_lang[version].map(p => html`
      <option value="${g.tag}/${p.id}">${g.titles[version]} · ${p.title}</option>`)}</optgroup>`)}`);
    r.phase.dispatchEvent(new Event('change'));
    renderLanes();
    return null;
  },
};
