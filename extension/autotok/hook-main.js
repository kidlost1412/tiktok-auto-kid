// MAIN-world hook, run_at document_start (before TikTok's SDK wraps XMLHttpRequest/fetch).
// Policy for POST /tiktok/web/project/post/v1/ once armed by content.js (per-job nonce):
//   - EVERYTHING is blocked (never fabricated as success: the page sees a network error, we report 'blocked')
//     except the one XHR object api-main.js hands to allow() right before its own send. allow() is single-shot.
//   - fetch to that endpoint is always blocked (our publisher uses XHR only, as browser_publish.py does).
// Unarmed: pass-through, except that a manual /project/post/ carrying anchors is OBSERVED after it was sent (K4 passive capture).
(function () {
  if (window.__autotokHook) return;

  const POST_RE = /\/tiktok\/web\/project\/post\/v1\//;
  const MAX_BODY = 64 * 1024;
  const st = { nonce: null, allowed: null };

  const nativeFetch = window.fetch;
  const nativeOpen = XMLHttpRequest.prototype.open;
  const nativeSend = XMLHttpRequest.prototype.send;
  const meta = new WeakMap();

  function relay(kind, data) {
    window.postMessage(Object.assign({ __autotok: 1, kind, t: Date.now(), nonce: st.nonce }, data), location.origin);
  }

  window.addEventListener('message', (e) => {
    const d = e.data;
    if (e.source !== window || !d || d.__autotok !== 1 || d.kind !== 'arm') return;
    st.nonce = String(d.nonce || '');
    window.postMessage({ __autotok: 1, kind: 'armed', nonce: st.nonce }, location.origin);
  });

  const isPost = (method, url) => String(method).toUpperCase() === 'POST' && POST_RE.test(String(url));
  const bodyText = (b) => (typeof b === 'string' ? b.slice(0, MAX_BODY) : b == null ? '' : '[non-string body: ' + Object.prototype.toString.call(b) + ']');

  XMLHttpRequest.prototype.open = function (method, url) {
    meta.set(this, { method: String(method), url: String(url) });
    return nativeOpen.apply(this, arguments);
  };

  // The page sees a plain network error (status 0), never a success.
  function failXhr(xhr) {
    xhr.__autotokBlocked = true;
    const def = (k, v) => Object.defineProperty(xhr, k, { configurable: true, get: () => v });
    def('readyState', 4); def('status', 0); def('responseText', '');
    setTimeout(() => {
      xhr.dispatchEvent(new Event('readystatechange'));
      for (const t of ['error', 'loadend']) xhr.dispatchEvent(new ProgressEvent(t));
    }, 0);
  }

  // PASSIVE capture of the owner's OWN manual post (K4): only while unarmed (our own publishes always run armed), only after the
  // request was handed to the native send, deferred to a macrotask, never touching/replaying/delaying the request.
  // Whatever goes wrong in here is swallowed: the page must never notice.
  function captureUserPost(bodyStr) {
    if (typeof bodyStr !== 'string') return;
    setTimeout(() => {
      try {
        const lib = window.AutotokLib;
        if (st.nonce || !lib || !lib.extractAnchorCapture) return;
        const c = lib.extractAnchorCapture(bodyStr);
        if (!c) return;
        window.postMessage({ __autotok: 1, from: 'hook', kind: 'anchor-capture', anchors: c.anchors, candidates: c.candidates, keyed: c.keyed, captured_at: new Date().toISOString() }, location.origin);
      } catch (_) { /* never affects the page */ }
    }, 0);
  }

  const send = function (body) {
    const m = meta.get(this);
    if (m && st.nonce && isPost(m.method, m.url)) {
      const ok = st.allowed === this;
      st.allowed = null;                                   // single-shot, whatever happens next
      relay('req', { via: 'xhr', path: new URL(m.url, location.href).pathname, body: bodyText(body), allowed: ok });
      if (!ok) { relay('blocked', { via: 'xhr' }); failXhr(this); return; }
      return nativeSend.apply(this, arguments);
    }
    if (m && !st.nonce && typeof body === 'string' && isPost(m.method, m.url)) {
      const out = nativeSend.apply(this, arguments);       // the request goes out first, unchanged
      captureUserPost(body);
      return out;
    }
    return nativeSend.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = send;

  window.fetch = async function (input, init) {
    const url = typeof input === 'string' ? input : (input && input.url) || String(input);
    const method = (init && init.method) || (input && input.method) || 'GET';
    if (st.nonce && isPost(method, url)) {
      relay('blocked', { via: 'fetch' });
      throw new TypeError('blocked by autotok (publish is XHR-only)');
    }
    if (!st.nonce && isPost(method, url)) {                // the owner's own manual post: observe only (see captureUserPost)
      let text = init && typeof init.body === 'string' ? init.body : null, pending = null;
      if (text == null && typeof Request !== 'undefined' && input instanceof Request) { try { pending = input.clone().text(); } catch (_) { pending = null; } }
      const out = nativeFetch.apply(this, arguments);
      if (text != null) captureUserPost(text); else if (pending) pending.then(captureUserPost, () => {});
      return out;
    }
    return nativeFetch.apply(this, arguments);
  };

  // api-main.js uses this. `wrapperSend` lets it detect that the page's SDK wrapped XHR.send on top of ours.
  window.__autotokHook = {
    allow(xhr) { st.allowed = xhr; },
    wrapperSend: send,
    nativeSend,
    armed: () => !!st.nonce,
  };
})();
