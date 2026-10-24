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
    if (value) lock.focus();
    else reveal.focus();
  };
  reveal.addEventListener("click", () => setUnlocked(true));
  lock.addEventListener("click", () => setUnlocked(false));
  hide.addEventListener("click", () => {
    setUnlocked(false);
    cover.scrollIntoView({behavior:"smooth",block:"center"});
  });
  // No localStorage, automatic unlocking, media requests, or third-party feed.
})();
