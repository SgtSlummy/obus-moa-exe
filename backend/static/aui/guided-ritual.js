(function initGuidedRitual() {
  const body = document.body;
  const one = (selector) => document.querySelector(selector);

  body.classList.add('guided-ritual');

  function activePage() {
    return one('.page.active')?.dataset.pagePanel || 'dashboard';
  }

  function syncPage() {
    const page = activePage();
    body.dataset.guidedPage = page;
    const header = one('#home-status-header');
    if (header) {
      const isHome = page === 'dashboard';
      header.hidden = !isHome;
      header.setAttribute('aria-hidden', String(!isHome));
    }
    const mobileTitle = one('#mobile-current-page');
    if (mobileTitle) {
      const labels = { dashboard: 'Home', plan: 'Tasks', workspace: 'Workspace', memory: 'Memory', settings: 'Settings' };
      mobileTitle.textContent = labels[page] || mobileTitle.textContent;
    }
  }

  function syncSurfaceLabel() {
    const select = one('#workspace-surface');
    const badge = one('#workspace-surface-badge');
    if (!select || !badge) return;
    const labels = { terminal: 'Simple', operator: 'Standard', ade: 'Advanced' };
    const label = `${labels[select.value] || 'Standard'} interface`;
    if (badge.textContent !== label) badge.textContent = label;
  }

  function syncRouteState() {
    const state = (one('#run-state')?.textContent || 'Idle').replace(/\s+/g, ' ').trim().toLowerCase();
    body.dataset.guidedRouteState = /^(idle|ready)$/.test(state) ? 'idle' : 'active';
  }

  function revealWorkspace() {
    if (typeof window.setPage === 'function') window.setPage('workspace');
    requestAnimationFrame(() => {
      window.scrollTo(0, 0);
      syncPage();
    });
  }

  const workspaceMount = one('#guided-workspace-mount');
  const workspacePanel = one('#workspace-context');
  if (workspaceMount && workspacePanel) workspaceMount.append(workspacePanel);

  const workspaceButton = one('[data-guided-workspace]');
  if (workspaceButton) workspaceButton.onclick = revealWorkspace;

  document.querySelectorAll('.nav button[data-page]').forEach((button) => {
    button.addEventListener('click', () => requestAnimationFrame(() => {
      window.scrollTo(0, 0);
      syncPage();
    }));
  });

  const pageObserver = new MutationObserver(() => requestAnimationFrame(syncPage));
  document.querySelectorAll('.page').forEach((page) => {
    pageObserver.observe(page, { attributes: true, attributeFilter: ['class'] });
  });

  one('#workspace-surface')?.addEventListener('change', () => requestAnimationFrame(syncSurfaceLabel));
  const surfaceBadge = one('#workspace-surface-badge');
  if (surfaceBadge) new MutationObserver(syncSurfaceLabel).observe(surfaceBadge, { childList: true, subtree: true });

  const routeState = one('#run-state');
  if (routeState) new MutationObserver(() => {
    syncRouteState();
  }).observe(routeState, { childList: true, subtree: true, characterData: true });

  document.querySelectorAll('[data-terminal-view="shell"]').forEach((button) => {
    button.addEventListener('click', () => one('#shell-panel')?.classList.add('guided-shell-open'), true);
  });

  document.querySelectorAll('[data-terminal-view="workspace"]').forEach((button) => {
    button.addEventListener('click', () => {
      const advanced = one('.guided-dashboard-advanced');
      if (advanced) advanced.open = true;
    }, true);
  });

  const input = one('#route-input');
  if (input) {
    input.placeholder = 'Describe your goal in plain language. OBus will plan the steps and get to work.';
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = `${Math.min(input.scrollHeight, 240)}px`;
    });
  }

  syncPage();
  syncSurfaceLabel();
  syncRouteState();
})();
