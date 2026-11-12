<!DOCTYPE html>
<html lang="vi" class="dark">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="csrf-token" content="{{ csrf_token() }}">
        <script>
            // Áp giao diện Sáng/Tối trước khi vẽ để không bị nháy; mặc định Tối.
            (function () {
                var t = 'dark';
                try { t = localStorage.getItem('theme') === 'light' ? 'light' : 'dark'; } catch (e) {}
                document.documentElement.classList.toggle('dark', t === 'dark');
            })();
        </script>
        <title data-inertia>{{ config('app.name', 'TikTok Auto Kid') }}</title>

        <link rel="icon" href="/favicon.ico" sizes="any">
        <link rel="icon" href="/favicon.svg" type="image/svg+xml">

        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400..700&family=Outfit:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">

        @vite(['resources/css/app.css', 'resources/js/app.ts'])
        @inertiaHead
    </head>
    <body class="font-sans antialiased">
        @inertia
    </body>
</html>
