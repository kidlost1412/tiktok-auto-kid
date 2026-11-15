<!DOCTYPE html>
<html lang="vi" class="dark">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="robots" content="noindex">
        <title>@yield('title') - TikTok Auto Kid</title>
        <script>
            // Cùng quy ước với app: mặc định Tối, localStorage.theme = 'light' thì Sáng.
            (function () {
                var t = 'dark';
                try { t = localStorage.getItem('theme') === 'light' ? 'light' : 'dark'; } catch (e) {}
                document.documentElement.classList.toggle('dark', t === 'dark');
            })();
        </script>
        <style>
            :root { color-scheme: light; --bg:#ffffff; --fg:#292928; --muted:#6b6b68; --card:#ffffff; --border:#e4e4e0; --accent:#6d28d9; --accent-fg:#ffffff; --soft:#ede9fe; --soft-fg:#6d28d9; }
            .dark { color-scheme: dark; --bg:#0d0e12; --fg:#f1f1f4; --muted:#9a9ca8; --card:#15171d; --border:#2a2d38; --accent:#8b5cf6; --accent-fg:#ffffff; --soft:#25203d; --soft-fg:#c4b5fd; }
            * { box-sizing: border-box; }
            body { margin:0; min-height:100vh; display:grid; place-items:center; padding:24px; background:var(--bg); color:var(--fg); font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; line-height:1.5; }
            .card { width:100%; max-width:30rem; text-align:center; background:var(--card); border:1px solid var(--border); border-radius:16px; padding:40px 28px 32px; box-shadow:0 12px 28px -12px rgb(0 0 0 / .25); }
            .brand { display:inline-flex; align-items:center; gap:10px; font-weight:600; letter-spacing:-.015em; margin-bottom:28px; }
            .logo { display:grid; place-items:center; width:34px; height:34px; border-radius:10px; background:linear-gradient(135deg,#8b5cf6,#6d28d9); color:#fff; }
            .logo svg { width:18px; height:18px; }
            .code { font-size:4.5rem; line-height:1; font-weight:700; letter-spacing:-.04em; color:var(--soft-fg); margin:0 0 8px; }
            h1 { font-size:1.375rem; margin:0 0 8px; letter-spacing:-.015em; }
            p { margin:0 0 28px; color:var(--muted); }
            .actions { display:flex; flex-wrap:wrap; gap:10px; justify-content:center; }
            .btn { display:inline-flex; align-items:center; justify-content:center; height:40px; padding:0 18px; border-radius:10px; font-weight:500; font-size:.9375rem; text-decoration:none; border:1px solid var(--border); color:var(--fg); }
            .btn:hover { background:var(--soft); }
            .btn.primary { background:var(--accent); border-color:var(--accent); color:var(--accent-fg); }
            .btn.primary:hover { filter:brightness(1.1); }
            .btn:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
        </style>
    </head>
    <body>
        <main class="card">
            <div class="brand">
                <span class="logo" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 7.917v4.034a9.948 9.948 0 0 1 -5 -1.951v4.5a6.5 6.5 0 1 1 -8 -6.326v4.326a2.5 2.5 0 1 0 4 2v-11.5h4.083a6.005 6.005 0 0 0 4.917 4.917"/></svg>
                </span>
                TikTok Auto Kid
            </div>
            <div class="code">@yield('code')</div>
            <h1>@yield('heading')</h1>
            <p>@yield('message')</p>
            <div class="actions">
                <a class="btn primary" href="/nha">Về Khu Tự Trị</a>
                <a class="btn" href="/auto">Tự động đăng</a>
                @yield('extra')
            </div>
        </main>
    </body>
</html>
