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
const scopeEl = document.getElementById('scope');

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

//пусто = ищем по всем
const selected = new Set();
let lastDocs = [];
let timer = null;

function readyDocs() {
  return lastDocs.filter(d => d.status === 'ready');
}

function pickedIds() {
  return readyDocs().filter(d => selected.has(d.id)).map(d => d.id);
}

function updateScope() {
  const ready = readyDocs();
  const picked = ready.filter(d => selected.has(d.id));
  scopeEl.innerHTML = '';

  const text = document.createElement('span');
  if (!ready.length) {
    text.textContent = 'Нет готовых документов';
  } else if (!picked.length) {
    text.textContent = 'Ищу по всем документам (' + ready.length + ')';
  } else {
    text.textContent = 'Ищу только в: ' + picked.map(d => d.title).join(', ');
  }
  scopeEl.append(text);

  if (picked.length) {
    const reset = document.createElement('button');
    reset.type = 'button';
    reset.className = 'link';
    reset.textContent = 'искать по всем';
    reset.onclick = () => { selected.clear(); renderDocs(); };
    scopeEl.append(reset);
  }
}

function renderDocs() {
  hintEl.style.display = lastDocs.length ? 'none' : 'block';
  pickHintEl.hidden = readyDocs().length < 2;
  docsEl.innerHTML = '';

  for (const d of lastDocs) {
    const li = document.createElement('li');
    if (selected.has(d.id) && d.status === 'ready') li.className = 'picked';

    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.id = 'doc' + d.id;
    cb.disabled = d.status !== 'ready';
    cb.checked = selected.has(d.id) && !cb.disabled;
    cb.onchange = () => {
      if (cb.checked) selected.add(d.id); else selected.delete(d.id);
      renderDocs();
    };

    const name = document.createElement('label');
    name.className = 'name';
    name.htmlFor = cb.id;
    name.textContent = d.title;
    if (d.error) name.title = d.error;

    const badge = document.createElement('span');
    badge.className = 'badge ' + d.status;
    badge.textContent = STATUS[d.status] || d.status;

    const del = document.createElement('button');
    del.className = 'del';
    del.textContent = '×';
    del.title = 'Удалить';
    del.onclick = async () => {
      if (!confirm('Удалить документ "' + d.title + '"?')) return;
      await fetch('/api/documents/' + d.id, { method: 'DELETE' });
      selected.delete(d.id);
      loadDocs();
    };

    li.append(cb, name, badge, del);
    docsEl.append(li);
  }
  updateScope();
}

async function loadDocs() {
  const resp = await fetch('/api/documents');
  lastDocs = await resp.json();
  renderDocs();

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
  if (!sources.length) return;
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

document.getElementById('form').onsubmit = async e => {
  e.preventDefault();
  const input = document.getElementById('question');
  const btn = document.getElementById('send');
  const question = input.value.trim();
  if (!question) return;

  //локальной ключ не нужен
  const key = isCloud() ? getKey(modelEl.value) : '';
  //нет ключа, открываем панель
  if (isCloud() && !key) {
    addMsg('Для этой модели нужен ключ: вставь его в панели «Ключ» вверху страницы или выбери локальную модель.', 'bot');
    keyOpen = true;
    updateKeyBox();
    document.getElementById('keyInput').focus();
    return;
  }

  addMsg(question, 'user');
  input.value = '';
  btn.disabled = true;
  const wait = addMsg('Ищу в документах и думаю...', 'bot wait');

  // null = по всем
  const ids = pickedIds();

  try {
    const headers = { 'Content-Type': 'application/json' };
    if (key) headers['X-LLM-Key'] = key;
    const resp = await fetch('/api/ask', {
      method: 'POST',
      headers,
      body: JSON.stringify({ question, document_ids: ids.length ? ids : null, model: modelEl.value }),
    });
    const data = await resp.json();
    wait.classList.remove('wait');
    if (!resp.ok) {
      wait.textContent = data.detail || 'Что-то пошло не так';
    } else {
      wait.textContent = data.answer;
      addSources(wait, data.sources);
      addBy(wait, data.model);
    }
  } catch (err) {
    wait.classList.remove('wait');
    wait.textContent = 'Сервер не отвечает';
  }
  btn.disabled = false;
  messages.scrollTop = messages.scrollHeight;
};

loadModels();
loadDocs();
