/* Kütüphanesiz kupon görseli üretimi ve paylaşımı. */
(function () {
  "use strict";
  const SITE = "iddia-oran.vercel.app";
  const palettes = { bg: "#0f1419", panel: "#171e26", line: "#2a3542", text: "#e6edf3", muted: "#8b98a5", green: "#2fbf71" };
  const dateText = (value) => {
    const d = new Date(`${value}T12:00:00Z`);
    return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric", timeZone: "Europe/Istanbul" });
  };
  const rounded = (ctx, x, y, w, h, r, color) => { ctx.fillStyle = color; ctx.beginPath(); ctx.roundRect(x, y, w, h, r); ctx.fill(); };
  function draw(data, size) {
    const story = size === "story", width = 1080, height = story ? 1920 : 1080;
    const canvas = document.createElement("canvas"); canvas.width = width; canvas.height = height;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = palettes.bg; ctx.fillRect(0, 0, width, height);
    const pad = 76, contentW = width - pad * 2;
    ctx.fillStyle = palettes.green; ctx.fillRect(0, 0, width, 14);
    ctx.fillStyle = palettes.text; ctx.font = "700 48px system-ui, -apple-system, sans-serif"; ctx.fillText("⚽ İddia Oran", pad, 88);
    ctx.fillStyle = palettes.muted; ctx.font = "24px system-ui, -apple-system, sans-serif"; ctx.fillText(dateText(data.date), pad, 132);
    ctx.fillStyle = palettes.green; ctx.font = "700 56px system-ui, -apple-system, sans-serif"; ctx.fillText(data.title || "Kuponum", pad, 218);
    let y = story ? 300 : 276;
    const picks = (data.picks || []).slice(0, 12), rowH = story ? 116 : (picks.length > 5 ? 86 : 98);
    const fit = Math.min(1, (height - y - 226) / Math.max(1, picks.length * rowH + 134));
    ctx.save(); ctx.translate(0, y); ctx.scale(1, fit); y = 0;
    picks.forEach((p, i) => {
      const rowY = y + i * rowH;
      rounded(ctx, pad, rowY, contentW, rowH - 12, 18, palettes.panel);
      ctx.fillStyle = palettes.text; ctx.font = "650 27px system-ui, -apple-system, sans-serif";
      const match = `${p.home || "Ev sahibi"} – ${p.away || "Deplasman"}`;
      ctx.fillText(match.length > 45 ? `${match.slice(0, 43)}…` : match, pad + 24, rowY + 38);
      ctx.fillStyle = palettes.muted; ctx.font = "22px system-ui, -apple-system, sans-serif";
      const kickoff = p.kickoff ? new Date(p.kickoff).toLocaleString("tr-TR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "";
      ctx.fillText(`${p.market || "Seçim"}${kickoff ? ` · ${kickoff}` : ""}`, pad + 24, rowY + 71);
      ctx.textAlign = "right"; ctx.fillStyle = palettes.green; ctx.font = "700 30px system-ui, -apple-system, sans-serif";
      const pickOdds = p.odds ?? p.odds_value;
      ctx.fillText(Number(pickOdds || 0).toFixed(2), width - pad - 24, rowY + 57); ctx.textAlign = "left";
    });
    const totalY = picks.length * rowH + 18;
    rounded(ctx, pad, totalY, contentW, 94, 18, "#1e2731");
    ctx.fillStyle = palettes.muted; ctx.font = "24px system-ui, -apple-system, sans-serif"; ctx.fillText("TOPLAM ORAN", pad + 24, totalY + 57);
    ctx.fillStyle = palettes.text; ctx.font = "700 38px system-ui, -apple-system, sans-serif"; ctx.textAlign = "right"; ctx.fillText(Number(data.totalOdds || 0).toFixed(2), width - pad - 24, totalY + 61); ctx.textAlign = "left";
    ctx.restore();
    const footY = height - 110;
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
  window.CouponShare = { share };
})();
