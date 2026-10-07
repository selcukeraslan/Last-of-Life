// Delegated match activation: rows are recreated as league/date filters change.
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.MatchEvents = api;
})(globalThis, function () {
  function bind(doc, openMatch, closeModal) {
    doc.addEventListener("click", (event) => {
      const target = event.target;
      const row = target.closest("[data-match-id]") || target.closest(".drop-row[data-id]") ||
        target.closest(".clickable[data-id]");
      const control = target.closest(".slip-add, .slip-remove, #slipClear, #slipRefresh");
      if (row && !control && !target.closest(".modal")) {
        openMatch(row.dataset.matchId || row.dataset.id, row.dataset.competitionId || null);
      }
      if (target.id === "modal") closeModal();
    });

    doc.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeModal();
      if (event.key !== "Enter" && event.key !== " ") return;
      if (!event.target.matches?.(".match[data-match-id], .clickable[data-match-id], .clickable[data-id], .drop-row[data-id]")) return;
      if (event.key === " ") event.preventDefault();
      openMatch(event.target.dataset.matchId || event.target.dataset.id,
        event.target.dataset.competitionId || null);
    });
  }

  return { bind };
});
