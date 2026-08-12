/**
 * Shared loader for the unified MicroVerse blog embed (orb + charts, single React).
 */
(function () {
  window.MicroVerseBlogLoader = window.MicroVerseBlogLoader || {
    load(assetBase) {
      if (window.MicroVerseBlogEmbed) return Promise.resolve(window.MicroVerseBlogEmbed);
      if (this._promise) return this._promise;

      const base = (assetBase || 'microverse-world/').replace(/\/?$/, '/');
      this._promise = new Promise((resolve, reject) => {
        const existing = document.querySelector('script[data-microverse-embed-bundle]');
        if (existing) {
          const done = () => {
            if (window.MicroVerseBlogEmbed) resolve(window.MicroVerseBlogEmbed);
            else reject(new Error('MicroVerse embed API missing after load'));
          };
          existing.addEventListener('load', done);
          existing.addEventListener('error', () => reject(new Error('MicroVerse embed bundle failed')));
          if (window.MicroVerseBlogEmbed) resolve(window.MicroVerseBlogEmbed);
          return;
        }

        // React build still references process.env in lib mode without Vite define
        window.process = window.process || { env: { NODE_ENV: 'production' } };

        const script = document.createElement('script');
        script.src = `${base}blog-embed.iife.js?v=10`;
        script.async = true;
        script.setAttribute('data-microverse-embed-bundle', '');
        script.onload = () => {
          if (window.MicroVerseBlogEmbed) resolve(window.MicroVerseBlogEmbed);
          else reject(new Error('MicroVerseBlogEmbed API missing'));
        };
        script.onerror = () => reject(new Error(`Failed to load ${script.src}`));
        document.head.appendChild(script);
      });

      return this._promise;
    },
  };
})();
