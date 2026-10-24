// Başarı zamanı: geç gelen eski metadata, doğrulanmış yeni zamanı geri alamaz.
(() => {
  function apply(state, response) {
    const stamp = response?.last_updated_at ?? response?.last_update;
    const next = Date.parse(stamp), previous = Date.parse(state.lastUpdate);
    if (!Number.isFinite(next) || (Number.isFinite(previous) && next < previous)) return false;
    const changed = state.lastUpdate !== stamp;
    state.lastUpdate = stamp;
    return changed;
  }
  const freshUrl = (path) => `${path}${path.includes("?") ? "&" : "?"}_fresh=${Date.now()}`;
  const api = { apply, freshUrl };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof window !== "undefined") window.UpdateStatus = api;
})();
