/** Povolené HTML v textu novinek — jen značky bez atributů. Enter = nový řádek. */
(function (global) {
  var VOID_TAGS = "br|hr";
  var PAIR_TAGS = "b|strong|u|i|em|p|h1|h2|h3|h4|h5|ul|ol|li|small|big";

  function escapeHtml(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatNovinkaHtml(raw) {
    return escapeHtml(raw)
      .replace(/\r\n|\r|\n/g, "<br>")
      .replace(new RegExp("&lt;(" + VOID_TAGS + ")\\s*\\/?&gt;", "gi"), function (_, tag) {
        return "<" + tag.toLowerCase() + ">";
      })
      .replace(new RegExp("&lt;(\\/?)(" + PAIR_TAGS + ")\\s*&gt;", "gi"), function (_, slash, tag) {
        return "<" + slash + tag.toLowerCase() + ">";
      });
  }

  global.formatNovinkaHtml = formatNovinkaHtml;
})(window);
