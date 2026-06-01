/**
 * Google Drive upload via OAuth 2.0 (Google Identity Services).
 * Requires VITE_GOOGLE_CLIENT_ID — Web application client from Google Cloud Console.
 * Enable "Google Drive API" and add your app origin to Authorized JavaScript origins.
 */

const DRIVE_SCOPE = 'https://www.googleapis.com/auth/drive.file';
const TOKEN_KEY = 'smarterp_google_drive_token';
const TOKEN_EXP_KEY = 'smarterp_google_drive_token_exp';

declare global {
  interface Window {
    google?: {
      accounts: {
        oauth2: {
          initTokenClient: (config: {
            client_id: string;
            scope: string;
            callback: (resp: { access_token?: string; error?: string }) => void;
          }) => { requestAccessToken: (opts?: { prompt?: string }) => void };
          revoke: (token: string, done: () => void) => void;
        };
      };
    };
  }
}

export function isGoogleDriveConfigured(): boolean {
  // Always show Drive buttons; upload will prompt Google sign-in.
  // If VITE_GOOGLE_CLIENT_ID is not set, uploadToGoogleDrive will throw with instructions.
  return true;
}

function loadGsiScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.oauth2) {
      resolve();
      return;
    }
    const existing = document.querySelector('script[data-gsi-client]');
    if (existing) {
      existing.addEventListener('load', () => resolve());
      existing.addEventListener('error', () => reject(new Error('Failed to load Google sign-in')));
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.dataset.gsiClient = '1';
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Failed to load Google sign-in'));
    document.head.appendChild(script);
  });
}

function readCachedToken(): string | null {
  try {
    const token = sessionStorage.getItem(TOKEN_KEY);
    const exp = Number(sessionStorage.getItem(TOKEN_EXP_KEY) || 0);
    if (token && exp > Date.now() + 60_000) return token;
  } catch { /* ignore */ }
  return null;
}

function cacheToken(token: string, expiresInSec = 3500) {
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
    sessionStorage.setItem(TOKEN_EXP_KEY, String(Date.now() + expiresInSec * 1000));
  } catch { /* ignore */ }
}

export async function getGoogleAccessToken(forcePrompt = false): Promise<string> {
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim();
  if (!clientId) {
    throw new Error('Google Drive is not configured for this deployment. Contact your administrator to enable Drive integration.');
  }

  if (!forcePrompt) {
    const cached = readCachedToken();
    if (cached) return cached;
  }

  await loadGsiScript();

  return new Promise((resolve, reject) => {
    const client = window.google!.accounts.oauth2.initTokenClient({
      client_id: clientId,
      scope: DRIVE_SCOPE,
      callback: (resp) => {
        if (resp.error || !resp.access_token) {
          reject(new Error(resp.error ?? 'Google sign-in was cancelled'));
          return;
        }
        cacheToken(resp.access_token);
        resolve(resp.access_token);
      },
    });
    client.requestAccessToken(forcePrompt ? { prompt: 'consent' } : undefined);
  });
}

export interface DriveUploadResult {
  fileId: string;
  name: string;
  webViewLink?: string;
}

export async function uploadToGoogleDrive(
  blob: Blob,
  filename: string,
  mimeType: string,
  retried = false,
): Promise<DriveUploadResult> {
  const token = await getGoogleAccessToken(retried);

  const metadata = { name: filename, mimeType };
  const form = new FormData();
  form.append('metadata', new Blob([JSON.stringify(metadata)], { type: 'application/json' }));
  form.append('file', blob);

  const res = await fetch(
    'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,webViewLink',
    {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    },
  );

  if (res.status === 401 && !retried) {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_EXP_KEY);
    return uploadToGoogleDrive(blob, filename, mimeType, true);
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const msg = (err as { error?: { message?: string } })?.error?.message;
    throw new Error(msg ?? `Google Drive upload failed (${res.status})`);
  }

  const data = await res.json() as { id: string; name: string; webViewLink?: string };
  return {
    fileId: data.id,
    name: data.name,
    webViewLink: data.webViewLink ?? `https://drive.google.com/file/d/${data.id}/view`,
  };
}
