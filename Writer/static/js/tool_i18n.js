/* ═══════════════════════════════════════════════════════════════
   tool_i18n.js — общий переключатель языка для автономных
   инструментов (/static/*.html): «Конвертер», «Вёрстка», «Аннотатор».

   Русский — исходный язык разметки; EN берётся из словаря, который
   инструмент передаёт в ToolI18N.init(dict, reapply). Выбор языка —
   глобальный (settings.ui_language), тот же en|ru, что в шапке
   приложения. Без приложения (file://) переключение работает
   локально, на одну страницу.

   dict — плоский словарь «русский текст → английский», для шаблонов
   с подстановками используются ключи вида 'строки 1–{a} из {b}' и
   вызов tr(key, {a: 1, b: 400}).
   ═══════════════════════════════════════════════════════════════ */
(function () {
'use strict';

let LANG = 'ru';
let DICT = {};
let REAPPLY = null;

/* ── перевод строки (для динамических текстов в JS инструмента) ── */
function tr(key, params) {
  let s = key;
  if (LANG === 'en' && Object.prototype.hasOwnProperty.call(DICT, key)) {
    s = DICT[key];
  }
  if (params) {
    for (const k of Object.keys(params)) {
      s = s.split('{' + k + '}').join(String(params[k]));
    }
  }
  return s;
}

function currentLang() { return LANG; }

/* Локаль форматирования чисел/дат — как в приложении. */
function locale() { return LANG === 'en' ? 'en-US' : 'ru-RU'; }

/* Десятичный разделитель: в RU — запятая (7,3 МБ), в EN — точка. */
function dec(x) {
  const s = String(x);
  return LANG === 'en' ? s.replace(',', '.') : s;
}

/* ── статичная разметка: текстовые узлы + placeholder/title/aria ── */
function applyDom() {
  if (!document.body) return;

  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const raw = node.nodeValue;
    if (!raw || !raw.trim()) continue;
    const key = raw.trim();
    if (LANG === 'en' && DICT[key] !== undefined) {
      if (node._ru === undefined) node._ru = raw;
      node.nodeValue = raw.replace(key, DICT[key]);
    } else if (LANG === 'ru' && node._ru !== undefined) {
      node.nodeValue = node._ru;
      delete node._ru;
    }
  }

  for (const attr of ['placeholder', 'title', 'aria-label']) {
    document.querySelectorAll('[' + attr + ']').forEach(el => {
      const key = (el.getAttribute(attr) || '').trim();
      if (!key) return;
      if (LANG === 'en' && DICT[key] !== undefined) {
        if (el['_ru_' + attr] === undefined) el['_ru_' + attr] = key;
        el.setAttribute(attr, DICT[key]);
      } else if (LANG === 'ru' && el['_ru_' + attr] !== undefined) {
        el.setAttribute(attr, el['_ru_' + attr]);
        delete el['_ru_' + attr];
      }
    });
  }

  // элементы с явным ключом data-i18n (когда один текст встречается
  // дважды и требует разных переводов)
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n') || '';
    if (!key) return;
    if (LANG === 'en' && DICT[key] !== undefined) {
      if (el._ru_i18n === undefined) el._ru_i18n = el.textContent;
      el.textContent = DICT[key];
    } else if (LANG === 'ru' && el._ru_i18n !== undefined) {
      el.textContent = el._ru_i18n;
      delete el._ru_i18n;
    }
  });

  // <title> документа
  const t = document.title;
  if (LANG === 'en' && DICT[t] !== undefined) {
    if (!document._ruTitle) document._ruTitle = t;
    document.title = DICT[t];
  } else if (LANG === 'ru' && document._ruTitle) {
    document.title = document._ruTitle;
    document._ruTitle = '';
  }

  document.documentElement.lang = LANG;
}

/* ── переключатель en | ru в шапке инструмента ────────────────── */
function renderSwitch() {
  document.querySelectorAll('.lang-slot').forEach(slot => {
    slot.innerHTML = '';
    for (const l of ['en', 'ru']) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'ti-btn' + (LANG === l ? ' active' : '');
      b.textContent = l;
      b.setAttribute('aria-label', l === 'en' ? 'English' : 'Русский');
      b.addEventListener('click', () => setLang(l));
      slot.appendChild(b);
    }
  });
}

async function setLang(lang) {
  if (lang === LANG) return;
  LANG = lang;
  // Сохраняем глобально; без приложения (file://) — только эта страница.
  try {
    await fetch('/api/ui/language', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ lang }).toString(),
    });
  } catch (e) { /* офлайн — переключаем локально */ }
  renderSwitch();
  applyDom();
  if (REAPPLY) { try { REAPPLY(); } catch (e) { /* частичный ререндер */ } }
}

/* init(dict, reapply): читает глобальный язык, применяет словарь к
   разметке, один раз запускает reapply (перерисовка динамики). */
async function init(dict, reapply) {
  DICT = dict || {};
  REAPPLY = reapply || null;
  try {
    const r = await fetch('/api/ui/language');
    if (r.ok) {
      const d = await r.json();
      if (d.lang === 'en') LANG = 'en';
    }
  } catch (e) { /* нет приложения — остаёмся на русском */ }
  renderSwitch();
  applyDom();
  if (REAPPLY) { try { REAPPLY(); } catch (e) { /* частичный ререндер */ } }
}

const style = document.createElement('style');
style.textContent = `
.lang-slot{display:inline-flex;border:1px solid rgba(38,32,26,.4);border-radius:6px;overflow:hidden;flex:none;align-self:center}
.ti-btn{appearance:none;border:none;background:transparent;cursor:pointer;
  font:600 10.5px 'IBM Plex Mono','JetBrains Mono',Consolas,monospace;
  letter-spacing:.08em;padding:4px 10px;color:inherit;opacity:.5;transition:all .15s}
.ti-btn:hover{opacity:.9}
.ti-btn.active{background:#93301B;color:#F8F3E7;opacity:1}
`;
document.head.appendChild(style);

window.ToolI18N = { init, tr, currentLang, locale, dec };
})();
