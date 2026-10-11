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
  let sessionProvider = null;
  let invalidateSession = null;

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
    if (getToken() === token) return;
    try {
      if (token) window.localStorage.setItem(TOKEN_KEY, token);
      else window.localStorage.removeItem(TOKEN_KEY);
    } catch (_) { /* storage unavailable */ }
    document.dispatchEvent(new CustomEvent("campus:auth-changed"));
  }

  function setSessionProvider(provider, invalidator) {
    sessionProvider = provider;
    invalidateSession = invalidator;
  }

  async function sessionToken() {
    if (!sessionProvider) return getToken();
    const token = await sessionProvider();
    setToken(token || null);
    return token || null;
  }

  function isAnonymousRead(method, path) {
    if (method !== "GET") return false;
    const route = path.split("?", 1)[0];
    return route === "/api/health" || route === "/api/meeting-spots" ||
      /^\/api\/profiles\/[^/]+$/.test(route) ||
      /^\/api\/listings(?:\/[^/]+)?$/.test(route) ||
      /^\/api\/requests(?:\/[^/]+)?$/.test(route) ||
      route.startsWith("/media/public/");
  }

  async function request(method, path, options) {
    options = options || {};
    const headers = Object.assign({ Accept: "application/json" }, options.headers || {});
    let token;
    try { token = await sessionToken(); }
    catch (error) {
      if (!isAnonymousRead(method, path) || !(error instanceof ApiError) ||
          !["auth_unavailable", "session_expired"].includes(error.code)) throw error;
      token = null; // public browsing remains available when sign-in is down
    }
    if (token) headers.Authorization = "Bearer " + token;

    let body = options.body;
    if (body !== undefined && !(body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(body);
    }

    let response;
    try { response = await fetch(path, { method, headers, body }); }
    catch (_) { throw new ApiError(503,{error:{code:"network_unavailable",message:"Could not reach Campus Current. Your session is saved; try again."}}); }
    const text = await response.text();
    let data = null;
    if (text) {
      try { data = JSON.parse(text); } catch (_) { data = null; }
    }
    if (!response.ok) {
      const error = new ApiError(response.status, data);
      if (response.status === 401 && token && error.code === "invalid_token") {
        setToken(null);
        if (invalidateSession) {
          try { await invalidateSession(); } catch (_) { /* keep the API error */ }
        }
      }
      throw error;
    }
    return data;
  }

  if (window.addEventListener) window.addEventListener("storage", event => {
    if (event.key === TOKEN_KEY) document.dispatchEvent(new CustomEvent("campus:auth-changed"));
  });

  const zone = "America/New_York";
  const wallFormat = new Intl.DateTimeFormat("en-CA", {timeZone: zone, year:"numeric", month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit", hourCycle:"h23"});
  function timeInput(iso) {
    if (!iso || !Number.isFinite(new Date(iso).getTime())) return "";
    const p = Object.fromEntries(wallFormat.formatToParts(new Date(iso)).map(x => [x.type,x.value]));
    return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
  }
  function timeToUtc(value) {
    if (!value) return null;
    const wall = Date.parse(value + "Z");
    const candidates = [4,5].map(h => new Date(wall + h*3600000)).filter(d => Number.isFinite(d.getTime()) && timeInput(d.toISOString()) === value);
    if (candidates.length !== 1) throw new Error("Choose an unambiguous Eastern time outside the daylight-saving change.");
    return candidates[0].toISOString();
  }
  window.api = {
    ApiError,
    getToken,
    setToken,
    setSessionProvider,
    sessionToken,
    get: (path) => request("GET", path),
    post: (path, body, options) => request("POST", path, Object.assign({},options,{body: body === undefined ? {} : body})),
    put: (path, body) => request("PUT", path, {body}),
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
    timeInput, timeToUtc,
    formatTime: (iso) => {
      if (!iso) return "unknown";
      const date = new Date(iso);
      if (!Number.isFinite(date.getTime())) return "unknown";
      return new Intl.DateTimeFormat("en-US", {timeZone: zone, month:"short", day:"numeric", year:"numeric", hour:"numeric", minute:"2-digit", timeZoneName:"short"}).format(date);
    },
    formatTimeRange: (start, end) => {
      const a = new Date(start), b = new Date(end);
      if (!start || !end || !Number.isFinite(a.getTime()) || !Number.isFinite(b.getTime()) || b < a) return "unknown";
      const fmt = new Intl.DateTimeFormat("en-US", {timeZone:zone, month:"short", day:"numeric", year:"numeric", hour:"numeric", minute:"2-digit", timeZoneName:"short"});
      return fmt.formatRange(a,b);
    },
  };
})();
