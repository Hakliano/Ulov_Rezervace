/** Cena služby na webu: prázdné = nic, 0 = Zdarma, rozsah, Od. */
(function (global) {
  function esc(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function toInt(value) {
    if (value == null || value === "") return null;
    var n = parseInt(value, 10);
    return Number.isFinite(n) ? n : null;
  }

  function formatCenikCena(item) {
    item = item || {};
    var a = toInt(item.cena);
    var b = toInt(item.cena_do);
    if (a == null) return "";
    if (a === 0) return "Zdarma";
    if (b != null && b !== a) {
      var lo = Math.min(a, b);
      var hi = Math.max(a, b);
      return lo + "–" + hi + " Kč";
    }
    if (item.zobrazit_od) return "Od " + a + " Kč";
    return a + " Kč";
  }

  function cenaInputVal(value) {
    if (value === 0 || value === "0") return "0";
    if (value == null || value === "") return "";
    return String(value);
  }

  function isZdarma(item) {
    return toInt(item && item.cena) === 0;
  }

  function cenikAdminPriceHtml(item) {
    item = item || {};
    var zdarma = isZdarma(item);
    var dis = zdarma ? " disabled" : "";
    return (
      '<div class="cenik-cena-row">' +
        '<input type="number" class="cenik-cena" min="0" placeholder="Cena" value="' +
          esc(cenaInputVal(zdarma ? "" : item.cena)) + '"' + dis + '>' +
        '<input type="number" class="cenik-cena-do" min="0" placeholder="Cena do" value="' +
          esc(cenaInputVal(item.cena_do)) + '"' + dis + '>' +
      "</div>" +
      '<textarea class="cenik-popis" rows="2" placeholder="Popis služby (volitelné)">' +
        esc(item.popis || "") +
      "</textarea>" +
      '<label class="checkbox cenik-flag">' +
        '<input type="checkbox" class="cenik-zobrazit-od"' +
          (item.zobrazit_od ? " checked" : "") + dis + ">" +
        "Na webu napsat „Od … Kč“" +
      "</label>" +
      '<label class="checkbox cenik-flag">' +
        '<input type="checkbox" class="cenik-zdarma"' + (zdarma ? " checked" : "") + ">" +
        "Zdarma (na webu se napíše Zdarma, do tržeb 0 Kč)" +
      "</label>"
    );
  }

  function collectCenikCenaFields(el) {
    if (el.querySelector(".cenik-zdarma") && el.querySelector(".cenik-zdarma").checked) {
      return {
        cena: 0,
        cena_do: null,
        zobrazit_od: false,
        popis: (el.querySelector(".cenik-popis") && el.querySelector(".cenik-popis").value || "").trim(),
      };
    }
    function parseNullable(sel) {
      var raw = ((el.querySelector(sel) && el.querySelector(sel).value) || "").trim();
      if (!raw) return null;
      var n = parseInt(raw, 10);
      return Number.isFinite(n) ? n : null;
    }
    return {
      cena: parseNullable(".cenik-cena"),
      cena_do: parseNullable(".cenik-cena-do"),
      zobrazit_od: !!(el.querySelector(".cenik-zobrazit-od") && el.querySelector(".cenik-zobrazit-od").checked),
      popis: (el.querySelector(".cenik-popis") && el.querySelector(".cenik-popis").value || "").trim(),
    };
  }

  function cenikPublicPriceInner(item, escapeFn) {
    var e = escapeFn || esc;
    var label = formatCenikCena(item);
    var popis = String((item && item.popis) || "").trim();
    return (
      '<div class="price-copy-text">' +
        '<span class="price-name">' + e(item.nazev) + "</span>" +
        (popis ? '<span class="price-popis">' + e(popis) + "</span>" : "") +
      "</div>" +
      (label ? '<span class="price-value">' + e(label) + "</span>" : "")
    );
  }

  function toggleZdarmaRow(row, on) {
    if (!row) return;
    ["cenik-cena", "cenik-cena-do", "cenik-zobrazit-od"].forEach(function (cls) {
      var node = row.querySelector("." + cls);
      if (node) node.disabled = on;
    });
    if (on) {
      var cena = row.querySelector(".cenik-cena");
      var cenaDo = row.querySelector(".cenik-cena-do");
      var od = row.querySelector(".cenik-zobrazit-od");
      if (cena) cena.value = "";
      if (cenaDo) cenaDo.value = "";
      if (od) od.checked = false;
    }
  }

  function initCenikAdmin() {
    if (typeof document === "undefined" || !document.body) return;
    document.addEventListener("change", function (e) {
      if (!e.target || !e.target.classList || !e.target.classList.contains("cenik-zdarma")) return;
      toggleZdarmaRow(e.target.closest(".cenik-edit-item"), e.target.checked);
    });
  }

  global.formatCenikCena = formatCenikCena;
  global.cenikAdminPriceHtml = cenikAdminPriceHtml;
  global.collectCenikCenaFields = collectCenikCenaFields;
  global.cenikPublicPriceInner = cenikPublicPriceInner;

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", initCenikAdmin);
    } else {
      initCenikAdmin();
    }
  }
})(typeof window !== "undefined" ? window : globalThis);
