// Giriş / kayıt / şifremi unuttum / şifre sıfırlama ekranı (/giris). Ana sayfadan bağımsızdır.
const $ = (s) => document.querySelector(s);
const MODES = {
  login: { title: "Giriş yap", submit: "Giriş yap", email: true, pass: "Şifre", ac: "current-password" },
  register: { title: "Kayıt ol", submit: "Hesap oluştur", email: true, pass: "Şifre (en az 10 karakter)", ac: "new-password" },
  forgot: { title: "Şifremi unuttum", submit: "Sıfırlama bağlantısı iste", email: true, pass: null },
  reset: { title: "Yeni şifre belirle", submit: "Şifreyi kaydet", email: false, pass: "Yeni şifre (en az 10 karakter)", ac: "new-password" },
};
const st = { mode: "login", token: new URLSearchParams(location.search).get("reset") };

async function post(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await r.json().catch(() => null);
  if (!r.ok) throw new Error(typeof data?.detail === "string" ? data.detail : `Hata ${r.status}`);
  return data;
}

function msg(text, err = false) {
  const el = $("#authMsg");
  el.textContent = text;
  el.classList.toggle("err", err);
}

function setMode(mode) {
  st.mode = mode;
  const m = MODES[mode];
  $("#authTitle").textContent = m.title;
  $("#authSubmit").textContent = m.submit;
  $("#authEmailWrap").classList.toggle("hidden", !m.email);
  $("#authPassWrap").classList.toggle("hidden", !m.pass);
  $("#authPass").required = Boolean(m.pass);
  if (m.pass) { $("#authPassLabel").textContent = m.pass; $("#authPass").autocomplete = m.ac; }
  $("#authLinks").classList.toggle("hidden", mode === "reset");
  msg("");
}

document.querySelectorAll("#authLinks a").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); setMode(a.dataset.mode); }));

$("#authForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = $("#authEmail").value.trim();
  const password = $("#authPass").value;
  const btn = $("#authSubmit");
  btn.disabled = true;
  try {
    if (st.mode === "login" || st.mode === "register") {
      await post(`/api/auth/${st.mode}`, { email, password });
      location.assign("/");
    } else if (st.mode === "forgot") {
      msg((await post("/api/auth/forgot", { email })).message);
    } else {
      await post("/api/auth/reset", { token: st.token, password });
      st.token = null;
      history.replaceState(null, "", "/giris");
      $("#authPass").value = "";
      setMode("login");
      msg("Şifreniz güncellendi. Yeni şifrenizle giriş yapın.");
    }
  } catch (err) {
    msg(err.message, true);
  } finally {
    btn.disabled = false;
  }
});

setMode(st.token ? "reset" : ["register", "forgot"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "login");
