(function () {
  function csrf() {
    var node = document.querySelector("[name=csrfmiddlewaretoken]");
    return node ? node.value : "";
  }

  function scrollToLead() {
    var row = document.querySelector(".lead-row.is-editing");
    if (!row && location.hash) {
      try { row = document.querySelector(location.hash); } catch (err) { row = null; }
    }
    if (row) row.scrollIntoView({ block: "center", behavior: "auto" });
  }
  if (document.querySelector(".lead-row.is-editing") || location.hash) {
    if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  }
  scrollToLead();

  document.querySelectorAll("form[data-autosave] select[name=stav]").forEach(function (select) {
    select.addEventListener("change", function () {
      var form = select.closest("form");
      var mark = form.querySelector(".lead-saved");
      var body = new URLSearchParams();
      body.set("stav", select.value);
      body.set("csrfmiddlewaretoken", csrf());
      fetch(form.action, {
        method: "POST",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": csrf(),
        },
        body: body,
      })
        .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
        .then(function (out) {
          if (!mark) return;
          mark.hidden = false;
          mark.textContent = out.ok ? "uloženo" : (out.data.detail || "chyba");
          window.setTimeout(function () { mark.hidden = true; }, 1600);
        })
        .catch(function () {
          if (mark) {
            mark.hidden = false;
            mark.textContent = "chyba";
          }
        });
    });
  });
  document.querySelectorAll("[data-web-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var row = btn.closest(".lead-row");
      var form = row && row.querySelector("form[data-web-save]");
      if (!form) return;
      var open = form.hidden;
      document.querySelectorAll("form[data-web-save]").forEach(function (other) {
        other.hidden = true;
      });
      form.hidden = !open;
      if (!form.hidden) {
        var input = form.querySelector("input[name=web_new]");
        if (input) {
          input.focus();
          input.select();
        }
      }
    });
  });

  document.querySelectorAll("[data-web-cancel]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var form = btn.closest("form[data-web-save]");
      if (form) form.hidden = true;
    });
  });

  document.querySelectorAll("form[data-web-save]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var row = form.closest(".lead-row");
      var body = new URLSearchParams(new FormData(form));
      fetch(form.action, {
        method: "POST",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": csrf(),
        },
        body: body,
      })
        .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
        .then(function (out) {
          if (!out.ok) return;
          var web = out.data.web || "";
          var label = row && row.querySelector(".lead-web");
          if (label) label.textContent = web || "bez webu";
          var toggle = row && row.querySelector("[data-web-toggle]");
          if (toggle) toggle.textContent = web ? "Web" : "+ Web";
          var input = form.querySelector("input[name=web_new]");
          if (input) input.value = web;
          form.hidden = true;
        });
    });
  });
})();
