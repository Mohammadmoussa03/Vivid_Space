import axios from 'axios';

// Relative by default so requests stay same-origin and flow through the Vite
// dev proxy (and any tunnel) to the backend. Override with VITE_API_URL if the
// backend is hosted elsewhere.
const BASE_URL = import.meta.env.VITE_API_URL || '/api';

// JWTs live in httpOnly cookies the browser sends automatically — they are never
// readable from JS/localStorage/the console. The only auth cookie JS can read is
// Django's `csrftoken`, which we echo back in the X-CSRFToken header so unsafe
// requests pass the backend's CSRF check.
function getCsrfToken() {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true, // send/receive the httpOnly auth cookies
});

const UNSAFE_METHODS = new Set(['post', 'put', 'patch', 'delete']);
api.interceptors.request.use((config) => {
  if (UNSAFE_METHODS.has((config.method || 'get').toLowerCase())) {
    const token = getCsrfToken();
    if (token) config.headers['X-CSRFToken'] = token;
  }
  return config;
});

// Let AuthContext react when the session is truly gone (refresh failed).
let onUnauthorized = null;
export function setUnauthorizedHandler(fn) { onUnauthorized = fn; }

// Transparent access-token refresh on 401 (once per request). The refresh token
// rides in its own httpOnly cookie, so the call needs no body.
let refreshing = null;
api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const { config, response } = error;
    const url = config?.url || '';
    const isAuthCall = url.includes('/auth/token/refresh') || url.includes('/auth/login');
    if (response?.status === 401 && config && !config._retry && !isAuthCall) {
      config._retry = true;
      try {
        refreshing = refreshing || api.post('/auth/token/refresh/');
        await refreshing;
        refreshing = null;
        return api(config); // retry with the fresh cookie
      } catch {
        refreshing = null;
        if (onUnauthorized) onUnauthorized();
      }
    }
    return Promise.reject(error);
  }
);

export default api;
