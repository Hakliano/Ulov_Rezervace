function postakCopyRichHtml(html, text, noticeEl) {
  function showOk() {
    if (noticeEl) {
      noticeEl.textContent = 'Formátovaný obsah je ve schránce — vložte do e-mailu (Ctrl+V).';
      noticeEl.className = 'copy-notice copy-ok';
    }
  }

  function showFail() {
    if (noticeEl) {
      noticeEl.textContent =
        'Prohlížeč neumožnil zkopírovat formátování. Zkuste jiný prohlížeč nebo HTTPS / localhost.';
      noticeEl.className = 'copy-notice copy-fail';
    }
  }

  if (!navigator.clipboard || !window.ClipboardItem) {
    showFail();
    return Promise.resolve(false);
  }

  return navigator.clipboard
    .write([
      new ClipboardItem({
        'text/html': new Blob([html || ''], { type: 'text/html' }),
        'text/plain': new Blob([text || ''], { type: 'text/plain' }),
      }),
    ])
    .then(function () {
      showOk();
      return true;
    })
    .catch(function () {
      showFail();
      return false;
    });
}

function postakCopyFromUrl(url, noticeEl) {
  return fetch(url, {
    credentials: 'same-origin',
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
  })
    .then(function (r) {
      if (!r.ok) {
        throw new Error('fetch');
      }
      return r.json();
    })
    .then(function (data) {
      return postakCopyRichHtml(data.html, data.plain, noticeEl);
    })
    .catch(function () {
      if (noticeEl) {
        noticeEl.textContent = 'Obsah se nepodařilo načíst.';
        noticeEl.className = 'copy-notice copy-fail';
      }
      return false;
    });
}
