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
const regions = new Intl.DisplayNames(["en"], { type: "region" });
const OS_NAMES = { Darwin: "macOS", Wsl: "WSL", WSL: "WSL", Windows: "Windows", Linux: "Linux" };
const PREFS = {
  北海道: "Hokkaido", 青森県: "Aomori", 岩手県: "Iwate", 宮城県: "Miyagi", 秋田県: "Akita", 山形県: "Yamagata",
  福島県: "Fukushima", 茨城県: "Ibaraki", 栃木県: "Tochigi", 群馬県: "Gunma", 埼玉県: "Saitama", 千葉県: "Chiba",
  東京都: "Tokyo", 神奈川県: "Kanagawa", 新潟県: "Niigata", 富山県: "Toyama", 石川県: "Ishikawa", 福井県: "Fukui",
  山梨県: "Yamanashi", 長野県: "Nagano", 岐阜県: "Gifu", 静岡県: "Shizuoka", 愛知県: "Aichi", 三重県: "Mie",
  滋賀県: "Shiga", 京都府: "Kyoto", 大阪府: "Osaka", 兵庫県: "Hyogo", 奈良県: "Nara", 和歌山県: "Wakayama",
  鳥取県: "Tottori", 島根県: "Shimane", 岡山県: "Okayama", 広島県: "Hiroshima", 山口県: "Yamaguchi",
  徳島県: "Tokushima", 香川県: "Kagawa", 愛媛県: "Ehime", 高知県: "Kochi", 福岡県: "Fukuoka", 佐賀県: "Saga",
  長崎県: "Nagasaki", 熊本県: "Kumamoto", 大分県: "Oita", 宮崎県: "Miyazaki", 鹿児島県: "Kagoshima", 沖縄県: "Okinawa",
};
const $ = (id) => document.getElementById(id);

function age(iso, now) {
  return now - Date.parse(iso);
}

function ago(iso, now) {
  const m = Math.floor(age(iso, now) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function setTime(el, iso, now) {
  el.dateTime = iso;
  el.textContent = ago(iso, now);
  el.title = new Date(iso).toLocaleString("en-GB");
}

// 経過時間 (`for …` 用)
function elapsed(ms) {
  const m = Math.max(0, Math.floor(ms / 60000));
  return m < 60 ? `${m}m` : `${Math.floor(m / 60)}h ${m % 60}m`;
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
  if (old) note.textContent = `fetched ${ago(at, now)}`;
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
  const parts = [];
  if (offline) {
    parts.push(`last seen ${ago(h.pushed_at, now)}`);
  } else {
    parts.push(`for ${elapsed(age(h.since, now))}`);
    if (h.agents >= 1) parts.push(`🤖 ×${h.agents}`);
    if (h.ai_ratio_today != null) parts.push(`AI ${Math.round(h.ai_ratio_today * 100)}%`);
  }
  $("human-sub").textContent = parts.join(" · ");
}

function placeName(l) {
  if (l.country === "JP" && l.pref) return PREFS[l.pref] || l.pref;
  return l.country ? regions.of(l.country) : "somewhere";
}

function hours(minutes) {
  const h = Math.abs(minutes) / 60;
  const s = Number.isInteger(h) ? `${h}` : h.toFixed(1);
  return `${minutes < 0 ? "−" : "+"}${s}h`;
}

function utcLabel(minutes) {
  const a = Math.abs(minutes);
  const mm = a % 60;
  return `UTC${minutes < 0 ? "−" : "+"}${Math.floor(a / 60)}${mm ? `:${String(mm).padStart(2, "0")}` : ""}`;
}

function renderLocation(l, now) {
  const card = $("location");
  card.hidden = !l;
  if (!l) return;
  $("location-flag").textContent = flag(l.country);
  $("location-place").textContent = placeName(l);
  $("location-moving").hidden = !l.moving;
  $("location-km").textContent = l.today_km.toFixed(1);
  setTime($("location-point"), l.point_at, now);
  const tz = $("location-time");
  const off = l.utc_offset_minutes;
  tz.hidden = off == null;
  if (off != null) {
    const local = new Date(now + off * 60000);
    const hh = String(local.getUTCHours()).padStart(2, "0");
    const mm = String(local.getUTCMinutes()).padStart(2, "0");
    let text = `${hh}:${mm} ${utcLabel(off)}`;
    const diff = -new Date(now).getTimezoneOffset() - off;
    if (diff !== 0) text += ` · you ${hours(diff)}`;
    tz.textContent = text;
  }
  markStale(card, l.at, now);
}

function osName(name) {
  return OS_NAMES[name] || name;
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
  $("code-os").hidden = c.oses.length === 0;
  $("code-os").textContent = c.oses.map(([name, ratio]) => `${osName(name)} ${Math.round(ratio * 100)}%`).join(" · ");
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

// 1 枚の描画が例外を投げても、他のカードを描かせる。
function safely(render, ...args) {
  try {
    render(...args);
  } catch (e) {
    console.error(`${render.name} failed`, e);
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
  safely(renderHuman, data.human, now);
  safely(renderLocation, data.location, now);
  safely(renderCode, data.code, now);
  safely(renderServices, data.services, now);
}

load();
setInterval(load, 60 * 1000);
