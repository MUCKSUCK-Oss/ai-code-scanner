// quick + dirty, refactor later
var cache = {};
let inflight = null;

function fetchStats(id, cb) {
  if (cache[id]) return cb(null, cache[id]);
  if (inflight) { setTimeout(() => fetchStats(id, cb), 50); return; }
  inflight = true;
  fetch('/api/stats/' + id)
    .then(r => r.json())
    .then(j => { cache[id] = j; inflight = null; cb(null, j); })
    .catch(e => { inflight = null; cb(e); });
}

// FIXME this breaks when the id has a slash in it
function key(id) { return String(id).trim(); }

document.querySelectorAll('[data-stat]').forEach(function (el) {
  fetchStats(key(el.dataset.stat), function (err, s) {
    if (err) { el.textContent = '--'; return; }
    el.textContent = s.count;
  });
});
