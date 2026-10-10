// Sign-in behavior and session status. Owned by Person 1.
//
// sandbox mode:  token is "sandbox:<email>" for a seeded user (labeled, not
//                real verification).
// supabase mode: Supabase JS (loaded from the CDN only in this mode) sends a
//                magic link; on return we store the access token. Only the
//                public anon key is ever present in the browser.

(function () {
  const cfg = window.CAMPUS_CONFIG || {};
  const $ = (id) => document.getElementById(id);

  async function refreshSessionStatus() {
    const status = $("session-status");
    const navSignIn = $("nav-sign-in");
    if (!status) return;
    if (!api.getToken()) {
      status.textContent = "Not signed in. Browsing only.";
      if (navSignIn) navSignIn.textContent = "Sign in";
      return;
    }
    try {
      const { profile } = await api.get("/api/me");
      status.innerHTML = "";
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
    } catch (err) {
      if (err instanceof api.ApiError && (err.status === 401 || err.status === 403)) {
        status.textContent = err.message;
        if (err.status === 401) api.setToken(null);
      } else {
        status.textContent = "Could not check session.";
      }
    }
  }

  function showError(message) {
    const el = $("sign-in-error");
    if (el) el.textContent = message || "";
  }

  // --- sandbox ---
  const sandboxForm = $("sandbox-form");
  if (sandboxForm) {
    sandboxForm.addEventListener("submit", (event) => {
      event.preventDefault();
      showError("");
      const email = $("sandbox-email").value;
      api.setToken("sandbox:" + email);
      refreshSessionStatus();
    });
  }

  // --- supabase magic link ---
  const magicForm = $("magic-link-form");
  if (magicForm && cfg.auth_mode === "supabase") {
    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js";
    script.onload = async () => {
      const client = window.supabase.createClient(cfg.supabase_url, cfg.supabase_anon_key);
      // Returning from the emailed link: the session is in the URL fragment.
      const { data } = await client.auth.getSession();
      if (data && data.session) {
        api.setToken(data.session.access_token);
        history.replaceState(null, "", location.pathname);
        refreshSessionStatus();
      }
      client.auth.onAuthStateChange((_event, session) => {
        api.setToken(session ? session.access_token : null);
        refreshSessionStatus();
      });
      magicForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        showError("");
        const email = $("email").value.trim();
        const { error } = await client.auth.signInWithOtp({
          email,
          options: { emailRedirectTo: location.origin + "/sign-in" },
        });
        if (error) { showError(error.message); return; }
        $("magic-link-hint").textContent = "Check your inbox for the sign-in link.";
      });
    };
    document.head.appendChild(script);
  }

  const signOut = $("sign-out");
  if (signOut) {
    signOut.addEventListener("click", () => {
      api.setToken(null);
      const meCard = $("me-card");
      if (meCard) meCard.hidden = true;
      signOut.hidden = true;
      refreshSessionStatus();
    });
  }

  document.addEventListener("campus:auth-changed", refreshSessionStatus);
  refreshSessionStatus();
})();
