(function () {
  var box = document.getElementById('chat-msgs');
  if (!box) return;

  var NEAR = 72;
  var sleduje_konec = true;

  function u_konce() {
    return box.scrollHeight - box.scrollTop - box.clientHeight <= NEAR;
  }

  function dolu(smooth) {
    var top = box.scrollHeight;
    try {
      box.scrollTo({ top: top, behavior: smooth ? 'smooth' : 'auto' });
    } catch (e) {
      box.scrollTop = top;
    }
  }

  box.addEventListener('scroll', function () {
    sleduje_konec = u_konce();
  }, { passive: true });

  var observer = new MutationObserver(function () {
    if (sleduje_konec) dolu(false);
  });
  observer.observe(box, { childList: true, subtree: true, characterData: true });

  dolu(false);

  var form = document.querySelector('.chat-compose');
  if (form) {
    form.addEventListener('submit', function () {
      sleduje_konec = true;
      requestAnimationFrame(function () { dolu(false); });
    });
  }

  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible' && sleduje_konec) dolu(false);
  });
})();