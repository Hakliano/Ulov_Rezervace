(function () {
  var notice = document.getElementById('copy-notice');
  document.querySelectorAll('.btn-copy-poznamka').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var url = btn.getAttribute('data-url');
      if (!url || typeof postakCopyFromUrl === 'undefined') {
        return;
      }
      btn.disabled = true;
      postakCopyFromUrl(url, notice).finally(function () {
        btn.disabled = false;
      });
    });
  });
})();
