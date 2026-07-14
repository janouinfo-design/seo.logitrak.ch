import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, timeout: 180000 }); // 3 min for slow LLM calls

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("logi_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    // Auto-logout only for session-auth failures — never for third-party
    // credential errors (GitHub PAT, Meta, Google...) which use 400.
    const url = err?.config?.url || "";
    const isThirdParty = /test-github|test-ftp|publish-|\/meta\/|\/gbp\/|\/linkedin\/|\/google\//.test(url);
    if (err?.response?.status === 401 && !isThirdParty) {
      localStorage.removeItem("logi_token");
      localStorage.removeItem("logi_user");
      if (window.location.pathname !== "/login" && window.location.pathname !== "/register") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);
