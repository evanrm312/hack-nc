// Browser session management shared by every page. Owned by Person 1.
(function () {
  const cfg = window.CAMPUS_CONFIG || {};
  const $ = (id) => document.getElementById(id);
  let supabaseClient = null;
  const safeDestination = (value) => typeof value === "string" && value.startsWith("/") && !value.startsWith("//") && !/[\\\r\n]/.test(value) && !value.startsWith("/sign-in") ? value : null;
  window.campusSafeDestination = safeDestination;
  const destination = typeof URLSearchParams !== "undefined" ? safeDestination(new URLSearchParams(location.search).get("next")) : null;
  if (destination && window.sessionStorage) window.sessionStorage.setItem("campus_return_to", destination);
  if (location.hash && /error=/.test(location.hash)) {
    showError("This sign-in link is invalid or expired. Request a new link when you are ready.");
    history.replaceState(null, "", location.pathname + location.search);
  }

  function showError(message) {
    const el = $("sign-in-error");
    if (el) el.textContent = message || "";
  }

  function clearProfile() {
    const card = $("me-card");
    if (card) card.hidden = true;
    const signOut = $("sign-out");
    if (signOut) signOut.hidden = true;
  }

  async function refreshSessionStatus() {
    const status = $("session-status");
    const navSignIn = $("nav-sign-in");
    if (!status) return;
    try {
      const token = await api.sessionToken();
      if (!token) {
        status.textContent = "Not signed in. Browsing only.";
        if (navSignIn) navSignIn.textContent = "Sign In";
        clearProfile();
        return;
      }
      const { profile } = await api.get("/api/me");
      status.replaceChildren();
      const name = document.createElement("span");
      name.textContent = profile.display_name + " ";
      const badge = document.createElement("span");
      badge.className = "badge" + (profile.verification_source === "supabase" ? "" : " badge--warn");
      badge.textContent = profile.badge;
      status.append(name, badge);
      if (navSignIn) navSignIn.textContent = "Account";
      const meJson = $("me-json");
      if (meJson) { meJson.textContent = JSON.stringify(profile, null, 2); $("me-card").hidden = false; }
      const signOut = $("sign-out");
      if (signOut) signOut.hidden = false;
      document.dispatchEvent(new CustomEvent("campus:profile-ready", {detail: profile}));
      if (location.pathname === "/sign-in" && window.sessionStorage) {
        const next = safeDestination(window.sessionStorage.getItem("campus_return_to"));
        if (next) { window.sessionStorage.removeItem("campus_return_to"); location.assign(next); }
      }
    } catch (err) {
      clearProfile();
      const sessionSaved = !!api.getToken();
      if (err instanceof api.ApiError && (err.status === 401 || err.status === 403)) {
        status.textContent = err.message;
      } else if (sessionSaved) {
        status.textContent = "Session saved. Account details are temporarily unavailable.";
      } else {
        status.textContent = "Could not check session. Try again shortly.";
      }
      if (navSignIn) navSignIn.textContent = sessionSaved ? "Account" : "Sign In";
      const signOut = $("sign-out");
      if (signOut) signOut.hidden = !sessionSaved;
    }
  }

  const sandboxForm = $("sandbox-form");
  if (sandboxForm) {
    sandboxForm.addEventListener("submit", (event) => {
      event.preventDefault();
      showError("");
      api.setToken("sandbox:" + $("sandbox-email").value);
    });
  }

  if (cfg.auth_mode === "supabase") {
    // Register before page scripts run, including on pages without the sign-in form.
    const clientReady = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js";
      script.onload = () => {
        try {
          supabaseClient = window.supabase.createClient(cfg.supabase_url, cfg.supabase_anon_key);
          supabaseClient.auth.onAuthStateChange((_event, session) => {
            api.setToken(session ? session.access_token : null);
            if (session && location.hash) history.replaceState(null, "", location.pathname + location.search);
          });
          resolve(supabaseClient);
        } catch (err) { reject(err); }
      };
      script.onerror = () => reject(new Error("Sign-in library could not load"));
      document.head.appendChild(script);
    });

    api.setSessionProvider(async () => {
      let client;
      try { client = await clientReady; }
      catch (_) { throw new api.ApiError(503, { error: { code: "auth_unavailable", message: "Sign-in service could not load" } }); }
      let result;
      try { result = await client.auth.getSession(); }
      catch (_) { throw new api.ApiError(503, { error: { code: "auth_unavailable", message: "Sign-in service is unavailable. Try again." } }); }
      const { data, error } = result;
      if (error) {
        if (error.status === 429 || error.status >= 500 || error.name === "AuthRetryableFetchError") {
          throw new api.ApiError(503, {error: {code: "auth_unavailable", message: "Sign-in service is temporarily unavailable. Your session is saved."}});
        }
        api.setToken(null);
        try { await client.auth.signOut({ scope: "local" }); } catch (_) { /* expired locally */ }
        throw new api.ApiError(401, { error: { code: "session_expired", message: "Session expired. Please sign in again." } });
      }
      return data && data.session ? data.session.access_token : null;
    }, async () => {
      const client = await clientReady;
      await client.auth.signOut({ scope: "local" });
      api.setToken(null);
    });

    const magicForm = $("magic-link-form");
    if (magicForm) {
      let sending = false;
      magicForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (sending) return;
        showError("");
        const email = $("email").value.trim();
        if (email.split("@").length !== 2 || email.split("@")[1].toLowerCase() !== cfg.allowed_email_domain) {
          showError("Use your @" + cfg.allowed_email_domain + " email address."); return;
        }
        sending = true;
        const button = magicForm.querySelector("button");
        if (button) button.disabled = true;
        try {
          const client = await clientReady;
          const { error } = await client.auth.signInWithOtp({
            email: $("email").value.trim(),
            options: { emailRedirectTo: location.origin + "/sign-in" },
          });
          if (error) { showError(error.status === 429 ? "Too many sign-in requests. Wait before requesting another link." : "Could not send the link. Try again shortly."); return; }
          $("magic-link-hint").textContent = "Check your inbox for the sign-in link.";
        } catch (_) { showError("Sign-in service is unavailable. Try again shortly."); }
        finally { sending = false; if (button) button.disabled = false; }
      });
    }
  }

  const signOut = $("sign-out");
  if (signOut) {
    signOut.addEventListener("click", async () => {
      showError("");
      signOut.disabled = true;
      try {
        if (cfg.auth_mode === "supabase") {
          const client = supabaseClient;
          if (!client) throw new Error("Sign-in service is unavailable");
          const { error } = await client.auth.signOut({ scope: "local" });
          if (error) throw error;
        }
        api.setToken(null);
        clearProfile();
        if(window.sessionStorage) window.sessionStorage.removeItem("campus_request_draft");
        await refreshSessionStatus();
      } catch (_) {
        showError("You are still signed in. Sign-out failed; please try again.");
      } finally {
        signOut.disabled = false;
      }
    });
  }

  document.addEventListener("campus:auth-changed", refreshSessionStatus);
  refreshSessionStatus();
})();
