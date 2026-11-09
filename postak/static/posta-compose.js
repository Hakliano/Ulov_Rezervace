(function () {
  var form = document.getElementById('compose-form');
  var editorEl = document.getElementById('compose-editor');
  var hidden = document.getElementById('telo-hidden');
  if (!form || !editorEl || !hidden || typeof Quill === 'undefined' || typeof postakQuillCreate === 'undefined') {
    return;
  }

  var quill = postakQuillCreate(editorEl, 'Napište zprávu…');
  postakQuillLoadInitial(quill, 'compose-initial');

  form.addEventListener('submit', function (ev) {
    hidden.value = quill.root.innerHTML;
    var submitter = ev.submitter;
    if (!submitter || submitter.value === 'odeslat') {
      if (submitter) {
        submitter.disabled = true;
        submitter.textContent = 'Odesílám…';
      }
    } else if (submitter.value === 'koncept') {
      submitter.disabled = true;
      submitter.textContent = 'Ukládám…';
    }
  });
})();
