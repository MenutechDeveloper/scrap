document.addEventListener('DOMContentLoaded', () => {
  const scraperForm = document.getElementById('scraperForm');
  const urlInput = document.getElementById('urlInput');
  const selectorInput = document.getElementById('selectorInput');
  const loader = document.getElementById('loader');
  const resultsSection = document.getElementById('resultsSection');
  const blocksGrid = document.getElementById('blocksGrid');
  const resTitle = document.getElementById('resTitle');
  const resUrl = document.getElementById('resUrl');
  const resCount = document.getElementById('resCount');
  const btnCopyAll = document.getElementById('btnCopyAll');
  const toast = document.getElementById('toast');
  const toastMsg = document.getElementById('toastMsg');

  let currentBlocks = [];

  function showToast(message) {
    toastMsg.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 3000);
  }

  function getTagClass(type) {
    switch(type) {
      case 'heading': return 'tag-heading';
      case 'paragraph': return 'tag-paragraph';
      case 'link': return 'tag-link';
      case 'image': return 'tag-image';
      case 'table': return 'tag-table';
      case 'custom': return 'tag-custom';
      default: return 'tag-paragraph';
    }
  }

  scraperForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    const selector = selectorInput.value.trim();
    const mode = document.querySelector('input[name="fetchMode"]:checked').value;

    if (!url) return;

    loader.style.display = 'block';
    resultsSection.style.display = 'none';
    blocksGrid.innerHTML = '';

    try {
      const response = await fetch('/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, selector, mode })
      });

      const data = await response.json();
      loader.style.display = 'none';

      if (data.status === 'success') {
        currentBlocks = data.blocks;
        resTitle.textContent = data.title || 'Resultados de Extracción';
        resUrl.textContent = data.url;
        resCount.textContent = data.total_blocks;

        renderBlocks(data.blocks);
        resultsSection.style.display = 'block';
        showToast(`¡Éxito! ${data.total_blocks} bloques extraídos.`);
      } else {
        alert('Error: ' + (data.message || 'No se pudo realizar el scraping.'));
      }
    } catch (err) {
      loader.style.display = 'none';
      alert('Error de conexión con el servidor: ' + err.message);
    }
  });

  function renderBlocks(blocks) {
    blocksGrid.innerHTML = '';

    if (blocks.length === 0) {
      blocksGrid.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 20px;">No se encontraron elementos con el criterio especificado.</p>';
      return;
    }

    blocks.forEach((block) => {
      const card = document.createElement('div');
      card.className = 'result-card';

      const tagClass = getTagClass(block.type);

      let mediaHtml = '';
      if (block.type === 'image' && block.img_src) {
        mediaHtml = `<div class="card-media"><img src="${block.img_src}" alt="Imagen extraída" loading="lazy" onerror="this.style.display='none'"></div>`;
      }

      let extraLinkHtml = '';
      if (block.link_url) {
        extraLinkHtml = `<div style="margin-top: 8px; font-size: 13px;"><a href="${block.link_url}" target="_blank" style="color: var(--accent-cyan); text-decoration: underline;">🔗 ${block.link_url}</a></div>`;
      }

      card.innerHTML = `
        <div class="card-top">
          <span class="card-tag ${tagClass}">#${block.id} • ${block.type}</span>
          <button class="btn-copy" data-id="${block.id}">
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
            </svg>
            Copiar Bloque
          </button>
        </div>
        <div style="font-size: 13px; font-weight: 600; color: var(--text-muted); margin-bottom: 6px;">${block.title}</div>
        <div class="card-content">${escapeHtml(block.content)}</div>
        ${mediaHtml}
        ${extraLinkHtml}
      `;

      const btnCopy = card.querySelector('.btn-copy');
      btnCopy.addEventListener('click', () => {
        let textToCopy = block.content;
        if (block.link_url) textToCopy += `\nLink: ${block.link_url}`;
        if (block.img_src) textToCopy += `\nImagen: ${block.img_src}`;

        navigator.clipboard.writeText(textToCopy).then(() => {
          showToast(`Bloque #${block.id} copiado al portapapeles`);
        });
      });

      blocksGrid.appendChild(card);
    });
  }

  btnCopyAll.addEventListener('click', () => {
    if (currentBlocks.length === 0) return;

    const fullText = currentBlocks.map(b => {
      let str = `[${b.id}] ${b.title.toUpperCase()}\n${b.content}`;
      if (b.link_url) str += `\nEnlace: ${b.link_url}`;
      if (b.img_src) str += `\nImagen: ${b.img_src}`;
      return str;
    }).join('\n\n----------------------------------------\n\n');

    navigator.clipboard.writeText(fullText).then(() => {
      showToast('¡Todos los bloques fueron copiados al portapapeles!');
    });
  });

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
