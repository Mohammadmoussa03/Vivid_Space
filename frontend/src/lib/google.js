// Google Identity Services loader.
//
// The GIS script is fetched lazily (only when an auth modal actually opens) and
// exactly once per page, no matter how many buttons ask for it. The client id
// is public by design — it identifies the app, it doesn't authorise anything;
// the backend re-verifies every token's signature and `aud` before trusting it.
const SRC = 'https://accounts.google.com/gsi/client';

export const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';

// Blank client id = the feature is off. Callers use this to hide the button
// rather than rendering one that can only fail.
export const googleEnabled = () => !!GOOGLE_CLIENT_ID;

let pending = null;
let initialized = false;
// GIS keeps one global config per page, so initialize() must be called exactly
// once — calling it again (switching login↔register, or React StrictMode's
// double-invoked effects in dev) logs a warning and silently discards the
// earlier instance. The live callback is read through this holder instead.
let credentialHandler = null;

export function loadGoogleIdentity() {
  if (!GOOGLE_CLIENT_ID) return Promise.reject(new Error('Google sign-in is not configured.'));
  if (window.google?.accounts?.id) return Promise.resolve(window.google.accounts.id);
  if (pending) return pending;

  pending = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => {
      if (window.google?.accounts?.id) resolve(window.google.accounts.id);
      else reject(new Error('Google sign-in failed to initialise.'));
    };
    script.onerror = () => {
      // Let a later attempt retry — a blocked/offline first load shouldn't
      // poison the button for the rest of the session.
      pending = null;
      reject(new Error('Google sign-in could not be loaded.'));
    };
    document.head.appendChild(script);
  });
  return pending;
}

/** Load GIS, configure it once, and point it at `onCredential`. */
export async function initGoogleIdentity(onCredential) {
  const gid = await loadGoogleIdentity();
  credentialHandler = onCredential;
  if (!initialized) {
    gid.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: (resp) => credentialHandler?.(resp.credential),
      ux_mode: 'popup',
      cancel_on_tap_outside: true,
    });
    initialized = true;
  }
  return gid;
}
