// Rendering adapters for catalog suggestions and private completed purchases.
// Uses existing APIs only. No recommendation scores or inferred transactions.
(function () {
  "use strict";
  const C = window.components;
  const enc = encodeURIComponent;
  const message = (host, text) => C.clear(host).append(C.el("p", { className: "sidebar-empty", text }));

  function completedPurchases(exchanges, profileId) {
    if (!profileId) return [];
    return (exchanges || []).filter((e) => e.mode === "sale" && e.status === "completed" && e.requester_id === profileId);
  }

  function catalogSymbol() {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    for (const [name, value] of Object.entries({ viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "1.7", "stroke-linecap": "round", "stroke-linejoin": "round" })) svg.setAttribute(name, value);
    // Same original geometry as the listing icon in templates/_icons.html.
    svg.innerHTML = '<path d="m3 7 9-4 9 4v13H3V7ZM3 7l9 4 9-4M12 11v9M12 3v5"/>';
    return C.el("span", { className: "sidebar-thumbnail", "aria-hidden": "true" }, svg);
  }

  function renderRecommended(host, data) {
    // Future personalized data must be explicitly identified by its provider.
    // This application currently supplies only ordinary catalog suggestions.
    C.clear(host);
    const items = data.items || [];
    if (!items.length) { message(host, "No browsing suggestions available."); return; }
    const list = C.el("ul", { className: "sidebar-list" });
    items.slice(0, 3).forEach((item) => {
      const service = (item.allowed_modes || []).includes("service");
      let terms;
      if (service) terms = api.formatCents(item.service_price_cents) + " per session";
      else if ((item.allowed_modes || []).includes("borrow")) terms = item.rental_fee_cents === 0 ? "Free loan · deposit may apply" : api.formatCents(item.rental_fee_cents) + " rental fee · deposit separate";
      else terms = api.formatCents(item.sale_price_cents) + " to buy";
      list.append(C.el("li", {}, C.el("a", { href: "/listings/" + enc(item.id) },
        item.public_photo_url ? C.el("img", { src: item.public_photo_url, alt: "", loading: "lazy" }) : catalogSymbol(),
        C.el("span", {}, C.el("strong", { text: item.title }), C.el("small", { text: terms })) )));
    });
    host.append(list);
  }

  function renderPreviousBuys(host, data) {
    C.clear(host);
    const purchases = completedPurchases(data.exchanges, data.profileId);
    if (!purchases.length) { message(host, "No completed purchases yet."); return; }
    host.append(C.el("ul", { className: "sidebar-list" }, purchases.slice(0, 3).map((e) =>
      C.el("li", {}, C.el("a", { href: "/exchanges/" + enc(e.id) },
        C.el("span", {}, C.el("strong", { text: (e.listing || {}).title || "Purchase details" }), C.el("small", { text: "Completed purchase" })))))));
  }

  function meetingSpotCatalog(spots) {
    return C.el("div", { className: "meeting-catalog" },
      C.el("p", { className: "field__hint", text: "All active catalog spots, unranked. The catalog has no coordinates or routing data." }),
      C.el("ul", {}, (spots || []).map((spot) => C.el("li", {},
        C.el("strong", { text: spot.label }), C.el("span", { text: spot.public_area }),
        C.el("p", { text: spot.access_notes || "Access notes not recorded." })))),
      C.el("p", { className: "field__hint", text: "These are recorded catalog notes, not live reports. Lighting, cameras, opening hours, and current activity are not provided as separate attributes. No location is guaranteed safe." }));
  }

  window.campusDiscovery = { completedPurchases, renderRecommended, renderPreviousBuys, meetingSpotCatalog };

  const suggestions = document.getElementById("recommended-items");
  const history = document.getElementById("previous-buys");
  if (suggestions && history) {
    message(suggestions, "Loading browsing suggestions…");
    api.get("/api/listings").then(({ listings }) => renderRecommended(suggestions, { kind: "catalog", items: (listings || []).filter((l) => l.status === "available") }))
      .catch(() => message(suggestions, "Browsing suggestions are temporarily unavailable."));
    let generation = 0;
    async function loadHistory() {
      const current = ++generation;
      const token = api.getToken();
      // Clear private content immediately when identity changes.
      message(history, token ? "Loading your purchases…" : "Sign in to see your completed purchases.");
      if (!token) return;
      try {
        const { profile } = await api.get("/api/me");
        if (current !== generation || token !== api.getToken()) return;
        const { exchanges } = await api.get("/api/exchanges");
        if (current !== generation || token !== api.getToken()) return;
        renderPreviousBuys(history, { profileId: profile.id, exchanges });
      } catch (_) {
        if (current === generation && token === api.getToken()) message(history, "Purchase history is temporarily unavailable.");
      }
    }
    document.addEventListener("campus:auth-changed", loadHistory);
    window.addEventListener("storage", (event) => { if (event.key === "campus_current_token") loadHistory(); });
    loadHistory();
  }

  // Public, read-only catalog in the account area. No unsaved profile control.
  if (document.body.dataset.page === "account") {
    const account = document.getElementById("me-card");
    if (!account) return;
    const catalog = C.el("div", {});
    const disclosure = C.el("details", { className: "meetup-reference" },
      C.el("summary", { text: "Campus meetup spots" }),
      C.el("p", { text: "Profile meetup preferences and private participant locations cannot be saved yet. For item exchanges, propose a catalog spot in the offer; both participants must accept it." }), catalog);
    account.append(disclosure);
    api.get("/api/meeting-spots").then(({ meeting_spots }) => {
      if (!meeting_spots.length) message(catalog, "No active campus spots in the catalog.");
      else C.clear(catalog).append(meetingSpotCatalog(meeting_spots));
    }).catch(() => message(catalog, "The meeting-spot catalog is temporarily unavailable."));
  }
})();
