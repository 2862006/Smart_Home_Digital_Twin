const $ = (id) => document.getElementById(id);
const set = (id, v) => { $(id).textContent = v; };
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

/* ---------- DEVICE CONFIG ---------- */
const DEVICES = [
  { id: "ac", name: "Air Conditioner", icon: "❄️", cat: "climate", extra: "acmode" },
  { id: "heater", name: "Heater", icon: "🔥", cat: "climate" },
  { id: "fan", name: "Fan", icon: "🌀", cat: "climate", extra: "fan" },
  { id: "window", name: "Smart Window", icon: "🪟", cat: "climate" },
  { id: "light", name: "Smart Light", icon: "💡", cat: "media", extra: "bright" },
  { id: "tv", name: "Smart TV", icon: "📺", cat: "media" },
  { id: "camera", name: "Security Camera", icon: "📷", cat: "security" },
  { id: "door", name: "Front Door", icon: "🚪", cat: "security" },
];

const ICONS = {
  Clear: "☀️", "Mainly clear": "🌤️", "Partly cloudy": "⛅", Overcast: "☁️",
  Fog: "🌫️", Drizzle: "🌦️", Rain: "🌧️", "Heavy rain": "🌧️",
  Showers: "🌦️", "Heavy showers": "⛈️", Thunderstorm: "⛈️",
};

let S = null;                       // latest status
let nextVersion = {};               // har device ka agla command version
let activeView = "dashboard";
let activeCat = "all";
let rawPage = 1, rawPages = 1;
const ARC = 377;

/* ---------- RENDER DEVICE CARDS (ek baar) ---------- */
function extraHTML(d) {
  if (d.extra === "acmode")
    return `<div class="mini">
      <button data-acmode="cool" onclick="setSetting({ac_mode:'cool'})">Cool</button>
      <button data-acmode="dry" onclick="setSetting({ac_mode:'dry'})">Dry</button></div>`;
  if (d.extra === "fan")
    return `<div class="mini">
      <button data-fan="1" onclick="setSetting({fan_speed:1})">Low</button>
      <button data-fan="2" onclick="setSetting({fan_speed:2})">Med</button>
      <button data-fan="3" onclick="setSetting({fan_speed:3})">High</button></div>`;
  if (d.extra === "bright")
    return `<input type="range" id="bright" min="0" max="100" onchange="setSetting({brightness:+this.value})">`;
  return "";
}

$("devices").innerHTML = DEVICES.map((d) => `
  <div class="dev" id="card-${d.id}" data-cat="${d.cat}" data-name="${d.name.toLowerCase()}">
    <div class="dev-top">
      <span class="dev-icon">${d.icon}</span>
      <label class="switch"><input type="checkbox" id="sw-${d.id}" onclick="toggle('${d.id}', event)"><span></span></label>
    </div>
    <h3>${d.name}</h3>
    <p id="st-${d.id}">OFF</p>
    <small class="watt" id="pw-${d.id}">0 W</small>
    ${extraHTML(d)}
  </div>`).join("");

/* ---------- NAVIGATION / FILTERS ---------- */
document.querySelectorAll(".nav").forEach((btn) => {
  btn.addEventListener("click", () => {
    activeView = btn.dataset.view;
    document.querySelectorAll(".nav").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    btn.classList.add("active");
    $("view-" + activeView).classList.add("active");
    Object.values(charts).forEach((c) => c.resize());
    refresh();
    if (activeView === "records") loadRaw();
    if (activeView === "logs") loadLogs();
    if (activeView === "analytics") loadAnalytics();
  });
});

document.querySelectorAll(".cat").forEach((b) => {
  b.addEventListener("click", () => {
    activeCat = b.dataset.cat;
    document.querySelectorAll(".cat").forEach((x) => x.classList.toggle("active", x === b));
    applyFilter();
  });
});
$("search").addEventListener("input", applyFilter);

function applyFilter() {
  const q = $("search").value.trim().toLowerCase();
  document.querySelectorAll(".dev").forEach((c) => {
    const okCat = activeCat === "all" || c.dataset.cat === activeCat;
    const okName = !q || c.dataset.name.includes(q);
    c.classList.toggle("hide", !(okCat && okName));
  });
}

/* ---------- CHARTS ---------- */
const line = (label, color, fill) => ({
  label, data: [], borderColor: color, backgroundColor: fill ? color + "33" : "transparent",
  fill: !!fill, tension: 0.4, pointRadius: 0, borderWidth: 2.5,
});

function mkChart(id, type, sets) {
  return new Chart($(id).getContext("2d"), {
    type,
    data: { labels: [], datasets: sets },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { intersect: false, mode: "index" },
      scales: {
        x: { ticks: { color: "#8b93a7", maxTicksLimit: 6 }, grid: { display: false } },
        y: { ticks: { color: "#8b93a7" }, grid: { color: "#262b38" }, beginAtZero: type === "bar" },
      },
      plugins: { legend: { labels: { color: "#e8ebf2", usePointStyle: true } } },
    },
  });
}

const charts = {
  main: mkChart("chart", "line", [line("Temperature (°C)", "#a78bfa", true), line("Humidity (%)", "#38bdf8", false)]),
  power: mkChart("chart-power", "line", [line("Power (kW)", "#4ade80", true)]),
  temp: mkChart("chart2", "line", [line("Temperature (°C)", "#a78bfa", true)]),
  hum: mkChart("chart3", "line", [line("Humidity (%)", "#38bdf8", true)]),
  energy: mkChart("chart-energy", "bar", [{
    label: "kWh", data: [], backgroundColor: "#7c5cff", borderRadius: 8,
  }]),
};

function fill(c, labels, ...series) {
  c.data.labels = labels;
  series.forEach((s, i) => { c.data.datasets[i].data = s; });
  c.update();
}

/* ---------- UI HELPERS ---------- */
function toast(msg, ok = true) {
  const t = $("toast");
  t.textContent = msg;
  t.className = "show" + (ok ? "" : " err");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.className = ""), 2800);
}

function setArc(id, value, min, max, color) {
  const p = clamp((value - min) / (max - min), 0, 1);
  const el = $(id);
  el.style.strokeDasharray = `${ARC * p} 503`;
  el.style.stroke = color;
}

function placeDot(id, value, min, max) {
  const p = clamp((value - min) / (max - min), 0, 1);
  const a = ((135 + 270 * p) * Math.PI) / 180;
  $(id).setAttribute("cx", 100 + 80 * Math.cos(a));
  $(id).setAttribute("cy", 100 + 80 * Math.sin(a));
}

function tagClass(status) {
  return { Successful: "ok", Auto: "auto", Alarm: "alarm", Scene: "scene" }[status] || "fail";
}

/* ---------- MAIN RENDER ---------- */
function render(s) {
  const w = s.weather, st = s.settings, d = s.devices;

  // Room numbers
  set("g-temp", s.temperature); set("g-hum", s.humidity);
  set("c-temp", s.temperature); set("c-hum", s.humidity);
  set("c-out", s.outside_temp); set("c-co2", s.co2);
  set("c-power", s.total_kw);

  // Weather tiles
  set("w-feels", w.feels); set("w-wind", w.wind);
  set("w-vis", w.visibility ?? "--"); set("w-rain", w.precip);
  set("w-press", w.pressure);
  $("press-bar").style.width = clamp(((w.pressure - 980) / 60) * 100, 0, 100) + "%";
  set("condition", w.condition);
  set("w-icon", ICONS[w.condition] || "🌤️");
  set("out-hum", s.outside_humidity);
  set("sunrise", w.sunrise); set("sunset", w.sunset);
  $("forecast").innerHTML = w.forecast.map((f) => `
    <li><span>${f.day}</span><span>${ICONS[f.condition] || "🌤️"} ${f.condition}</span>
    <span class="t">${f.min}° / ${f.max}°</span></li>`).join("");

  // Devices
  DEVICES.forEach((dv) => {
    const on = d[dv.id];
    $("sw-" + dv.id).checked = on;
    let text = s.labels[dv.id];
    if (dv.id === "ac" && on) text += st.ac_mode === "cool" ? " · Cooling" : " · Drying";
    if (dv.id === "heater" && on) text += " · Heating";
    if (dv.id === "fan" && on) text += " · " + ["", "Low", "Med", "High"][st.fan_speed];
    if (dv.id === "light" && on) text += " · " + st.brightness + "%";
    set("st-" + dv.id, text);
    set("pw-" + dv.id, (s.power[dv.id] || 0) + " W");
    $("card-" + dv.id).classList.toggle("on", on);
    // version sync (auto/scene server-side bump ke baad bhi sahi rahe)
    nextVersion[dv.id] = Math.max(nextVersion[dv.id] || 1, s.versions[dv.id] + 1);
  });
  document.querySelectorAll("[data-acmode]").forEach((b) => b.classList.toggle("act", b.dataset.acmode === st.ac_mode));
  document.querySelectorAll("[data-fan]").forEach((b) => b.classList.toggle("act", +b.dataset.fan === st.fan_speed));
  if (document.activeElement !== $("bright")) $("bright").value = st.brightness;

  // Mode text
  let mode = "Idle";
  if (d.ac) mode = st.ac_mode === "cool" ? "Cooling" : "Drying";
  else if (d.heater) mode = "Heating";
  if (d.window) mode += " · Window open";
  set("g-mode", mode); set("mode-pill", mode);
  $("mode-pill").className = "pill " + (d.ac ? "cool" : d.heater ? "heat" : "");

  // Secure pill
  set("secure-pill", s.secure ? "🔒 Home Secure" : "⚠️ Check Door/Window");
  $("secure-pill").className = "pill " + (s.secure ? "good" : "warn");

  // Thermostat
  const color = d.ac ? "#38bdf8" : d.heater ? "#fb923c" : "#a78bfa";
  setArc("arc", s.temperature, 16, 40, color);
  placeDot("target-dot", st.target, 16, 40);
  set("target-val", st.target);
  $("auto-sw").checked = st.auto;

  // Humidity + air quality
  setArc("arc-h", s.humidity, 0, 100, "#38bdf8");
  set("aq-label", s.air); set("aq-co2", s.co2); set("aq-pm", s.pm25);
  const aqc = { Good: "good", Moderate: "warn", Poor: "bad" }[s.air];
  $("aq-label").className = aqc;
  $("co2-bar").style.width = clamp(((s.co2 - 400) / 1200) * 100, 0, 100) + "%";

  // Alarm
  set("alarm-val", st.alarm);
  set("alarm-badge", s.alarm ? "ALARM" : "OK");
  $("alarm-badge").className = "badge" + (s.alarm ? " bad" : "");
  $("alarm-banner").classList.toggle("hidden", !s.alarm);

  // Status strip
  set("ss-air", s.air); $("ss-air").className = aqc;
  const diff = s.temperature - st.target;
  const tl = Math.abs(diff) <= 1 ? "Comfortable" : diff > 0 ? "Warm" : "Cool";
  set("ss-temp", tl + " · " + s.temperature + "°C");
  $("ss-temp").className = Math.abs(diff) <= 1 ? "good" : "warn";
  set("ss-occ", s.occupants + " at home");
  set("ss-sec", s.secure ? "Protected" : "Check door/window");
  $("ss-sec").className = s.secure ? "good" : "warn";

  // Members
  $("members").innerHTML = Object.entries(st.members).map(([n, home]) => `
    <button class="member ${home ? "in" : ""}" onclick="setMember('${n}', ${!home})">
      <div class="av">${n[0]}</div>${n}<small>${home ? "Home" : "Away"}</small>
    </button>`).join("");

  // Rules
  setRule("rule1", d.window ? "on" : "", d.window ? "TRIGGERED · Heater locked OFF" : "Waiting · Window closed");
  setRule("rule2", st.auto ? "ok" : "", st.auto ? `ACTIVE · target ${st.target}°C` : "Disabled · Auto OFF hai");
  setRule("rule3", s.alarm ? "bad" : "", s.alarm ? "TRIGGERED · Alarm ON" : `Waiting · limit ${st.alarm}°C`);

  // Lists
  $("logs").innerHTML = s.logs.map((l) => `<li>${l}</li>`).join("");
  $("notifs").innerHTML = s.notifications.length
    ? s.notifications.map((n) => `<li>${n.time.slice(11)} · ${n.activity}</li>`).join("")
    : `<li class="empty">Koi notification nahi</li>`;
  set("bell-n", s.notifications.length);

  // Charts
  fill(charts.power, s.power_hist.map((_, i) => i + 1), s.power_hist);

  // Energy view
  set("e-kw", s.total_kw); set("e-kwh", s.kwh_total); set("e-cost", s.cost);
  set("e-active", Object.values(d).filter(Boolean).length + " / " + DEVICES.length);
  const names = { ...Object.fromEntries(DEVICES.map((x) => [x.id, x.name])), wifi: "Wi-Fi Router" };
  const keys = Object.keys(s.energy);
  fill(charts.energy, keys.map((k) => names[k]), keys.map((k) => s.energy[k]));
  const maxP = Math.max(1, ...Object.values(s.power));
  $("power-list").innerHTML = keys.map((k) => `
    <li><div class="row"><span>${names[k]}</span><span>${s.power[k]} W</span></div>
    <div class="bar"><i style="width:${(s.power[k] / maxP) * 100}%"></i></div></li>`).join("");
}

function setRule(id, cls, text) {
  $(id).textContent = text;
  $(id).className = "rule-status " + cls;
}

/* ---------- DATA LOADING ---------- */
async function refresh() {
  try {
    S = await (await fetch("/api/status")).json();
    render(S);
    const h = await (await fetch("/api/history?n=30")).json();
    fill(charts.main, h.map((p) => p.t), h.map((p) => p.temp), h.map((p) => p.hum));
    if (activeView === "logs") loadLogs();
    if (activeView === "records" && rawPage === 1) loadRaw();
    if (activeView === "analytics") loadAnalytics();
  } catch (e) {
    console.error("refresh error", e);
  }
}

async function loadAnalytics() {
  const h = await (await fetch("/api/history?n=100")).json();
  if (!h.length) return;
  const t = h.map((p) => p.temp), hm = h.map((p) => p.hum);
  const avg = (a) => (a.reduce((x, y) => x + y, 0) / a.length).toFixed(1);
  fill(charts.temp, h.map((p) => p.t), t);
  fill(charts.hum, h.map((p) => p.t), hm);
  set("s-min", Math.min(...t) + "°C");
  set("s-max", Math.max(...t) + "°C");
  set("s-avg", avg(t) + "°C");
  set("s-hum", avg(hm) + "%");
}

async function loadLogs() {
  const r = await (await fetch("/api/records")).json();
  $("logs-table").innerHTML = r.logs.map((l) => `
    <tr><td>${l.time}</td><td>${l.activity}</td>
    <td><span class="tag ${tagClass(l.status)}">${l.status}</span></td></tr>`).join("");
}

async function loadRaw() {
  const r = await (await fetch(`/api/raw?page=${rawPage}&per=10`)).json();
  rawPage = r.page; rawPages = r.pages;
  $("rec-room").innerHTML = r.rows.map((d) => `
    <tr><td>${d.id}</td><td>${d.temperature}°C</td><td>${d.humidity}%</td><td>${d.date}</td></tr>`).join("");
  set("pg-info", `Page ${r.page} / ${r.pages} · ${r.total} records`);
  $("pg-prev").disabled = r.page <= 1;
  $("pg-next").disabled = r.page >= r.pages;
}

function changePage(d) {
  rawPage = clamp(rawPage + d, 1, rawPages);
  loadRaw();
}

/* ---------- COMMANDS ---------- */
async function post(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

async function sendCommand(device, state, version) {
  const data = await post("/api/command", { device, state, version });
  toast(data.message, data.success);
  refresh();
}

function toggle(device, ev) {
  ev.preventDefault(); // UI sirf server ke jawab ke baad badlega
  const v = nextVersion[device]++;
  sendCommand(device, !S.devices[device], v);
}

async function setSetting(obj) {
  const data = await post("/api/settings", obj);
  toast(data.message, data.success);
  refresh();
}

function setMember(name, home) { setSetting({ member: name, home }); }
function stepTarget(d) { setSetting({ target: S.settings.target + d }); }
function stepAlarm(d) { setSetting({ alarm: S.settings.alarm + d }); }
function toggleAuto(ev) { ev.preventDefault(); setSetting({ auto: !S.settings.auto }); }

async function scene(name) {
  const data = await post("/api/scene", { scene: name });
  toast(data.message, data.success);
  refresh();
}

/* ---------- DELAYED COMMAND DEMOS ---------- */
function sendStale() {
  // Server ke current version ya usse purana version -> ignore hoga
  sendCommand("ac", true, S.versions.ac);
}

async function outOfOrder() {
  const v = nextVersion.light;      // purani command
  nextVersion.light += 2;
  await sendCommand("light", true, v + 1);        // nayi command pehle pahunchi
  toast("Nayi command (v" + (v + 1) + ") apply hui. Purani abhi raaste mein...");
  setTimeout(() => sendCommand("light", false, v), 1800);   // purani late pahunchi
}

/* ---------- CLOCK + START ---------- */
setInterval(() => { set("clock", new Date().toLocaleTimeString()); }, 1000);
refresh();
setInterval(refresh, 2000);