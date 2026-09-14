/**
 * CatalogUI.js
 * Dynamic Map Selection Catalog Modal.
 * Renders real map cards from catalog.json without hardcoded map entries.
 */
class CatalogUI {
    constructor(onSelectMap) {
        this.onSelectMap = onSelectMap;
        this.modal = document.getElementById('map-catalog-modal');
        this.cardContainer = document.getElementById('catalog-cards-container');
        this.btnClose = document.getElementById('btn-close-modal');
        this.activeMapId = null;

        if (this.btnClose) {
            this.btnClose.addEventListener('click', () => this.hide());
        }
    }

    show() {
        this.modal.style.display = 'flex';
    }

    hide() {
        this.modal.style.display = 'none';
    }

    render(catalog, currentMapId) {
        this.activeMapId = currentMapId;
        this.cardContainer.innerHTML = '';

        if (!catalog || !catalog.maps || catalog.maps.length === 0) {
            this.cardContainer.innerHTML = '<p style="color:#8b949e;">No maps found in catalog.</p>';
            return;
        }

        catalog.maps.forEach(m => {
            const card = document.createElement('div');
            card.className = `map-card ${m.id === currentMapId ? 'active-map' : ''}`;

            const dims = m.bounds && m.bounds.extents
                ? `${m.bounds.extents[0].toFixed(2)}m × ${m.bounds.extents[1].toFixed(2)}m × ${m.bounds.extents[2].toFixed(2)}m`
                : '-';

            const tri = m.metrics ? m.metrics.render_triangles.toLocaleString() : '-';
            const colTri = m.metrics ? m.metrics.collision_triangles.toLocaleString() : '-';

            card.innerHTML = `
                <div class="card-title">${m.name || m.id}</div>
                <div class="card-stats">
                    <div><strong>Dimensions:</strong> ${dims}</div>
                    <div><strong>Render Triangles:</strong> ${tri}</div>
                    <div><strong>Collision Triangles:</strong> ${colTri}</div>
                    <div><strong>Walkable Ground:</strong> ${m.features.has_walkable ? 'Verified' : 'No'}</div>
                    <div><strong>AI Segmentation:</strong> ${m.features.has_ai_segmentation ? 'Active' : 'No'}</div>
                </div>
                <button class="btn btn-primary btn-select-map" data-map="${m.id}">
                    ${m.id === currentMapId ? 'Currently Exploring' : 'Explore Map'}
                </button>
            `;

            const btn = card.querySelector('.btn-select-map');
            btn.addEventListener('click', () => {
                this.hide();
                if (this.onSelectMap) {
                    this.onSelectMap(m.id);
                }
            });

            this.cardContainer.appendChild(card);
        });
    }
}

window.CatalogUI = CatalogUI;
