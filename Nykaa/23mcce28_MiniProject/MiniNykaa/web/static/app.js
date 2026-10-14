// MiniNykaa frontend. No frameworks, no build step - plain fetch() calls
// against the HTTP bridge in web_server.py, which itself talks to the
// socket-based Gateway. The browser never touches raw sockets directly
// (browsers can't open arbitrary TCP sockets); web_server.py is the bridge.

const TILE_COLORS = { Makeup: "#E80071", Skincare: "#2F9E5B", Haircare: "#B06B2B", Fragrance: "#6B4FA0" };
const TILE_ICON = { Makeup: "💄", Skincare: "🧴", Haircare: "💆", Fragrance: "🌸" };

// Some browser contexts (private/incognito mode in a few older browsers,
// and some embedded renderers) make `localStorage` itself null/throw
// rather than just an empty store, so every access is wrapped.
const storage = {
  get(key) { try { return localStorage.getItem(key); } catch (e) { return null; } },
  set(key, val) { try { localStorage.setItem(key, val); } catch (e) { /* ignore */ } }
};

let currentUser = storage.get("mininykaa_user") || null;
let currentCategory = "";
let lastNodeStatus = {};

// ------------------------------------------------------------ small utils
function $(sel) { return document.querySelector(sel); }
function $all(sel) { return document.querySelectorAll(sel); }

// Plain-for-loop iterator used everywhere instead of NodeList.forEach /
// Object.entries / object spread. Those are all unsupported in some older
// or embedded WebKit-based renderers (confirmed while testing this site),
// so sticking to ES5-level constructs here keeps the storefront working on
// the widest range of browsers, old and new.
function each(listLike, fn) {
  for (let i = 0; i < listLike.length; i++) fn(listLike[i], i);
}
function shallowCopy(obj) {
  const out = {};
  for (const k in obj) if (Object.prototype.hasOwnProperty.call(obj, k)) out[k] = obj[k];
  return out;
}

function toast(msg, kind) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (kind ? " " + kind : "");
  t.classList.remove("hidden");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => t.classList.add("hidden"), 3200);
}

// Plain XMLHttpRequest wrapped in a Promise instead of fetch(). fetch() is
// unsupported in some older embedded/headless renderers (and some kiosk
// browsers); XHR has been universally supported since IE7, so this keeps
// the site working everywhere without a polyfill.
function api(path, opts) {
  opts = opts || {};
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(opts.method || "GET", path, true);
    if (opts.headers) {
      Object.keys(opts.headers).forEach(h => xhr.setRequestHeader(h, opts.headers[h]));
    }
    xhr.onload = () => {
      try { resolve(JSON.parse(xhr.responseText)); }
      catch (e) { resolve({ status: "ERROR", message: "bad response from server" }); }
    };
    xhr.onerror = () => resolve({ status: "ERROR", message: "network error" });
    xhr.send(opts.body || null);
  });
}

function userQuery() {
  return currentUser ? `?user=${encodeURIComponent(currentUser)}` : "";
}

// Small helpers used instead of URLSearchParams, which some embedded /
// older WebKit-based renderers (used for automated screenshots in the
// tutorial) do not implement. Manual string building keeps the site
// working on the widest range of browsers.
function buildQuery(pairs) {
  const parts = [];
  Object.keys(pairs).forEach(k => {
    if (pairs[k] !== undefined && pairs[k] !== null && pairs[k] !== "") {
      parts.push(encodeURIComponent(k) + "=" + encodeURIComponent(pairs[k]));
    }
  });
  return parts.join("&");
}
function parseQuery(search) {
  const out = {};
  (search || "").replace(/^\?/, "").split("&").forEach(pair => {
    if (!pair) return;
    const idx = pair.indexOf("=");
    const k = decodeURIComponent(idx >= 0 ? pair.slice(0, idx) : pair);
    const v = idx >= 0 ? decodeURIComponent(pair.slice(idx + 1).replace(/\+/g, " ")) : "";
    out[k] = v;
  });
  return out;
}

// -------------------------------------------------------------- sign in
function refreshUserUI() {
  const chip = $("#user-chip"), btn = $("#signin-btn");
  if (currentUser) {
    chip.textContent = "Hi, " + currentUser;
    chip.classList.remove("hidden");
    btn.textContent = "Switch user";
  } else {
    chip.classList.add("hidden");
    btn.textContent = "Sign in";
  }
}

$("#signin-btn").onclick = () => $("#signin-modal").classList.remove("hidden");
$("#signin-cancel").onclick = () => $("#signin-modal").classList.add("hidden");
$("#signin-ok").onclick = () => {
  const name = $("#signin-name").value.trim();
  if (!name) return;
  currentUser = name;
  storage.set("mininykaa_user", name);
  $("#signin-modal").classList.add("hidden");
  $("#signin-name").value = "";
  refreshUserUI();
  refreshCartBadge();
  toast("Signed in as " + name, "success");
};

// ------------------------------------------------------------- navigation
function showView(name) {
  each($all(".view"), v => v.classList.add("hidden"));
  $("#view-" + name).classList.remove("hidden");
  if (name === "cart") loadCart();
  if (name === "orders") loadOrders();
  if (name === "system") loadSystem();
}

each($all("[data-view]"), el => {
  el.addEventListener("click", e => {
    e.preventDefault();
    if (el.dataset.cat !== undefined) { currentCategory = el.dataset.cat; loadCatalog(); }
    showView(el.dataset.view);
  });
});

// --------------------------------------------------------------- catalog
function loadCatalog(keyword) {
  const qs = buildQuery({ q: keyword, category: currentCategory });
  return api("/api/catalog" + (qs ? "?" + qs : "")).then(r => {
    if (r.status !== "OK") { toast("Error loading catalog: " + r.message, "error"); return; }
    renderProducts(r.products);
    $("#shard-note").textContent = `Showing ${r.products.length} products, merged from shards: ${(r.shards_used || []).join(", ")}`;
  });
}

function renderProducts(products) {
  const grid = $("#product-grid");
  grid.innerHTML = "";
  products.sort((a, b) => a.product_id.localeCompare(b.product_id)).forEach(p => {
    const card = document.createElement("div");
    card.className = "card";
    const outOfStock = p.stock <= 0;
    const lowStock = !outOfStock && p.stock <= 10;
    card.className = "card" + (outOfStock ? " oos" : "");
    card.setAttribute("data-pid", p.product_id);
    card.innerHTML = `
      <div class="card-tile" style="background:${TILE_COLORS[p.category] || '#999'}">
        <img src="/img/${p.product_id}.svg" alt="${p.name}">
        <span class="card-badge">${p.category}</span>
        ${outOfStock ? '<span class="oos-badge">OUT OF STOCK</span>' : (lowStock ? `<span class="low-badge">Only ${p.stock} left</span>` : "")}
      </div>
      <div class="card-body">
        <div class="card-brand">${p.brand}</div>
        <div class="card-name">${p.name}</div>
        <div class="card-price">Rs. ${p.price}</div>
        <div class="card-stock">${outOfStock ? "Currently unavailable" : p.stock + " in stock · " + p.product_id}</div>
        <div class="card-actions">
          <input type="number" class="qty-input" min="1" max="${Math.max(p.stock,1)}" value="1" ${outOfStock ? "disabled" : ""}>
          <button class="add-btn" ${outOfStock ? "disabled" : ""}>${outOfStock ? "Out of stock" : "Add to cart"}</button>
        </div>
      </div>`;
    const qtyInput = card.querySelector(".qty-input");
    card.querySelector(".add-btn").onclick = () => addToCart(p.product_id, parseInt(qtyInput.value || "1", 10));
    grid.appendChild(card);
  });
}

$("#search-btn").onclick = () => loadCatalog($("#search-box").value.trim());
$("#search-box").addEventListener("keydown", e => { if (e.key === "Enter") loadCatalog($("#search-box").value.trim()); });

// ------------------------------------------------------------------ cart
function requireUser() {
  if (!currentUser) { $("#signin-modal").classList.remove("hidden"); return false; }
  return true;
}

function addToCart(productId, qty) {
  if (!requireUser()) return;
  return api("/api/cart/add", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: currentUser, product_id: productId, qty })
  }).then(r => {
    if (r.status === "OUT_OF_STOCK") {
      toast(r.message, "error");
      loadCatalog($("#search-box").value.trim()); // refresh so the badge/stock number updates
    } else if (r.status !== "OK") {
      toast("Error: " + r.message, "error");
    } else {
      toast(`Added to cart (served by ${r.served_by})`, "success");
      refreshCartBadge();
    }
  });
}

function loadCart() {
  if (!currentUser) { $("#cart-items").innerHTML = "<p class='muted'>Sign in to see your cart.</p>"; return Promise.resolve(); }
  return api("/api/cart" + userQuery()).then(r => {
    if (r.status !== "OK") { toast("Error: " + r.message, "error"); return; }
    renderCart(r.items || [], r.total || 0);
  });
}

function renderCart(items, total) {
  const box = $("#cart-items");
  box.innerHTML = "";
  if (items.length === 0) box.innerHTML = "<p class='muted'>Your cart is empty.</p>";
  items.forEach(i => {
    const row = document.createElement("div");
    row.className = "cart-row";
    row.innerHTML = `
      <img class="ci-img" src="/img/${i.product_id}.svg" alt="">
      <div class="ci-name">${i.name}${!i.in_stock ? `<div class="stock-warning">Only ${i.stock} left — reduce quantity</div>` : ""}</div>
      <div class="ci-price">Rs. ${i.price}</div>
      <div class="ci-qty">
        <button class="qty-btn minus">−</button>
        <span>${i.qty}</span>
        <button class="qty-btn plus">+</button>
      </div>
      <div class="ci-sub">Rs. ${i.subtotal}</div>
      <button class="remove-btn">Remove</button>`;
    row.querySelector(".minus").onclick = () => updateCartQty(i.product_id, i.qty - 1);
    row.querySelector(".plus").onclick = () => updateCartQty(i.product_id, i.qty + 1);
    row.querySelector(".remove-btn").onclick = () => removeFromCart(i.product_id);
    box.appendChild(row);
  });
  $("#cart-total").textContent = "Rs. " + total;
  $("#checkout-btn").disabled = items.length === 0 || items.some(i => !i.in_stock);
}

function updateCartQty(productId, qty) {
  if (qty <= 0) return removeFromCart(productId);
  return api("/api/cart/update", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: currentUser, product_id: productId, qty })
  }).then(r => {
    if (r.status === "OUT_OF_STOCK") toast(r.message, "error");
    else if (r.status !== "OK") toast("Error: " + r.message, "error");
    loadCart();
    refreshCartBadge();
  });
}

function removeFromCart(productId) {
  return api("/api/cart/remove", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: currentUser, product_id: productId })
  }).then(() => {
    loadCart();
    refreshCartBadge();
  });
}

function refreshCartBadge() {
  if (!currentUser) { $("#cart-badge").classList.add("hidden"); return Promise.resolve(); }
  return api("/api/cart" + userQuery()).then(r => {
    const count = (r.items || []).reduce((n, i) => n + i.qty, 0);
    const badge = $("#cart-badge");
    if (count > 0) { badge.textContent = count; badge.classList.remove("hidden"); }
    else badge.classList.add("hidden");
  });
}

$("#checkout-btn").onclick = () => {
  api("/api/checkout", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: currentUser })
  }).then(r => {
    if (r.status === "OK") {
      toast(`Order ${r.order.order_id} confirmed — Rs. ${r.order.total_amount}`, "success");
      showView("orders");
      refreshCartBadge();
    } else {
      toast("Checkout failed: " + r.message, "error");
      loadCart();
    }
  });
};

// ---------------------------------------------------------------- orders
function loadOrders() {
  if (!currentUser) { $("#orders-list").innerHTML = "<p class='muted'>Sign in to see your orders.</p>"; return Promise.resolve(); }
  return api("/api/orders" + userQuery()).then(r => {
    const box = $("#orders-list");
    box.innerHTML = "";
    if (r.status !== "OK") { toast("Error: " + r.message, "error"); return; }
    if (r.orders.length === 0) box.innerHTML = "<p class='muted'>No orders yet.</p>";
    r.orders.slice().reverse().forEach(o => {
      const div = document.createElement("div");
      div.className = "order-card";
      div.innerHTML = `
        <div class="order-head"><span>${o.order_id}</span><span class="order-status ${o.status === "CANCELLED" ? "cancelled" : ""}">${o.status}</span></div>
        <div class="order-items">${o.items.map(i => `${i.name} × ${i.qty}`).join(", ")}</div>
        <div style="margin-top:6px;font-weight:700;">Rs. ${o.total_amount}</div>
        ${o.status === "CANCELLED" ? '<div class="restock-note">Cancelled — items returned to stock.</div>' : '<button class="cancel-btn">Cancel order</button>'}`;
      const cb = div.querySelector(".cancel-btn");
      if (cb) cb.onclick = () => cancelOrder(o.order_id);
      box.appendChild(div);
    });
  });
}

function cancelOrder(orderId) {
  if (!window.confirm("Cancel order " + orderId + "? The items will be returned to stock.")) return;
  api("/api/orders/cancel", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: currentUser, order_id: orderId })
  }).then(r => {
    if (r.status === "OK") toast("Order " + orderId + " cancelled — stock restored", "success");
    else toast("Could not cancel: " + r.message, "error");
    loadOrders();
    loadCatalog($("#search-box").value.trim());
  });
}

// ---------------------------------------------------------------- system
function sysTile(name, state, metaHtml, cls) {
  return `<div class="node-card ${cls || (state === "UP" ? "up" : "down")}"><div class="nc-name">${name}</div>` +
         `<div class="nc-state">${state}</div><div class="nc-meta">${metaHtml || ""}</div></div>`;
}
function sysGroup(title, sub, tiles) {
  return `<div class="sys-group"><h3>${title}</h3><div class="sub">${sub}</div><div class="sys-row">${tiles.join("")}</div></div>`;
}
function loadSystem() {
  return api("/api/status").then(r => {
    const root = $("#node-grid");
    if (r.status !== "OK") { root.innerHTML = "<p class='muted'>Gateway unreachable.</p>"; return; }
    const nodes = r.nodes || {}, gws = r.gateways || {};
    const leader = nodes.active_order_node;
    const logLines = [];
    const watch = (key, label, val) => {
      if (lastNodeStatus[key] !== undefined && lastNodeStatus[key] !== val)
        logLines.push(`${new Date().toLocaleTimeString()}  ${label}: ${lastNodeStatus[key]} -> ${val}`);
      lastNodeStatus[key] = val;
    };
    let html = "";
    html += sysGroup("1. Load balancer (front door, port 5000)",
      "Every request lands here first and is handed to a healthy gateway.",
      [sysTile("load-balancer", "UP", `algorithm: <b>${(r.lb || {}).algo || "?"}</b>`, "lb")]);
    const gTiles = [];
    each(Object.keys(gws), n => {
      const g = gws[n], c = g.cache;
      watch("gw:" + n, n, g.state);
      const meta = `requests handled: <b>${g.requests}</b><br>in flight: ${g.inflight} · failures: ${g.failures}` +
                   (c ? `<br>cache: ${c.hits} hits / ${c.misses} misses (<b>${c.hit_rate}%</b>)<br>size ${c.size}/${c.capacity} · TTL ${c.ttl_sec}s · evict ${c.evictions}` : "");
      gTiles.push(sysTile(n, g.state, meta));
    });
    html += sysGroup("2. Gateways (stateless, each with an LRU+TTL cache)",
      "Round-robin / least-connections picks one per request. A crashed gateway is skipped and the request retried.", gTiles);
    const cTiles = [];
    each(["catalog-1", "catalog-2", "catalog-3"], n => { watch("n:" + n, n, nodes[n]); cTiles.push(sysTile(n, nodes[n] || "DOWN", "consistent-hash shard")); });
    html += sysGroup("3. Catalog shards", "Products are partitioned across shards with consistent hashing.", cTiles);
    const oTiles = [];
    each(["order-1", "order-2", "order-3"], n => {
      watch("n:" + n, n, nodes[n]);
      const isL = (n === leader && nodes[n] === "UP");
      oTiles.push(`<div class="node-card ${nodes[n] === "UP" ? "up" : "down"}${isL ? " leader" : ""}"><div class="nc-name">${n}${isL ? '<span class="crown">LEADER</span>' : ""}</div>` +
                  `<div class="nc-state">${nodes[n] || "DOWN"}</div><div class="nc-meta">Bully id = ${n.slice(-1)}${isL ? " (highest alive id)" : ""}</div></div>`);
    });
    watch("leader", "order leader", leader);
    html += sysGroup("4. Order service (Bully leader election)", "The highest-id alive node leads. Kill the leader and the next-highest takes over.", oTiles);
    root.innerHTML = html;
    if (logLines.length) {
      const log = $("#system-log");
      log.textContent = (logLines.join("\n") + "\n" + log.textContent).split("\n").slice(0, 14).join("\n");
    }
  });
}
setInterval(() => { if (!$("#view-system").classList.contains("hidden")) loadSystem(); }, 2000);


// ------------------------------------------------- Get App / Stores / Gift / Help
// Static demo content (no real stores, payments or app). Help is a plain FAQ.
function qrHtml() {
  // decorative QR-style pattern (not a scannable code), deterministic
  let cells = "", seed = 7;
  for (let y = 0; y < 21; y++) for (let x = 0; x < 21; x++) {
    const finder = (x < 7 && y < 7) || (x > 13 && y < 7) || (x < 7 && y > 13);
    let on;
    if (finder) { const fx = x % 14 > 6 ? x - 14 : x, fy = y > 13 ? y - 14 : y; on = (fx === 0 || fx === 6 || fy === 0 || fy === 6 || (fx > 1 && fx < 5 && fy > 1 && fy < 5)); }
    else { seed = (seed * 1103515245 + 12345) & 0x7fffffff; on = (seed >> 8) % 2 === 0; }
    cells += `<i class="${on ? "k" : ""}"></i>`;
  }
  return `<div class="qr">${cells}</div>`;
}

const PANELS = {
  app: () => `<div class="panel"><h3>📱 Get the MiniNykaa app</h3><span class="tag">Demo</span>
    <p>This prototype is a website only — there is no real mobile app. This panel shows where an app-download page would live.</p>
    ${qrHtml()}<ul><li>Browse the sharded catalog on your phone</li><li>Track and cancel orders</li><li>Live stock updates over a WebSocket</li></ul></div>`,
  stores: () => `<div class="panel"><h3>📍 Store &amp; Events</h3><span class="tag">Sample data</span>
    <div class="store-row"><b>MiniNykaa Luxe — Mumbai</b><br>Sample mall address · 10:00–22:00</div>
    <div class="store-row"><b>MiniNykaa On Trend — Delhi</b><br>Sample market road · 10:00–21:30</div>
    <div class="store-row"><b>MiniNykaa — Bengaluru</b><br>Sample high street · 10:00–22:00</div>
    <h3 style="margin-top:16px">Upcoming events</h3>
    <div class="event-row"><b>Skincare Masterclass</b> · Sat 11:00 · in-store</div>
    <div class="event-row"><b>Makeup Live: Festive Looks</b> · Sun 16:00 · online</div></div>`,
  gift: () => `<div class="panel"><h3>🎁 Gift Card</h3><span class="tag">Demo — no payment</span>
    <p>Pick an amount and a name to generate a gift-card code.</p>
    <div class="gift-amounts"><button class="gift-amt" data-a="500">Rs. 500</button><button class="gift-amt sel" data-a="1000">Rs. 1000</button><button class="gift-amt" data-a="2000">Rs. 2000</button></div>
    <input type="text" id="gift-to" placeholder="Recipient name">
    <button class="pink-btn" id="gift-make">Generate gift card</button><div id="gift-out"></div></div>`,
  help: () => `<div class="panel"><h3>❓ Help &amp; FAQ</h3><span class="tag">Self-service</span>
    <button class="faq-q">How do I change or remove an item in my cart?</button><div class="faq-a">Open the cart (bag icon). Use − and + to change the quantity, or Remove to delete the line.</div>
    <button class="faq-q">Why can't I add more of a product?</button><div class="faq-a">You can't add more than the units in stock (counting what is already in your cart). The product card shows "Only N left" or "Out of stock".</div>
    <button class="faq-q">How do I cancel an order?</button><div class="faq-a">Go to Orders (box icon) and press "Cancel order" on a confirmed order. The items are returned to stock immediately.</div>
    <button class="faq-q">What does the System icon show?</button><div class="faq-a">Live health of every backend node. If the order primary goes down, the backup takes over automatically.</div>
    <button class="faq-q">Is my data saved?</button><div class="faq-a">No — everything is held in memory and resets when the backend restarts.</div></div>`
};

function openPanel(name) {
  $("#panel-body").innerHTML = PANELS[name]();
  $("#panel-modal").classList.remove("hidden");
  each($all(".faq-q"), q => { q.onclick = () => q.nextElementSibling.classList.toggle("open"); });
  each($all(".gift-amt"), b => { b.onclick = () => { each($all(".gift-amt"), x => x.classList.remove("sel")); b.classList.add("sel"); }; });
  const mk = $("#gift-make");
  if (mk) mk.onclick = () => {
    const sel = $(".gift-amt.sel"), to = ($("#gift-to").value || "a friend").trim();
    const code = "MN-" + Math.random().toString(36).slice(2, 6).toUpperCase() + "-" + Math.random().toString(36).slice(2, 6).toUpperCase();
    $("#gift-out").innerHTML = `<div class="gift-card-view"><div>Gift card for ${to}</div><div class="code">${code}</div><div>Value: Rs. ${sel.getAttribute("data-a")}</div></div>`;
  };
}
each($all("[data-panel]"), el => el.addEventListener("click", e => { e.preventDefault(); openPanel(el.getAttribute("data-panel")); }));
$("#panel-close").onclick = () => $("#panel-modal").classList.add("hidden");

// ------------------------------------------------------------ WebSocket push
// The page keeps one WebSocket open to ws_server.py (raw-socket server).
// The server pushes whenever node health or any product's stock changes, so
// badges and the System tab update with no polling and no refresh.
let wsOk = false;
function applyLiveUpdate(msg) {
  if (msg.nodes && !$("#view-system").classList.contains("hidden")) loadSystem();
  if (msg.stock && !$("#view-catalog").classList.contains("hidden")) {
    each($all(".card"), card => {
      const pid = card.getAttribute("data-pid"), now = msg.stock[pid], was = products[pid];
      if (now !== undefined && was !== undefined && now !== was) { loadCatalog($("#search-box").value.trim()); return; }
    });
  }
  if (msg.stock) { products = msg.stock; }
}
let products = {};
function connectWS() {
  try {
    const proto = location.protocol === "https:" ? "wss://" : "ws://";
    const ws = new WebSocket(proto + location.hostname + ":8081/");
    ws.onopen = () => { wsOk = true; const d = $("#live-dot"); d.textContent = "● live"; d.className = "live-dot on"; };
    ws.onmessage = ev => { try { applyLiveUpdate(JSON.parse(ev.data)); } catch (e) {} };
    ws.onclose = () => { wsOk = false; const d = $("#live-dot"); d.textContent = "● offline"; d.className = "live-dot"; setTimeout(connectWS, 3000); };
  } catch (e) { /* WebSocket unavailable: the page still works via normal requests */ }
}

// ------------------------------------------------------------------ init
// Optional URL parameters make specific screens linkable/bookmarkable, e.g.
// /?user=priya&view=cart or /?q=serum - also handy for scripted demos.
(function init() {
  try {
    const params = parseQuery(location.search);
    if (params.user) {
      currentUser = params.user;
      storage.set("mininykaa_user", currentUser);
    }
    refreshUserUI();
    if (params.cat) currentCategory = params.cat;
    loadCatalog(params.q || undefined);
    refreshCartBadge();
    if (params.view) showView(params.view);
    if (params.panel && PANELS[params.panel]) openPanel(params.panel);
    connectWS();
  } catch (e) {
    // Fall back to a plain catalog load even if URL-parameter handling
    // fails for any reason, so the storefront still works.
    refreshUserUI();
    loadCatalog();
    refreshCartBadge();
  }
})();
