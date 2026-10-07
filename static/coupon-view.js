(() => {
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));
  const numeric = (value) => value === null || value === undefined || value === ""
    ? null : Number.isFinite(Number(value)) ? Number(value) : null;
  const displayNumber = (value, digits = 2) => {
    const number = numeric(value);
    return number === null ? "-" : number.toFixed(digits);
  };
  const probability = (value) => {
    const number = numeric(value);
    return number === null ? "-" : `${Math.round(number * 100)}%`;
  };
  const pickTime = (kickoff) => {
    const time = kickoff ? new Date(kickoff) : null;
    return time && !Number.isNaN(time.getTime())
      ? time.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })
      : "-";
  };

  function odds(pick) {
    const amount = esc(displayNumber(pick.odds));
    const claude = esc(displayNumber(pick.claude_odds));
    return pick.odds_source === "iddaa"
      ? `<b class="iddaa-odd">${amount}</b><span class="src src-iddaa">iddaa</span><span class="claude-odd">Claude oran: ${claude}</span>`
      : `<b class="iddaa-odd">${amount}</b><span class="src src-claude">Claude oran</span><span class="claude-odd">iddaa oranı yok</span>`;
  }

  function source(coupon, picks) {
    if (!picks.length) return "";
    if (coupon.odds_source === "iddaa") return `<span class="badge b-info">oranlar: iddaa</span>`;
    if (coupon.odds_source === "claude") return `<span class="badge b-warn">oranlar: Claude oran</span>`;
    const iddaaPicks = numeric(coupon.iddaa_picks) ?? 0;
    return `<span class="badge b-info">oranlar: ${Math.trunc(iddaaPicks)}/${picks.length} iddaa, kalanı Claude oran</span>`;
  }

  function couponCard(coupon, title, badgeClass, share = null) {
    coupon = coupon && typeof coupon === "object" ? coupon : {};
    const picks = Array.isArray(coupon.picks) ? coupon.picks.filter((pick) => pick && typeof pick === "object") : [];
    const rows = picks.map((pick) => `<tr>
      <td class="l"><b>${esc(pick.home || "Takım bilgisi yok")}</b> – ${esc(pick.away || "Takım bilgisi yok")}</td>
      <td>${esc(pick.league_name || pick.league || "-")}</td>
      <td>${esc(pickTime(pick.kickoff))}</td>
      <td><span class="badge b-info">${esc(pick.market || "-")}</span></td>
      <td>${odds(pick)}</td>
      <td>${probability(pick.p)}</td>
    </tr>`).join("");
    const content = picks.length
      ? `<table><thead><tr><th class="l">Maç</th><th>Lig</th><th>Saat</th><th>Seçim</th><th>Oran</th><th>Olasılık</th></tr></thead><tbody>${rows}</tbody></table>`
      : `<p class="muted">Bu kupon için uygun maç bulunamadı.</p>`;
    const totals = picks.length
      ? `<div class="coupon-total"><b>Toplam oran:</b> ${esc(displayNumber(coupon.total_odds))} · <b>Toplam tutma:</b> ${probability(coupon.total_probability)}<br><span class="muted">${esc(coupon.stake_note || "")}</span></div>`
      : "";
    const shareActions = picks.length && share
      ? `<div class="coupon-share-actions"><button type="button" class="btn" data-share-coupon data-share-type="${esc(share.kind)}" data-share-index="${share.index}">Paylaş</button><select aria-label="Görsel boyutu" data-share-size><option value="square">Kare 1080×1080</option><option value="story">Story 1080×1920</option></select></div>`
      : "";
    return `<div class="card coupon-card"><div class="row-between"><h3>${esc(title)}</h3><span>${source(coupon, picks)} <span class="badge ${esc(badgeClass)}">${picks.length} maç</span></span></div>${content}${totals}${shareActions}</div>`;
  }

  function alternatives(data, type) {
    if (!data || typeof data !== "object") return [];
    const key = `${type}_alternatives`;
    const listed = Array.isArray(data[key])
      ? data[key].filter((coupon) => coupon && typeof coupon === "object" && Array.isArray(coupon.picks) && coupon.picks.length)
      : [];
    if (listed.length) return listed;
    return data[type] && typeof data[type] === "object" && Array.isArray(data[type].picks) && data[type].picks.length
      ? [data[type]] : [];
  }

  function couponGroup(data, type, badgeClass, date) {
    const label = type === "surprise" ? "Sürpriz" : "Banko";
    const coupons = alternatives(data, type);
    const content = coupons.length
      ? coupons.map((coupon, index) => couponCard(coupon, `${label} Kuponu ${index + 1}`, badgeClass, { kind: type, index, date })).join("")
      : `<div class="card muted">${label} türünde uygun kupon bulunamadı.</div>`;
    return `<section class="coupon-group"><h3>${label} Kupon Alternatifleri</h3>${content}</section>`;
  }

  const api = { alternatives, couponCard, couponGroup };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof window !== "undefined") window.CouponView = api;
})();
