(() => {
  const root = document.documentElement;
  const videos = [...document.querySelectorAll('video')];
  const pauseStyle = document.createElement('style');
  pauseStyle.textContent = 'html.document-hidden *,html.document-hidden *::before,html.document-hidden *::after{animation-play-state:paused!important}';
  document.head.appendChild(pauseStyle);

  const setDocumentState = () => {
    const hidden = document.visibilityState === 'hidden';
    root.classList.toggle('document-hidden', hidden);
    videos.forEach(video => {
      if (hidden) {
        video.dataset.resumePlayback = String(!video.paused);
        video.pause();
      } else if (video.dataset.resumePlayback === 'true' && video.dataset.inViewport !== 'false') {
        video.play().catch(() => {});
      }
    });
  };

  videos.forEach(video => {
    video.preload = 'metadata';
    video.setAttribute('preload', 'metadata');
  });

  if ('IntersectionObserver' in window && videos.length) {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        const video = entry.target;
        video.dataset.inViewport = String(entry.isIntersecting);
        if (entry.isIntersecting && document.visibilityState !== 'hidden') {
          if (video.autoplay || video.dataset.autoplay === 'true' || video.dataset.resumePlayback === 'true') video.play().catch(() => {});
        } else {
          video.dataset.resumePlayback = String(!video.paused);
          video.pause();
        }
      });
    }, { rootMargin: '180px 0px', threshold: 0.01 });
    videos.forEach(video => observer.observe(video));
  }

  document.addEventListener('visibilitychange', setDocumentState);
  window.addEventListener('pagehide', () => videos.forEach(video => video.pause()));
  setDocumentState();
})();
