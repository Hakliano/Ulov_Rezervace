(function () {
  var form = document.getElementById('poznamka-form');
  var editorEl = document.getElementById('compose-editor');
  var hidden = document.getElementById('obsah-hidden');
  var copyBtn = document.getElementById('copy-btn');
  var notice = document.getElementById('copy-notice');
  if (!form || !editorEl || !hidden || typeof Quill === 'undefined' || typeof postakQuillCreate === 'undefined') {
    return;
  }

  var quill = postakQuillCreate(editorEl, 'Obsah poznámky…');
  postakQuillLoadInitial(quill, 'compose-initial');

  form.addEventListener('submit', function () {
    hidden.value = quill.root.innerHTML;
    var saveBtn = form.querySelector('button[type="submit"]');
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.textContent = 'Ukládám…';
    }
  });

  if (!copyBtn) {
    return;
  }

  copyBtn.addEventListener('click', function () {
    if (typeof postakCopyRichHtml === 'undefined') {
      return;
    }
    postakCopyRichHtml(quill.root.innerHTML, quill.getText(), notice);
  });
})();
