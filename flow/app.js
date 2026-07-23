const API_BASE = ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname)
  ? 'http://localhost:8000/api'
  : 'https://api.ulovklienty.cz/api';
const TOKEN_KEY = 'flow_token';

const $ = (sel) => document.querySelector(sel);

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}

function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function api(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };
  const token = getToken();
  if (token) headers['X-Flow-Token'] = token;
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  let data = null;
  try {
    data = await res.json();
  } catch (_) {
    data = null;
  }
  if (!res.ok) {
    const detail = data?.detail || data?.new_password?.[0] || res.statusText || 'Chyba';
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data;
}

function showMsg(el, text, ok) {
  el.hidden = false;
  el.textContent = text;
  el.className = ok ? 'msg ok' : 'msg error';
}

function showLoggedIn(user) {
  $('#view-login').classList.add('hidden');
  $('#view-home').classList.remove('hidden');
  $('#btn-logout').classList.remove('hidden');
  $('#home-name').textContent = user.zamestnanec?.jmeno || '—';
  $('#home-salon').textContent = user.salon?.name || '—';
  $('#home-email').textContent = user.email || '—';
  $('#home-overview').textContent = user.visible_overview ? 'zapnuto (zatím jen příznak)' : 'vypnuto';
}

function showLogin() {
  $('#view-login').classList.remove('hidden');
  $('#view-home').classList.add('hidden');
  $('#btn-logout').classList.add('hidden');
}

async function boot() {
  if (!getToken()) {
    showLogin();
    return;
  }
  try {
    const user = await api('/flow/me/');
    showLoggedIn(user);
  } catch (_) {
    setToken('');
    showLogin();
  }
}

$('#form-login')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = $('#login-msg');
  try {
    const data = await api('/flow/prihlaseni/', {
      method: 'POST',
      body: JSON.stringify({
        email: $('#login-email').value.trim(),
        password: $('#login-password').value,
      }),
    });
    setToken(data.token);
    showLoggedIn(data.user);
    msg.hidden = true;
  } catch (err) {
    showMsg(msg, err.message, false);
  }
});

$('#btn-logout')?.addEventListener('click', async () => {
  try {
    await api('/flow/odhlaseni/', { method: 'POST' });
  } catch (_) { /* ignore */ }
  setToken('');
  showLogin();
});

$('#form-password')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = $('#pwd-msg');
  try {
    const data = await api('/flow/zmena-hesla/', {
      method: 'POST',
      body: JSON.stringify({
        current_password: $('#pwd-current').value,
        new_password: $('#pwd-new').value,
      }),
    });
    showMsg(msg, data.detail || 'Hotovo.', true);
    e.target.reset();
  } catch (err) {
    showMsg(msg, err.message, false);
  }
});

boot();
