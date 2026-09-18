(function () {
  const pricing = window.ARCHIVNIK_PRICING || {};
  const valueEl = document.querySelector("[data-price-solo]");
  const noteEl = document.querySelector("[data-price-note]");
  const amount = String(pricing.soloAmount || "").trim();

  if (valueEl) {
    valueEl.textContent = amount
      ? `${amount} ${pricing.soloUnit || "Kč / měsíc"}`.trim()
      : pricing.soloPlaceholder || "Cenu upřesníme";
  }
  if (noteEl && pricing.soloNote) {
    noteEl.textContent = pricing.soloNote;
  }

  const dialog = document.getElementById("arc-lightbox");
  const dialogImg = document.getElementById("arc-lightbox-img");
  const closeBtn = document.getElementById("arc-lightbox-close");

  function openLightbox(img) {
    if (!dialog || !dialogImg || !img) return;
    dialogImg.src = img.currentSrc || img.src;
    dialogImg.alt = img.alt || "";
    if (typeof dialog.showModal === "function") dialog.showModal();
  }

  function closeLightbox() {
    if (dialog?.open) dialog.close();
  }

  document.querySelectorAll(".arc-shot-open").forEach((btn) => {
    btn.addEventListener("click", () => {
      openLightbox(btn.querySelector("img"));
    });
  });

  closeBtn?.addEventListener("click", closeLightbox);
  dialog?.addEventListener("click", (event) => {
    if (event.target === dialog) closeLightbox();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeLightbox();
  });
})();
