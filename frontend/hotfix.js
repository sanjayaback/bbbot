// Production hardening loaded after app.js.
// Keeps the original UI but prevents cascading null-workspace requests and unreadable FastAPI errors.

function dqFormatErrorPayload(payload, fallback='Request failed') {
  if (!payload) return fallback;
  if (typeof payload === 'string') return payload;
  if (typeof payload.message === 'string') return payload.message;
  if (typeof payload.detail === 'string') return payload.detail;
  if (Array.isArray(payload.detail)) {
    return payload.detail.map(item => {
      if (typeof item === 'string') return item;
      const loc = Array.isArray(item?.loc) ? item.loc.filter(x => x !== 'body').join('.') : '';
      const msg = item?.msg || item?.message || 'Validation error';
      return loc ? `${loc}: ${msg}` : msg;
    }).join('; ');
  }
  try { return JSON.stringify(payload); } catch { return fallback; }
}

function dqRequireWorkspace(action='perform this action') {
  if (state.workspaceId) return true;
  toast(`Create or select a workspace before you ${action}.`, true);
  return false;
}

api = async function(path, opts={}, retried=false) {
  let res;
  try {
    res = await fetch(path, {...opts, headers: authHeaders(opts.headers || {})});
  } catch (err) {
    const offline = typeof navigator !== 'undefined' && navigator.onLine === false;
    throw new Error(offline ? 'You are offline. Reconnect and try again.' : 'Could not reach DocuQuery API. Check your network and server health.');
  }

  if (res.status === 401 && state.authMode === 'supabase' && !retried && await refreshSession()) {
    return api(path, opts, true);
  }
  if (res.status === 401 && state.authMode === 'supabase') {
    logout(false);
    throw new Error('Session expired. Sign in again.');
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try { msg = dqFormatErrorPayload(await res.json(), msg); } catch {}
    throw new Error(msg);
  }
  if (res.status === 204) return null;
  return res.json();
};

const dqOriginalLoadWorkspaces = loadWorkspaces;
loadWorkspaces = async function() {
  try {
    state.workspaces = await api('/api/workspaces');
    if (!Array.isArray(state.workspaces)) state.workspaces = [];
    if (!state.workspaces.length) {
      state.workspaceId = null;
      state.kbs = [];
      state.documents = [];
      state.chatSessions = [];
      state.chatId = null;
      showWorkspaceCreate(true);
      return;
    }
    renderWorkspaceSelect();
    if (!state.workspaceId || !state.workspaces.some(w => w.id === state.workspaceId)) {
      state.workspaceId = state.workspaces[0].id;
    }
    $('#workspaceSelect').value = state.workspaceId;
    await refreshWorkspace();
  } catch (e) {
    state.workspaceId = null;
    toast(e.message || 'Could not load workspaces', true);
  }
};

const dqLoadActivity = loadActivity;
loadActivity = async function() {
  if (!dqRequireWorkspace('view activity')) return;
  return dqLoadActivity();
};

const dqLoadMembers = loadMembers;
loadMembers = async function() {
  if (!dqRequireWorkspace('view members')) return;
  try { return await dqLoadMembers(); }
  catch (e) { toast(e.message || 'Could not load workspace members', true); }
};

const dqLoadSettings = loadSettings;
loadSettings = async function() {
  if (!dqRequireWorkspace('open settings')) return;
  return dqLoadSettings();
};

const dqShowKbCreate = showKbCreate;
showKbCreate = function() {
  if (!dqRequireWorkspace('create a knowledge base')) return;
  return dqShowKbCreate();
};

const dqShowUpload = showUpload;
showUpload = function() {
  if (!dqRequireWorkspace('upload a document')) return;
  return dqShowUpload();
};

const dqShowSourceChooser = showSourceChooser;
showSourceChooser = function() {
  if (!dqRequireWorkspace('start a chat')) return;
  return dqShowSourceChooser();
};

window.addEventListener('unhandledrejection', event => {
  const message = event.reason?.message || 'Unexpected request failure';
  toast(message, true);
});
