"use strict";

// status.json を 60 秒ごとに取り直して描画する。相対時刻と古さの判定はここで行う。
const STALE_MS = 10 * 60 * 1000;
const STATES = {
  computering: ["💻", "computering"],
  delegating: ["🤖", "delegating to AI"],
  reading: ["📖", "reading"],
  chore: ["🧹", "chore"],
  eating: ["🍚", "eating"],
  sleeping: ["😴", "sleeping"],
  working: ["🏢", "working"],
  away: ["🚶", "away"],
  offline: ["🌙", "offline"],
};
const LANG_COLORS = ["var(--c1)", "var(--c2)", "var(--c3)"];
const regions = new Intl.DisplayNames(["ja"], { type: "region" });
const $ = (id) => document.getElementById(id);

function age(iso, now) {
  return now - Date.parse(iso);
}

function ago(iso, now) {
  const m = Math.floor(age(iso, now) / 60000);
  if (m < 1) return "たった今";
  if (m < 60) return `${m}分前`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}時間前`;
  return `${Math.floor(h / 24)}日前`;
}

function setTime(el, iso, now) {
  el.dateTime = iso;
  el.textContent = ago(iso, now);
  el.title = new Date(iso).toLocaleString("ja-JP");
}

function duration(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return h ? `${h}h ${m}m` : `${m}m`;
}

function flag(code) {
  return code ? [...code].map((c) => String.fromCodePoint(0x1f1a5 + c.charCodeAt(0))).join("") : "🌏";
}

function markStale(card, at, now) {
  const note = card.querySelector(".stale");
  const old = age(at, now) > STALE_MS;
  card.classList.toggle("is-stale", old);
  note.hidden = !old;
  if (old) note.textContent = `最終取得 ${ago(at, now)}`;
}

function fromTemplate(id) {
  return $(id).content.firstElementChild.cloneNode(true);
}

function renderHuman(h, now) {
  const card = $("human");
  card.hidden = !h;
  if (!h) return;
  const offline = age(h.pushed_at, now) > STALE_MS;
  const [emoji, label] = STATES[offline ? "offline" : h.state] || STATES.away;
  $("human-emoji").textContent = emoji;
  $("human-state").textContent = label;
  setTime($("human-since"), offline ? h.pushed_at : h.since, now);
  const ai = h.delegated_ratio_today;
  $("human-ai").hidden = ai == null;
  if (ai != null) $("human-ai-value").textContent = `${Math.round(ai * 100)}%`;
}

function renderLocation(l, now) {
  const card = $("location");
  card.hidden = !l;
  if (!l) return;
  $("location-flag").textContent = flag(l.country);
  $("location-place").textContent = l.pref || (l.country ? regions.of(l.country) : "どこか");
  $("location-moving").hidden = !l.moving;
  $("location-km").textContent = l.today_km.toFixed(1);
  setTime($("location-point"), l.point_at, now);
  markStale(card, l.at, now);
}

function renderCode(c, now) {
  const card = $("code");
  card.hidden = !c;
  if (!c) return;
  $("code-total").textContent = duration(c.today_sec);
  const bar = $("code-bar");
  const legend = $("code-legend");
  bar.replaceChildren();
  legend.replaceChildren();
  c.langs.forEach(([name, ratio], i) => {
    const color = name === "other" ? "var(--idle)" : LANG_COLORS[i % LANG_COLORS.length];
    const seg = document.createElement("span");
    seg.style.flexGrow = ratio;
    seg.style.background = color;
    seg.title = name;
    bar.append(seg);
    const li = fromTemplate("tpl-lang");
    li.querySelector(".swatch").style.background = color;
    li.querySelector(".name").textContent = name;
    li.querySelector(".pct").textContent = `${Math.round(ratio * 100)}%`;
    legend.append(li);
  });
  $("code-os").textContent = c.os ? `on ${c.os}` : "";
  markStale(card, c.at, now);
}

function renderServices(list, now) {
  const card = $("services");
  card.hidden = !list || list.length === 0;
  if (card.hidden) return;
  const ul = $("services-list");
  ul.replaceChildren();
  for (const s of list) {
    const li = fromTemplate("tpl-service");
    const status = s.up ? "up" : s.event_only ? "idle" : "down";
    li.dataset.status = status;
    const name = li.querySelector(".name");
    if (s.url) {
      const a = document.createElement("a");
      a.href = s.url;
      a.rel = "noopener";
      a.textContent = s.name;
      name.append(a);
    } else {
      name.textContent = s.name;
    }
    const notes = [];
    if (s.private) notes.push("private");
    if (status === "idle") notes.push("event only");
    if (status === "down") notes.push("down");
    li.querySelector(".note").textContent = notes.join(" · ");
    li.title = `checked ${ago(s.checked_at, now)}`;
    ul.append(li);
  }
}

async function load() {
  let data;
  try {
    const res = await fetch("status.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch {
    document.body.classList.add("is-error");
    return;
  }
  document.body.classList.remove("is-error");
  const now = Date.now();
  setTime($("generated"), data.generated_at, now);
  document.body.classList.toggle("is-stale", age(data.generated_at, now) > STALE_MS);
  renderHuman(data.human, now);
  renderLocation(data.location, now);
  renderCode(data.code, now);
  renderServices(data.services, now);
}

load();
setInterval(load, 60 * 1000);
