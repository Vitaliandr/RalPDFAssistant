const STATUS = {
  queued: 'в очереди',
  processing: 'обработка',
  ready: 'готов',
  error: 'ошибка',
};

const docsEl = document.getElementById('docs');
const hintEl = document.getElementById('docsHint');
const messages = document.getElementById('messages');
const dropEl = document.getElementById('drop');
const fileEl = document.getElementById('file');

const modelEl = document.getElementById('model');
const modelNoteEl = document.getElementById('modelNote');

let models = {};

const memKeys = {};

function getKey(id) {
  try { return localStorage.getItem('llmKey:' + id) || memKeys[id] || ''; } catch (e) { return memKeys[id] || ''; }
}

function setKey(id, value) {
  memKeys[id] = value;
  try {
    if (value) localStorage.setItem('llmKey:' + id, value); else localStorage.removeItem('llmKey:' + id);
  } catch (e) { /* в приватном окне хранилища может не быть, тогда ключ живёт до перезагрузки */ }
}

function maskKey(key) {
  return key.length > 10 ? key.slice(0, 4) + '…' + key.slice(-4) : '••••';
}

const keyToggle = document.getElementById('keyToggle');
const keyBox = document.getElementById('keyBox');

//открыта ли панель, виден ли ключ
let keyOpen = false;
let keyRevealed = false;

function curModel() {
  return models[modelEl.value];
}

function isCloud() {
  const m = curModel();
  return !!(m && m.cloud);
}

function updateKeyBox() {
  keyToggle.hidden = !isCloud();
  if (!isCloud()) {
    keyBox.hidden = true;
    return;
  }

  const key = getKey(modelEl.value);

  keyToggle.textContent = key ? 'Ключ: задан' : 'Ключ не задан';
  keyToggle.classList.toggle('warn', !key);

  keyBox.hidden = !keyOpen;
  document.getElementById('keyForm').hidden = !!key;
  document.getElementById('keySaved').hidden = !key;
  document.getElementById('keyMask').textContent = key ? (keyRevealed ? key : maskKey(key)) : '';
  document.getElementById('keyReveal').textContent = keyRevealed ? 'скрыть' : 'показать';

  document.getElementById('keyStatus').textContent = key
    ? 'Ключ сохранён в этом браузере.'
    : 'Ключ не задан. Вставь свой, чтобы пользоваться облачной моделью.';
}

keyToggle.onclick = () => {
  keyOpen = !keyOpen;
  keyRevealed = false;
  updateKeyBox();
};

document.getElementById('keySave').onclick = () => {
  const input = document.getElementById('keyInput');
  const value = input.value.trim();
  if (!value || /\s/.test(value)) {
    alert('Вставь ключ целиком, без пробелов');
    return;
  }
  setKey(modelEl.value, value);
  input.value = '';
  keyRevealed = false;
  keyOpen = false;
  updateKeyBox();
};

document.getElementById('keyReveal').onclick = () => {
  keyRevealed = !keyRevealed;
  updateKeyBox();
};

document.getElementById('keyForget').onclick = () => {
  if (!confirm('Удалить сохранённый ключ из этого браузера?')) return;
  setKey(modelEl.value, '');
  keyRevealed = false;
  updateKeyBox();
};

function showModelNote() {
  const m = curModel();
  modelNoteEl.textContent = m ? m.note : '';
  //открываем сами, если ключа нет
  keyOpen = isCloud() && !getKey(modelEl.value);
  keyRevealed = false;
  updateKeyBox();
}

async function loadModels() {
  const resp = await fetch('/api/models');
  const list = await resp.json();
  models = {};
  modelEl.innerHTML = '';

  for (const m of list) {
    models[m.id] = m;
    const opt = document.createElement('option');
    opt.value = m.id;
    opt.textContent = m.label;
    modelEl.append(opt);
  }

  // прошлый выбор, если ещё есть
  let saved = null;
  try { saved = localStorage.getItem('model'); } catch (e) { /* без хранилища тоже живём */ }
  const def = list.find(m => m.default) || list[0];
  modelEl.value = saved && models[saved] ? saved : def.id;
  modelEl.disabled = list.length < 2;
  showModelNote();
}

modelEl.onchange = () => {
  try { localStorage.setItem('model', modelEl.value); } catch (e) { /* ничего страшного */ }
  showModelNote();
};

const pickHintEl = document.getElementById('pickHint');
const chatTitleEl = document.getElementById('chatTitle');
const chatSubEl = document.getElementById('chatSub');
const clearBtn = document.getElementById('clearChat');

let lastDocs = [];
let timer = null;

// all общий, остальные по id документа
let chats = {};
let current = 'all';
const MAX_MSGS = 60;

try {
  chats = JSON.parse(localStorage.getItem('chats') || '{}');
  current = localStorage.getItem('chatCurrent') || 'all';
} catch (e) { chats = {}; }

function saveChats() {
  try {
    localStorage.setItem('chats', JSON.stringify(chats));
    localStorage.setItem('chatCurrent', current);
  } catch (e) {
    //не влезло, без источников они самые тяжёлые
    try {
      const light = {};
      for (const k in chats) light[k] = chats[k].map(m => ({ ...m, sources: undefined }));
      localStorage.setItem('chats', JSON.stringify(light));
    } catch (e2) { /* ну и ладно, история доживёт до перезагрузки */ }
  }
}

function pushMsg(key, msg) {
  if (!chats[key]) chats[key] = [];
  chats[key].push(msg);
  if (chats[key].length > MAX_MSGS) chats[key].splice(0, chats[key].length - MAX_MSGS);
  saveChats();
}

function readyDocs() {
  return lastDocs.filter(d => d.status === 'ready');
}

function curDoc() {
  return lastDocs.find(d => String(d.id) === current);
}

function renderHead() {
  if (current === 'all') {
    chatTitleEl.textContent = 'Все документы' + (readyDocs().length ? ' (' + readyDocs().length + ')' : '');
    chatSubEl.textContent = 'ищу по всем сразу';
  } else {
    const d = curDoc();
    chatTitleEl.textContent = d ? d.title : 'Документ';
    chatSubEl.textContent = 'ищу только в нём';
  }
  clearBtn.disabled = !(chats[current] && chats[current].length);
}

function addMsg(text, cls) {
  const div = document.createElement('div');
  div.className = 'msg ' + cls;
  div.textContent = text;
  messages.append(div);
  messages.scrollTop = messages.scrollHeight;
  return div;
}

function addBy(msgEl, modelId) {
  const by = document.createElement('div');
  by.className = 'by';
  by.textContent = models[modelId] ? models[modelId].label : modelId;
  msgEl.append(by);
}

function addSources(msgEl, sources) {
  if (!sources || !sources.length) return;
  const det = document.createElement('details');
  det.className = 'sources';
  const sum = document.createElement('summary');
  sum.textContent = 'Источники (' + sources.length + ')';
  det.append(sum);

  for (const s of sources) {
    const box = document.createElement('div');
    box.className = 'src';
    const head = document.createElement('b');
    head.textContent = s.document + (s.page ? ', стр. ' + s.page : '') + ' · ' + s.score;
    const body = document.createElement('div');
    body.textContent = s.text;
    box.append(head, body);
    det.append(box);
  }
  msgEl.append(det);
}

function drawMsg(m) {
  const div = addMsg(m.text, m.role === 'user' ? 'user' : 'bot');
  if (m.role === 'bot') {
    addSources(div, m.sources);
    if (m.model) addBy(div, m.model);
  }
}

function renderChat() {
  messages.innerHTML = '';
  const list = chats[current] || [];
  if (!list.length) {
    addMsg(current === 'all'
      ? 'Привет! Загрузи документ слева, а потом спрашивай, например про тарифы или условия.'
      : 'Тут отдельный чат по этому документу, спрашивай.', 'bot');
  }
  for (const m of list) drawMsg(m);
  messages.scrollTop = messages.scrollHeight;
  renderHead();
}

function selectChat(key) {
  current = key;
  saveChats();
  renderDocs();
  renderChat();
  document.getElementById('question').focus();
}

clearBtn.onclick = () => {
  if (!confirm('Очистить этот чат?')) return;
  chats[current] = [];
  saveChats();
  renderChat();
};

function renderDocs() {
  hintEl.style.display = lastDocs.length ? 'none' : 'block';
  pickHintEl.hidden = readyDocs().length < 1;
  docsEl.innerHTML = '';

  const all = document.createElement('li');
  all.className = 'all' + (current === 'all' ? ' picked' : '');
  const allName = document.createElement('span');
  allName.className = 'name';
  allName.textContent = 'Все документы';
  const allCount = document.createElement('span');
  allCount.className = 'badge ready';
  allCount.textContent = readyDocs().length;
  all.append(allName, allCount);
  all.onclick = () => selectChat('all');
  docsEl.append(all);

  for (const d of lastDocs) {
    const li = document.createElement('li');
    const ready = d.status === 'ready';
    li.className = (current === String(d.id) ? 'picked' : '') + (ready ? '' : ' off');

    const name = document.createElement('span');
    name.className = 'name';
    name.textContent = d.title;
    if (d.error) name.title = d.error;

    const badge = document.createElement('span');
    badge.className = 'badge ' + d.status;
    badge.textContent = STATUS[d.status] || d.status;

    const del = document.createElement('button');
    del.className = 'del';
    del.textContent = '×';
    del.title = 'Удалить';
    del.onclick = async e => {
      e.stopPropagation();
      if (!confirm('Удалить документ "' + d.title + '"? Его чат тоже удалится.')) return;
      await fetch('/api/documents/' + d.id, { method: 'DELETE' });
      delete chats[String(d.id)];
      if (current === String(d.id)) current = 'all';
      saveChats();
      await loadDocs();
      renderChat();
    };

    if (ready) li.onclick = () => selectChat(String(d.id));
    li.append(name, badge, del);
    docsEl.append(li);
  }
  renderHead();
}

async function loadDocs() {
  const resp = await fetch('/api/documents');
  lastDocs = await resp.json();

  //чаты удалённых документов выкидываем
  const ids = new Set(lastDocs.map(d => String(d.id)));
  let changed = false;
  for (const k of Object.keys(chats)) {
    if (k !== 'all' && !ids.has(k)) { delete chats[k]; changed = true; }
  }
  const lost = current !== 'all' && !ids.has(current);
  if (lost) { current = 'all'; changed = true; }
  if (changed) saveChats();

  renderDocs();
  if (lost) renderChat();

  // опрос раз в 2 сек пока идёт обработка
  const busy = lastDocs.some(d => d.status === 'queued' || d.status === 'processing');
  clearTimeout(timer);
  if (busy) timer = setTimeout(loadDocs, 2000);
}

async function uploadFile(file) {
  const fd = new FormData();
  fd.append('file', file);
  const resp = await fetch('/api/documents', { method: 'POST', body: fd });
  if (!resp.ok) {
    const err = await resp.json();
    alert(err.detail || 'Не получилось загрузить файл');
    return;
  }
  loadDocs();
}

fileEl.onchange = () => {
  if (fileEl.files[0]) uploadFile(fileEl.files[0]);
  fileEl.value = '';
};

dropEl.ondragover = e => { e.preventDefault(); dropEl.classList.add('over'); };
dropEl.ondragleave = () => dropEl.classList.remove('over');
dropEl.ondrop = e => {
  e.preventDefault();
  dropEl.classList.remove('over');
  if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]);
};

document.getElementById('textSend').onclick = async () => {
  const title = document.getElementById('textTitle').value;
  const text = document.getElementById('textBody').value;
  const resp = await fetch('/api/documents/text', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, text }),
  });
  if (!resp.ok) {
    const err = await resp.json();
    alert(err.detail || 'Не получилось добавить текст');
    return;
  }
  document.getElementById('textTitle').value = '';
  document.getElementById('textBody').value = '';
  loadDocs();
};

document.getElementById('form').onsubmit = async e => {
  e.preventDefault();
  const input = document.getElementById('question');
  const btn = document.getElementById('send');
  const question = input.value.trim();
  if (!question) return;

  // локальной ключ не нужен
  const key = isCloud() ? getKey(modelEl.value) : '';
  // нет ключа, открываем панель
  if (isCloud() && !key) {
    addMsg('Для этой модели нужен ключ: вставь его в панели «Ключ» вверху страницы или выбери локальную модель.', 'bot');
    keyOpen = true;
    updateKeyBox();
    document.getElementById('keyInput').focus();
    return;
  }

  // чат где спросили, ответ придёт туда
  const asked = current;
  const userMsg = { role: 'user', text: question };
  pushMsg(asked, userMsg);
  drawMsg(userMsg);
  renderHead();
  input.value = '';
  btn.disabled = true;
  const wait = addMsg('Ищу в документах и думаю...', 'bot wait');

  // null = по всем
  const ids = asked === 'all' ? null : [Number(asked)];

  let reply;
  try {
    const headers = { 'Content-Type': 'application/json' };
    if (key) headers['X-LLM-Key'] = key;
    const resp = await fetch('/api/ask', {
      method: 'POST',
      headers,
      body: JSON.stringify({ question, document_ids: ids, model: modelEl.value }),
    });
    const data = await resp.json();
    reply = resp.ok
      ? { role: 'bot', text: data.answer, sources: data.sources, model: data.model }
      : { role: 'bot', text: data.detail || 'Что-то пошло не так' };
  } catch (err) {
    reply = { role: 'bot', text: 'Сервер не отвечает' };
  }

  wait.remove();
  pushMsg(asked, reply);
  if (current === asked) drawMsg(reply);
  renderHead();
  btn.disabled = false;
};

loadModels();
loadDocs().then(renderChat);
