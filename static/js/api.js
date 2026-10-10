// Shared API helper. Owned by Person 1. Everyone uses window.api; nobody
// calls fetch("/api/...") directly, so auth headers and error handling stay
// in one place.
//
//   const { listings } = await api.get("/api/listings");
//   const { listing } = await api.post("/api/listings", { title: "..." });
//   await api.upload("/api/listings/" + id + "/photo", "photo", fileInput.files[0]);
//
// Errors throw ApiError { status, code, message, fields } using the server's
// {"error":{"code","message","fields"}} shape.

(function () {
  const TOKEN_KEY = "campus_current_token";

  class ApiError extends Error {
    constructor(status, body) {
      const err = (body && body.error) || {};
      super(err.message || "Request failed (" + status + ")");
      this.name = "ApiError";
      this.status = status;
      this.code = err.code || "http_" + status;
      this.fields = err.fields || {};
    }
  }

  function getToken() {
    try { return window.localStorage.getItem(TOKEN_KEY); } catch (_) { return null; }
  }
  function setToken(token) {
    try {
      if (token) window.localStorage.setItem(TOKEN_KEY, token);
      else window.localStorage.removeItem(TOKEN_KEY);
    } catch (_) { /* storage unavailable */ }
    document.dispatchEvent(new CustomEvent("campus:auth-changed"));
  }

  async function request(method, path, options) {
    options = options || {};
    const headers = Object.assign({ Accept: "application/json" }, options.headers || {});
    const token = getToken();
    if (token) headers.Authorization = "Bearer " + token;

    let body = options.body;
    if (body !== undefined && !(body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(body);
    }

    const response = await fetch(path, { method, headers, body });
    const text = await response.text();
    let data = null;
    if (text) {
      try { data = JSON.parse(text); } catch (_) { data = null; }
    }
    if (!response.ok) throw new ApiError(response.status, data);
    return data;
  }

  window.api = {
    ApiError,
    getToken,
    setToken,
    get: (path) => request("GET", path),
    post: (path, body) => request("POST", path, { body: body === undefined ? {} : body }),
    patch: (path, body) => request("PATCH", path, { body }),
    del: (path) => request("DELETE", path),
    upload: (path, field, file) => {
      const form = new FormData();
      form.append(field, file);
      return request("POST", path, { body: form });
    },
    formatCents: (cents) => {
      if (cents === null || cents === undefined) return "unknown";
      return (cents / 100).toLocaleString("en-US", { style: "currency", currency: "USD" });
    },
    formatTime: (iso) => {
      if (!iso) return "unknown";
      return new Date(iso).toLocaleString("en-US", { timeZone: "America/New_York" });
    },
  };
})();
