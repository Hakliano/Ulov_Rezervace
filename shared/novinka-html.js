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

  var BLOCK = "ul|ol|li|p|h1|h2|h3|h4|h5|hr";

  function formatNovinkaHtml(raw) {
    var html = escapeHtml(raw)
      .replace(/\r\n|\r|\n/g, "<br>")
      .replace(new RegExp("&lt;(" + VOID_TAGS + ")\\s*\\/?&gt;", "gi"), function (_, tag) {
        return "<" + tag.toLowerCase() + ">";
      })
      .replace(new RegExp("&lt;(\\/?)(" + PAIR_TAGS + ")\\s*&gt;", "gi"), function (_, slash, tag) {
        return "<" + slash + tag.toLowerCase() + ">";
      });
    // Enter around lists/headings must not become extra <br> — that blows up card height.
    html = html.replace(new RegExp("(?:<br>)+(?=</?(?:" + BLOCK + ")\\b)", "gi"), "");
    html = html.replace(new RegExp("(</?(?:" + BLOCK + ")>|<hr>)(?:<br>)+", "gi"), "$1");
    html = html.replace(new RegExp("(<(?:" + BLOCK + ")>)\\s+", "gi"), "$1");
    html = html.replace(new RegExp("\\s+(</(?:" + BLOCK + ")>)", "gi"), "$1");
    html = html.replace(/(?:<br>\s*){3,}/gi, "<br><br>");
    return html;
  }

  function replaceSelection(ta, insert, cursorOffset) {
    var start = ta.selectionStart;
    var end = ta.selectionEnd;
    var val = ta.value;
    ta.value = val.slice(0, start) + insert + val.slice(end);
    var pos = start + (cursorOffset == null ? insert.length : cursorOffset);
    ta.focus();
    ta.setSelectionRange(pos, pos);
  }

  function wrapSelection(ta, open, close, placeholder) {
    var start = ta.selectionStart;
    var end = ta.selectionEnd;
    var val = ta.value;
    var selected = val.slice(start, end);
    var inner = selected || placeholder || "";
    ta.value = val.slice(0, start) + open + inner + close + val.slice(end);
    ta.focus();
    if (selected) {
      ta.setSelectionRange(start, start + open.length + inner.length + close.length);
    } else {
      var innerStart = start + open.length;
      ta.setSelectionRange(innerStart, innerStart + inner.length);
    }
  }

  function wrapList(ta, ordered) {
    var start = ta.selectionStart;
    var end = ta.selectionEnd;
    var val = ta.value;
    var selected = val.slice(start, end);
    var lines = (selected || "položka").split(/\r\n|\r|\n/);
    var items = lines.map(function (line) {
      var clean = line.replace(/^\s*(?:[-•*]|\d+[.)])\s*/, "");
      return "<li>" + (clean || "položka") + "</li>";
    }).join("");
    var tag = ordered ? "ol" : "ul";
    var block = "<" + tag + ">" + items + "</" + tag + ">";
    replaceSelection(ta, block, block.length);
  }

  var ACTIONS = [
    { label: "Tučně", title: "Tučné písmo", run: function (ta) { wrapSelection(ta, "<b>", "</b>", "tučný text"); } },
    { label: "Kurzíva", title: "Šikmé písmo", run: function (ta) { wrapSelection(ta, "<i>", "</i>", "kurzíva"); } },
    { label: "Podtrhnout", title: "Podtržení", run: function (ta) { wrapSelection(ta, "<u>", "</u>", "podtržený text"); } },
    { label: "Nadpis", title: "Nadpis v článku", run: function (ta) { wrapSelection(ta, "<h2>", "</h2>", "Nadpis"); } },
    { label: "Odrážky", title: "Seznam s odrážkami", run: function (ta) { wrapList(ta, false); } },
    { label: "Čísla", title: "Číslovaný seznam", run: function (ta) { wrapList(ta, true); } },
    { label: "Čára", title: "Oddělovací čára", run: function (ta) { replaceSelection(ta, "<hr>"); } },
  ];

  function enhanceTextarea(ta) {
    if (!ta || ta.nodeName !== "TEXTAREA" || ta.dataset.novinkaTb === "1") return;
    ta.dataset.novinkaTb = "1";
    var bar = document.createElement("div");
    bar.className = "novinka-toolbar";
    ACTIONS.forEach(function (action) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = action.label;
      btn.title = action.title;
      btn.addEventListener("mousedown", function (e) { e.preventDefault(); });
      btn.addEventListener("click", function () { action.run(ta); });
      bar.appendChild(btn);
    });
    ta.parentNode.insertBefore(bar, ta);
  }

  function scanEditors() {
    var list = document.querySelectorAll("textarea.novinka-text");
    for (var i = 0; i < list.length; i++) enhanceTextarea(list[i]);
  }

  function initNovinkaEditor() {
    scanEditors();
    if (typeof MutationObserver === "undefined") return;
    new MutationObserver(scanEditors).observe(document.body, { childList: true, subtree: true });
  }

  global.formatNovinkaHtml = formatNovinkaHtml;

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", initNovinkaEditor);
    } else {
      initNovinkaEditor();
    }
  }
})(typeof window !== "undefined" ? window : globalThis);
