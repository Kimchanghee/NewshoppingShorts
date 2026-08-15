(() => {
  const viewButtons = Array.from(document.querySelectorAll("[data-view]"))
    .filter((element) => element.tagName === "BUTTON");

  const setView = (view) => {
    document.body.dataset.view = view;
    viewButtons.forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.view === view));
    });
  };

  viewButtons.forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.view));
  });

  document.querySelectorAll(".sample-card").forEach((card) => {
    const videos = Array.from(card.querySelectorAll("video"));
    const playButton = card.querySelector(".pair-play");
    const resetButton = card.querySelector(".pair-reset");

    const updatePlayLabel = () => {
      const isPlaying = videos.some((video) => !video.paused && !video.ended);
      playButton.lastChild.textContent = isPlaying ? " 두 영상 일시정지" : " 두 영상 함께 재생";
    };

    playButton.addEventListener("click", async () => {
      const shouldPlay = videos.every((video) => video.paused || video.ended);
      if (shouldPlay) {
        const commonTime = Math.min(...videos.map((video) => video.currentTime || 0));
        videos.forEach((video) => { video.currentTime = commonTime; });
        await Promise.allSettled(videos.map((video) => video.play()));
      } else {
        videos.forEach((video) => video.pause());
      }
      updatePlayLabel();
    });

    resetButton.addEventListener("click", () => {
      videos.forEach((video) => {
        video.pause();
        video.currentTime = 0;
      });
      updatePlayLabel();
    });

    videos.forEach((video) => {
      video.addEventListener("play", () => {
        document.querySelectorAll("video").forEach((other) => {
          if (!card.contains(other)) other.pause();
        });
        updatePlayLabel();
      });
      video.addEventListener("pause", updatePlayLabel);
      video.addEventListener("ended", updatePlayLabel);
    });
  });

  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) {
          entry.target.querySelectorAll("video").forEach((video) => video.pause());
        }
      });
    }, { threshold: 0.08 });

    document.querySelectorAll(".sample-card").forEach((card) => observer.observe(card));
  }
})();

