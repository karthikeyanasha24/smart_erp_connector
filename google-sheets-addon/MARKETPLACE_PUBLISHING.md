# Publishing SmarterP to Google Workspace Marketplace

Checklist for listing **SmarterP ERP Connector** (Google Sheets add-on) publicly or privately.

---

## Before you start

| Decision | Recommendation |
|----------|----------------|
| **Public vs private** | **Private** first (your Workspace org only) — no Google review, faster. **Public** requires review + OAuth verification (days to weeks). |
| **Audience** | You cannot change public/private after publish — choose carefully. |
| **Cloud project** | Create a **standard** GCP project and link it to the Apps Script project (default GCP project cannot publish). |

---

## Step-by-step (public listing)

### 1. Google Cloud & Apps Script

1. [Google Cloud Console](https://console.cloud.google.com/) → **Create project** (e.g. `smarterp-marketplace`).
2. Apps Script → **Project Settings** → **Google Cloud Platform (GCP) Project** → change to the new project number.
3. Enable **Google Workspace Marketplace SDK** on that GCP project.
4. Enable **Google Apps Script API** (for clasp): https://script.google.com/home/usersettings

### 2. OAuth consent screen

**APIs & Services → OAuth consent screen**

| Field | What to use |
|-------|-------------|
| User type | **External** (public) or **Internal** (Workspace org only) |
| App name | **SmarterP ERP Connector** (must match Marketplace listing) |
| Support email | Your support email |
| App logo | 120×120 PNG |
| App domain | Your verified domain (e.g. `yourcompany.com`) |
| **Privacy policy** | `https://yourdomain.com/smarterp/privacy.html` |
| **Terms of service** | `https://yourdomain.com/smarterp/terms.html` |
| Authorized domains | Domain where policies + homepage are hosted |

**Scopes** (must match `appsscript.json`):

- `https://www.googleapis.com/auth/spreadsheets.currentonly`
- `https://www.googleapis.com/auth/script.container.ui`
- `https://www.googleapis.com/auth/script.external_request`

`script.external_request` + storing backend credentials usually triggers **OAuth verification** for public apps. Plan 1–4 weeks for Google review.

### 3. Host required web pages (you must own the domain)

Host the HTML files on HTTPS (dev: copy from `google-sheets-addon/legal/` to `public/smarterp/` — served at `http://localhost:5173/smarterp/`):

| Page | URL example | Used in |
|------|-------------|---------|
| **Homepage** | `https://yourdomain.com/smarterp/` | Marketplace listing, OAuth |
| **Privacy policy** | `https://yourdomain.com/smarterp/privacy.html` | OAuth + Marketplace |
| **Terms of service** | `https://yourdomain.com/smarterp/terms.html` | Marketplace |
| **Support / Help** | `https://yourdomain.com/smarterp/support.html` | Marketplace “Support URL” |

Options to host:

- Company website / static hosting (Netlify, Vercel, GitHub Pages)
- Subpath on your Render backend (static files in FastAPI or separate static site)
- Google Sites on a **verified** Workspace domain (less ideal but works for small teams)

**Important:** Privacy policy must be on a domain **you verify** in Google Search Console or GCP (same domain as homepage is easiest).

Customize templates in `legal/` — replace `[COMPANY]`, `[EMAIL]`, `[DOMAIN]`, `[BACKEND URL]` before publishing.

### 4. Marketplace store listing assets

| Asset | Spec |
|-------|------|
| **Icon** | 128×128 and 32×32 PNG, square, transparent background, no Google trademarks |
| **Screenshots** | At least 1; 1280×800 recommended; show menu, Setup, AI sidebar, data in sheet |
| **Short description** | ≤200 chars |
| **Detailed description** | What it does, that it connects to **your** SmarterP backend, periods (MTD/Today/YTD) |
| **Category** | Business tools / Analytics |
| **Pricing** | Free, or link to pricing page if paid |

**Description must mention:** Users need a SmarterP backend URL and account; data is fetched from **your ERP API**, not stored by Google beyond Sheets cells the user writes.

### 5. Configure Marketplace SDK

In GCP → **Google Workspace Marketplace SDK** → **Store listing**:

- Application type: **Google Workspace add-on**
- Sheets add-on: link Apps Script deployment
- Install settings: Everyone or admins only
- **Support URL** → `support.html`
- **Privacy policy URL** → `privacy.html`
- **Terms of service URL** → `terms.html`
- **Developer website** → homepage

### 6. Test account for Google reviewers

Provide in the submission form:

- Backend URL (production, HTTPS, stable — not localhost)
- Test email + password (RBAC user with `query:*` permission)
- Short steps: Open sheet → SmarterP → Settings → Test → Pull Dashboard / AI query

### 7. Deploy add-on version

1. Apps Script → **Deploy** → **New deployment** → type **Add-on**.
2. Or use clasp: `clasp deploy --description "Marketplace v1"`
3. Submit deployment ID in Marketplace SDK.

### 8. Submit for review

- Fix all SDK validation errors first.
- Submit → status **Pending review** (typically several days).
- Respond quickly if Google requests OAuth or policy changes.

---

## URLs to enter in Marketplace (copy after hosting)

```
Homepage:          https://[DOMAIN]/smarterp/
Privacy policy:    https://[DOMAIN]/smarterp/privacy.html
Terms of service:  https://[DOMAIN]/smarterp/terms.html
Support / Help:    https://[DOMAIN]/smarterp/support.html
```

---

## What your privacy policy must disclose (SmarterP-specific)

- **Google data:** Current spreadsheet only (`spreadsheets.currentonly`); UI dialogs/sidebar (`script.container.ui`).
- **External API:** Add-on calls **your configured backend** (`script.external_request`); URL, email, password stored in **Apps Script Script Properties** (Google-hosted, per-user/script).
- **ERP data:** Query results written into sheets the user chooses; you do not sell sheet content to third parties.
- **Retention:** Credentials until user clears Settings or deletes script properties.
- **Subprocessors:** Google (Apps Script, Sheets), your hosting provider (e.g. Render), ERP database host.
- **Contact:** Support email for privacy requests.

---

## Common rejection reasons (avoid these)

- Privacy link goes to 404 or unrelated page
- OAuth app still in **Testing** with only test users (public apps need **Production** + verification)
- App name on consent screen ≠ Marketplace name
- Broken backend during review
- Using “Google” in the product name/logo incorrectly
- `http://` backend URL (must be **HTTPS**)

---

## Faster path: private (internal) app

1. OAuth consent screen → **Internal** (same Workspace domain as publisher).
2. Marketplace SDK → visibility **Private**.
3. Publish to organization — **no** public Marketplace review (still good practice to host privacy/terms).

---

## Help content in the add-on

`Code.gs` → `showHelp()` is in-product help. Point Marketplace **Support URL** to `support.html` for setup steps, FAQ, and contact.

---

## Links

- [How to publish](https://developers.google.com/workspace/marketplace/how-to-publish)
- [App review requirements](https://developers.google.com/workspace/marketplace/about-app-review)
- [Program policies](https://developers.google.com/workspace/marketplace/terms/policies)
- [Publish add-on overview](https://developers.google.com/workspace/add-ons/how-tos/publish-add-on-overview)
- [OAuth verification](https://support.google.com/cloud/answer/9110914)
