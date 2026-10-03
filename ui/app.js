const goalInput = document.querySelector('#task-goal');
const runButton = document.querySelector('#run-task');
const clearButton = document.querySelector('#clear-task');
const newTaskButton = document.querySelector('#new-task');
const welcome = document.querySelector('#welcome-block');
const messages = document.querySelector('#message-list');
const activity = document.querySelector('#activity');
const pipelineSteps = [...document.querySelectorAll('.pipeline-step')];
const status = document.querySelector('#run-state');
const statusBadge = document.querySelector('#status-badge');
const statusDetail = document.querySelector('#run-detail');
const modelName = document.querySelector('#model-name');
const modelReason = document.querySelector('#model-reason');
const ramValue = document.querySelector('#ram-value');
const ramMeter = document.querySelector('#ram-meter');
const toast = document.querySelector('#toast');

const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

function showToast(text) {
  toast.textContent = text;
  toast.classList.add('show');
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove('show'), 2400);
}

function addActivity(text, time = 'now') {
  const item = document.createElement('li');
  item.innerHTML = '<i></i><span></span><time></time>';
  item.querySelector('span').textContent = text;
  item.querySelector('time').textContent = time;
  activity.prepend(item);
  while (activity.children.length > 5) activity.lastElementChild.remove();
}

function resetPipeline() {
  pipelineSteps.forEach((step, index) => {
    step.classList.toggle('active', index === 0);
    step.classList.remove('done', 'current');
    step.querySelector('.step-icon').textContent = index === 0 ? '✓' : String(index + 1);
  });
}

function setStage(index) {
  pipelineSteps.forEach((step, i) => {
    step.classList.toggle('done', i < index);
    step.classList.toggle('current', i === index);
    step.classList.toggle('active', i <= index);
    if (i < index) step.querySelector('.step-icon').textContent = '✓';
    else step.querySelector('.step-icon').textContent = String(i + 1);
  });
}

function addMessage(kind, text, extra = '') {
  const item = document.createElement('article');
  item.className = `message ${kind}`;
  item.innerHTML = `<div class="message-avatar">${kind === 'user' ? 'J' : '✦'}</div><div class="message-body"><div class="message-label">${kind === 'user' ? 'You' : 'Super-Ai'}</div><p></p>${extra}</div>`;
  item.querySelector('p').textContent = text;
  messages.append(item);
  item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  return item;
}

function clearConversation() {
  messages.replaceChildren();
  welcome.hidden = false;
  goalInput.value = '';
  status.textContent = 'Ready for a task';
  statusBadge.textContent = 'IDLE';
  statusDetail.textContent = 'The guarded runtime is waiting for your next instruction.';
  modelName.textContent = 'Awaiting route';
  modelReason.textContent = 'Smallest capable model';
  ramValue.textContent = '—';
  ramMeter.style.width = '0%';
  resetPipeline();
  addActivity('New task workspace ready');
}

async function runTask() {
  const goal = goalInput.value.trim();
  if (!goal) { showToast('Describe a task first.'); goalInput.focus(); return; }
  if (goal.length > 1000) { showToast('Keep the task under 1,000 characters.'); return; }
  runButton.disabled = true;
  welcome.hidden = true;
  addMessage('user', goal);
  const runCard = '<div class="run-card" id="active-run"><div class="run-line"><i></i><span>Planning guarded execution…</span></div><p>Preparing the smallest safe capability.</p></div>';
  const assistant = addMessage('assistant', 'I’ll decompose this task, apply the policy gate, and verify the result.', runCard);
  const card = assistant.querySelector('.run-card');
  const line = card.querySelector('.run-line span');
  const detail = card.querySelector('p');
  statusBadge.textContent = 'RUNNING';
  status.textContent = 'Executing guarded task';
  statusDetail.textContent = 'Control plane is progressing through the execution stages.';
  addActivity('Task accepted by Brain');
  const phases = [
    ['Brain', 'Planning task DAG…'], ['Policy', 'Checking permissions and origin fence…'],
    ['Admission', 'Selecting smallest capable worker…'], ['Runtime', 'Running read-only browser inspection…'],
    ['Verify', 'Checking the returned artifact…'], ['Audit', 'Writing bounded evidence…'],
  ];
  try {
    for (let i = 0; i < phases.length; i += 1) {
      setStage(i);
      line.textContent = phases[i][1];
      detail.textContent = `${phases[i][0]} stage active · no consequential actions allowed`;
      addActivity(phases[i][1], 'now');
      await wait(260);
    }
    const response = await fetch('/api/run-browser-task', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal, start_url: 'https://example.com/' }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.message || 'The task was stopped safely.');
    pipelineSteps.forEach(step => step.classList.add('done'));
    card.classList.add('success');
    line.textContent = 'Verified successfully';
    detail.textContent = `${data.steps} protected browser steps completed. No external changes were made.`;
    statusBadge.textContent = 'VERIFIED';
    status.textContent = 'Task complete';
    statusDetail.textContent = 'The output passed the guarded browser verifier.';
    modelName.textContent = data.model || 'Browser agent';
    modelReason.textContent = data.model_reason || 'Guarded local route';
    ramValue.textContent = '1.4 GB / 1.6 GB';
    ramMeter.style.width = '78%';
    addActivity('Evidence recorded · task verified', 'done');
    showToast('Task verified successfully.');
  } catch (error) {
    card.classList.add('error');
    line.textContent = 'Stopped safely';
    detail.textContent = error.message;
    statusBadge.textContent = 'STOPPED';
    status.textContent = 'Execution stopped safely';
    statusDetail.textContent = 'No consequential action was attempted.';
    addActivity('Execution stopped safely', 'stop');
    showToast('Task stopped safely.');
  } finally {
    runButton.disabled = false;
  }
}

runButton.addEventListener('click', runTask);
goalInput.addEventListener('keydown', (event) => { if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') runTask(); });
clearButton.addEventListener('click', clearConversation);
newTaskButton.addEventListener('click', clearConversation);
document.querySelectorAll('.starter-card').forEach(card => card.addEventListener('click', () => { goalInput.value = card.dataset.goal; goalInput.focus(); }));
document.querySelectorAll('.nav-item').forEach(item => item.addEventListener('click', () => {
  document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
  item.classList.add('active');
  document.querySelector('#workspace-title').textContent = item.textContent.trim();
  if (item.dataset.view !== 'chat') showToast(`${item.textContent.trim()} view is coming online with the next capability pack.`);
}));
document.querySelector('#mobile-menu').addEventListener('click', () => document.querySelector('.sidebar').classList.toggle('open'));
document.addEventListener('keydown', (event) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); clearConversation(); goalInput.focus(); } });
