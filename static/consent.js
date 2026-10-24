(() => {
  "use strict";
  const cover = document.getElementById("consent-cover");
  const unlocked = document.getElementById("consent-unlocked");
  const reveal = document.getElementById("consent-reveal");
  const hide = document.getElementById("consent-hide");
  const lock = document.getElementById("consent-lock");
  if (!cover || !unlocked || !reveal || !hide || !lock) return;
  const setUnlocked = (value) => {
    cover.hidden = value;
    unlocked.hidden = !value;
  };
  async function api(path, options = {}) {
    const response = await fetch(path, {
      credentials: "same-origin", cache: "no-store", ...options,
      headers: {"Content-Type": "application/json", ...(options.headers || {})}
    });
    if (!response.ok) throw new Error("Request rejected (" + response.status + ")");
    return response.json();
  }
  reveal.addEventListener("click", async () => {
    reveal.disabled = true;
    try {
      await api("/api/restricted/consent", {method:"POST", body:JSON.stringify({adult:true})});
      const result = await api("/api/restricted/items");
      setUnlocked(true);
      unlocked.querySelector("p").textContent = result.message || "No reviewed items available.";
      lock.focus();
    } catch (error) {
      window.alert("Could not unlock the section. Check server configuration.");
    } finally {
      reveal.disabled = false;
    }
  });
  lock.addEventListener("click", async () => {
    try { await api("/api/restricted/revoke", {method:"POST", body:"{}"}); }
    finally { setUnlocked(false); reveal.focus(); }
  });
  hide.addEventListener("click", () => { setUnlocked(false); });
  // Locked on each load. No restricted media is delivered to the initial page.
})();
