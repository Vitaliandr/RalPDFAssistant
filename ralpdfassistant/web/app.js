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

// какие документы отмечены галочкой, по умолчанию все готовые
const unchecked = new Set();
let timer = null;

async function loadDocs() {
  const resp = await fetch('/api/documents');
  const docs = await resp.json();

  hintEl.style.display = docs.length ? 'none' : 'block';
  docsEl.innerHTML = '';

  for (const d of docs) {
    const li = document.createElement('li');

    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.disabled = d.status !== 'ready';
    cb.checked = !unchecked.has(d.id);
    cb.dataset.id = d.id;
    cb.onchange = () => cb.checked ? unchecked.delete(d.id) : unchecked.add(d.id);

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
    del.onclick = async () => {
      if (!confirm('Удалить документ "' + d.title + '"?')) return;
      await fetch('/api/documents/' + d.id, { method: 'DELETE' });
      loadDocs();
    };

    li.append(cb, name, badge, del);
    docsEl.append(li);
  }

  // пока что-то обрабатывается опрашиваем список раз в 2 сек
  const busy = docs.some(d => d.status === 'queued' || d.status === 'processing');
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

  addMsg(question, 'user');
  input.value = '';
  btn.disabled = true;
  const wait = addMsg('Ищу в документах и думаю...', 'bot wait');

  //если ничего не отмечено шлём null, ищем по всем
  const ids = [...docsEl.querySelectorAll('input[type=checkbox]:checked')].map(c => Number(c.dataset.id));

  try {
    const resp = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, document_ids: ids.length ? ids : null }),
    });
    const data = await resp.json();
    wait.classList.remove('wait');
    if (!resp.ok) {
      wait.textContent = data.detail || 'Что-то пошло не так';
    } else {
      wait.textContent = data.answer;
      addSources(wait, data.sources);
    }
  } catch (err) {
    wait.classList.remove('wait');
    wait.textContent = 'Сервер не отвечает';
  }
  btn.disabled = false;
  messages.scrollTop = messages.scrollHeight;
};

loadDocs();
