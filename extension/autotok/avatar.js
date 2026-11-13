// Content script (isolated world) on every https://www.tiktok.com/* page, TikTok Studio included (v1.4.5).
// Reads the signed-in channel's avatar from the page header (the picture the owner sees top right) and hands the
// URL to the service worker, which sends it with the next hello. The old way (service worker fetching the profile
// API / HTML) is blocked by TikTok's request signing, so the avatar never arrived. Passive: no clicks, no requests.
(function () {
  'use strict';
  const CDN = /^https:\/\/[a-z0-9.-]*(tiktokcdn(-us)?|ibyteimg|byteimg|tiktokw|ttwstatic)\.(com|us)\//i;

  // cands: [{ src, cls, alt, top, w, h }]. Returns the best own-avatar URL or ''.
  // Own avatar = a CDN image in an "avatar" element sitting in the page header (top 160 px), roughly square, 20-200 px.
  // Avatars lower on the page are other people's (comments, followers, video authors) and are ignored.
  function pickAvatar(cands) {
    let best = null, bestScore = 0;
    for (const c of cands || []) {
      if (!c || typeof c.src !== 'string' || c.src.length > 1900 || !CDN.test(c.src)) continue;
      if (!(c.w >= 20 && c.w <= 200 && c.h >= 20 && c.h <= 200) || Math.abs(c.w - c.h) > 6) continue;
      if (!(c.top >= 0 && c.top < 160)) continue;
      const avatarish = /avatar/i.test(c.cls || '') || /avatar/i.test(c.src) || /avatar|profile|account/i.test(c.alt || '');
      if (!avatarish) continue;
      let score = 10 - c.top / 20;
      if (/avatar/i.test(c.src)) score += 3;
      if (c.w >= 28) score += 1;
      if (score > bestScore) { best = c; bestScore = score; }
    }
    return best ? best.src : '';
  }
  if (typeof globalThis !== 'undefined') globalThis.__autotokPickAvatar = pickAvatar;
  if (typeof document === 'undefined' || typeof chrome === 'undefined' || !chrome.runtime || !chrome.runtime.sendMessage) return;
  if (window.top !== window || window.__autotokAvatar) return;
  window.__autotokAvatar = true;

  function clsChain(el) {
    let s = '';
    for (let i = 0, e = el; e && i < 4; i++, e = e.parentElement) s += ' ' + (typeof e.className === 'string' ? e.className : '') + ' ' + (e.getAttribute && e.getAttribute('data-e2e') || '');
    return s;
  }
  function collect() {
    const out = [];
    for (const img of document.images) {
      const r = img.getBoundingClientRect();
      out.push({ src: img.currentSrc || img.src, cls: clsChain(img), alt: img.alt || '', top: r.top, w: r.width, h: r.height });
    }
    for (const el of document.querySelectorAll('[class*="vatar"]')) {   // avatars drawn as CSS background
      const m = /url\(["']?([^"')]+)["']?\)/.exec(getComputedStyle(el).backgroundImage || '');
      if (!m) continue;
      const r = el.getBoundingClientRect();
      out.push({ src: m[1], cls: clsChain(el), alt: '', top: r.top, w: r.width, h: r.height });
    }
    return out;
  }

  let lastSent = '', timer = null, tries = 0;
  function scan() {
    timer = null;
    let url = '';
    try { url = pickAvatar(collect()); } catch (_) { /* ignore */ }
    if (url && url !== lastSent) {
      lastSent = url;
      chrome.runtime.sendMessage({ type: 'avatarSeen', url, where: location.pathname.slice(0, 60) }).catch(() => {});
    }
    // Studio renders the header late: keep looking for ~2 minutes after load, then rely on DOM mutations (throttled).
    if (!url && ++tries < 24) timer = setTimeout(scan, 5000);
  }
  function later(ms) { if (!timer) timer = setTimeout(scan, ms); }
  later(1500);
  try { new MutationObserver(() => { if (!lastSent) later(1500); }).observe(document.documentElement, { childList: true, subtree: true }); } catch (_) { /* ignore */ }
})();
