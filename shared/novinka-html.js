/** Povolené HTML v textu novinek: b/strong, i/em, small, big, br. Enter = nový řádek. Ostatní značky se escapují. */
(function (global) {
  function escapeHtml(str) {
    return String(str ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatNovinkaHtml(raw) {
    return escapeHtml(raw)
      .replace(/\r\n|\r|\n/g, '<br>')
      .replace(/&lt;br\s*\/?&gt;/gi, '<br>')
      .replace(/&lt;(\/?)(b|strong|i|em|small|big)\s*&gt;/gi, function (_, slash, tag) {
        return '<' + slash + tag.toLowerCase() + '>';
      });
  }

  global.formatNovinkaHtml = formatNovinkaHtml;
})(window);
