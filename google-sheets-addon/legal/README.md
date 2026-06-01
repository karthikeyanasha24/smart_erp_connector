# Legal pages (Marketplace / OAuth)

**Source files** live here. For the web app dev server and production build, copy them to:

```
project/public/smarterp/
```

Then they are available at:

- `http://localhost:5173/smarterp/privacy.html` (Vite dev)
- `https://yourdomain.com/smarterp/privacy.html` (after `npm run build` deploy)

Vite only serves static files from `public/`, not this folder directly.

After editing HTML here, run:

```powershell
Copy-Item google-sheets-addon\legal\*.html public\smarterp\ -Force
```
