// Browser session management shared by every page. Owned by Person 1.
(function () {
  const cfg = window.CAMPUS_CONFIG || {};
  const $ = (id) => document.getElementById(id);
  let supabaseClient = null;
  // Recovery must stay on the account page until the new password is saved.
  let recoveringPassword = !!(location.hash && /(?:^#|&)type=recovery(?:&|$)/.test(location.hash));
  if (window.sessionStorage) {
    recoveringPassword = recoveringPassword || window.sessionStorage.getItem("campus_password_recovery") === "1";
    if (recoveringPassword) window.sessionStorage.setItem("campus_password_recovery", "1");
  }
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
    if ($("password-sign-in-form")) $("password-sign-in-form").hidden = false;
    if ($("registration-details")) $("registration-details").hidden = false;
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
      if ($("password-sign-in-form")) $("password-sign-in-form").hidden = true;
      if ($("registration-details")) $("registration-details").hidden = true;
      if ($("password-update-hint") && recoveringPassword) $("password-update-hint").textContent = "Choose your new password below. Then use it whenever you sign in.";
      document.dispatchEvent(new CustomEvent("campus:profile-ready", {detail: profile}));
      if (location.pathname === "/sign-in" && window.sessionStorage && !recoveringPassword) {
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
          supabaseClient.auth.onAuthStateChange((event, session) => {
            if (event === "PASSWORD_RECOVERY") {
              recoveringPassword = true;
              if (window.sessionStorage) window.sessionStorage.setItem("campus_password_recovery", "1");
            }
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

    function allowedEmail(input) {
      const email = input.value.trim();
      if (email.split("@").length !== 2 || email.split("@")[1].toLowerCase() !== cfg.allowed_email_domain) {
        showError("Use your @" + cfg.allowed_email_domain + " email address.");
        input.focus();
        return null;
      }
      return email;
    }
    function newPassword(input, confirmation) {
      if (input.value.length < 8) { showError("Choose a password with at least 8 characters."); input.focus(); return null; }
      if (input.value !== confirmation.value) { showError("The passwords do not match."); confirmation.focus(); return null; }
      return input.value;
    }
    function authError(error) {
      if (error.status === 429) return "Too many attempts. Wait a little before trying again.";
      if (error.status >= 500 || error.name === "AuthRetryableFetchError") return "Sign-in service is temporarily unavailable. Try again shortly.";
      if (error.code === "email_not_confirmed") return "Confirm your UNC email using the account confirmation email, then sign in.";
      if (error.code === "weak_password") return "Choose a stronger password with at least 8 characters.";
      return "Could not sign in. Check your email and password, or use password recovery.";
    }
    // Submit locks also cover recovery so an accidental repeat never sends two emails.
    function submitHandler(form, handler) {
      if (!form) return;
      let pending = false;
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (pending) return;
        showError("");
        if ($("auth-hint")) $("auth-hint").textContent = "";
        pending = true;
        const buttons = Array.from(form.querySelectorAll("button"));
        buttons.forEach((button) => { button.disabled = true; });
        try { await handler(await clientReady); }
        catch (_) { showError("Sign-in service is unavailable. Try again shortly."); }
        finally { pending = false; buttons.forEach((button) => { button.disabled = false; }); }
      });
    }
    submitHandler($("password-sign-in-form"), async (client) => {
      const email = allowedEmail($("email"));
      if (!email) return;
      if (!$("password").value) { showError("Enter your password."); return; }
      const { error } = await client.auth.signInWithPassword({ email, password: $("password").value });
      $("password").value = "";
      if (error) { showError(authError(error)); return; }
      await refreshSessionStatus();
    });
    submitHandler($("password-sign-up-form"), async (client) => {
      const email = allowedEmail($("signup-email"));
      const password = newPassword($("signup-password"), $("signup-password-confirm"));
      if (!email || !password) return;
      const { data, error } = await client.auth.signUp({ email, password,
        options: { emailRedirectTo: location.origin + "/sign-in" } });
      $("signup-password").value = "";
      $("signup-password-confirm").value = "";
      if (error) { showError(authError(error)); return; }
      if (data?.session) {
        api.setToken(data.session.access_token);
        $("auth-hint").textContent = "Account created. You're signed in and ready to test.";
        await refreshSessionStatus();
        return;
      }
      $("auth-hint").textContent = "Check your UNC inbox to confirm your account once, then sign in with your password. If you already have an account, sign in or use password recovery.";
    });
    const recoveryButton = $("password-recovery");
    if (recoveryButton) recoveryButton.addEventListener("click", async () => {
      if (recoveryButton.disabled) return;
      showError("");
      $("auth-hint").textContent = "";
      const email = allowedEmail($("email"));
      if (!email) return;
      recoveryButton.disabled = true;
      try {
        const client = await clientReady;
        const { error } = await client.auth.resetPasswordForEmail(email, { redirectTo: location.origin + "/sign-in" });
        if (error) { showError(error.status === 429 ? "Email requests are temporarily limited. Wait before requesting another reset email." : "Could not send a recovery email. Try again shortly."); return; }
        $("auth-hint").textContent = "If this email has an account, a recovery link is on its way. Open it to set your password. You only need this email when setting or recovering a password.";
      } catch (_) { showError("Sign-in service is unavailable. Try again shortly."); }
      finally { recoveryButton.disabled = false; }
    });
    submitHandler($("password-update-form"), async (client) => {
      $("password-update-status").textContent = "";
      const password = newPassword($("new-password"), $("new-password-confirm"));
      if (!password) return;
      const { data, error: sessionError } = await client.auth.getSession();
      if (sessionError || !data?.session) { showError("Open your recovery link or sign in before setting a password."); return; }
      const { error } = await client.auth.updateUser({ password });
      $("new-password").value = "";
      $("new-password-confirm").value = "";
      if (error) { showError(error.code === "weak_password" ? "Choose a stronger password." : "Could not save your password. Try again."); return; }
      recoveringPassword = false;
      if (window.sessionStorage) window.sessionStorage.removeItem("campus_password_recovery");
      $("password-update-status").textContent = "Password saved. Future sign-ins use your email and password.";
      await refreshSessionStatus();
    });
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
        if(window.sessionStorage) {
          window.sessionStorage.removeItem("campus_request_draft");
          window.sessionStorage.removeItem("campus_password_recovery");
        }
        recoveringPassword = false;
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
