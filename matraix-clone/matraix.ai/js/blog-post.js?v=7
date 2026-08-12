(function () {
  const article = document.querySelector('.article');
  const toc = document.querySelector('.article-toc');
  const list = toc && toc.querySelector('ol');
  if (!article) return;

  /* Shared article actions: native/mobile share, social links, copy, and print. */
  const articleTitle = document.querySelector('.blog-title')?.textContent.trim() || document.title;
  const articleSummary = document.querySelector('.article-summary p')?.textContent.trim() || '';
  const declaredCanonical = document.querySelector('link[rel="canonical"]')?.href;
  const articleUrl = new URL(
    declaredCanonical || (/^(localhost|127\.0\.0\.1)$/.test(window.location.hostname)
      ? `https://matraix.ai${window.location.pathname}`
      : window.location.href)
  );
  articleUrl.hash = '';
  const canonicalUrl = articleUrl.href;
  if (!declaredCanonical) {
    const canonicalLink = document.createElement('link');
    canonicalLink.rel = 'canonical';
    canonicalLink.href = canonicalUrl;
    document.head.appendChild(canonicalLink);
  }
  const shareText = articleSummary || articleTitle;
  const header = document.querySelector('.blog-header');

  const icon = paths => `<svg viewBox="0 0 24 24" aria-hidden="true">${paths}</svg>`;
  const icons = {
    share: icon('<circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="19" r="2.5"/><path d="m8.2 10.8 7.6-4.5M8.2 13.2l7.6 4.5"/>'),
    x: icon('<path d="M5 4l14 16M19 4 5 20"/>'),
    linkedin: icon('<rect x="4" y="9" width="4" height="11" rx=".4"/><path d="M6 4.5v.1M11 20V9h4v1.8c.9-1.3 4-1.7 5 1.5V20h-4v-6.2c0-1.7-2-1.8-2 0V20z"/>'),
    wechat: icon('<path d="M13.8 15.4c-1.2.7-2.7 1.1-4.3 1.1-.6 0-1.2-.1-1.8-.2L4 18l1.1-3C3.8 13.9 3 12.4 3 10.8 3 7.7 5.9 5.2 9.5 5.2c3.3 0 6 2 6.4 4.7"/><path d="M21 14.4c0 2.3-2.2 4.2-5 4.2-.5 0-.9 0-1.4-.2L12 19.7l.8-2.2c-1.1-.8-1.8-1.9-1.8-3.1 0-2.3 2.2-4.2 5-4.2s5 1.9 5 4.2z"/><circle cx="7" cy="9.5" r=".5"/><circle cx="11.5" cy="9.5" r=".5"/>'),
    redbook: icon('<path d="M5 5.5h14v13H5z"/><path d="M8 9h8M8 12h8M8 15h5"/>'),
    copy: icon('<rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>'),
    print: icon('<path d="M7 8V4h10v4M7 17H4v-7h16v7h-3M7 14h10v6H7z"/>')
  };

  const toolbar = document.createElement('div');
  toolbar.className = 'article-actions';
  toolbar.setAttribute('aria-label', 'Share and print this article');
  toolbar.innerHTML = `
    <span class="article-actions-label">Share</span>
    <button type="button" data-action="native">${icons.share}<span>Share</span></button>
    <a data-action="x" target="_blank" rel="noopener noreferrer" aria-label="Share on X">${icons.x}<span>X</span></a>
    <a data-action="linkedin" target="_blank" rel="noopener noreferrer" aria-label="Share on LinkedIn">${icons.linkedin}<span>LinkedIn</span></a>
    <button type="button" data-action="wechat">${icons.wechat}<span>微信</span></button>
    <button type="button" data-action="redbook">${icons.redbook}<span>小红书</span></button>
    <button type="button" data-action="copy">${icons.copy}<span>Copy link</span></button>
    <button type="button" data-action="print">${icons.print}<span>Print</span></button>
    <span class="article-action-status" role="status" aria-live="polite"></span>`;

  toolbar.querySelector('[data-action="x"]').href =
    `https://x.com/intent/tweet?text=${encodeURIComponent(articleTitle)}&url=${encodeURIComponent(canonicalUrl)}`;
  toolbar.querySelector('[data-action="linkedin"]').href =
    `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(canonicalUrl)}`;
  article.appendChild(toolbar);

  const printUrl = document.createElement('p');
  printUrl.className = 'article-print-url';
  printUrl.textContent = canonicalUrl;
  header?.appendChild(printUrl);

  const status = toolbar.querySelector('.article-action-status');
  let statusTimer;
  const announce = message => {
    status.textContent = message;
    toolbar.classList.add('has-status');
    clearTimeout(statusTimer);
    statusTimer = setTimeout(() => {
      status.textContent = '';
      toolbar.classList.remove('has-status');
    }, 3200);
  };
  const copyLink = async message => {
    try {
      await navigator.clipboard.writeText(canonicalUrl);
    } catch (_) {
      const field = document.createElement('textarea');
      field.value = canonicalUrl;
      field.setAttribute('readonly', '');
      field.style.position = 'fixed';
      field.style.opacity = '0';
      document.body.appendChild(field);
      field.select();
      document.execCommand('copy');
      field.remove();
    }
    announce(message);
  };
  const nativeShare = async fallbackMessage => {
    if (navigator.share) {
      try {
        await navigator.share({ title: articleTitle, text: shareText, url: canonicalUrl });
        return;
      } catch (error) {
        if (error?.name === 'AbortError') return;
      }
    }
    await copyLink(fallbackMessage);
  };

  toolbar.addEventListener('click', event => {
    const action = event.target.closest('[data-action]')?.dataset.action;
    if (!action || action === 'x' || action === 'linkedin') return;
    if (action === 'native') nativeShare('Link copied');
    if (action === 'wechat') nativeShare('链接已复制，请打开微信分享');
    if (action === 'redbook') nativeShare('链接已复制，请打开小红书分享');
    if (action === 'copy') copyLink('Link copied');
    if (action === 'print') window.print();
  });

  if (!toc || !list) return;

  const headings = Array.from(article.querySelectorAll('h2, h3'));
  let currentH2Item = null;
  let currentSubList = null;

  headings.forEach((heading, index) => {
    if (!heading.id) {
      const slug = heading.textContent
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '');
      heading.id = slug || `section-${index + 1}`;
    }

    const item = document.createElement('li');
    const link = document.createElement('a');
    link.href = `#${heading.id}`;
    link.textContent = heading.textContent;
    item.appendChild(link);

    if (heading.tagName === 'H2') {
      list.appendChild(item);
      currentH2Item = item;
      currentSubList = null;
    } else if (heading.tagName === 'H3' && currentH2Item) {
      if (!currentSubList) {
        currentSubList = document.createElement('ol');
        currentH2Item.appendChild(currentSubList);
      }
      currentSubList.appendChild(item);
    } else {
      list.appendChild(item);
    }
  });

  const tocHeadings = Array.from(article.querySelectorAll('h2, h3'));
  if (!tocHeadings.length) {
    toc.hidden = true;
    return;
  }

  const links = Array.from(list.querySelectorAll('a'));
  const activate = id => {
    links.forEach(link => {
      const active = link.hash === `#${id}`;
      link.classList.toggle('active', active);
      if (active) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  };

  let scheduled = false;
  const updateActive = () => {
    scheduled = false;
    let current = tocHeadings[0];
    tocHeadings.forEach(heading => {
      if (heading.getBoundingClientRect().top <= 190) current = heading;
    });
    activate(current.id);
  };

  links.forEach(link => {
    link.addEventListener('click', () => {
      const id = link.hash.slice(1);
      activate(id);
    });
  });
  window.addEventListener('scroll', () => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(updateActive);
  }, { passive: true });
  updateActive();
})();