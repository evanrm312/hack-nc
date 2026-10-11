// A hypothetical spending model. No analytics or transaction records are used.
(function () {
  const form = document.getElementById("monthly-simulation");
  if (!form) return;
  const $ = (id) => document.getElementById(id);
  const money = (cents) => new Intl.NumberFormat("en-US", {
    style: "currency", currency: "USD", maximumFractionDigits: 0,
  }).format(cents / 100);
  function update() {
    const exchanges = Number($("monthly-exchanges").value);
    const replacementRate = Number($("replacement-rate").value);
    // Controls use whole dollars; calculations use integer USD cents.
    const newCost = Number($("new-item-cost").value) * 100;
    const reuseCost = Number($("reuse-cost").value) * 100;
    const replaced = Math.floor(exchanges * replacementRate / 100);
    const newSpending = replaced * newCost;
    const reuseSpending = exchanges * reuseCost;
    const savings = newSpending - reuseSpending;
    $("monthly-exchanges-value").textContent = exchanges;
    $("replacement-rate-value").textContent = replacementRate + "%";
    $("new-item-cost-value").textContent = money(newCost);
    $("reuse-cost-value").textContent = money(reuseCost);
    $("savings-label").textContent = savings < 0 ? "Additional monthly spending" : "Potential monthly savings";
    $("monthly-savings").textContent = money(Math.abs(savings));
    $("new-spending").textContent = money(newSpending);
    $("reuse-spending").textContent = money(reuseSpending);
    const scale = Math.max(newSpending, reuseSpending, 1);
    $("new-spending-bar").style.width = (newSpending / scale * 100) + "%";
    $("reuse-spending-bar").style.width = (reuseSpending / scale * 100) + "%";
    $("simulation-summary").textContent = `${exchanges} exchanges. ${replaced} replace a new purchase. ${money(newSpending)} in new purchases avoided, minus ${money(reuseSpending)} in used prices and fees.`;
    form.querySelectorAll("[data-monthly-exchanges]").forEach((button) => {
      button.setAttribute("aria-pressed", String(Number(button.dataset.monthlyExchanges) === exchanges));
    });
  }
  form.addEventListener("submit", (event) => event.preventDefault());
  form.addEventListener("input", update);
  form.querySelectorAll("[data-monthly-exchanges]").forEach((button) => {
    button.addEventListener("click", () => { $("monthly-exchanges").value = button.dataset.monthlyExchanges; update(); });
  });
  update();
})();
