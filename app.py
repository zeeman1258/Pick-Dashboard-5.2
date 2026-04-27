from flask import Flask, request, jsonify, render_template_string, Response, session
import requests, re, sqlite3, os, json, signal, threading, webbrowser, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, 'pick_dashboard.db')
REQUESTS_ARCHIVE_DIR = os.path.join(BASE_DIR, 'requests')
USERS_TXT_PATH = os.path.join(BASE_DIR, 'users.txt')
MAIN_ADMIN_USERNAME = os.environ.get('MAIN_ADMIN_USERNAME', 'zeck')
MAIN_ADMIN_PASSWORD = os.environ.get('MAIN_ADMIN_PASSWORD', 'zeeman1258')
DEFAULT_SITE_USERNAME = os.environ.get('DEFAULT_SITE_USERNAME', 'zeckm')
DEFAULT_SITE_PASSWORD = os.environ.get('DEFAULT_SITE_PASSWORD', 'Zm0948')
SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-secret-key')
HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', '10000'))
ROUTE_CACHE = {}
ROUTE_CACHE_LOCK = threading.Lock()
CACHE_TTL_SECONDS = 150
REQUEST_TIMEOUT = 12
MAX_ROUTE_SCAN = 20
BASE_ROOTS = {'liquor': 'http://dp1.bellboycorp.com', 'hemp': 'http://dp4.bellboycorp.com'}
LAST_REFRESH = {}

app = Flask(__name__)
app.secret_key = SECRET_KEY

HTML = r'''
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Pick Dashboard</title>
  <link href="https://api.fontshare.com/v2/css?f[]=satoshi@400,500,700&display=swap" rel="stylesheet">
  <style>
    :root, [data-theme="light"] {--bg:#f7f6f2;--surface:#f9f8f5;--surface2:#fbfbf9;--offset:#f3f0ec;--border:#d4d1ca;--divider:#dcd9d5;--text:#28251d;--muted:#6f6d67;--primary:#01696f;--primary2:#cedcd8;--error:#a12c7b;--warn:#da7101;--success:#437a22;--radius:.9rem;--shadow:0 8px 24px rgba(0,0,0,.08)}
    [data-theme="dark"] {--bg:#171614;--surface:#1c1b19;--surface2:#201f1d;--offset:#22211f;--border:#393836;--divider:#262523;--text:#e3e1dd;--muted:#aaa8a3;--primary:#4f98a3;--primary2:#313b3b;--error:#d163a7;--warn:#fdab43;--success:#6daa45;--radius:.9rem;--shadow:0 12px 32px rgba(0,0,0,.34)}
    *{box-sizing:border-box}body{margin:0;font-family:'Satoshi',system-ui,sans-serif;background:var(--bg);color:var(--text)}button,input,select,textarea{font:inherit;color:inherit}button{cursor:pointer}table{width:100%;border-collapse:collapse}
    .wrap{display:grid;grid-template-columns:300px 1fr;min-height:100vh}.side{padding:24px;background:var(--surface);border-right:1px solid var(--divider);display:grid;gap:18px;align-content:start}.main{padding:24px;display:grid;gap:18px}
    .card{background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius);padding:18px;box-shadow:var(--shadow)}
    .brand{display:flex;gap:12px;align-items:center}.logo{width:40px;height:40px;border-radius:12px;display:grid;place-items:center;background:linear-gradient(135deg,var(--primary),transparent)}
    h1,h2,h3,p{margin:0}.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:10px}.field{display:grid;gap:6px}.field label{font-size:14px;color:var(--muted)}
    .field input,.field select,.field textarea{width:100%;padding:12px 13px;border-radius:12px;border:1px solid var(--border);background:var(--surface)}.btn{border:0;border-radius:12px;padding:12px 14px;font-weight:700}.primary{background:var(--primary);color:#fff}.secondary{background:var(--offset);border:1px solid var(--border)} .ghost{background:transparent;border:1px dashed var(--border)} .danger{background:var(--error);color:#fff}
    .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.metric{font-size:34px;font-weight:700;font-variant-numeric:tabular-nums}.status{padding:12px 14px;border-radius:12px;background:var(--offset);border:1px solid var(--border);font-size:14px}.error{color:var(--error);border-color:color-mix(in srgb,var(--error) 50%, var(--border))}
    th,td{padding:12px 10px;border-bottom:1px solid var(--divider);text-align:left;font-size:14px;vertical-align:top}th{color:var(--muted)} .badge{display:inline-flex;padding:4px 10px;border-radius:999px;background:var(--primary2);color:var(--primary);font-size:12px;font-weight:700}
    .layout{display:grid;grid-template-columns:1.1fr .9fr;gap:16px}.muted{color:var(--muted)} .warn{color:var(--warn);font-weight:700}
    .tabs{display:flex;gap:10px;flex-wrap:wrap}.tab.active{background:var(--primary);color:#fff}.hidden{display:none!important}.toolbar{display:flex;justify-content:space-between;gap:12px;align-items:flex-end;flex-wrap:wrap;margin-bottom:12px}
    .auth{position:fixed;inset:0;background:rgba(0,0,0,.55);backdrop-filter:blur(8px);display:grid;place-items:center;padding:20px;z-index:10}.authCard{width:min(440px,100%)} .split{display:grid;grid-template-columns:1fr 1fr;gap:16px} .ticket{padding:14px;border:1px solid var(--border);border-radius:12px;background:var(--surface);margin-bottom:12px} .ticket-meta{font-size:13px;color:var(--muted);margin-bottom:8px}
    @media (max-width:1100px){.wrap{grid-template-columns:1fr}.kpis,.layout,.split{grid-template-columns:1fr}}
  </style>
</head>
<body>
<div id="authScreen" class="auth">
  <div class="card authCard">
    <div class="brand"><div class="logo">⇢</div><div><h1 style="font-size:22px">Pick Dashboard</h1><p class="muted" style="font-size:14px">Multi-user local app</p></div></div>
    <div id="authMessage" class="status hidden" style="margin-top:14px"></div>
    <div id="loginPane" class="split" style="margin-top:14px">
      <div class="field"><label>Username</label><input id="appUsername" type="text"></div>
      <div class="field"><label>Password</label><input id="appPassword" type="password"></div>
    </div>
    <button class="btn primary" id="loginBtn" style="width:100%;margin-top:14px">Login</button>
  </div>
</div>
<div class="wrap hidden" id="appWrap">
  <aside class="side">
    <div class="brand"><div class="logo">⇢</div><div><h1 style="font-size:22px">Pick Dashboard 5.1.5</h1><p class="muted" style="font-size:14px">Multi-user route loader</p></div></div>
    <div class="card"><div class="eyebrow">Signed in</div><div id="currentUserBox" class="muted">Not signed in</div><div style="margin-top:12px"><button class="btn secondary" id="logoutBtn" style="width:100%">Logout</button></div></div>
    
    <div class="card"><div class="eyebrow">Routes</div><div class="field"><label>Day prefix</label><select id="day"><option>MON</option><option selected>TUE</option><option>WED</option><option>THU</option><option>FRI</option></select></div><div class="field"><label>Warehouse</label><select id="warehouse"><option value="hemp" selected>Hemp</option><option value="liquor">Liquor</option></select></div><div class="muted" style="margin-top:10px;font-size:13px">Routes auto-detect and refresh every 3 minutes.</div></div>
    <div class="card hidden" id="adminSidebarCard"><div class="eyebrow">Admin</div><button class="btn secondary" id="showAdminBtn" style="width:100%">Open account admin</button></div>
  </aside>
  <main class="main">
    <div style="display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap"><div style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start"><button class="btn secondary" id="restartBtn" style="display:none">Restart app</button><button class="btn secondary" id="manualRefreshBtn">Refresh now</button><button class="btn secondary" id="saveTonightBtn" onclick="saveTonightRoutes()">Save tonight's routes</button><button class="btn secondary" id="routeDebugBtn">Route debug</button><div><h2 style="font-size:30px">Route picking</h2><p class="muted">Live ordered totals, stock levels, and day views</p><p class="muted" id="lastRefreshText" style="font-size:13px;margin-top:4px">Last refresh: not yet</p></div></div><div style="display:flex;gap:10px;flex-wrap:wrap"><a class="btn secondary" id="ordersPageBtn" href="/orders-window" target="PickDashboardOrders" rel="noopener noreferrer">Orders</a><button class="btn secondary" id="supportBtn" style="display:none">Request feature</button><button class="btn secondary" id="accountBtn">My account</button><button class="btn secondary" id="themeBtn">Toggle theme</button></div></div>
    <div class="tabs">
      <button class="btn tab active" data-view="routesView">Route totals</button>
      <button class="btn tab ghost" data-view="itemsView">All items for day</button>
      <button class="btn tab ghost" data-view="stockView">Needs stocked</button>
      <button class="btn tab ghost" data-view="printView">Print pick sheet</button>
    </div>
    <div id="status" class="status">Ready.</div><div id="routeDebugPanel" class="card hidden" style="margin-top:12px"><div class="eyebrow">Route debug</div><pre id="routeDebugOutput" style="white-space:pre-wrap;font-size:13px;line-height:1.5"></pre></div>
    <section class="kpis">
      <div class="card"><div class="eyebrow">Routes loaded</div><div class="metric" id="routesLoaded">0</div></div>
      <div class="card"><div class="eyebrow">Total ordered</div><div class="metric" id="totalQty">0</div></div>
      <div class="card"><div class="eyebrow">Unique items</div><div class="metric" id="uniqueItems">0</div></div>
      <div class="card"><div class="eyebrow">Needs stocked</div><div class="metric" id="needsStockCount">0</div></div>
    </section>
    <section id="routesView" class="layout"><div class="card"><div class="eyebrow">Route totals</div><table><thead><tr><th>Route</th><th>Name</th><th>Ordered</th><th>Items</th><th>Status</th></tr></thead><tbody id="routeRows"></tbody></table></div><div class="card"><div class="eyebrow">Debug</div><div id="debug" class="muted" style="font-size:14px;line-height:1.6">No route loads yet.</div></div></section>
    <section id="itemsView" class="card hidden"><div class="toolbar"><div><div class="eyebrow">All items ordered for selected day</div></div><div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center"><input id="itemSearch" type="text" placeholder="Search item ID or description" style="min-width:260px;padding:12px 13px;border-radius:12px;border:1px solid var(--border);background:var(--surface)"><button class="btn secondary" id="exportBtn">Export CSV</button></div></div><table><thead><tr><th>Item ID</th><th>Description</th><th>Total ordered</th><th>In stock</th><th>Picked</th><th>Routes</th></tr></thead><tbody id="itemRows"></tbody></table></section>
    <section id="stockView" class="card hidden"><div class="toolbar"><div><div class="eyebrow">Needs to be stocked</div><p class="muted">Items where total ordered is greater than available in-stock quantity.</p></div></div><table><thead><tr><th>Item ID</th><th>Description</th><th>Ordered</th><th>In stock</th><th>Short by</th><th>Routes</th></tr></thead><tbody id="stockRows"></tbody></table></section>
    <section id="printView" class="card hidden"><div class="toolbar"><div><div class="eyebrow">Print-friendly pick sheet</div><p class="muted" id="printSubtitle">Routes update automatically and generate the current pick sheet.</p></div><div style="display:flex;gap:10px;flex-wrap:wrap;align-items:end"><div class="field"><label for="printSort">Sort by</label><select id="printSort"><option value="item_id">Item ID</option><option value="total_ordered">Total quantity</option></select></div><div class="field"><label for="minPrintQty">Minimum quantity</label><input id="minPrintQty" type="number" min="1" value="2" style="width:110px"></div><button class="btn secondary" id="printBtn">Print</button></div></div><table><thead><tr><th>Done</th><th>Item ID</th><th>Description</th><th>Total ordered</th><th>In stock</th><th>Routes</th></tr></thead><tbody id="printRows"></tbody></table></section>
    <section id="ordersPage" class="hidden"><div style="display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap"><div style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start"><button class="btn secondary" id="ordersBackBtn">Back to routes</button><button class="btn secondary" id="ordersRefreshBtn">Refresh orders</button><div><h2 style="font-size:30px">Orders</h2><p class="muted">Current SOP orders kept separate from route mode</p><p class="muted" id="ordersLastRefreshText" style="font-size:13px;margin-top:4px">Last refresh: not yet</p></div></div></div><div class="grid cols-3" style="margin-top:18px"><div class="card"><div class="eyebrow">Orders loaded</div><div class="metric" id="ordersLoaded">0</div></div><div class="card"><div class="eyebrow">Total qty</div><div class="metric" id="ordersTotalQty">0</div></div><div class="card"><div class="eyebrow">Unique items</div><div class="metric" id="ordersUniqueItems">0</div></div></div><section class="layout" style="margin-top:18px"><div class="card"><div class="eyebrow">Order totals</div><table><thead><tr><th>Order</th><th>Customer</th><th>Ordered</th><th>Items</th><th>Status</th></tr></thead><tbody id="ordersRows"></tbody></table></div><div class="card"><div class="eyebrow">Debug</div><div id="ordersDebug" class="muted" style="font-size:14px;line-height:1.6">No order loads yet.</div></div></section><section id="ordersItemsView" class="card" style="margin-top:18px"><div class="toolbar"><div><div class="eyebrow">All items ordered in current orders</div></div><div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center"><input id="ordersItemSearch" type="text" placeholder="Search item ID or description" style="min-width:260px;padding:12px 13px;border-radius:12px;border:1px solid var(--border);background:var(--surface)"></div></div><table><thead><tr><th>Item ID</th><th>Description</th><th>Total ordered</th><th>In stock</th><th>Picked</th><th>Orders</th></tr></thead><tbody id="ordersItemRows"></tbody></table></section><section id="ordersStockView" class="card" style="margin-top:18px"><div class="toolbar"><div><div class="eyebrow">Orders needing stock</div><p class="muted">Items where total ordered is greater than available in-stock quantity.</p></div></div><table><thead><tr><th>Item ID</th><th>Description</th><th>Ordered</th><th>In stock</th><th>Short by</th><th>Orders</th></tr></thead><tbody id="ordersStockRows"></tbody></table></section></section>
    <section id="accountView" class="hidden"><div class="card" style="max-width:720px"><div class="eyebrow">My account</div><div class="split"><div class="field"><label>Username</label><input id="accountUsername"></div><div class="field"><label>Current password</label><input id="accountCurrentPassword" type="password"></div></div><div class="field" style="margin-top:12px"><label>New password</label><input id="accountNewPassword" type="password"></div><button class="btn secondary" id="saveAccountBtn" style="margin-top:12px">Save account changes</button><div id="accountMsg" class="muted" style="margin-top:8px;font-size:13px"></div></div></section>
    <section id="ticketsView" class="hidden"><div class="card" style="max-width:980px"><div class="toolbar"><div><div class="eyebrow">Request feature</div><p class="muted">Users can submit requests and see admin replies here.</p></div></div><div class="card" style="margin-bottom:16px;background:var(--surface);box-shadow:none"><div class="field"><label>Subject</label><input id="requestSubject"></div><div class="field"><label>Request details</label><textarea id="requestBody" rows="6" placeholder="Describe the feature or issue"></textarea></div><button class="btn primary" id="submitRequestBtn" style="margin-top:12px">Send ticket</button><div id="requestMsg" class="muted" style="margin-top:8px;font-size:13px"></div></div><div id="ticketsList"></div></div></section>
    <section id="adminView" class="hidden"><div class="split"><div class="card"><div class="eyebrow">Create user</div><div class="field"><label>Username</label><input id="newUserUsername"></div><div class="field"><label>Password</label><input id="newUserPassword" type="password"></div><div class="field"><label>Admin role</label><select id="newUserAdmin"><option value="false">Regular user</option><option value="true">Admin</option></select></div><button class="btn primary" id="createUserBtn" style="margin-top:12px">Create account</button><div id="adminMessage" class="muted" style="margin-top:12px"></div></div><div class="card"><div class="eyebrow">Manage users</div><table><thead><tr><th>Username</th><th>Role</th><th>Actions</th></tr></thead><tbody id="userRows"></tbody></table></div></div></section>
  </main>
</div>
<script>
const qs=id=>document.getElementById(id);
const state={routes:[],items:[],orders:[],orderItems:[],picked:{},lastPayload:null,lastOrdersPayload:null,currentUser:null,lastRefreshTs:null,lastOrdersRefreshTs:null,autoRefresh:null,loading:false,ordersLoading:false,preferences:{},routeCache:{},ordersCache:{}};
const api=(p)=>new URL(p, window.location.origin).toString();
async function fetchJson(path, options){const res=await fetch(api(path),options);const ct=(res.headers.get('content-type')||'').toLowerCase();const raw=await res.text();if(!ct.includes('application/json')){throw new Error(`Expected JSON from ${path} but received ${ct||'unknown content type'}\n\n${raw.slice(0,400)}`);}let data;try{data=JSON.parse(raw);}catch(err){throw new Error(`Invalid JSON from ${path}\n\n${raw.slice(0,400)}`);}return {res,data};}
qs('themeBtn').onclick=()=>document.documentElement.setAttribute('data-theme',document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark');
function setStatus(msg,isError=false){const el=qs('status');el.textContent=msg;el.classList.toggle('error',!!isError)}
function showAuthMessage(msg,isError=false){const el=qs('authMessage');el.textContent=msg;el.classList.remove('hidden');el.classList.toggle('error',!!isError)}
function showMainView(viewId){document.querySelectorAll('[data-view]').forEach(b=>b.classList.remove('active'));['routesView','itemsView','stockView','printView','adminView','accountView','ticketsView','ordersPage'].forEach(id=>{const el=qs(id); if(el) el.classList.add('hidden');});const target=qs(viewId); if(target) target.classList.remove('hidden');const tab=document.querySelector(`[data-view="${viewId}"]`);if(tab) tab.classList.add('active');}
function updateLastRefresh(ts){state.lastRefreshTs=ts||null;const el=qs('lastRefreshText');if(!ts){el.textContent='Last refresh: not yet';return;}const secs=Math.max(0,Math.floor(Date.now()/1000-ts));el.textContent=secs<60?`Last refresh: ${secs} sec ago`:`Last refresh: ${Math.floor(secs/60)} min ago`;}
setInterval(()=>updateLastRefresh(state.lastRefreshTs),30000);
async function refreshSession(){const {res,data}=await fetchJson('/api/session');state.currentUser=data.user||null;state.preferences=data.preferences||{};if(data.authenticated){qs('authScreen').classList.add('hidden');qs('appWrap').classList.remove('hidden');qs('currentUserBox').innerHTML=`<div><strong>${data.user.username}</strong></div><div>${data.user.is_admin?'Admin':'User'}</div>`;qs('accountUsername').value=data.user.username||'';qs('accountCurrentPassword').value='';qs('accountNewPassword').value='';qs('adminSidebarCard').classList.toggle('hidden',!data.user.is_main_admin);qs('restartBtn').style.display=(data.user.is_admin)?'inline-flex':'none';qs('supportBtn').style.display='inline-flex';qs('day').value=data.user.day||'TUE';qs('warehouse').value=(data.user.base_root||'').includes('dp1.bellboycorp.com')?'liquor':'hemp';if(data.user.is_main_admin) loadUsers();showMainView('routesView');loadPicked();await loadDay(false);if(state.autoRefresh) clearInterval(state.autoRefresh);state.autoRefresh=setInterval(()=>loadDay(false),180000);} else {qs('authScreen').classList.remove('hidden');qs('appWrap').classList.add('hidden');}}
async function loadDay(forceRefresh=false){const cacheKey=getRouteCacheKey();if(!forceRefresh&&state.routeCache[cacheKey]){const cached=state.routeCache[cacheKey];state.routes=cached.routes||[];state.items=cached.items||[];state.lastPayload=cached.lastPayload||null;updateLastRefresh(cached.lastRefresh||null);applyCurrentData();setStatus(`Loaded ${state.routes.length} routes and ${state.items.length} unique items. (saved)`);return;}if(state.loading) return;state.loading=true;setStatus(forceRefresh?'Refreshing routes...':'Loading routes...');try{const payload={username:(state.preferences&&state.preferences.site_username)||'',password:(state.preferences&&state.preferences.site_password)||'',day:qs('day').value,route_count:Number((state.preferences&&state.preferences.route_count)||9),base_root:qs('warehouse').value==='liquor'?'http://dp1.bellboycorp.com':'http://dp4.bellboycorp.com'};if(!payload.username||!payload.password){setStatus('Route site username and password are required in your saved account settings.',true);return;}const {res,data}=await fetchJson('/api/load-routes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(!res.ok){setStatus(data.error||'Failed to load routes',true);return;}state.routes=data.routes||[];state.items=data.items||[];state.lastPayload=payload;const now=Math.floor(Date.now()/1000);state.routeCache[cacheKey]={routes:state.routes,items:state.items,lastPayload:payload,lastRefresh:now};qs('routesLoaded').textContent=state.routes.length.toLocaleString();qs('totalQty').textContent=(state.routes.reduce((s,r)=>s+Number(r.quantity||r.total_qty||0),0)).toLocaleString();qs('uniqueItems').textContent=state.items.length.toLocaleString();applyCurrentData();updateLastRefresh(now);setStatus(`Loaded ${state.routes.length} routes and ${state.items.length} unique items.`);}catch(e){console.error(e);setStatus(String(e&&e.message?e.message:e),true);const panel=qs('routeDebugPanel');const out=qs('routeDebugOutput');if(panel&&out){panel.classList.remove('hidden');out.textContent=String(e&&e.stack?e.stack:e);}}finally{state.loading=false;}}
async function loadPicked(){try{const {res,data}=await fetchJson('/api/picked');state.picked=Object.fromEntries(Object.entries(data.items||{}).map(([k,v])=>[String(k).trim(),v]));applyCurrentData();}catch(e){}}
function getRouteCacheKey(){return `${qs('warehouse').value}|${qs('day').value}`;}
function updateOrdersRefresh(ts){state.lastOrdersRefreshTs=ts||null;const el=qs('ordersLastRefreshText');if(!el) return;el.textContent='Last refresh: '+formatLastRefresh(ts);}
async function loadOrders(forceRefresh=false){const cacheKey=`${qs('warehouse').value}`;if(!forceRefresh&&state.ordersCache[cacheKey]){const cached=state.ordersCache[cacheKey];state.orders=cached.orders||[];state.orderItems=cached.items||[];state.lastOrdersPayload=cached.lastPayload||null;updateOrdersRefresh(cached.lastRefresh||null);renderOrdersPage();setStatus(`Loaded ${state.orders.length} orders and ${state.orderItems.length} unique items. (saved)`);return;}if(state.ordersLoading) return;state.ordersLoading=true;setStatus(forceRefresh?'Refreshing orders...':'Loading orders...');try{const payload={username:'zeckm',password:'Zm0948',base_root:qs('warehouse').value==='liquor'?'http://dp1.bellboycorp.com':'http://dp4.bellboycorp.com'};const {res,data}=await fetchJson('/api/load-orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(!res.ok){setStatus(data.error||'Failed to load orders',true);return;}state.orders=data.orders||[];state.orderItems=data.items||[];state.lastOrdersPayload=payload;const now=Math.floor(Date.now()/1000);state.ordersCache[cacheKey]={orders:state.orders,items:state.orderItems,lastPayload:payload,lastRefresh:now};updateOrdersRefresh(now);renderOrdersPage();setStatus(`Loaded ${state.orders.length} orders and ${state.orderItems.length} unique items.`);}catch(e){console.error(e);setStatus(String(e&&e.message?e.message:e),true);const debug=qs('ordersDebug');if(debug) debug.textContent=String(e&&e.stack?e.stack:e);}finally{state.ordersLoading=false;}}
function renderOrdersPage(){qs('ordersLoaded').textContent=(state.orders||[]).length.toLocaleString();qs('ordersTotalQty').textContent=((state.orders||[]).reduce((s,r)=>s+Number(r.quantity||r.total_qty||0),0)).toLocaleString();qs('ordersUniqueItems').textContent=(state.orderItems||[]).length.toLocaleString();const body=qs('ordersRows');body.innerHTML='';(state.orders||[]).forEach(r=>{const tr=document.createElement('tr');tr.innerHTML=`<td><span class="badge">${r.order_no||r.route||'—'}</span></td><td>${r.customer||r.name||'—'}</td><td>${Number(r.total_qty||r.quantity||0).toLocaleString()}</td><td>${Number((r.items||[]).length||r.item_count||0).toLocaleString()}</td><td>${r.status||'loaded'}</td>`;body.appendChild(tr);});qs('ordersDebug').textContent=(state.orders||[]).map(r=>`${r.order_no||r.route||'—'}: ${r.customer||r.name||'unknown'} | ${r.status||'loaded'}`).join(' | ')||'No order loads yet.';const q=(qs('ordersItemSearch').value||'').toLowerCase().trim();const itemBody=qs('ordersItemRows');itemBody.innerHTML='';(state.orderItems||[]).filter(it=>!q||String(it.item_id).toLowerCase().includes(q)||String(it.description||'').toLowerCase().includes(q)).forEach(it=>{const key=String(it.item_id).trim();const picked=state.picked[key];const tr=document.createElement('tr');tr.innerHTML=`<td>${renderItemIdCell(it.item_id, qs('warehouse').value)}</td><td>${it.description||''}</td><td>${Number(it.total_ordered||0).toLocaleString()}</td><td>${Number((state.picked[String(it.item_id).trim()]?.stock)??it.in_stock??0).toLocaleString()}</td><td>${picked?`<span class="ok">${picked.qty}</span>`:'—'}</td><td>${(it.routes||[]).join(', ')}</td>`;itemBody.appendChild(tr);});const stockBody=qs('ordersStockRows');stockBody.innerHTML='';(state.orderItems||[]).forEach(it=>{const inStock=Number((state.picked[String(it.item_id).trim()]?.stock)??it.in_stock??0);const shortBy=Number(it.total_ordered||0)-inStock;if(shortBy<=0) return;const tr=document.createElement('tr');tr.innerHTML=`<td>${renderItemIdCell(it.item_id, qs('warehouse').value)}</td><td>${it.description||''}</td><td>${Number(it.total_ordered||0).toLocaleString()}</td><td>${inStock.toLocaleString()}</td><td class="warn">${shortBy.toLocaleString()}</td><td>${(it.routes||[]).join(', ')}</td>`;stockBody.appendChild(tr);});}
function applyCurrentData(){qs('routesLoaded').textContent=(state.routes||[]).length.toLocaleString();qs('totalQty').textContent=((state.routes||[]).reduce((s,r)=>s+Number(r.quantity||r.total_qty||0),0)).toLocaleString();qs('uniqueItems').textContent=(state.items||[]).length.toLocaleString();renderRoutes(state.routes);renderItems();renderStockView();renderPrintSheet();}
function renderRoutes(rows){const body=qs('routeRows');body.innerHTML='';let total=0;(rows||[]).forEach(r=>{total+=Number(r.total_qty||r.quantity||0);const tr=document.createElement('tr');tr.innerHTML=`<td><span class="badge">${r.route}</span></td><td>${r.name||r.route_name||'—'}</td><td>${Number(r.total_qty||r.quantity||0).toLocaleString()}</td><td>${Number((r.items||[]).length||r.item_count||0).toLocaleString()}</td><td>${r.status||'loaded'}</td>`;body.appendChild(tr);});qs('debug').textContent=(rows||[]).map(r=>`${r.route}: ${r.name||r.route_name||'unknown'} | ${r.status||'loaded'}`).join(' | ')||'No route loads yet.';}
function getItemLookupUrl(itemId, warehouse){const item=String(itemId||'').trim();if(!/^\d{7}$/.test(item)) return null;const whse=(warehouse==='liquor')?'NO':'NO';return `http://dp4.bellboycorp.com/wm/binr/?scan=${encodeURIComponent(item)}%E2%80%8D&whseID=${whse}`;}
function renderItemIdCell(itemId, warehouse){const item=String(itemId||'').trim();const url=getItemLookupUrl(item, warehouse);if(!url) return `<span class="badge">${item||'—'}</span>`;return `<a class="badge" href="${url}" target="_blank" rel="noopener noreferrer">${item}</a>`;}
function renderItems(){const q=(qs('itemSearch').value||'').toLowerCase().trim();const hidePicked=false;const body=qs('itemRows');body.innerHTML='';const filtered=(state.items||[]).filter(it=>!q||String(it.item_id).toLowerCase().includes(q)||String(it.description||'').toLowerCase().includes(q)).filter(it=>{const key=String(it.item_id).trim();return !(hidePicked&&state.picked[key]);});filtered.forEach(it=>{const key=String(it.item_id).trim();const picked=state.picked[key];const tr=document.createElement('tr');tr.innerHTML=`<td>${renderItemIdCell(it.item_id, qs('warehouse').value)}</td><td>${it.description||''}</td><td>${Number(it.total_ordered||0).toLocaleString()}</td><td>${Number(picked?.stock||it.in_stock||0).toLocaleString()}</td><td>${picked?'Yes':'No'}</td><td>${(it.routes||[]).join(', ')}</td>`;if(picked) tr.style.opacity='.55';body.appendChild(tr);});if(!filtered.length) body.innerHTML='<tr><td colspan="6" class="muted">No items loaded.</td></tr>';}
function renderStockView(){const needs=(state.items||[]).filter(it=>Number(it.total_ordered||0)>Number(it.in_stock||0)).sort((a,b)=>(b.total_ordered-b.in_stock)-(a.total_ordered-a.in_stock)||String(a.item_id).localeCompare(String(b.item_id)));const body=qs('stockRows');body.innerHTML='';needs.forEach(it=>{const shortBy=Number(it.total_ordered||0)-Number(it.in_stock||0);const tr=document.createElement('tr');tr.innerHTML=`<td>${renderItemIdCell(it.item_id, qs('warehouse').value)}</td><td>${it.description||''}</td><td>${Number(it.total_ordered||0).toLocaleString()}</td><td>${Number((state.picked[String(it.item_id).trim()]?.stock)??it.in_stock??0).toLocaleString()}</td><td class="warn">${shortBy.toLocaleString()}</td><td>${(it.routes||[]).join(', ')}</td>`;body.appendChild(tr);});qs('needsStockCount').textContent=needs.length.toLocaleString();}
function renderPrintSheet(){let items=[...(state.items||[])];const minQty=Number(qs('minPrintQty').value||1);items=items.filter(it=>Number(it.total_ordered||0)>=minQty);const sort=qs('printSort').value;if(sort==='total_ordered'){items.sort((a,b)=>b.total_ordered-a.total_ordered||String(a.item_id).localeCompare(String(b.item_id)));}else{items.sort((a,b)=>String(a.item_id).localeCompare(String(b.item_id)));}const body=qs('printRows');body.innerHTML='';items.forEach(it=>{const tr=document.createElement('tr');tr.innerHTML=`<td style="width:56px"><span style="display:inline-block;width:18px;height:18px;border:2px solid #666;border-radius:4px"></span></td><td>${renderItemIdCell(it.item_id, qs('warehouse').value)}</td><td>${it.description||''}</td><td>${Number(it.total_ordered||0).toLocaleString()}</td><td>${Number((state.picked[String(it.item_id).trim()]?.stock)??it.in_stock??0).toLocaleString()}</td><td>${(it.routes||[]).join(', ')}</td>`;body.appendChild(tr);});qs('printSubtitle').textContent=state.lastPayload?`${state.lastPayload.day} pick sheet · ${items.length} items · min qty ${minQty}`:'Routes update automatically and generate the current pick sheet.';}
async function loadRouteDebug(){qs('routeDebugPanel').classList.remove('hidden');qs('routeDebugOutput').textContent=JSON.stringify({api_load:'/api/load',api_load_routes:'/api/load-routes',day:qs('day')?.value||'',warehouse:qs('warehouse')?.value||'',currentUser:state.currentUser?{username:state.currentUser.username,is_admin:state.currentUser.is_admin}:null,lastPayload:state.lastPayload||null,routes:state.routes.length,items:state.items.length},null,2);}
qs('loginBtn').onclick=async()=>{try{const {res,data}=await fetchJson('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:qs('appUsername').value,password:qs('appPassword').value})});if(!res.ok){showAuthMessage(data.error||'Login failed',true);return;}showAuthMessage('Login successful');qs('authScreen').classList.add('hidden');qs('appWrap').classList.remove('hidden');setTimeout(()=>refreshSession().catch(e=>{showAuthMessage(String(e&&e.message?e.message:e),true);qs('authScreen').classList.remove('hidden');qs('appWrap').classList.add('hidden');}),0);}catch(e){showAuthMessage(String(e&&e.message?e.message:e),true);}};
qs('logoutBtn').onclick=async()=>{if(state.autoRefresh) clearInterval(state.autoRefresh);await fetch(api('/api/logout'),{method:'POST'});await refreshSession();};
qs('restartBtn').onclick=async()=>{if(!confirm('Restart the app now?')) return; const {res,data}=await fetchJson('/api/admin/restart',{method:'POST'}); setStatus(data.message||data.error,!res.ok); if(res.ok){setTimeout(()=>window.location.reload(),4000);} };
qs('saveAccountBtn').onclick=async()=>{const payload={username:qs('accountUsername').value,current_password:qs('accountCurrentPassword').value,new_password:qs('accountNewPassword').value};const {res,data}=await fetchJson('/api/account',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});qs('accountMsg').textContent=data.message||data.error||'';if(res.ok){qs('appUsername').value=payload.username;qs('accountCurrentPassword').value='';qs('accountNewPassword').value='';await refreshSession();}};
qs('showAdminBtn').onclick=()=>{showMainView('adminView');loadUsers();};
qs('accountBtn').onclick=()=>{showMainView('accountView');};
qs('supportBtn').onclick=()=>{showMainView('ticketsView');loadTickets();};
qs('manualRefreshBtn').onclick=()=>loadDay(true);
document.querySelectorAll('.tabs [data-view]').forEach(btn=>{btn.onclick=()=>showMainView(btn.getAttribute('data-view'));});
qs('routeDebugBtn').onclick=loadRouteDebug;
qs('day').onchange=()=>loadDay(false);
qs('warehouse').onchange=()=>loadDay(false);
qs('itemSearch').addEventListener('input',renderItems);
qs('hidePickedToggle').addEventListener('change',renderItems);
qs('printSort').addEventListener('change',renderPrintSheet);
qs('minPrintQty').addEventListener('input',renderPrintSheet);
qs('printBtn').onclick=()=>window.print();
qs('submitRequestBtn').onclick=async()=>{const payload={subject:qs('requestSubject').value,body:qs('requestBody').value};const {res,data}=await fetchJson('/api/tickets',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});qs('requestMsg').textContent=data.message||data.error||'';if(res.ok){qs('requestSubject').value='';qs('requestBody').value='';loadTickets();}};
async function loadTickets(){const {res,data}=await fetchJson('/api/tickets');const wrap=qs('ticketsList');wrap.innerHTML='';(data.tickets||[]).forEach(t=>{const replies=(t.replies||[]).map(r=>`<div class="ticket" style="margin-left:18px"><div class="ticket-meta">${r.author} replied · ${r.created_at||''}</div><div>${r.body}</div></div>`).join('');const box=document.createElement('div');box.className='ticket';let actions=`<div class="field" style="margin-top:10px"><label>${state.currentUser&&state.currentUser.is_main_admin?'Reply':'Add message'}</label><textarea id="reply-${t.id}" rows="3"></textarea></div><div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px"><button class="btn secondary" onclick="replyTicket(${t.id})">Send reply</button>`;if(state.currentUser&&state.currentUser.is_main_admin){actions += `<button class="btn secondary" onclick="closeTicket(${t.id})">Mark closed</button><button class="btn danger" onclick="deleteTicket(${t.id})">Delete ticket</button>`;}actions += `</div>`;box.innerHTML=`<div class="ticket-meta">${state.currentUser&&state.currentUser.is_main_admin?('From '+t.username+' · '):''}${t.status}</div><h3 style="font-size:18px;margin-bottom:8px">${t.subject}</h3><div style="margin-bottom:12px">${t.body}</div>${replies}${actions}`;wrap.appendChild(box);});if(!(data.tickets||[]).length){wrap.innerHTML='<div class="muted">No tickets yet.</div>';}}
window.replyTicket=async(id)=>{const body=qs(`reply-${id}`).value;const res=await fetch(`/api/tickets/${id}/reply`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({body})});const data=await res.json();setStatus(data.message||data.error,!res.ok);if(res.ok) loadTickets();};
window.closeTicket=async(id)=>{const res=await fetch(`/api/tickets/${id}/close`,{method:'POST'});const data=await res.json();setStatus(data.message||data.error,!res.ok);if(res.ok) loadTickets();};
window.deleteTicket=async(id)=>{if(!confirm('Remove this ticket from the dashboard and keep it archived?')) return;const res=await fetch(`/api/tickets/${id}`,{method:'DELETE'});const data=await res.json();setStatus(data.message||data.error,!res.ok);if(res.ok) loadTickets();};
async function loadUsers(){const {res,data}=await fetchJson('/api/admin/users');const body=qs('userRows');body.innerHTML='';(data.users||[]).forEach(u=>{const tr=document.createElement('tr');tr.innerHTML=`<td>${u.username}</td><td>${u.is_admin?'Admin':'User'}</td><td style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn secondary" onclick="editUser(${u.id},'${u.username.replace(/'/g,"\'")}',${u.is_admin?'true':'false'})">Edit</button>${!u.is_main_admin?`<button class="btn danger" onclick="deleteUser(${u.id})">Delete</button>`:''}</td>`;body.appendChild(tr);});}
qs('createUserBtn').onclick=async()=>{const payload={username:qs('newUserUsername').value,password:qs('newUserPassword').value,is_admin:qs('newUserAdmin').value==='true'};const {res,data}=await fetchJson('/api/admin/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});qs('adminMessage').textContent=data.message||data.error||'';if(res.ok){qs('newUserUsername').value='';qs('newUserPassword').value='';loadUsers();}};
window.deleteUser=async(id)=>{if(!confirm('Delete this user?')) return;const res=await fetch(`/api/admin/users/${id}`,{method:'DELETE'});const data=await res.json();qs('adminMessage').textContent=data.message||data.error||'';if(res.ok) loadUsers();};
window.editUser=(id,username,isAdmin)=>{const newUsername=prompt('Edit username',username);if(newUsername===null) return;const newPassword=prompt('Enter a new password (leave blank to keep current)','');const adminValue=confirm('Make this account an admin? Click Cancel for regular user.');fetch(`/api/admin/users/${id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:newUsername,password:newPassword,is_admin:adminValue})}).then(r=>r.json().then(data=>({ok:r.ok,data}))).then(({ok,data})=>{qs('adminMessage').textContent=data.message||data.error||'';if(ok) loadUsers();});};
refreshSession();

// ── AUTO-SAVE AT 5PM ──────────────────────────────────────────
(function scheduleAutoSave(){
  function msUntil5pm(){
    const now=new Date(),t=new Date(now);
    t.setHours(17,0,0,0);
    if(now>=t) t.setDate(t.getDate()+1);
    return t-now;
  }
  function doSave(){
    fetch('/api/save-tonight',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({warehouse:'both'})})
      .then(r=>r.json()).then(d=>console.log('[auto-save 5pm]',d.message))
      .catch(e=>console.error('[auto-save 5pm]',e));
  }
  setTimeout(function tick(){doSave();setTimeout(tick,24*60*60*1000);},msUntil5pm());
})();
// ── END AUTO-SAVE ─────────────────────────────────────────────


async function saveTonightRoutes(){
  const btn=document.getElementById('saveTonightBtn');
  if(!btn) return;
  const orig=btn.textContent;
  btn.disabled=true; btn.textContent='Saving...';
  try{
    const r=await fetch('/api/save-tonight',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({warehouse:'both'})});
    const d=await r.json();
    btn.textContent=d.message||'Saved!';
    setTimeout(()=>{btn.textContent=orig;btn.disabled=false;},4000);
  }catch(e){
    btn.textContent='Error';
    setTimeout(()=>{btn.textContent=orig;btn.disabled=false;},3000);
  }
}

</script>
</body>
</html>
'''

def open_browser_once():
    try:
        webbrowser.open(f'http://127.0.0.1:{PORT}')
    except Exception:
        pass

def normalize_base_root(value):
    v = (value or '').strip().lower()
    if v in BASE_ROOTS:
        return BASE_ROOTS[v]
    if 'dp1.bellboycorp.com' in v:
        return BASE_ROOTS['liquor']
    return BASE_ROOTS['hemp']

def warehouse_key_from_root(root):
    root = normalize_base_root(root)
    return 'liquor' if 'dp1.bellboycorp.com' in root else 'hemp'

def record_last_refresh(day, base_root, site_username):
    LAST_REFRESH[get_cache_key(day, base_root, site_username)] = time.time()

def get_last_refresh(day, base_root, site_username):
    return LAST_REFRESH.get(get_cache_key(day, base_root, site_username))

def refresh_user_routes(user_row, force=False):
    day = (user_row['day'] or 'TUE').strip().upper()
    base_root = normalize_base_root(user_row['base_root'] or BASE_ROOTS['hemp'])
    site_username = ((user_row['site_username'] if isinstance(user_row, dict) else user_row['site_username']) or DEFAULT_SITE_USERNAME).strip()
    if not force:
        cached = get_cached_day(day, base_root, site_username)
        if cached is not None:
            return cached
    s = requests.Session()
    if site_username:
        try:
            s.auth = (site_username, (user_row['site_password'] if isinstance(user_row, dict) else user_row['site_password']) or DEFAULT_SITE_PASSWORD)
            s.headers.update({'User-Agent': 'Mozilla/5.0 PickDashboard/2.1'})
        except Exception:
            pass
    summary = build_day_summary(s, base_root, day)
    set_cached_day(day, base_root, site_username, summary)
    record_last_refresh(day, base_root, site_username)
    return summary

def prewarm_all_routes(force=False):
    conn = db_conn()
    users = conn.execute('SELECT * FROM users ORDER BY id').fetchall()
    conn.close()
    for user in users:
        try:
            refresh_user_routes(user, force=force)
        except Exception:
            pass

def background_refresh_loop():
    while True:
        try:
            prewarm_all_routes(force=True)
        except Exception:
            pass
        time.sleep(180)

def get_cache_key(day, base_root, site_username):
    return f"{day}|{base_root.rstrip('/')}|{site_username}"

def get_cached_day(day, base_root, site_username):
    key = get_cache_key(day, base_root, site_username)
    with ROUTE_CACHE_LOCK:
        cached = ROUTE_CACHE.get(key)
        if cached and time.time() - cached['timestamp'] < CACHE_TTL_SECONDS:
            return cached['data']
    return None

def set_cached_day(day, base_root, site_username, data):
    key = get_cache_key(day, base_root, site_username)
    with ROUTE_CACHE_LOCK:
        ROUTE_CACHE[key] = {'timestamp': time.time(), 'data': data}

def route_exists(session_obj, base_root, route_code):
    url = f"{base_root.rstrip('/')}/wm/rsop/?route={route_code}"
    r = session_obj.get(url, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        return False, None
    text = r.text or ''
    if 'invalid route' in text.lower() or 'no route' in text.lower():
        return False, text
    return True, text

def auto_detect_route_codes(session_obj, base_root, day):
    found = []
    misses = 0
    for n in range(1, MAX_ROUTE_SCAN + 1):
        code = f"{day}{n}"
        ok, html = route_exists(session_obj, base_root, code)
        if ok:
            found.append((code, html))
            misses = 0
        else:
            misses += 1
            if found and misses >= 2:
                break
    return found

def get_picked_map():
    conn = db_conn()
    try:
        rows = conn.execute('SELECT item_id, stock FROM picked_items').fetchall()
    except sqlite3.OperationalError:
        conn.execute('CREATE TABLE IF NOT EXISTS picked_items (item_id TEXT PRIMARY KEY, stock INTEGER NOT NULL DEFAULT 0)')
        conn.commit()
        rows = []
    conn.close()
    return {str(r['item_id']).strip(): {'stock': int(r['stock'] or 0), 'picked': True} for r in rows}

def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db_conn()
    conn.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, password_plain TEXT DEFAULT "", is_admin INTEGER NOT NULL DEFAULT 0, site_username TEXT DEFAULT "", site_password TEXT DEFAULT "", day TEXT DEFAULT "TUE", route_count INTEGER DEFAULT 9, base_root TEXT DEFAULT "http://dp4.bellboycorp.com")')
    conn.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL DEFAULT "open", created_at TEXT DEFAULT CURRENT_TIMESTAMP, hidden INTEGER NOT NULL DEFAULT 0)')
    conn.execute('CREATE TABLE IF NOT EXISTS ticket_replies (id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER NOT NULL, author_id INTEGER NOT NULL, body TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
    conn.execute('CREATE TABLE IF NOT EXISTS picked_items (item_id TEXT PRIMARY KEY, stock INTEGER NOT NULL DEFAULT 0)')
    conn.commit()
    ticket_cols = [r['name'] for r in conn.execute('PRAGMA table_info(tickets)').fetchall()]
    if 'hidden' not in ticket_cols:
        conn.execute('ALTER TABLE tickets ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0')
    os.makedirs(REQUESTS_ARCHIVE_DIR, exist_ok=True)
    conn.commit()
    cols = [r['name'] for r in conn.execute('PRAGMA table_info(users)').fetchall()]
    migrations = {
        'password_plain': 'ALTER TABLE users ADD COLUMN password_plain TEXT DEFAULT ""',
        'site_username': 'ALTER TABLE users ADD COLUMN site_username TEXT DEFAULT ""',
        'site_password': 'ALTER TABLE users ADD COLUMN site_password TEXT DEFAULT ""',
        'day': 'ALTER TABLE users ADD COLUMN day TEXT DEFAULT "TUE"',
        'route_count': 'ALTER TABLE users ADD COLUMN route_count INTEGER DEFAULT 9',
        'base_root': 'ALTER TABLE users ADD COLUMN base_root TEXT DEFAULT "http://dp4.bellboycorp.com"'
    }
    for col, sql in migrations.items():
        if col not in cols:
            conn.execute(sql)
    conn.commit()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (MAIN_ADMIN_USERNAME,)).fetchone()
    if not user:
        conn.execute('INSERT INTO users (username, password_hash, password_plain, is_admin, site_username, site_password) VALUES (?, ?, ?, ?, ?, ?)', (MAIN_ADMIN_USERNAME, generate_password_hash(MAIN_ADMIN_PASSWORD), MAIN_ADMIN_PASSWORD, 1, DEFAULT_SITE_USERNAME, DEFAULT_SITE_PASSWORD))
        conn.commit()
    else:
        conn.execute("UPDATE users SET password_hash = ?, password_plain = ?, is_admin = 1, site_username = COALESCE(NULLIF(site_username, ''), ?), site_password = COALESCE(NULLIF(site_password, ''), ?) WHERE username = ?", (generate_password_hash(MAIN_ADMIN_PASSWORD), MAIN_ADMIN_PASSWORD, DEFAULT_SITE_USERNAME, DEFAULT_SITE_PASSWORD, MAIN_ADMIN_USERNAME))
        conn.commit()
    conn.close()
    conn = db_conn()
    conn.execute('UPDATE users SET site_username = ? WHERE COALESCE(site_username, "") = ""', (DEFAULT_SITE_USERNAME,))
    conn.execute('UPDATE users SET site_password = ? WHERE COALESCE(site_password, "") = ""', (DEFAULT_SITE_PASSWORD,))
    conn.commit()
    conn.close()
    sync_users_txt()
    sync_users_txt()

def require_login():
    uid = session.get('user_id')
    if not uid:
        return None
    conn = db_conn()
    user = conn.execute('SELECT id, username, is_admin, site_username, site_password, day, route_count, base_root, password_hash FROM users WHERE id = ?', (uid,)).fetchone()
    conn.close()
    return user

def require_admin():
    user = require_login()
    return user if user and user['is_admin'] else None

def require_main_admin():
    user = require_login()
    return user if user and user['username'] == MAIN_ADMIN_USERNAME else None

def clean_text(html: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html)).strip()

def parse_route_name(text: str, route: str) -> str:
    m = re.search(rf'Route:\s*{re.escape(route)}\s*-\s*[^\n]*?\s+([A-Z][A-Z\s&/-]+?)\s+Whse:', text, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r'Route:\s*[A-Z0-9]+\s*-\s*([^\n]+?)\s+Whse:', text, re.I)
    if m:
        return re.sub(r'^.*?#\d+\s*', '', m.group(1)).strip()
    return ''

def parse_ordered_values(text: str):
    matches = re.findall(r'Order\s*#\s*\d+\s+(\d+(?:\.\d+)?)\s+(?:\d+(?:\.\d+)?)\s+(?:\d+(?:\.\d+)?)', text, re.I)
    if matches:
        ordered = [float(a) for a in matches]
        return int(sum(ordered)), len(ordered), f'ordered-column x{len(ordered)}'
    return 0, 0, 'no ordered values found'

def normalize_desc(desc: str, item_id: str) -> str:
    desc = re.sub(r'\bUse Overstock\b', '', desc, flags=re.I)
    desc = re.sub(rf'\b{re.escape(item_id)}\b', '', desc)
    desc = re.sub(r'\s+', ' ', desc).strip(' -')
    return desc

def parse_items(text: str):
    items = []
    pattern = re.compile(r'(\d{6})\s+(In\s+Stock:\s*[0-9.]+|Use\s+Overstock|Out\s+of\s+Stock|No\s+Stock)\s+(\d{6,7})\s+(.+?)\s+UoM:\s+.*?Order\s*#\s*\d+\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)', re.I)
    for _bin_id, stock_marker, item_id, raw_desc, ordered, mid_col, end_col in pattern.findall(text):
        stock_match = re.search(r'In\s+Stock:\s*([0-9.]+)', stock_marker, re.I)
        in_stock = float(stock_match.group(1)) if stock_match else 0.0
        desc = normalize_desc(raw_desc, item_id)
        items.append({'item_id': item_id, 'description': desc, 'ordered': float(ordered), 'in_stock': in_stock, '_cols': [mid_col, end_col]})
    return items


def sync_users_txt():
    conn = db_conn()
    users = conn.execute('SELECT username, password_hash, is_admin FROM users ORDER BY username').fetchall()
    lines = ['Pick Dashboard users', '']
    for u in users:
        lines.append(f"username: {u['username']} | password: [hashed only: {u['password_hash']}] | role: {'admin' if u['is_admin'] else 'user'}")
    with open(USERS_TXT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    conn.close()

def archive_ticket_snapshot(conn, ticket_id):
    ticket = conn.execute('SELECT t.id, t.subject, t.body, t.status, t.created_at, t.hidden, u.username FROM tickets t JOIN users u ON u.id = t.user_id WHERE t.id = ?', (ticket_id,)).fetchone()
    if not ticket:
        return
    replies = conn.execute('SELECT tr.id, tr.body, tr.created_at, u.username FROM ticket_replies tr JOIN users u ON u.id = tr.author_id WHERE tr.ticket_id = ? ORDER BY tr.id', (ticket_id,)).fetchall()
    safe_user = re.sub(r'[^A-Za-z0-9._-]+', '_', ticket['username']) or 'unknown'
    user_dir = os.path.join(REQUESTS_ARCHIVE_DIR, safe_user)
    os.makedirs(user_dir, exist_ok=True)
    archive_path = os.path.join(user_dir, f"ticket-{ticket_id}.json")
    payload = {'ticket_id': ticket['id'], 'username': ticket['username'], 'subject': ticket['subject'], 'body': ticket['body'], 'status': ticket['status'], 'hidden': bool(ticket['hidden']), 'created_at': ticket['created_at'], 'replies': [{'id': r['id'], 'author': r['username'], 'body': r['body'], 'created_at': r['created_at']} for r in replies]}
    with open(archive_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)

def archive_all_visible_tickets():
    conn = db_conn()
    ticket_ids = [r['id'] for r in conn.execute('SELECT id FROM tickets').fetchall()]
    for ticket_id in ticket_ids:
        archive_ticket_snapshot(conn, ticket_id)
    conn.close()

def write_ticket_archive_now(ticket_id):
    conn = db_conn()
    archive_ticket_snapshot(conn, ticket_id)
    conn.close()

def schedule_restart():
    def _restart():
        os.kill(os.getpid(), signal.SIGTERM)
    threading.Timer(1.0, _restart).start()

def load_single_route(session_obj, base_root, route):
    route_url = f"{base_root}/wm/rsop/?route={route}"
    session_obj.get(route_url, timeout=30)
    resp = session_obj.post(route_url, data={'action':'init-order','route':route}, timeout=30)
    html = resp.text
    if '<title>Login</title>' in html:
        return {'route': route, 'route_name': '', 'quantity': 0, 'item_count': 0, 'status': 'Login returned', 'debug': 'session not authenticated', 'items': []}
    text = clean_text(html)
    route_name = parse_route_name(text, route)
    qty, item_count, debug = parse_ordered_values(text)
    items = parse_items(text)
    return {'route': route, 'route_name': route_name, 'quantity': qty, 'item_count': item_count, 'status': 'Parsed', 'debug': debug, 'items': items}

def login_session(site_username, site_password, base_root, day):
    s = requests.Session()
    first_route = f'{day}1'
    s.get(f'{base_root}/wm/rsop/?route={first_route}', timeout=30)
    login = s.post(f'{base_root}/login/', data={'username':site_username,'password':site_password}, headers={'Referer':f'{base_root}/wm/rsop/?route={first_route}'}, timeout=30)
    if 'Login' in login.text and 'username' in login.text.lower() and 'password' in login.text.lower():
        raise ValueError('Route site login failed')
    return s

def aggregate_day(site_username, site_password, base_root, day, route_count):
    s = login_session(site_username, site_password, base_root, day)
    routes = []
    aggregated = defaultdict(lambda: {'item_id':'','description':'','total_ordered':0,'in_stock':0,'routes':set()})
    for i in range(1, route_count + 1):
        route = f'{day}{i}'
        try:
            result = load_single_route(s, base_root, route)
            routes.append({k:v for k,v in result.items() if k != 'items'})
            for item in result['items']:
                agg = aggregated[item['item_id']]
                agg['item_id'] = item['item_id']
                agg['description'] = item['description']
                agg['total_ordered'] += item['ordered']
                agg['in_stock'] = max(agg['in_stock'], item['in_stock'])
                agg['routes'].add(route)
        except Exception as e:
            routes.append({'route':route,'route_name':'','quantity':0,'item_count':0,'status':'Error','debug':str(e)})
    items = sorted([{'item_id':v['item_id'],'description':v['description'],'total_ordered':int(v['total_ordered']),'in_stock':v['in_stock'],'routes':sorted(v['routes'])} for v in aggregated.values()], key=lambda x: (-x['total_ordered'], x['item_id']))
    return routes, items


DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

@app.post("/api/save-tonight")
def api_save_tonight():
    user = require_login()
    if not user or not user["is_admin"]:
        return jsonify({"error": "Admin required"}), 403
    import datetime as _dt
    from pathlib import Path as _P
    data = request.get_json() or {}
    warehouse = data.get("warehouse", "both")
    day_label = user["day"] or "TUE"
    today = _dt.date.today().isoformat()
    date_dir = _P(DATA_DIR) / today
    date_dir.mkdir(parents=True, exist_ok=True)
    saved, errors = [], []
    warehouses = ["liquor", "hemp"] if warehouse == "both" else [warehouse]
    for wh in warehouses:
        br = BASE_ROOTS.get(wh)
        if not br:
            errors.append(f"Unknown warehouse: {wh}")
            continue
        try:
            routes, items = aggregate_day(
                user["site_username"], user["site_password"],
                br, day_label, user["route_count"] or 9
            )
            out = {"warehouse": wh, "day": day_label, "saved_at": today, "routes": routes, "items": items}
            (date_dir / f"{wh}.json").write_text(json.dumps(out, indent=2))
            saved.append(wh)
        except Exception as e:
            errors.append(f"{wh}: {str(e)}")
    msg = f"Saved {', '.join(saved)} for {today}" if saved else "Nothing saved"
    if errors:
        msg += " | Errors: " + "; ".join(errors)
    return jsonify({"message": msg, "saved": saved, "errors": errors})

@app.route('/')
def index():
    return render_template_string(HTML)

@app.get('/health')
def health():
    return jsonify({'ok': True})

@app.get('/api/session')
def api_session():
    user = require_login()
    if not user:
        return jsonify({'authenticated': False})
    return jsonify({'authenticated': True, 'user': {'id': user['id'], 'username': user['username'], 'is_admin': bool(user['is_admin']), 'is_main_admin': user['username'] == MAIN_ADMIN_USERNAME, 'main_admin_username': MAIN_ADMIN_USERNAME, 'day': user['day'] or 'TUE', 'route_count': user['route_count'] or 9, 'site_username': user['site_username'] or '', 'base_root': user['base_root'] or 'http://dp4.bellboycorp.com'}, 'preferences': {'site_username': user['site_username'] or '', 'site_password': user['site_password'] or '', 'day': user['day'] or 'TUE', 'route_count': user['route_count'] or 9, 'base_root': user['base_root'] or 'http://dp4.bellboycorp.com'}})

@app.post('/api/login')
def api_login():
    data = request.get_json(force=True)
    username = data.get('username','').strip()
    password = data.get('password','')
    conn = db_conn()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error':'Invalid username or password'}), 401
    session['user_id'] = user['id']
    session.permanent = True
    return jsonify({'message':'Login successful'})

@app.post('/api/logout')
def api_logout():
    session.clear()
    return jsonify({'message':'Logged out'})

@app.post('/api/admin/restart')
def api_admin_restart():
    admin = require_admin()
    if not admin:
        return jsonify({'error':'Admin access required'}), 403
    schedule_restart()
    return jsonify({'message':'App restart has been requested'})

@app.post('/api/account')
def api_account():
    user = require_login()
    if not user:
        return jsonify({'error':'Not authenticated'}), 401
    data = request.get_json(force=True)
    new_username = data.get('username','').strip()
    current_password = data.get('current_password','')
    new_password = data.get('new_password','')
    if not current_password or not check_password_hash(user['password_hash'], current_password):
        return jsonify({'error':'Current password is incorrect'}), 400
    if not new_username:
        return jsonify({'error':'Username is required'}), 400
    conn = db_conn()
    existing = conn.execute('SELECT id FROM users WHERE username = ? AND id != ?', (new_username, user['id'])).fetchone()
    if existing:
        conn.close(); return jsonify({'error':'That username is already taken'}), 400
    password_hash = user['password_hash']
    if new_password.strip():
        password_hash = generate_password_hash(new_password)
    plain_password = user['password_plain'] if 'password_plain' in user.keys() else ''
    if new_password.strip():
        plain_password = new_password
    conn.execute('UPDATE users SET username = ?, password_hash = ?, password_plain = ? WHERE id = ?', (new_username, password_hash, plain_password, user['id']))
    conn.commit(); conn.close()
    sync_users_txt()
    sync_users_txt()
    return jsonify({'message':'Account updated'})

@app.post('/api/preferences')
def api_preferences():
    user = require_login()
    if not user:
        return jsonify({'error':'Not authenticated'}), 401
    data = request.get_json(force=True)
    conn = db_conn()
    chosen_root = normalize_base_root(data.get('warehouse') or data.get('base_root') or BASE_ROOTS['hemp'])
    conn.execute('UPDATE users SET site_username = ?, site_password = ?, day = ?, route_count = ?, base_root = ? WHERE id = ?', (data.get('site_username','').strip(), data.get('site_password',''), data.get('day','TUE'), int(data.get('route_count',9) or 9), chosen_root, user['id']))
    conn.commit(); conn.close()
    sync_users_txt()
    return jsonify({'message':'Saved to your account'})

@app.post('/api/tickets')
def api_create_ticket():
    user = require_login()
    if not user:
        return jsonify({'error':'Not authenticated'}), 401
    if user['username'] == MAIN_ADMIN_USERNAME:
        return jsonify({'error':'Main admin does not submit feature requests here'}), 403
    data = request.get_json(force=True)
    subject = data.get('subject','').strip()
    body = data.get('body','').strip()
    if not subject or not body:
        return jsonify({'error':'Subject and request details are required'}), 400
    conn = db_conn()
    cur = conn.execute('INSERT INTO tickets (user_id, subject, body, status) VALUES (?, ?, ?, ?)', (user['id'], subject, body, 'open'))
    ticket_id = cur.lastrowid
    conn.commit(); conn.close()
    write_ticket_archive_now(ticket_id)
    return jsonify({'message':'Request sent to main admin'})

@app.get('/api/tickets')
def api_list_tickets():
    user = require_login()
    if not user:
        return jsonify({'error':'Not authenticated'}), 401
    conn = db_conn()
    if user['username'] == MAIN_ADMIN_USERNAME:
        tickets = conn.execute('SELECT t.id, t.subject, t.body, t.status, u.username FROM tickets t JOIN users u ON u.id = t.user_id WHERE t.hidden = 0 ORDER BY t.id DESC').fetchall()
    else:
        tickets = conn.execute('SELECT t.id, t.subject, t.body, t.status, u.username FROM tickets t JOIN users u ON u.id = t.user_id WHERE t.hidden = 0 AND t.user_id = ? ORDER BY t.id DESC', (user['id'],)).fetchall()
    out = []
    for t in tickets:
        replies = conn.execute('SELECT tr.body, tr.created_at, u.username FROM ticket_replies tr JOIN users u ON u.id = tr.author_id WHERE tr.ticket_id = ? ORDER BY tr.id', (t['id'],)).fetchall()
        out.append({'id': t['id'], 'subject': t['subject'], 'body': t['body'], 'status': t['status'], 'username': t['username'], 'replies': [{'body': r['body'], 'author': r['username'], 'created_at': r['created_at']} for r in replies]})
    conn.close()
    return jsonify({'tickets': out})

@app.post('/api/tickets/<int:ticket_id>/reply')
def api_reply_ticket(ticket_id):
    user = require_login()
    if not user:
        return jsonify({'error':'Not authenticated'}), 401
    data = request.get_json(force=True)
    body = data.get('body','').strip()
    if not body:
        return jsonify({'error':'Reply is required'}), 400
    conn = db_conn()
    ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
    if not ticket:
        conn.close(); return jsonify({'error':'Ticket not found'}), 404
    if user['username'] != MAIN_ADMIN_USERNAME and ticket['user_id'] != user['id']:
        conn.close(); return jsonify({'error':'You can only reply to your own tickets'}), 403
    conn.execute('INSERT INTO ticket_replies (ticket_id, author_id, body) VALUES (?, ?, ?)', (ticket_id, user['id'], body))
    new_status = 'customer-replied' if user['username'] != MAIN_ADMIN_USERNAME else 'answered'
    conn.execute('UPDATE tickets SET status = ? WHERE id = ?', (new_status, ticket_id))
    conn.commit(); conn.close()
    write_ticket_archive_now(ticket_id)
    return jsonify({'message':'Reply sent'})

@app.post('/api/tickets/<int:ticket_id>/close')
def api_close_ticket(ticket_id):
    main_admin = require_main_admin()
    if not main_admin:
        return jsonify({'error':'Main admin access required'}), 403
    conn = db_conn()
    ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
    if not ticket:
        conn.close(); return jsonify({'error':'Ticket not found'}), 404
    conn.execute('UPDATE tickets SET status = ? WHERE id = ?', ('closed', ticket_id))
    conn.commit(); conn.close()
    write_ticket_archive_now(ticket_id)
    return jsonify({'message':'Ticket closed'})

@app.delete('/api/tickets/<int:ticket_id>')
def api_delete_ticket(ticket_id):
    main_admin = require_main_admin()
    if not main_admin:
        return jsonify({'error':'Main admin access required'}), 403
    conn = db_conn()
    ticket = conn.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()
    if not ticket:
        conn.close(); return jsonify({'error':'Ticket not found'}), 404
    conn.execute('UPDATE tickets SET hidden = 1, status = ? WHERE id = ?', ('deleted', ticket_id))
    conn.commit(); conn.close()
    write_ticket_archive_now(ticket_id)
    return jsonify({'message':'Ticket removed from dashboard and archived'})

@app.post('/api/load-routes')
def api_load_routes():
    if not require_login():
        return jsonify({'error':'Not authenticated'}), 401
    data = request.get_json(force=True)
    site_username = data.get('username','')
    site_password = data.get('password','')
    base_root = data.get('base_root','http://dp4.bellboycorp.com').rstrip('/')
    day = data.get('day','TUE')
    route_count = int(data.get('route_count', 9))
    if not site_username or not site_password:
        return jsonify({'error':'Route site username and password are required'}), 400
    try:
        routes, items = aggregate_day(site_username, site_password, base_root, day, route_count)
        return jsonify({'routes': routes, 'items': items})
    except ValueError as e:
        return jsonify({'error': str(e)}), 401

@app.post('/api/export-items-csv')
def api_export_items_csv():
    if not require_login():
        return jsonify({'error':'Not authenticated'}), 401
    data = request.get_json(force=True)
    site_username = data.get('username','')
    site_password = data.get('password','')
    base_root = data.get('base_root','http://dp4.bellboycorp.com').rstrip('/')
    day = data.get('day','TUE')
    route_count = int(data.get('route_count', 9))
    try:
        _, items = aggregate_day(site_username, site_password, base_root, day, route_count)
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    csv_lines = ['item_id,description,total_ordered,in_stock,routes']
    for row in items:
        desc = row['description'].replace('"', '""')
        routes = ' '.join(row['routes'])
        csv_lines.append(f'"{row["item_id"]}","{desc}",{row["total_ordered"]},{row["in_stock"]},"{routes}"')
    return Response('\n'.join(csv_lines), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename={day}-items.csv'})

@app.get('/api/admin/users')
def api_admin_users():
    if not require_admin():
        return jsonify({'error':'Admin access required'}), 403
    conn = db_conn()
    users = conn.execute('SELECT id, username, is_admin FROM users ORDER BY username').fetchall()
    conn.close()
    return jsonify({'users':[{'id':u['id'],'username':u['username'],'is_admin':bool(u['is_admin'])} for u in users]})

@app.post('/api/admin/users')
def api_admin_create_user():
    if not require_admin():
        return jsonify({'error':'Admin access required'}), 403
    data = request.get_json(force=True)
    username = data.get('username','').strip()
    password = data.get('password','')
    is_admin = 1 if data.get('is_admin') else 0
    if not username or not password:
        return jsonify({'error':'Username and password are required'}), 400
    conn = db_conn()
    try:
        conn.execute('INSERT INTO users (username, password_hash, password_plain, is_admin, site_username, site_password, day, route_count, base_root) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', (username, generate_password_hash(password), password, is_admin, DEFAULT_SITE_USERNAME, DEFAULT_SITE_PASSWORD, 'TUE', 9, 'http://dp4.bellboycorp.com'))
        conn.commit()
        sync_users_txt()
    except sqlite3.IntegrityError:
        conn.close(); return jsonify({'error':'Username already exists'}), 400
    conn.close()
    sync_users_txt()
    return jsonify({'message':'User created'})

@app.patch('/api/admin/users/<int:user_id>')
def api_admin_update_user(user_id):
    admin = require_admin()
    if not admin:
        return jsonify({'error':'Admin access required'}), 403
    conn = db_conn()
    target = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not target:
        conn.close(); return jsonify({'error':'User not found'}), 404
    if target['username'] == MAIN_ADMIN_USERNAME:
        conn.close(); return jsonify({'error':'The main admin account admin role cannot be changed'}), 400
    if target['id'] == admin['id']:
        conn.close(); return jsonify({'error':'You cannot change your own admin privileges'}), 400
    data = request.get_json(force=True)
    is_admin = 1 if data.get('is_admin') else 0
    conn.execute('UPDATE users SET is_admin = ? WHERE id = ?', (is_admin, user_id))
    conn.commit(); conn.close()
    sync_users_txt()
    return jsonify({'message':'User updated'})

@app.delete('/api/admin/users/<int:user_id>')
def api_admin_delete_user(user_id):
    admin = require_admin()
    if not admin:
        return jsonify({'error':'Admin access required'}), 403
    conn = db_conn()
    target = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not target:
        conn.close(); return jsonify({'error':'User not found'}), 404
    if target['username'] == MAIN_ADMIN_USERNAME:
        conn.close(); return jsonify({'error':'The main admin account cannot be deleted'}), 400
    if target['id'] == admin['id']:
        conn.close(); return jsonify({'error':'You cannot delete your own account'}), 400
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit(); conn.close()
    sync_users_txt()
    sync_users_txt()
    return jsonify({'message':'User deleted'})

init_db()
archive_all_visible_tickets()

prewarm_all_routes(force=False)
threading.Thread(target=background_refresh_loop, daemon=True).start()




ORDERS_WINDOW = """
<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Pick Dashboard 5.1.5 Orders</title>
<style>
:root{--bg:#0f1115;--panel:#171a21;--panel2:#1e2330;--text:#eef2ff;--muted:#aab4d6;--line:#2e3850;--accent:#7c5cff;--ok:#28c76f;--warn:#ffb020}
*{box-sizing:border-box}body{margin:0;font-family:Arial,sans-serif;background:var(--bg);color:var(--text)}
.wrap{max-width:1500px;margin:0 auto;padding:20px}.top{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:flex-start}.panel{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:16px}.grid{display:grid;gap:16px}.kpi{grid-template-columns:repeat(4,minmax(0,1fr));margin-top:16px}.split{grid-template-columns:1.2fr .8fr;margin-top:16px}.btn{display:inline-flex;align-items:center;justify-content:center;padding:12px 16px;border-radius:12px;border:1px solid var(--line);background:var(--panel2);color:var(--text);text-decoration:none;cursor:pointer}.btn.primary{background:var(--accent);border-color:var(--accent)}.eyebrow{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:8px}.metric{font-size:34px;font-weight:700}.muted{color:var(--muted)}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px 8px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.06em}input,select{padding:11px 12px;border-radius:10px;border:1px solid var(--line);background:var(--panel2);color:var(--text)}.toolbar{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:12px}.badge{display:inline-block;padding:5px 10px;border-radius:999px;background:var(--panel2);border:1px solid var(--line)}.warn{color:var(--warn);font-weight:700}.stack{display:grid;gap:16px;margin-top:16px}@media (max-width:1000px){.kpi,.split{grid-template-columns:1fr}.wrap{padding:12px}}
</style></head><body>
<div class="wrap"><div class="top"><div><div class="eyebrow">Pick Dashboard 5.1.5</div><h1 style="margin:0 0 6px 0">Current orders</h1><div class="muted">Pulls current SOP orders and shows order details, line items, and picked status.</div></div><div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center"><select id="warehouse"><option value="hemp">Hemp</option><option value="liquor">Liquor</option></select><button class="btn primary" id="loadBtn">Load orders</button></div></div>
<div class="grid kpi"><div class="panel"><div class="eyebrow">Orders</div><div class="metric" id="ordersCount">0</div></div><div class="panel"><div class="eyebrow">Total items ordered</div><div class="metric" id="totalQty">0</div></div><div class="panel"><div class="eyebrow">Unique items</div><div class="metric" id="uniqueItems">0</div></div><div class="panel"><div class="eyebrow">Need stocked</div><div class="metric" id="needStock">0</div></div></div>
<div class="grid split"><div class="panel"><div class="toolbar"><div><div class="eyebrow">Order list</div><div class="muted" id="status">Ready.</div></div><input id="orderSearch" placeholder="Search order, customer, or type"></div><table><thead><tr><th>Order</th><th>Type</th><th>Customer</th><th>Picked</th><th>Ordered</th><th>Lines</th></tr></thead><tbody id="ordersRows"></tbody></table></div><div class="panel"><div class="eyebrow">Debug</div><pre id="debug" style="white-space:pre-wrap;font-size:12px;line-height:1.45;margin:0"></pre></div></div>
<div class="stack"><div class="panel"><div class="toolbar"><div><div class="eyebrow">All order details</div><div class="muted">Customer, type, line items, picked status, and notes when available.</div></div></div><div id="orderCards"></div></div><div class="panel"><div class="toolbar"><div><div class="eyebrow">Items needed</div></div><input id="itemSearch" placeholder="Search item ID or description"></div><table><thead><tr><th>Item ID</th><th>Description</th><th>Ordered</th><th>Picked</th><th>In stock</th><th>Orders</th></tr></thead><tbody id="itemsRows"></tbody></table></div><div class="panel"><div class="eyebrow">Items needing stocked</div><table><thead><tr><th>Item ID</th><th>Description</th><th>Ordered</th><th>Picked</th><th>In stock</th><th>Short by</th><th>Orders</th></tr></thead><tbody id="stockRows"></tbody></table></div></div></div>
<script>
const state={orders:[],items:[]};const qs=id=>document.getElementById(id);function fmt(n){return Number(n||0).toLocaleString();}function esc(v){return String(v??'').replace(/[&<>\"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));}function itemLink(id){const item=String(id||'').trim();if(!/^\d{7}$/.test(item)) return esc(item||'—');const url=`http://dp4.bellboycorp.com/wm/binr/?scan=${encodeURIComponent(item)}%E2%80%8D&whseID=NO`;return `<a class="badge" href="${url}" target="_blank" rel="noopener noreferrer">${item}</a>`;}function render(){const oq=(qs('orderSearch').value||'').toLowerCase().trim();const iq=(qs('itemSearch').value||'').toLowerCase().trim();const orders=state.orders.filter(o=>!oq||[o.order_no,o.customer,o.order_type,o.status].join(' ').toLowerCase().includes(oq));qs('ordersCount').textContent=fmt(state.orders.length);qs('totalQty').textContent=fmt(state.orders.reduce((s,o)=>s+Number(o.total_qty||0),0));qs('uniqueItems').textContent=fmt(state.items.length);qs('needStock').textContent=fmt(state.items.filter(i=>Number(i.total_ordered||0)>Number(i.in_stock||0)).length);qs('ordersRows').innerHTML=orders.map(o=>`<tr><td><span class="badge">${esc(o.order_no||'—')}</span></td><td>${esc(o.order_type||'—')}</td><td>${esc(o.customer||'—')}</td><td>${fmt(o.picked_qty||0)}</td><td>${fmt(o.total_qty||0)}</td><td>${fmt((o.lines||[]).length)}</td></tr>`).join('')||'<tr><td colspan="6" class="muted">No current orders found.</td></tr>';qs('orderCards').innerHTML=orders.map(o=>`<div class="panel" style="margin-bottom:14px"><div class="toolbar"><div><div style="font-weight:700;font-size:18px">Order ${esc(o.order_no||'—')}</div><div class="muted">${esc(o.order_type||'—')} · ${esc(o.customer||'—')} · Status: ${esc(o.status||'—')}</div></div><div><span class="badge">Picked ${fmt(o.picked_qty||0)}</span> <span class="badge">Ordered ${fmt(o.total_qty||0)}</span></div></div><div class="muted" style="margin-bottom:10px">${esc(o.notes||'')}</div><table><thead><tr><th>Item ID</th><th>Description</th><th>Ordered</th><th>Picked</th><th>In stock</th></tr></thead><tbody>${(o.lines||[]).map(line=>`<tr><td>${itemLink(line.item_id)}</td><td>${esc(line.description||'')}</td><td>${fmt(line.quantity||0)}</td><td>${fmt(line.picked_qty||0)}</td><td>${fmt(line.in_stock||0)}</td></tr>`).join('')||'<tr><td colspan="5" class="muted">No line items found.</td></tr>'}</tbody></table></div>`).join('');const items=state.items.filter(i=>!iq||String(i.item_id).toLowerCase().includes(iq)||String(i.description||'').toLowerCase().includes(iq));qs('itemsRows').innerHTML=items.map(i=>`<tr><td>${itemLink(i.item_id)}</td><td>${esc(i.description||'')}</td><td>${fmt(i.total_ordered||0)}</td><td>${fmt(i.picked_qty||0)}</td><td>${fmt(i.in_stock||0)}</td><td>${esc((i.orders||[]).join(', '))}</td></tr>`).join('')||'<tr><td colspan="6" class="muted">No order items found.</td></tr>';qs('stockRows').innerHTML=items.filter(i=>Number(i.total_ordered||0)>Number(i.in_stock||0)).map(i=>`<tr><td>${itemLink(i.item_id)}</td><td>${esc(i.description||'')}</td><td>${fmt(i.total_ordered||0)}</td><td>${fmt(i.picked_qty||0)}</td><td>${fmt(i.in_stock||0)}</td><td class="warn">${fmt(Number(i.total_ordered||0)-Number(i.in_stock||0))}</td><td>${esc((i.orders||[]).join(', '))}</td></tr>`).join('')||'<tr><td colspan="7" class="muted">No stock shortages found.</td></tr>';}async function loadOrders(){qs('status').textContent='Loading current orders...';qs('debug').textContent='';const res=await fetch('/api/orders-current',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({warehouse:qs('warehouse').value})});const data=await res.json();if(!res.ok){qs('status').textContent=data.error||'Failed to load orders';qs('debug').textContent=JSON.stringify(data,null,2);return;}state.orders=data.orders||[];state.items=data.items||[];qs('status').textContent=`Loaded ${state.orders.length} current orders.`;qs('debug').textContent=JSON.stringify(data.debug||{},null,2);render();}qs('loadBtn').addEventListener('click',loadOrders);qs('orderSearch').addEventListener('input',render);qs('itemSearch').addEventListener('input',render);
</script></body></html>
"""

@app.get('/orders-window')
def orders_window():
    return render_template_string(ORDERS_WINDOW)

@app.post('/api/orders-current')
def api_orders_current():
    if not session.get('user_id'):
        return jsonify({'error':'Unauthorized'}),401
    data=request.get_json(force=True) or {}
    warehouse=(data.get('warehouse') or 'hemp').strip().lower()
    base_root='http://dp1.bellboycorp.com' if warehouse=='liquor' else 'http://dp4.bellboycorp.com'
    username='zeckm'
    password='Zm0948'
    debug={'warehouse':warehouse,'base_root':base_root,'list_url':f'{base_root}/ajax/wm/picking/sop-list/','steps':[]}
    try:
        import requests, re, json, html as htmlmod
        from urllib.parse import urljoin
        from html.parser import HTMLParser
        sess=requests.Session()
        login_page=sess.get(f'{base_root}/wm/sop/', timeout=30)
        debug['steps'].append({'step':'get_login','status':login_page.status_code,'url':login_page.url})
        html=login_page.text
        input_pattern = r"<input[^>]*name=['\"]([^'\"]+)['\"][^>]*value=['\"]([^'\"]*)['\"]"
        form_pattern = r"<form[^>]*action=['\"]([^'\"]*)['\"]"
        inputs=dict(re.findall(input_pattern, html, re.I))
        form_match=re.search(form_pattern, html, re.I)
        action=(form_match.group(1).strip() if form_match else '/wm/sop/') or '/wm/sop/'
        payload=dict(inputs)
        found_user=False
        found_pass=False
        for key in ['username','user','login','name','identity']:
            if key in payload:
                payload[key]=username
                found_user=True
        for key in ['password','pass','passwd']:
            if key in payload:
                payload[key]=password
                found_pass=True
        if not found_user:
            payload['username']=username
        if not found_pass:
            payload['password']=password
        login_resp=sess.post(urljoin(f'{base_root}/wm/sop/', action), data=payload, timeout=30, allow_redirects=True)
        debug['steps'].append({'step':'post_login','status':login_resp.status_code,'url':login_resp.url})
        params={
            'useCachedFilter':'true',
            'whseID':'NO' if warehouse=='hemp' else 'MN',
            'action':'request-list',
            'available':'Y',
            'complete':'N',
            'shipped':'N',
            'filter':'0',
            'rqstdatefrom':'',
            'rqstdatethru':'',
            'orderBy':'rqstdate',
            'sortDir':'ASC'
        }
        list_url=f'{base_root}/ajax/wm/picking/sop-list/'
        headers={
            'X-Requested-With':'XMLHttpRequest',
            'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
            'Referer':f'{base_root}/wm/sop/',
            'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        list_resp=sess.get(list_url, params=params, timeout=30, allow_redirects=True, headers=headers)
        list_html=list_resp.text
        debug['steps'].append({'step':'get_order_list','status':list_resp.status_code,'url':list_resp.url,'length':len(list_html)})
        debug['list_html_preview']=list_html[:2000]
        debug['contains_data_id']='data-id=' in list_html
        debug['contains_pick_item']='pick-item' in list_html
        debug['contains_list_group_item']='list-group-item' in list_html
        debug['contains_form_row']='form-row' in list_html
        debug['contains_ordn']='ordn=' in list_html
        import re as _re_dbg
        debug['data_id_matches']=_re_dbg.findall(r'data-id=\"(\d+)\"', list_html)[:20]
        debug['ordn_matches']=_re_dbg.findall(r'ordn=(\d+)', list_html)[:20]

        def strip_tags(s):
            s=htmlmod.unescape(str(s or ''))
            s=s.replace('\xa0',' ')
            s=re.sub(r'\s+',' ',s).strip()
            return s

        class SopListParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.orders=[]
                self.in_item=False
                self.item_depth=0
                self.current=None
                self.found_data_id=False
                self.capture=False
                self.capture_depth=0
                self.capture_role=''
                self.capture_parts=[]
                self.row_type=None
                self.row_depth=0
                self.row_col=None
                self.row_values={}
                self.row_link=''
            def _start_capture(self, role):
                self.capture=True
                self.capture_depth=1
                self.capture_role=role
                self.capture_parts=[]
            def _finish_capture(self):
                txt=strip_tags(' '.join(self.capture_parts))
                if txt and self.capture_role == 'row_cell' and self.row_col is not None:
                    prev=self.row_values.get(self.row_col,'')
                    self.row_values[self.row_col]=(prev + ' ' + txt).strip() if prev else txt
                self.capture=False
                self.capture_depth=0
                self.capture_role=''
                self.capture_parts=[]
            def _to_int(self, value):
                try:
                    return int(float(str(value).strip()))
                except:
                    return 0
            def _finalize_row(self):
                if not self.current:
                    self.row_type=None
                    self.row_depth=0
                    self.row_col=None
                    self.row_values={}
                    self.row_link=''
                    return
                if self.row_type == 'summary':
                    order_no=(self.row_values.get(1,'') or '').strip()
                    if not order_no and self.row_link:
                        m=re.search(r'ordn=(\d+)', self.row_link)
                        if m:
                            order_no=m.group(1)
                    if order_no:
                        self.current['order_no']=order_no
                        self.current['order_number']=order_no
                        self.found_data_id=True
                    self.current['line_count']=self._to_int(self.row_values.get(6,''))
                    self.current['avail_lines']=self._to_int(self.row_values.get(7,''))
                elif self.row_type == 'details':
                    self.current['customer']=self.row_values.get(2, self.current.get('customer','')).strip()
                    self.current['customer_name']=self.current['customer']
                    self.current['order_type']=self.row_values.get(3, self.current.get('order_type','')).strip()
                    self.current['status']=self.row_values.get(4, self.current.get('status','')).strip() or self.current.get('status','current')
                    self.current['ship_via']=self.row_values.get(5, self.current.get('ship_via','')).strip()
                    self.current['requested_date']=self.row_values.get(6, self.current.get('requested_date','')).strip()
                    self.current['pick_date']=self.row_values.get(7, self.current.get('pick_date','')).strip()
                self.row_type=None
                self.row_depth=0
                self.row_col=None
                self.row_values={}
                self.row_link=''
            def handle_starttag(self, tag, attrs):
                attrs=dict(attrs)
                cls=attrs.get('class','')
                if tag=='div' and 'list-group-item' in cls and attrs.get('data-id'):
                    self.in_item=True
                    self.item_depth=1
                    order_no=attrs.get('data-id','').strip()
                    self.current={
                        'order_no':order_no,
                        'order_number':order_no,
                        'requested_date':'',
                        'pick_date':'',
                        'order_type':'',
                        'customer_code':'',
                        'customer':'',
                        'customer_name':'',
                        'line_count':0,
                        'avail_lines':0,
                        'ship_via':'',
                        'status':'current'
                    }
                    self.found_data_id=bool(order_no)
                    self.row_type=None
                    self.row_depth=0
                    self.row_col=None
                    self.row_values={}
                    self.row_link=''
                    return
                if not self.in_item:
                    return
                if tag=='div':
                    self.item_depth += 1
                if self.capture and tag in ('div','span','small','a'):
                    self.capture_depth += 1
                if tag=='div' and 'form-row' in cls and self.row_type is None:
                    self.row_type='summary' if not self.current.get('_summary_done') else 'details'
                    self.current['_summary_done']=True
                    self.row_depth=1
                    self.row_col=None
                    self.row_values={}
                    self.row_link=''
                    return
                if self.row_type:
                    if tag=='div':
                        self.row_depth += 1
                        m=re.search(r'col(?:-sm)?-(\d+)', cls)
                        if m:
                            self.row_col=int(m.group(1))
                            self._start_capture('row_cell')
                    elif tag=='a' and attrs.get('href'):
                        self.row_link=attrs.get('href','')
                    return
            def handle_endtag(self, tag):
                if self.capture and tag in ('div','span','small','a'):
                    self.capture_depth -= 1
                    if self.capture_depth <= 0:
                        self._finish_capture()
                if self.row_type and tag=='div':
                    self.row_depth -= 1
                    if self.row_depth <= 0:
                        self._finalize_row()
                        return
                if self.in_item and tag=='div':
                    self.item_depth -= 1
                    if self.item_depth <= 0:
                        if self.current:
                            self.current.pop('_summary_done', None)
                        if self.current and self.found_data_id:
                            self.orders.append(self.current)
                        self.in_item=False
                        self.current=None
                        self.found_data_id=False
            def handle_data(self, data):
                if self.capture:
                    self.capture_parts.append(data)
        parser = SopListParser()
        try:
            parser.feed(list_html)
            parser.close()
        except Exception as parse_err:
            debug['list_parse_error'] = str(parse_err)
        raw_orders = []
        seen_order_nos = set()
        for parsed in getattr(parser, 'orders', []) or []:
            order_no = str(parsed.get('order_no') or parsed.get('order_number') or '').strip()
            if not order_no or order_no in seen_order_nos:
                continue
            seen_order_nos.add(order_no)
            raw_orders.append({
                'order_no': order_no,
                'order_number': order_no,
                'customer': (parsed.get('customer') or parsed.get('customer_name') or f'Order {order_no}').strip(),
                'customer_name': (parsed.get('customer_name') or parsed.get('customer') or '').strip(),
                'customer_code': str(parsed.get('customer_code') or '').strip(),
                'ship_via': str(parsed.get('ship_via') or '').strip(),
                'status': str(parsed.get('status') or 'New').strip(),
                'order_type': str(parsed.get('order_type') or '').strip(),
                'requested_date': str(parsed.get('requested_date') or '').strip(),
                'pick_date': str(parsed.get('pick_date') or '').strip(),
                'line_count': int(parsed.get('line_count') or 0),
                'avail_lines': int(parsed.get('avail_lines') or 0),
            })
        if not raw_orders:
            for order_no in debug.get('data_id_matches', []):
                order_no = str(order_no).strip()
                if not order_no or order_no in seen_order_nos:
                    continue
                seen_order_nos.add(order_no)
                raw_orders.append({
                    'order_no': order_no,
                    'order_number': order_no,
                    'customer': f'Order {order_no}',
                    'customer_name': '',
                    'customer_code': '',
                    'ship_via': '',
                    'status': 'New',
                    'order_type': '',
                    'requested_date': '',
                    'pick_date': '',
                    'line_count': 0,
                    'avail_lines': 0,
                })

        def parse_detail_html(detail_html, order_no):
            items = []

            def clean_text(value):
                if value is None:
                    return ''
                value = str(value).replace('\xa0', ' ')
                value = re.sub(r'<[^>]+>', ' ', value)
                return re.sub(r'\s+', ' ', value).strip()

            def to_float(value, default=0.0):
                try:
                    if value in (None, ''):
                        return default
                    return float(str(value).replace(',', '').strip())
                except Exception:
                    return default

            seen = set()
            html_text = detail_html or ''

            for match in re.finditer(r'pick-item\b', html_text, re.I):
                start_idx = max(0, match.start() - 300)
                end_idx = min(len(html_text), match.start() + 6000)
                block_html = html_text[start_idx:end_idx]
                data_json_matches = re.findall(r'data-jsonquot(.*?)(?=\s+[a-zA-Z-]+=|>)', block_html, re.S)
                if not data_json_matches:
                    data_json_matches = re.findall(r'data-json="([^"]+)"', block_html, re.S)

                item = None
                for raw_json in data_json_matches:
                    decoded = raw_json.replace('&quot;', '"').replace('quot', '"').replace('\\"', '"').strip()
                    decoded = re.sub(r"^[\"']+|[\"']+$", "", decoded)
                    try:
                        candidate = json.loads(decoded)
                        if isinstance(candidate, dict) and candidate.get('itemid'):
                            item = candidate
                            break
                    except Exception:
                        continue

                if not item:
                    continue

                line_no = clean_text(item.get('linenbr'))
                item_id = clean_text(item.get('itemid'))
                description = clean_text(item.get('description1') or item.get('description'))
                bin_id = clean_text(item.get('binid') or item.get('frombinid') or item.get('itemPrimaryBinid'))
                uom = clean_text(item.get('uom'))
                qty_case = to_float(item.get('qtypercase'), None)
                quantity = to_float(item.get('qtyordered'), 0.0)
                picked_qty = to_float(item.get('qtypicked'), 0.0)
                remaining_qty = to_float(item.get('qtyremaining'), max(quantity - picked_qty, 0.0))
                in_stock = to_float(item.get('inStock', item.get('instock')), 0.0)

                key = (str(order_no), line_no, item_id, bin_id, uom)
                if key in seen or not item_id:
                    continue
                seen.add(key)

                items.append({
                    'item_id': item_id,
                    'description': description,
                    'bin_id': bin_id,
                    'uom': uom,
                    'qty_case': qty_case,
                    'quantity': quantity,
                    'picked_qty': picked_qty,
                    'remaining_qty': remaining_qty,
                    'in_stock': in_stock,
                    'picked': picked_qty > 0,
                })

            return items

        orders=[]
        items_map={}
        for order in raw_orders:
            if not order.get('order_no'):
                continue
            detail_resp=sess.get(f'{base_root}/wm/sop/', params={'ordn':order['order_no']}, timeout=30, allow_redirects=True)
            debug['steps'].append({'step':f"detail_{order['order_no']}",'status':detail_resp.status_code,'url':detail_resp.url,'length':len(detail_resp.text)})
            lines=parse_detail_html(detail_resp.text, order['order_no'])
            order['lines']=lines
            order['total_qty']=sum(float(x.get('quantity') or 0) for x in lines)
            order['picked_qty']=sum(float(x.get('picked_qty') or 0) for x in lines)
            order['picked_line_count']=sum(1 for x in lines if float(x.get('picked_qty') or 0) > 0)
            for line in lines:
                item_id=str(line.get('item_id') or '').strip()
                if not item_id:
                    continue
                entry=items_map.setdefault(item_id,{'item_id':item_id,'description':line.get('description',''),'total_ordered':0,'picked_qty':0,'in_stock':line.get('in_stock',0),'orders':[],'picked':False})
                entry['total_ordered']+=float(line.get('quantity') or 0)
                entry['picked_qty']+=float(line.get('picked_qty') or 0)
                entry['picked']=entry['picked'] or (float(line.get('picked_qty') or 0) > 0)
                if line.get('description') and not entry.get('description'):
                    entry['description']=line['description']
                if order['order_no'] not in entry['orders']:
                    entry['orders'].append(order['order_no'])
            orders.append(order)
        debug['orders_found']=len(orders)
        debug['items_found']=len(items_map)
        debug['filtered_ship_via_bb']='not-filtered'
        return jsonify({'orders':orders,'items':list(items_map.values()),'debug':debug})
    except Exception as e:
        debug['exception']=str(e)
        return jsonify({'error':f'Failed to load current orders: {e}','debug':debug}),500

if __name__ == '__main__':
    threading.Timer(1.25, open_browser_once).start()
    app.run(host=HOST, port=PORT, debug=False, threaded=True)

@app.get('/api/route_debug')
def api_route_debug():
    user = require_login()
    if not user:
        return jsonify({'error':'Not authenticated'}), 401
    day = (user['day'] or 'TUE').strip().upper()
    base_root = normalize_base_root(user['base_root'] or BASE_ROOTS['hemp'])
    site_username = (user['site_username'] or DEFAULT_SITE_USERNAME).strip()
    cached = get_cached_day(day, base_root, site_username)
    return jsonify({'day': day, 'base_root': base_root, 'site_username': site_username, 'has_cached_data': cached is not None, 'last_refresh': int(get_last_refresh(day, base_root, site_username) or 0)})

@app.post('/api/load')
def api_load():
    user = require_login()
    if not user:
        return jsonify({'error':'Not authenticated'}), 401
    data = request.get_json(force=True) if request.data else {}
    day = (data.get('day') or user['day'] or 'TUE').strip().upper()
    warehouse = (data.get('warehouse') or '').strip().lower()
    if warehouse == 'liquor':
        base_root = BASE_ROOTS['liquor']
    elif warehouse == 'hemp':
        base_root = BASE_ROOTS['hemp']
    else:
        base_root = normalize_base_root(user['base_root'] or BASE_ROOTS['hemp'])
    route_count = int(user['route_count'] or 9)
    payload = {
        'username': (user['site_username'] or DEFAULT_SITE_USERNAME).strip(),
        'password': user['site_password'] or DEFAULT_SITE_PASSWORD,
        'base_root': base_root.rstrip('/'),
        'day': day,
        'route_count': route_count
    }
    if not payload['username'] or not payload['password']:
        return jsonify({'error':'Route site username and password are required'}), 400
    try:
        routes, items = aggregate_day(payload['username'], payload['password'], payload['base_root'], payload['day'], payload['route_count'])
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    total_qty = sum(int(r.get('quantity', 0) or 0) for r in routes)
    return jsonify({
        'routes': routes,
        'items': items,
        'routes_loaded': len(routes),
        'total_qty': total_qty,
        'unique_items': len(items),
        'cached': False,
        'last_refresh': int(time.time())
    })

@app.get('/api/picked')
def api_get_picked():
    user = require_login()
    if not user:
        return jsonify({'error':'Not authenticated'}), 401
    return jsonify({'items': get_picked_map()})

@app.post('/api/picked')
def api_set_picked():
    user = require_login()
    if not user:
        return jsonify({'error':'Not authenticated'}), 401
    data = request.get_json(force=True)
    item_id = str(data.get('item_id','')).strip()
    stock = int(data.get('stock', 0) or 0)
    picked = bool(data.get('picked', True))
    if not item_id:
        return jsonify({'error':'item_id is required'}), 400
    conn = db_conn()
    if picked:
        conn.execute('INSERT INTO picked_items (item_id, stock) VALUES (?, ?) ON CONFLICT(item_id) DO UPDATE SET stock = excluded.stock', (item_id, stock))
    else:
        conn.execute('DELETE FROM picked_items WHERE item_id = ?', (item_id,))
    conn.commit()
    conn.close()
    return jsonify({'message':'Picked state saved'})
