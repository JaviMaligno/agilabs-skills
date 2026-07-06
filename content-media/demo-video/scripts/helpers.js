(() => { if (window.__naturalHelpers) return 'ok';
window.__naturalHelpers = true;
window.__cursorEl = () => { let c = document.getElementById('__vcur'); if (c) return c;
  c = document.createElement('div'); c.id = '__vcur';
  c.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24"><path d="M5 2 L5 19.5 L9.3 15.8 L12.2 22 L14.6 20.9 L11.8 14.9 L17.5 14.5 Z" fill="#111" stroke="white" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  Object.assign(c.style, {position:'fixed', left: (innerWidth*0.58)+'px', top: (innerHeight*0.72)+'px',
    zIndex: 2147483647, pointerEvents:'none', filter:'drop-shadow(0 1px 2px rgba(0,0,0,.35))'});
  document.body.appendChild(c); return c; };
window.__findEl = (q) => {
  if (typeof q !== 'string') return q;
  if (q.startsWith('css:')) return document.querySelector(q.slice(4));
  const t = q.toLowerCase();
  return [...document.querySelectorAll('button,[role=button],a')]
    .find(e => (e.textContent || '').toLowerCase().includes(t));
};
window.__moveTo = (q, dur=650) => new Promise(res => {
  const el = window.__findEl(q); const c = window.__cursorEl();
  if (!el) { res(false); return; }
  el.scrollIntoView({behavior:'smooth', block:'center'});
  setTimeout(() => {
    const r = el.getBoundingClientRect();
    const tx = r.left + r.width*0.55, ty = r.top + r.height*0.55;
    const sx = parseFloat(c.style.left) || innerWidth*0.6, sy = parseFloat(c.style.top) || innerHeight*0.7;
    const t0 = performance.now();
    const ease = t => t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3) / 2;
    const step = now => { const p = Math.min(1, (now - t0) / dur), e = ease(p);
      c.style.left = (sx + (tx - sx) * e) + 'px'; c.style.top = (sy + (ty - sy) * e) + 'px';
      if (p < 1) requestAnimationFrame(step); else res(true); };
    requestAnimationFrame(step);
  }, 380);
});
window.__ripple = () => { const c = window.__cursorEl();
  const r = document.createElement('div');
  Object.assign(r.style, {position:'fixed', left:(parseFloat(c.style.left)-12)+'px',
    top:(parseFloat(c.style.top)-12)+'px', width:'26px', height:'26px', borderRadius:'50%',
    border:'2.5px solid rgba(37,99,235,.85)', zIndex:2147483646, pointerEvents:'none',
    transition:'transform .45s ease-out, opacity .45s ease-out'});
  document.body.appendChild(r);
  requestAnimationFrame(() => { r.style.transform = 'scale(1.9)'; r.style.opacity = '0'; });
  setTimeout(() => r.remove(), 500); };
window.__click = async (q, dur=650) => { const el = window.__findEl(q);
  if (!el) return false;
  await window.__moveTo(el, dur); window.__ripple();
  await new Promise(r => setTimeout(r, 150)); el.click(); return true; };
window.__typeIn = async (el, text, cps=26) => {
  el = window.__findEl(el); if (!el) return false;
  const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
  const set = Object.getOwnPropertyDescriptor(proto, 'value').set;
  await window.__moveTo(el, 450);
  el.focus();
  const base = 1000 / cps;
  for (let i = 1; i <= text.length; i++) {
    set.call(el, text.slice(0, i));
    el.dispatchEvent(new Event('input', {bubbles: true}));
    const ch = text[i-1];
    await new Promise(r => setTimeout(r, base + (ch === ' ' ? 20 : 0) + ((i % 11 === 0) ? 85 : 0)));
  }
  return true;
};
window.__typeChat = (text, cps=30) => window.__typeIn(document.querySelector('textarea'), text, cps);
return 'helpers injected';
})()
