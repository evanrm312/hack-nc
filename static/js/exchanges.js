// Person 4: exchange list, private messages, and negotiating -> reserved.
// All API access uses Person 1's shared helper; all user content is plain text.
(function () {
  "use strict";
  const listPage = document.getElementById("my-exchanges-page");
  const roomPage = document.getElementById("exchange-room-page");
  if (!listPage && !roomPage) return;
  const $ = (id) => document.getElementById(id);
  const initialToken = api.getToken();
  const statusLabels = {
    negotiating: "Negotiating", reserved: "Reserved", on_loan: "On loan",
    return_pending: "Return pending", completed: "Completed",
    disputed: "Disputed", cancelled: "Cancelled",
  };
  const modeLabel = (mode) => mode === "borrow" ? "Borrow" : "Buy";
  const node = (tag, text, className) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  };
  function errorText(error) {
    const fields = Object.entries(error.fields || {}).map(([key, message]) =>
      key.replaceAll("_", " ") + ": " + message);
    return [error.message || "Unable to reach the server. Please try again.", ...fields].join("\n");
  }
  function hidePrivateContent() {
    if ($("room-content")) $("room-content").hidden = true;
    if ($("exchange-list")) $("exchange-list").replaceChildren();
    if ($("start-card")) $("start-card").hidden = true;
    if ($("participants")) $("participants").textContent = "";
    if ($("room-title")) $("room-title").textContent = "Exchange room";
    if ($("exchange-status")) $("exchange-status").textContent = "";
  }
  function sessionIsCurrent() {
    if (api.getToken() === initialToken) return true;
    hidePrivateContent();
    location.reload();
    return false;
  }
  function pageError(error) {
    $("page-error").textContent = errorText(error);
    $("page-status").textContent = "";
    if ([401, 403, 404].includes(error.status)) hidePrivateContent();
    $("sign-in-hint").hidden = ![401, 403].includes(error.status);
  }
  function changedSession() {
    hidePrivateContent();
    location.reload();
  }
  document.addEventListener("campus:auth-changed", changedSession);
  window.addEventListener("storage", (event) => {
    if (event.key === "campus_current_token") changedSession();
  });

  async function initList() {
    let listings = [];
    let profile = null;
    let loading = false;
    const requested = new URLSearchParams(location.search);
    const selectedId = requested.get("listing_id");
    function updateModes() {
      const listing = listings.find((item) => item.id === $("start-listing").value);
      $("start-mode").replaceChildren();
      if (!listing) return;
      listing.allowed_modes.forEach((mode) => {
        const option = node("option", modeLabel(mode));
        option.value = mode;
        $("start-mode").append(option);
      });
      if (listing.allowed_modes.includes(requested.get("mode"))) {
        $("start-mode").value = requested.get("mode");
      }
      updateProposal();
    }
    function updateProposal() {
      const listing = listings.find((item) => item.id === $("start-listing").value);
      if (!listing) return;
      const terms = $("start-mode").value === "sale"
        ? "Asking sale price: " + api.formatCents(listing.sale_price_cents)
        : "Proposed rental fee: " + api.formatCents(listing.rental_fee_cents)
          + " · Proposed item value: " + api.formatCents(listing.proposed_item_value_cents)
          + " · Owner's proposed collateral: " + (listing.collateral_percent ?? "unknown") + "%";
      $("listing-proposal").textContent = terms + ". Confirm final terms in the exchange room.";
    }
    async function load() {
      if (loading) return;
      loading = true;
      $("refresh-exchanges").disabled = true;
      $("page-error").textContent = "";
      $("page-status").textContent = "Loading your exchanges…";
      try {
        const me = await api.get("/api/me");
        if (!sessionIsCurrent()) return;
        profile = me.profile;
        const [exchangesResult, listingsResult] = await Promise.allSettled([
          api.get("/api/exchanges"), api.get("/api/listings"),
        ]);
        if (!sessionIsCurrent()) return;
        if (exchangesResult.status === "rejected") throw exchangesResult.reason;
        $("sign-in-hint").hidden = true;
        $("exchange-list").replaceChildren();
        const exchanges = exchangesResult.value.exchanges;
        $("page-status").textContent = exchanges.length
          ? exchanges.length + " private exchange" + (exchanges.length === 1 ? "" : "s")
          : "No exchanges yet. Choose an available item below to start a conversation.";
        exchanges.forEach((exchange) => {
          const card = node("article", undefined, "card");
          const link = node("a", exchange.listing.title);
          link.href = "/exchanges/" + encodeURIComponent(exchange.id);
          const heading = node("h2");
          heading.append(link);
          const role = exchange.owner_id === profile.id ? "Your item" : "Requested by you";
          card.append(heading,
            node("p", modeLabel(exchange.mode) + " · " + role),
            node("span", statusLabels[exchange.status] || exchange.status, "exchange-status"),
            node("p", "Offer revision " + exchange.current_offer_revision + " · Updated " + api.formatTime(exchange.updated_at) + " Eastern", "exchange-help"));
          if (exchange.status === "disputed") {
            card.append(node("p", "Disputed. No charge is triggered automatically.", "exchange-error"));
          }
          $("exchange-list").append(card);
        });
        $("start-card").hidden = false;
        if (listingsResult.status === "rejected") {
          $("listing-status").textContent = "Could not load available listings. Refresh to try again.";
          $("start-fields").disabled = true;
          return;
        }
        listings = listingsResult.value.listings.filter((listing) => listing.owner_id !== profile.id);
        $("start-listing").replaceChildren();
        listings.forEach((listing) => {
          const option = node("option", listing.title);
          option.value = listing.id;
          $("start-listing").append(option);
        });
        const selected = listings.find((listing) => listing.id === selectedId);
        if (selected) $("start-listing").value = selected.id;
        $("listing-status").textContent = !listings.length
          ? "No available items from another member. Check back after a listing is posted."
          : selectedId && !selected
            ? "The linked item is unavailable or belongs to you. Choose another available item."
            : "";
        $("start-fields").disabled = !listings.length;
        updateModes();
      } catch (error) {
        if (sessionIsCurrent()) pageError(error);
      } finally {
        loading = false;
        $("refresh-exchanges").disabled = false;
      }
    }
    $("refresh-exchanges").addEventListener("click", load);
    $("start-listing").addEventListener("change", updateModes);
    $("start-mode").addEventListener("change", updateProposal);
    $("start-exchange-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      $("start-error").textContent = "";
      $("start-fields").disabled = true;
      try {
        const body = { listing_id: $("start-listing").value, mode: $("start-mode").value };
        if (requested.get("source_request_id")) body.source_request_id = requested.get("source_request_id");
        const result = await api.post("/api/exchanges", body);
        if (sessionIsCurrent()) location.assign("/exchanges/" + encodeURIComponent(result.exchange.id));
      } catch (error) {
        if (!sessionIsCurrent()) return;
        $("start-error").textContent = errorText(error);
        if ([401, 403].includes(error.status)) pageError(error);
        $("start-fields").disabled = false;
      }
    });
    await load();
  }

  // Convert Eastern wall time explicitly; never silently use the browser's zone.
  // Reject DST gaps and repeated hours, asking for an unambiguous meeting time.
  const easternFormatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  });
  function easternInput(iso) {
    if (!iso) return "";
    const parts = Object.fromEntries(easternFormatter.formatToParts(new Date(iso)).map((part) => [part.type, part.value]));
    return parts.year + "-" + parts.month + "-" + parts.day + "T" + parts.hour + ":" + parts.minute;
  }
  function easternToUtc(value) {
    if (!value) return null;
    const wallTime = Date.parse(value + "Z");
    const candidates = [4, 5].map((hours) => new Date(wallTime + hours * 3600000))
      .filter((date) => Number.isFinite(date.getTime()) && easternInput(date.toISOString()) === value);
    if (candidates.length !== 1) {
      throw new Error("Choose a different Eastern time: this time is missing or repeated at the daylight-saving change.");
    }
    return candidates[0].toISOString();
  }
  function cents(id) {
    const value = $(id).value.trim();
    if (!/^\d+(\.\d{1,2})?$/.test(value)) throw new Error("Enter a nonnegative USD amount with at most two decimal places.");
    const [dollars, fraction = ""] = value.split(".");
    return Number(dollars) * 100 + Number(fraction.padEnd(2, "0"));
  }

  async function initRoom() {
    const base = "/api/exchanges/" + encodeURIComponent(roomPage.dataset.exchangeId);
    let profile, detail, listing, spots = [];
    let draftVersion = null, dirty = false, busy = false, refreshing = false, timer;
    let initialized = false, initializing = false;
    let displayedVersion = null;
    let historySignature = null;
    const messages = new Map();
    let after = null;
    const spotName = (id) => spots.find((spot) => spot.id === id)?.label || (id ? "Meeting spot unavailable; needs confirmation" : "Not selected");
    const participantName = (id) => {
      const participants = Object.values(detail.participants);
      return participants.find((person) => person.id === id)?.display_name || "Participant";
    };
    function moneyRows(offer) {
      if (detail.exchange.mode === "sale") return [["Sale price", api.formatCents(offer.sale_price_cents)]];
      const percentage = offer.agreed_item_value_cents
        ? (100 * offer.deposit_cents / offer.agreed_item_value_cents).toLocaleString("en-US", { maximumFractionDigits: 2 }) + "%"
        : "percentage not applicable";
      return [
        ["Rental fee", api.formatCents(offer.rental_fee_cents)],
        ["Agreed item value", api.formatCents(offer.agreed_item_value_cents)],
        ["Simulated deposit", api.formatCents(offer.deposit_cents) + " (" + percentage + ")"],
        ["Value not covered", api.formatCents(offer.uncovered_value_cents)],
        ["Simulated fee + deposit", api.formatCents(offer.rental_fee_cents + offer.deposit_cents)],
        ["Lender acknowledgment", offer.lower_deposit_acknowledged ? "Acknowledged for this revision" : "Not acknowledged"],
      ];
    }
    function summary(target, offer) {
      const snapshot = offer.condition_snapshot || {};
      const listText = (items) => items === null || items === undefined ? "Unknown" : items.length ? items.join("\n") : "None listed";
      const rows = moneyRows(offer).concat([
        ["Pickup", spotName(offer.pickup_meeting_spot_id) + "\n" + api.formatTime(offer.pickup_at) + " Eastern"],
      ]);
      if (detail.exchange.mode === "borrow") {
        rows.push(["Return", spotName(offer.return_meeting_spot_id) + "\n" + api.formatTime(offer.return_deadline) + " Eastern"]);
      }
      rows.push(["Condition", snapshot.condition?.replaceAll("_", " ") || "Unknown / needs confirmation"],
        ["Included accessories", listText(snapshot.accessories)], ["Known defects", listText(snapshot.known_defects)]);
      target.replaceChildren();
      rows.forEach(([label, value]) => target.append(node("dt", label), node("dd", value)));
    }
    function fillDraft() {
      const offer = detail.current_offer;
      const dollars = (amount) => amount === null ? "" : (amount / 100).toFixed(2);
      $("sale-price").value = dollars(offer.sale_price_cents);
      $("rental-fee").value = dollars(offer.rental_fee_cents);
      $("item-value").value = dollars(offer.agreed_item_value_cents);
      $("deposit").value = dollars(offer.deposit_cents);
      $("pickup-spot").value = offer.pickup_meeting_spot_id || "";
      $("pickup-at").value = easternInput(offer.pickup_at);
      $("return-spot").value = offer.return_meeting_spot_id || "";
      $("return-deadline").value = easternInput(offer.return_deadline);
      $("condition").value = offer.condition_snapshot.condition || "";
      $("accessories").value = (offer.condition_snapshot.accessories || []).join("\n");
      $("known-defects").value = (offer.condition_snapshot.known_defects || []).join("\n");
      draftVersion = offer.version;
      dirty = false;
      $("draft-status").textContent = "";
      draftInfo();
      updateAcceptance();
    }
    function draftInfo() {
      const spot = spots.find((item) => item.id === $("pickup-spot").value);
      $("meeting-notes").textContent = spot ? spot.public_area + ". " + (spot.access_notes || "Access notes unknown.") : "";
      if (detail.exchange.mode !== "borrow") { $("draft-deposit").textContent = ""; return; }
      try {
        const value = cents("item-value"), deposit = cents("deposit");
        $("draft-deposit").textContent = "Simulated deposit: " + api.formatCents(deposit)
          + " · Value not covered: " + api.formatCents(Math.max(value - deposit, 0))
          + ". A deposit below the agreed value requires the lender's explicit acknowledgment.";
      } catch (_) {
        $("draft-deposit").textContent = "Enter the agreed value and simulated deposit separately.";
      }
    }
    function updateAcceptance() {
      const exchange = detail.exchange, offer = detail.current_offer;
      const borrow = exchange.mode === "borrow", owner = profile.id === exchange.owner_id;
      const accepted = owner ? offer.owner_accepted_at : offer.requester_accepted_at;
      const needsAck = borrow && owner && offer.uncovered_value_cents > 0 && !offer.lower_deposit_acknowledged;
      $("acknowledgment-label").hidden = !needsAck || Boolean(accepted) || exchange.status !== "negotiating";
      $("lower-deposit-acknowledged").required = needsAck && !accepted && exchange.status === "negotiating";
      $("lower-deposit-acknowledged").disabled = busy || dirty || Boolean(accepted) || exchange.status !== "negotiating";
      $("acknowledgment-text").textContent = "I voluntarily accept "
        + api.formatCents(offer.uncovered_value_cents) + " of agreed item value not covered by this deposit. The platform does not guarantee compensation.";
      const incomplete = !offer.pickup_at || !offer.pickup_meeting_spot_id
        || (borrow && (!offer.return_deadline || !offer.return_meeting_spot_id));
      $("accept-offer").disabled = busy || dirty || incomplete || Boolean(accepted) || exchange.status !== "negotiating";
      $("accept-offer").textContent = accepted ? "You accepted revision " + offer.version : "Accept revision " + offer.version;
      $("accept-help").textContent = exchange.status === "reserved"
        ? "Both participants accepted this revision. The item is reserved."
        : exchange.status !== "negotiating" ? "This exchange is no longer negotiating."
          : dirty ? "You have unsaved terms. Propose them or use current terms before accepting."
            : incomplete ? "Propose pickup details" + (borrow ? " and a return deadline/location" : "") + " before accepting."
              : accepted ? "Waiting for the other participant to accept this same revision."
                : "Review every term before accepting. Changes clear both acceptances.";
    }
    function render() {
      const exchange = detail.exchange, offer = detail.current_offer;
      const borrow = exchange.mode === "borrow", owner = profile.id === exchange.owner_id;
      $("room-title").textContent = listing.title + " · " + modeLabel(exchange.mode);
      $("exchange-status").textContent = statusLabels[exchange.status] || exchange.status;
      $("participants").textContent = detail.participants.owner.display_name + " (owner) · "
        + detail.participants.requester.display_name + (borrow ? " (borrower)" : " (buyer)")
        + ". You are the " + (owner ? "owner" : borrow ? "borrower" : "buyer") + ".";
      $("offer-heading").textContent = "Current offer · revision " + offer.version;
      summary($("offer-summary"), offer);
      $("owner-acceptance").textContent = "Owner: " + (offer.owner_accepted_at ? "accepted revision " + offer.version : "awaiting acceptance");
      $("requester-acceptance").textContent = (borrow ? "Borrower: " : "Buyer: ")
        + (offer.requester_accepted_at ? "accepted revision " + offer.version : "awaiting acceptance");
      $("deposit-status").textContent = borrow
        ? "Simulated deposit status: " + detail.deposit_status.state.replace("simulated_", "") + ". " + detail.deposit_status.label
        : "Purchase payment is simulated. " + detail.simulation_notice;
      $("reservation-notice").hidden = exchange.status !== "reserved";
      $("offer-editor-card").hidden = exchange.status !== "negotiating";
      document.querySelectorAll("[data-mode]").forEach((field) => {
        const applies = field.dataset.mode === exchange.mode;
        field.hidden = !applies;
        field.querySelectorAll("input, select").forEach((input) => { input.disabled = !applies; input.required = applies; });
      });
      if (displayedVersion !== offer.version) $("lower-deposit-acknowledged").checked = false;
      displayedVersion = offer.version;
      if (!dirty) fillDraft();
      else if (draftVersion !== offer.version) {
        $("draft-status").textContent = "The current offer changed while you were editing. Use current terms to review the latest revision before proposing again.";
      }
      updateAcceptance();
      const signature = JSON.stringify(detail.offers);
      if (signature !== historySignature) {
        const history = $("offer-history");
        const openVersions = new Set(Array.from(history.querySelectorAll("details[open]")).map((item) => item.dataset.version));
        const focusedVersion = history.contains(document.activeElement)
          ? document.activeElement.closest("details")?.dataset.version : null;
        history.replaceChildren();
        detail.offers.slice().reverse().forEach((revision) => {
          const disclosure = node("details", undefined, "exchange-revision");
          disclosure.dataset.version = String(revision.version);
          disclosure.open = openVersions.has(disclosure.dataset.version);
          disclosure.append(node("summary", "Revision " + revision.version + " · " + api.formatTime(revision.created_at) + " Eastern"));
          const terms = node("dl", undefined, "exchange-terms");
          summary(terms, revision);
          disclosure.append(terms, node("p", "Owner: " + (revision.owner_accepted_at ? "accepted" : "not accepted")
            + " · " + (borrow ? "Borrower: " : "Buyer: ") + (revision.requester_accepted_at ? "accepted" : "not accepted")));
          history.append(disclosure);
          if (disclosure.dataset.version === focusedVersion) disclosure.querySelector("summary").focus({ preventScroll: true });
        });
        historySignature = signature;
      }
      $("room-content").hidden = false;
    }
    function renderMessages(newMessages) {
      const container = $("message-list");
      const nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 60;
      let changed = false;
      newMessages.forEach((message) => {
        if (!messages.has(message.id)) changed = true;
        messages.set(message.id, message);
      });
      const sorted = Array.from(messages.values()).sort((a, b) =>
        a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id));
      if (sorted.length) after = sorted[sorted.length - 1].created_at;
      if (changed) {
        container.replaceChildren();
        sorted.forEach((message) => {
          const item = node("li", undefined, "exchange-message" + (message.sender_id === profile.id ? " exchange-message--mine" : ""));
          const time = node("time", api.formatTime(message.created_at) + " Eastern");
          time.dateTime = message.created_at;
          item.append(node("strong", participantName(message.sender_id)), time, node("p", message.body));
          container.append(item);
        });
        if (nearBottom) container.scrollTop = container.scrollHeight;
      }
      $("message-status").textContent = sorted.length ? sorted.length + (sorted.length === 1 ? " message" : " messages") : "No messages yet. Start the conversation below.";
    }
    async function refresh() {
      if (busy || refreshing || !profile) return;
      refreshing = true;
      $("refresh-room").disabled = true;
      try {
        const [latest, conversation] = await Promise.all([
          api.get(base), api.get(base + "/messages" + (after ? "?after=" + encodeURIComponent(after) : "")),
        ]);
        if (!sessionIsCurrent()) return;
        detail = latest;
        render();
        renderMessages(conversation.messages);
        $("page-error").textContent = "";
        $("page-status").textContent = "Private exchange up to date.";
      } catch (error) {
        if (!sessionIsCurrent()) return;
        if ([401, 403, 404].includes(error.status)) clearInterval(timer);
        pageError(error);
      } finally {
        refreshing = false;
        $("refresh-room").disabled = false;
      }
    }
    async function action(errorId, work) {
      if (busy || !sessionIsCurrent()) return;
      busy = true;
      $(errorId).textContent = "";
      $("offer-fields").disabled = true;
      $("message-fields").disabled = true;
      $("accept-offer").disabled = true;
      try { await work(); }
      catch (error) {
        if (!sessionIsCurrent()) return;
        $(errorId).textContent = errorText(error);
        if ([401, 403, 404].includes(error.status)) {
          clearInterval(timer);
          pageError(error);
        }
      } finally {
        busy = false;
        $("offer-fields").disabled = false;
        $("message-fields").disabled = false;
        if (!$("room-content").hidden) await refresh();
      }
    }
    $("refresh-room").addEventListener("click", () => initialized ? refresh() : loadInitial());
    $("reset-draft").addEventListener("click", () => {
      fillDraft(); $("offer-error").textContent = ""; $("accept-error").textContent = "";
    });
    $("offer-form").addEventListener("input", () => { dirty = true; draftInfo(); updateAcceptance(); });
    $("offer-form").addEventListener("change", () => { dirty = true; draftInfo(); updateAcceptance(); });
    $("offer-form").addEventListener("submit", (event) => {
      event.preventDefault();
      action("offer-error", async () => {
        if (draftVersion !== detail.current_offer.version) {
          throw new Error("Use current terms to review the changed offer before proposing again.");
        }
        const borrow = detail.exchange.mode === "borrow";
        const snapshot = detail.current_offer.condition_snapshot;
        const lines = (id, key) => {
          const values = $(id).value.split("\n").map((value) => value.trim()).filter(Boolean);
          return !values.length && snapshot[key] === null ? null : values;
        };
        const meetingTime = (id, key) => {
          const current = detail.current_offer[key];
          // A fee-only edit must preserve the exact agreed time, including seconds.
          return $(id).value === easternInput(current) ? current : easternToUtc($(id).value);
        };
        await api.post(base + "/offers", {
          sale_price_cents: borrow ? null : cents("sale-price"),
          rental_fee_cents: borrow ? cents("rental-fee") : null,
          agreed_item_value_cents: borrow ? cents("item-value") : null,
          deposit_cents: borrow ? cents("deposit") : null,
          pickup_meeting_spot_id: $("pickup-spot").value || null,
          pickup_at: meetingTime("pickup-at", "pickup_at"),
          return_meeting_spot_id: borrow ? $("return-spot").value || null : null,
          return_deadline: borrow ? meetingTime("return-deadline", "return_deadline") : null,
          condition_snapshot: { condition: $("condition").value || null, accessories: lines("accessories", "accessories"), known_defects: lines("known-defects", "known_defects") },
        });
        dirty = false;
        $("accept-error").textContent = "";
        $("page-status").textContent = "Terms saved. Review the current revision before accepting.";
      });
    });
    $("accept-form").addEventListener("submit", (event) => {
      event.preventDefault();
      const version = detail.current_offer.version;
      action("accept-error", async () => {
        if (dirty) throw new Error("Propose your unsaved terms or use current terms before accepting.");
        await api.post(base + "/accept", {
          version, lower_deposit_acknowledged: $("lower-deposit-acknowledged").checked,
        });
      });
    });
    $("message-form").addEventListener("submit", (event) => {
      event.preventDefault();
      const body = $("message-body").value;
      action("message-error", async () => {
        const result = await api.post(base + "/messages", { body });
        if (!sessionIsCurrent()) return;
        $("message-body").value = "";
        renderMessages([result.message]);
      });
    });
    async function loadInitial() {
      if (initializing) return;
      initializing = true;
      $("refresh-room").disabled = true;
      $("page-error").textContent = "";
      $("page-status").textContent = "Loading your private exchange…";
      try {
        const [me, latest, meetingData, conversation] = await Promise.all([
          api.get("/api/me"), api.get(base), api.get("/api/meeting-spots"), api.get(base + "/messages"),
        ]);
        if (!sessionIsCurrent()) return;
        profile = me.profile; detail = latest; spots = meetingData.meeting_spots;
        listing = (await api.get("/api/listings/" + encodeURIComponent(detail.exchange.listing_id))).listing;
        if (!sessionIsCurrent()) return;
        ["pickup-spot", "return-spot"].forEach((id) => {
          $(id).replaceChildren(node("option", "Select a campus meeting spot"));
          $(id).firstElementChild.value = "";
          spots.forEach((spot) => {
            const option = node("option", spot.label); option.value = spot.id; $(id).append(option);
          });
        });
        render();
        renderMessages(conversation.messages);
        initialized = true;
        $("sign-in-hint").hidden = true;
        $("page-status").textContent = "Private exchange up to date.";
        timer = setInterval(() => { if (!document.hidden) refresh(); }, 5000);
        document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
        window.addEventListener("pagehide", () => clearInterval(timer));
      } catch (error) { if (sessionIsCurrent()) pageError(error); }
      finally {
        initializing = false;
        $("refresh-room").disabled = false;
      }
    }
    await loadInitial();
  }

  if (listPage) initList();
  if (roomPage) initRoom();
})();
