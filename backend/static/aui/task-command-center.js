(() => {
  'use strict';
  const style = document.createElement('style');
  style.textContent = `.task-command-center{margin:0 0 16px}.task-command-head{align-items:flex-start}.task-command-summary{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px}.task-command-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}.task-command-pane{min-width:0;border:1px solid var(--line);border-radius:12px;background:#090d19;padding:13px}.task-command-pane h4{margin:0 0 10px;font-size:13px}.task-command-list{display:grid;gap:8px;max-height:360px;overflow:auto}.task-command-card{display:grid;gap:5px;width:100%;border:1px solid var(--line);border-radius:10px;background:#0c1120;color:var(--text);padding:11px;text-align:left}.task-command-card:not(.approval-card){cursor:pointer}.task-command-card:not(.approval-card):hover,.task-command-card:not(.approval-card):focus-visible{border-color:var(--violet);background:#12172a;outline:none}.task-command-card .badge{justify-self:start;margin:0}.task-command-card strong{font-size:12px;line-height:1.35}.task-command-card small{color:var(--muted);font-size:11px;line-height:1.35}@media(max-width:720px){.task-command-grid{grid-template-columns:1fr}.task-command-head{gap:10px;flex-wrap:wrap}.task-command-head .actions{width:100%}.task-command-head .actions .button{flex:1}}`;
  document.head.append(style);
  const TASKS_URL = '/api/harness/tasks?limit=12';
  const APPROVAL_URLS = ['/api/harness/approvals?limit=12', '/api/approvals?limit=12'];
  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const formatTime = value => value ? new Date(value).toLocaleString([], {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'}) : 'awaiting update';
  const fetchJson = async (url, options = {}) => {
    const response = await fetch(url, {...options, headers:{Accept:'application/json', ...(options.headers || {})}});
    if (!response.ok) throw new Error(`Request unavailable (${response.status})`);
    return response.json();
  };
  const listOf = value => Array.isArray(value) ? value : (value?.items || value?.tasks || value?.approvals || []);
  const statusClass = value => /succeed|complete|ready|approved/i.test(value || '') ? 'ready' : /fail|reject|cancel|risk/i.test(value || '') ? 'warn' : '';

  function mount() {
    const page = document.querySelector('[data-page-panel="plan"]');
    if (!page || document.querySelector('#task-command-center')) return;
    const center = document.createElement('section');
    center.id = 'task-command-center';
    center.className = 'panel task-command-center';
    center.setAttribute('aria-labelledby', 'task-command-center-title');
    center.innerHTML = `
      <div class="panel-head task-command-head">
        <div><h3 id="task-command-center-title">Task command center</h3><span class="hint">Recent autonomous work, safe resume points, and major-risk approvals in one place.</span></div>
        <div class="actions"><button class="button mini" type="button" data-task-center-action="refresh">Refresh</button><button class="button mini" type="button" data-task-center-action="runtime">Open agent jobs</button></div>
      </div>
      <div class="panel-body">
        <div class="task-command-summary" aria-live="polite"><span class="badge" id="task-center-summary">Loading task state…</span><span class="hint">Opening a task never replays it. Resuming always re-inspects its checkpoint.</span></div>
        <div class="task-command-grid">
          <section class="task-command-pane" aria-labelledby="task-center-recent-title"><h4 id="task-center-recent-title">Recent autonomous work</h4><div id="task-center-tasks" class="task-command-list"><p class="empty">Loading durable task history…</p></div></section>
          <section class="task-command-pane" aria-labelledby="task-center-approval-title"><h4 id="task-center-approval-title">Approval inbox</h4><div id="task-center-approvals" class="task-command-list"><p class="empty">Checking major-risk requests…</p></div></section>
          <section class="task-command-pane task-command-detail" aria-labelledby="task-center-detail-title"><h4 id="task-center-detail-title">Selected task</h4><div id="task-center-detail" class="task-command-list"><p class="empty">Select a task to inspect its durable local checkpoint. This never starts or replays work.</p></div></section>
        </div>
      </div>`;
    page.prepend(center);
    center.addEventListener('click', event => {
      const action = event.target.closest('[data-task-center-action]')?.dataset.taskCenterAction;
      if (action === 'refresh') load();
      if (action === 'runtime') document.querySelector('.nav button[data-page="runtime"]')?.dispatchEvent(new MouseEvent('click', {bubbles:true}));
      const task = event.target.closest('[data-task-center-open]')?.dataset.taskCenterOpen;
      if (task) inspectTask(task);
      const resume = event.target.closest('[data-task-center-resume]')?.dataset.taskCenterResume;
      if (resume) resumeTask(resume);
      if (event.target.closest('[data-task-center-live]')) openLiveTask();
    });
    load();
  }

  async function load() {
    const tasksEl = document.querySelector('#task-center-tasks');
    const approvalsEl = document.querySelector('#task-center-approvals');
    const summary = document.querySelector('#task-center-summary');
    if (!tasksEl || !approvalsEl || !summary) return;
    try {
      const taskResult = await fetchJson(TASKS_URL);
      const tasks = listOf(taskResult);
      let approvals = [];
      for (const url of APPROVAL_URLS) {
        try { approvals = listOf(await fetchJson(url)); if (approvals.length || url === APPROVAL_URLS.at(-1)) break; } catch (_) { /* Older local builds expose approvals through Runtime only. */ }
      }
      renderTasks(tasksEl, tasks);
      renderApprovals(approvalsEl, approvals);
      const waiting = tasks.filter(task => /queued|running|verifying|approval/i.test(task.status || task.state || '')).length;
      const pending = approvals.filter(item => /pending|requested|awaiting/i.test(item.status || item.state || '')).length;
      summary.className = `badge ${pending ? 'warn' : waiting ? '' : 'ready'}`;
      summary.textContent = `${tasks.length} recent task${tasks.length === 1 ? '' : 's'} · ${waiting} active · ${pending} approval${pending === 1 ? '' : 's'} waiting`;
    } catch (error) {
      tasksEl.innerHTML = `<p class="empty">Task history is temporarily unavailable: ${escapeHtml(error.message)}</p>`;
      approvalsEl.innerHTML = '<p class="empty">Approval state remains available from Agent jobs.</p>';
      summary.className = 'badge warn'; summary.textContent = 'Task command center needs a refresh';
    }
  }

  function renderTasks(target, tasks) {
    if (!tasks.length) { target.innerHTML = '<p class="empty">No autonomous tasks yet. Start one from Home when you are ready.</p>'; return; }
    target.innerHTML = tasks.map(task => {
      const id = task.id || task.task_id || '';
      const state = task.status || task.state || 'unknown';
      const objective = task.objective || task.goal || task.title || 'Untitled local task';
      return `<button class="task-command-card" type="button" data-task-center-open="${escapeHtml(id)}"><span class="badge ${statusClass(state)}">${escapeHtml(state)}</span><strong>${escapeHtml(objective)}</strong><small>${escapeHtml(task.provider || task.model || 'local provider')} · ${escapeHtml(formatTime(task.updated_at || task.finished_at || task.created_at))}</small></button>`;
    }).join('');
  }

  function renderApprovals(target, approvals) {
    if (!approvals.length) { target.innerHTML = '<p class="empty">No major-risk approval is waiting. Ordinary work can continue autonomously.</p>'; return; }
    target.innerHTML = approvals.map(item => {
      const state = item.status || item.state || 'pending';
      const title = item.summary || item.objective || item.action || 'Major-risk action';
      return `<div class="task-command-card approval-card"><span class="badge ${statusClass(state)}">${escapeHtml(state)}</span><strong>${escapeHtml(title)}</strong><small>Review in Agent jobs before anything consequential runs.</small></div>`;
    }).join('');
  }

  async function inspectTask(id) {
    const detail = document.querySelector('#task-center-detail');
    if (!detail) return;
    detail.innerHTML = '<p class="empty">Loading the selected task’s local checkpoint…</p>';
    try {
      const task = await fetchJson(`/api/harness/tasks/${encodeURIComponent(id)}`);
      try { sessionStorage.setItem('obus-last-autonomous-task', id); } catch (_) {}
      document.querySelectorAll('[data-task-center-open]').forEach(button => button.classList.toggle('selected', button.dataset.taskCenterOpen === id));
      const state = task.status || task.state || 'unknown';
      const retryable = /failed|cancelled|interrupted|paused/i.test(state);
      detail.innerHTML = `<div class="task-command-card selected-task-card"><span class="badge ${statusClass(state)}">${escapeHtml(state)}</span><strong>${escapeHtml(task.objective || task.goal || task.title || 'Untitled local task')}</strong><small>${escapeHtml(task.provider || task.model || 'local provider')} · attempt ${escapeHtml(task.attempt || task.retry_count || 1)}</small><small>${escapeHtml(formatTime(task.updated_at || task.finished_at || task.created_at))}</small>${task.result ? `<pre>${escapeHtml(String(task.result).slice(0, 1200))}</pre>` : '<small>No result has been recorded yet.</small>'}<div class="actions"><button class="button mini" type="button" data-task-center-live>Open live activity</button>${retryable ? `<button class="button mini primary" type="button" data-task-center-resume="${escapeHtml(id)}">Resume safely</button>` : ''}</div></div>`;
    } catch (error) {
      detail.innerHTML = `<p class="empty">Task detail is temporarily unavailable: ${escapeHtml(error.message)}</p>`;
    }
  }

  async function resumeTask(id) {
    const detail = document.querySelector('#task-center-detail');
    if (detail) detail.insertAdjacentHTML('afterbegin', '<p class="hint">Re-inspecting the workspace before resume…</p>');
    try {
      await fetchJson(`/api/harness/tasks/${encodeURIComponent(id)}/resume`, {method:'POST'});
      await load();
      await inspectTask(id);
    } catch (error) {
      if (detail) detail.insertAdjacentHTML('afterbegin', `<p class="empty">Safe resume was not started: ${escapeHtml(error.message)}</p>`);
    }
  }

  function openLiveTask() {
    document.querySelector('.nav button[data-page="dashboard"]')?.dispatchEvent(new MouseEvent('click', {bubbles:true}));
  }

  document.addEventListener('DOMContentLoaded', mount);
  if (document.readyState !== 'loading') mount();
})();
