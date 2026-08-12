/**
 * MicroVerse hero orb for matrAIx blog — mounts the real HeroCube React component.
 */
(function () {
  function loadEmbed(assetBase) {
    if (!window.MicroVerseBlogLoader) {
      return Promise.reject(new Error('MicroVerseBlogLoader missing — include blog-microverse-loader.js first'));
    }
    return window.MicroVerseBlogLoader.load(assetBase);
  }

  document.querySelectorAll('[data-microverse-orb]').forEach((mount) => {
    const assetBase = mount.dataset.assetBase || 'microverse-world/';
    const base = assetBase.endsWith('/') ? assetBase : `${assetBase}/`;
    const scrollTarget = mount.dataset.scrollTarget || 'research-demo';

    loadEmbed(assetBase)
      .then((api) => {
        const mountHero = api.mountHero || (window.MicroVerseBlogOrb && window.MicroVerseBlogOrb.mount);
        if (!mountHero) throw new Error('MicroVerse mountHero API missing');
        mountHero(mount, {
          assetBase: base,
          replayUrl: `${base}replay.json`,
          hideHint: true,
          onEnter: () => {
            document.getElementById(scrollTarget)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
          },
        });
      })
      .catch((err) => {
        console.warn('[microverse-hero]', err);
      });
  });
})();
