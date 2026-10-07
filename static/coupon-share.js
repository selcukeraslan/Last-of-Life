/* Kütüphanesiz kupon görseli üretimi ve paylaşımı. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.CouponShare = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  const SITE = "iddia-oran.vercel.app";
  const palettes = { bg: "#0f1419", panel: "#171e26", line: "#2a3542", text: "#e6edf3", muted: "#8b98a5", green: "#2fbf71" };
  const dateText = (value) => {
    const d = new Date(`${value}T12:00:00Z`);
    return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric", timeZone: "Europe/Istanbul" });
  };
  const rounded = (ctx, x, y, w, h, r, color) => {
    ctx.fillStyle = color; ctx.beginPath();
    if (typeof ctx.roundRect === "function") ctx.roundRect(x, y, w, h, r);
    else { ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); }
    ctx.closePath(); ctx.fill();
  };
  function prepare(data, size) {
    const story = size === "story", width = 1080, height = story ? 1920 : 1080;
    const top = story ? 300 : 276, footerTop = height - 130, totalHeight = 84;
    const picks = (data.picks || []).map((p) => {
      const odds = p.odds ?? p.odds_value;
      return { ...p, oddsText: Number.isFinite(Number(odds)) && odds !== null && odds !== "" ? Number(odds).toFixed(2) : "-" };
    });
    const gap = 6, rowH = picks.length ? Math.min(story ? 116 : 94, (footerTop - top - totalHeight - picks.length * gap) / picks.length) : 0;
    return { width, height, top, footerTop, totalHeight, gap, rowH, picks, totalOddsText: Number.isFinite(Number(data.totalOdds)) ? Number(data.totalOdds).toFixed(2) : "-" };
  }
  const trimText = (ctx, text, maxWidth) => {
    if (ctx.measureText(text).width <= maxWidth) return text;
    let s = text;
    while (s.length && ctx.measureText(`${s}…`).width > maxWidth) s = s.slice(0, -1);
    return `${s}…`;
  };
  function draw(data, size) {
    const story = size === "story", layout = prepare(data, size), { width, height } = layout;
    const canvas = document.createElement("canvas"); canvas.width = width; canvas.height = height;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = palettes.bg; ctx.fillRect(0, 0, width, height);
    const pad = 76, contentW = width - pad * 2;
    ctx.fillStyle = palettes.green; ctx.fillRect(0, 0, width, 14);
    ctx.fillStyle = palettes.text; ctx.font = "700 48px system-ui, -apple-system, sans-serif"; ctx.fillText("⚽ İddia Oran", pad, 88);
    ctx.fillStyle = palettes.muted; ctx.font = "24px system-ui, -apple-system, sans-serif"; ctx.fillText(dateText(data.date), pad, 132);
    ctx.fillStyle = palettes.green; ctx.font = "700 56px system-ui, -apple-system, sans-serif"; ctx.fillText(data.title || "Kuponum", pad, 218);
    const { top, footerTop, totalHeight, gap, rowH, picks } = layout;
    picks.forEach((p, i) => {
      const rowY = top + i * (rowH + gap), compact = rowH < 62;
      const fontSize = Math.max(12, Math.min(compact ? 17 : 27, rowH * (compact ? 0.68 : 0.34)));
      rounded(ctx, pad, rowY, contentW, Math.max(1, rowH), Math.min(12, rowH / 2), palettes.panel);
      ctx.fillStyle = palettes.text; ctx.font = `650 ${fontSize}px system-ui, -apple-system, sans-serif`;
      const match = `${p.home || "Ev sahibi"} – ${p.away || "Deplasman"}`;
      const kickoff = p.kickoff ? new Date(p.kickoff).toLocaleString("tr-TR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Istanbul" }) : "";
      const details = `${p.market || "Seçim"}${kickoff ? ` · ${kickoff}` : ""}`;
      const left = pad + 18, right = width - pad - 18, oddsW = Math.max(40, fontSize * 3.5);
      if (compact) {
        ctx.fillText(trimText(ctx, `${match} · ${details}`, contentW - 36 - oddsW), left, rowY + rowH * 0.68);
      } else {
        ctx.fillText(trimText(ctx, match, contentW - 36 - oddsW), left, rowY + rowH * 0.38);
        ctx.fillStyle = palettes.muted; ctx.font = `${Math.max(14, fontSize * 0.78)}px system-ui, -apple-system, sans-serif`;
        ctx.fillText(trimText(ctx, details, contentW - 36 - oddsW), left, rowY + rowH * 0.76);
      }
      ctx.textAlign = "right"; ctx.fillStyle = palettes.green; ctx.font = `700 ${fontSize}px system-ui, -apple-system, sans-serif`;
      ctx.fillText(p.oddsText, right, rowY + rowH * 0.58); ctx.textAlign = "left";
    });
    const totalY = top + picks.length * (rowH + gap);
    rounded(ctx, pad, totalY, contentW, totalHeight, 18, "#1e2731");
    ctx.fillStyle = palettes.muted; ctx.font = "24px system-ui, -apple-system, sans-serif"; ctx.fillText("TOPLAM ORAN", pad + 24, totalY + 53);
    ctx.fillStyle = palettes.text; ctx.font = "700 38px system-ui, -apple-system, sans-serif"; ctx.textAlign = "right"; ctx.fillText(layout.totalOddsText, width - pad - 24, totalY + 57); ctx.textAlign = "left";
    const footY = footerTop + 55;
    ctx.fillStyle = palettes.muted; ctx.font = "22px system-ui, -apple-system, sans-serif";
    ctx.fillText("18+ · garanti değildir", pad, footY); ctx.textAlign = "right"; ctx.fillText(SITE, width - pad, footY); ctx.textAlign = "left";
    return new Promise((resolve) => canvas.toBlob((blob) => resolve(blob), "image/png"));
  }
  async function share(data, size) {
    try {
      const blob = await draw(data, size);
      if (!blob) throw new Error("Görsel oluşturulamadı.");
      const file = new File([blob], "iddia-oran-kupon.png", { type: "image/png" });
      if (navigator.share && navigator.canShare?.({ files: [file] })) {
        try { await navigator.share({ title: data.title || "Kuponum", text: `${data.title || "Kuponum"} · toplam oran ${Number(data.totalOdds || 0).toFixed(2)} · ${SITE}`, files: [file] }); return; }
        catch (e) { if (e.name === "AbortError") return; }
      }
      const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "iddia-oran-kupon.png"; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      try { await navigator.clipboard.writeText(`Kupon: ${SITE}`); window.alert("Görsel indirildi, site linki kopyalandı."); }
      catch { window.prompt("Görsel indirildi. Site linkini kopyalayın:", SITE); }
    } catch (e) { window.alert(`Paylaşım görseli hazırlanamadı: ${e.message}`); }
  }
  return { share, prepare };
});
