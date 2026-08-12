/**
 * MicroVerse interactive charts for matrAIx blog — uses unified embed bundle.
 */
(function () {
  function showError(mount, message) {
    mount.innerHTML = `<p class="blog-charts-error">${message}</p>`;
  }

  function init() {
    const mounts = document.querySelectorAll('[data-microverse-charts]');
    if (!mounts.length) return;

    const first = mounts[0];
    const assetBase = first.dataset.assetBase || 'microverse-world/';

    if (!window.MicroVerseBlogLoader) {
      mounts.forEach((el) => showError(el, 'Chart loader failed to start. Please refresh the page.'));
      return;
    }

    window.MicroVerseBlogLoader.load(assetBase)
      .then((api) => {
        api.mountAllCharts();
      })
      .catch((err) => {
        console.warn('[microverse-charts]', err);
        mounts.forEach((el) => showError(el, 'Charts could not load. Please refresh the page.'));
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
