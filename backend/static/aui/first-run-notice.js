(() => {
  'use strict';

  const acknowledgementKey = 'obus.commandCenter.setupNoticeAcknowledged.v1';
  const warningPrefix = 'Voice uses an explicit microphone permission';

  function hasAcknowledged() {
    try { return window.localStorage.getItem(acknowledgementKey) === 'true'; }
    catch (_) { return false; }
  }

  function acknowledge() {
    try { window.localStorage.setItem(acknowledgementKey, 'true'); }
    catch (_) { /* A private profile can still hide the notice for this visit. */ }
  }

  function installFirstRunNotice() {
    const warning = [...document.querySelectorAll('p')].find((node) =>
      node.textContent.trim().startsWith(warningPrefix),
    );
    if (!warning) return;

    if (hasAcknowledged()) {
      warning.hidden = true;
      return;
    }

    warning.hidden = true;
    const notice = document.createElement('section');
    notice.className = 'first-run-notice';
    notice.setAttribute('role', 'note');
    notice.innerHTML = `
      <div>
        <strong>Before you start</strong>
        <p>Voice, files, and autonomous work stay under your control. Review the prompt before beginning; OBus asks before consequential actions.</p>
      </div>
      <button class="button mini" type="button">Got it</button>`;
    const button = notice.querySelector('button');
    button.addEventListener('click', () => {
      acknowledge();
      notice.remove();
    });
    warning.before(notice);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', installFirstRunNotice, { once: true });
  } else {
    installFirstRunNotice();
  }
})();
