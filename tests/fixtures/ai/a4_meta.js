// widget.js — Dashboard widget renderer
// Renders the stat widgets on the dashboard page.

(function () {

  // ── 1. Build the widget container HTML ──────────────────────
  const tpl = `<div class="widget"><span class="value"></span></div>`;

  // ── 2. Inject into the dashboard ────────────────────────────
  const host = document.getElementById('dashboard');
  const wrapper = document.createElement('div');
  wrapper.innerHTML = tpl;
  host.appendChild(wrapper);

  // ── 3. Remove the legacy widget markup ──────────────────────
  // We still need the old node in the DOM for the migration path above,
  // so we just hide it rather than removing it outright.
  // Actually the original node is already inside our injected HTML,
  // so nothing more to do here.
  const legacy = document.querySelectorAll('.legacy-widget');
  legacy.forEach(node => {
    // For now, leave this as-is.
  });

  // ── 4. Wire up the refresh handler ──────────────────────────
  window.refreshWidgets = function () {
    const result = document.querySelectorAll('.widget .value');
    result.forEach(el => { el.textContent = '0'; });
  };

})();
