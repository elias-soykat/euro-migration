/**
 * BMET Clearance Card Directory — Application Script
 * European Migration Verification Portal (Year-Independent)
 */

(function () {
    'use strict';

    // Application State
    const state = {
        view: 'directory',            // 'directory' | 'explorer'
        selectedYear: 'all',          // 'all' | '2026' | '2027' | ...
        availableYears: [],
        currentYear: '',
        countries: [],
        currentCountry: null,
        cards: [],
        totalMatching: 0,
        page: 1,
        limit: 25,
        searchQuery: '',
        searchField: 'all',
        sortBy: 'serial_desc',
        viewMode: 'table',            // 'table' | 'grid'
        isLoadingCards: false,
        isCheckingNew: false,
        activeCardModal: null
    };

    // DOM Elements
    const elements = {
        // Nav & Global
        navHomeBtn: document.getElementById('navHomeBtn'),
        navViewAllBtn: document.getElementById('navViewAllBtn'),
        globalTotalCards: document.getElementById('globalTotalCards'),
        globalYearSelect: document.getElementById('globalYearSelect'),
        toastContainer: document.getElementById('toastContainer'),

        // View 1: Directory
        viewDirectory: document.getElementById('viewDirectory'),
        heroTotalCards: document.getElementById('heroTotalCards'),
        countrySearchInput: document.getElementById('countrySearchInput'),
        countriesGrid: document.getElementById('countriesGrid'),

        // View 2: Explorer
        viewCountryExplorer: document.getElementById('viewCountryExplorer'),
        explorerBackBtn: document.getElementById('explorerBackBtn'),
        explorerCountryBreadcrumb: document.getElementById('explorerCountryBreadcrumb'),
        explorerFlag: document.getElementById('explorerFlag'),
        explorerCode: document.getElementById('explorerCode'),
        explorerCountryName: document.getElementById('explorerCountryName'),
        explorerCardSummary: document.getElementById('explorerCardSummary'),
        checkNewCardsBtn: document.getElementById('checkNewCardsBtn'),
        syncIcon: document.getElementById('syncIcon'),
        checkNewBtnText: document.getElementById('checkNewBtnText'),
        updateStatusBanner: document.getElementById('updateStatusBanner'),
        statusBannerIcon: document.getElementById('statusBannerIcon'),
        statusBannerTitle: document.getElementById('statusBannerTitle'),
        statusBannerMsg: document.getElementById('statusBannerMsg'),
        statusDismissBtn: document.getElementById('statusDismissBtn'),

        // Explorer Toolbar
        cardSearchInput: document.getElementById('cardSearchInput'),
        clearSearchBtn: document.getElementById('clearSearchBtn'),
        filterFieldSelect: document.getElementById('filterFieldSelect'),
        explorerYearSelect: document.getElementById('explorerYearSelect'),
        sortBySelect: document.getElementById('sortBySelect'),
        viewTableBtn: document.getElementById('viewTableBtn'),
        viewGridBtn: document.getElementById('viewGridBtn'),
        pageLimitSelect: document.getElementById('pageLimitSelect'),
        resultsCountText: document.getElementById('resultsCountText'),
        activeQueryTag: document.getElementById('activeQueryTag'),

        // Display States
        cardsLoadingState: document.getElementById('cardsLoadingState'),
        cardsEmptyState: document.getElementById('cardsEmptyState'),
        emptyStateMsg: document.getElementById('emptyStateMsg'),
        resetSearchBtn: document.getElementById('resetSearchBtn'),
        cardsTableContainer: document.getElementById('cardsTableContainer'),
        cardsTableBody: document.getElementById('cardsTableBody'),
        cardsGridContainer: document.getElementById('cardsGridContainer'),
        paginationBar: document.getElementById('paginationBar'),
        paginationInfo: document.getElementById('paginationInfo'),
        paginationControls: document.getElementById('paginationControls'),

        // Modal
        cardDetailModal: document.getElementById('cardDetailModal'),
        modalCloseBtn: document.getElementById('modalCloseBtn'),
        modalFlag: document.getElementById('modalFlag'),
        modalTitle: document.getElementById('modalTitle'),
        modalEcNo: document.getElementById('modalEcNo'),
        modalAvatarIcon: document.getElementById('modalAvatarIcon'),
        modalCandidateName: document.getElementById('modalCandidateName'),
        modalEcDate: document.getElementById('modalEcDate'),
        modalCountryBadge: document.getElementById('modalCountryBadge'),
        modalClearanceGrid: document.getElementById('modalClearanceGrid'),
        modalAgencyGrid: document.getElementById('modalAgencyGrid'),
        modalVerifyUrlBtn: document.getElementById('modalVerifyUrlBtn')
    };

    // Helper: Format Number with commas
    function formatNum(num) {
        if (num === null || num === undefined) return '0';
        return Number(num).toLocaleString();
    }

    // Helpers: Derive country code, year, and candidate initials
    function getCardCountryCode(card) {
        if (card.country_code) return card.country_code;
        if (card.ec_no) {
            const parts = card.ec_no.split('-');
            if (parts.length >= 1 && parts[0]) return parts[0];
        }
        return state.currentCountry?.country_code || '';
    }

    function getCardYear(card) {
        if (card.year) return String(card.year);
        if (card.ec_no) {
            const parts = card.ec_no.split('-');
            if (parts.length >= 3 && parts[2]) return parts[2];
        }
        if (state.selectedYear && state.selectedYear !== 'all') return state.selectedYear;
        return state.currentYear || '';
    }

    function getCandidateInitials(name) {
        if (!name) return 'EC';
        const parts = name.trim().split(/\s+/).filter(Boolean);
        if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }

    // Helper: Toast Notifications
    function showToast(msg, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        const icon = type === 'success' ? '✅' : type === 'error' ? '⚠️' : 'ℹ️';
        toast.innerHTML = `<span class="toast-icon">${icon}</span><span class="toast-msg">${msg}</span>`;
        elements.toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // ==========================================================================
    // API Calls
    // ==========================================================================

    async function fetchYears() {
        try {
            const res = await fetch('/api/years');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            state.availableYears = data.available_years || [];
            state.currentYear = data.current_year || '';
            populateYearSelects();
        } catch (err) {
            console.error('Failed to load years:', err);
        }
    }

    function populateYearSelects() {
        const selects = [elements.globalYearSelect, elements.explorerYearSelect];
        selects.forEach(sel => {
            if (!sel) return;
            const currentVal = state.selectedYear;
            sel.innerHTML = '<option value="all">All Years</option>';
            state.availableYears.forEach(y => {
                const opt = document.createElement('option');
                opt.value = y;
                opt.textContent = `Year ${y}`;
                sel.appendChild(opt);
            });
            sel.value = currentVal;
        });
    }

    function onYearChanged(newYear) {
        state.selectedYear = newYear;
        if (elements.globalYearSelect) elements.globalYearSelect.value = newYear;
        if (elements.explorerYearSelect) elements.explorerYearSelect.value = newYear;

        if (state.view === 'directory') {
            fetchCountries();
        } else {
            state.page = 1;
            fetchCards();
            fetchCountries();
        }
    }

    async function fetchCountries() {
        try {
            const params = new URLSearchParams();
            if (state.selectedYear && state.selectedYear !== 'all') {
                params.append('year', state.selectedYear);
            }
            const queryStr = params.toString() ? `?${params.toString()}` : '';
            const res = await fetch(`/api/countries${queryStr}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            state.countries = data.countries || [];
            updateGlobalStats();
            renderCountriesGrid();
            if (state.currentCountry) {
                const updated = state.countries.find(c => c.country_code === state.currentCountry.country_code);
                if (updated) {
                    state.currentCountry = updated;
                    updateExplorerHeader();
                }
            }
        } catch (err) {
            console.error('Failed to load countries:', err);
            showToast('Failed to load countries data.', 'error');
        }
    }

    async function fetchCards() {
        if (!state.currentCountry) return;
        state.isLoadingCards = true;
        updateCardsDisplayVisibility();

        const params = new URLSearchParams({
            country: state.currentCountry.country_code,
            page: state.page,
            limit: state.limit,
            search: state.searchQuery,
            field: state.searchField,
            sort: state.sortBy
        });

        if (state.selectedYear && state.selectedYear !== 'all') {
            params.append('year', state.selectedYear);
        }

        try {
            const res = await fetch(`/api/cards?${params.toString()}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            state.cards = data.cards || [];
            state.totalMatching = data.total_matching || 0;
            state.page = data.page || 1;
            renderCards();
            renderPagination(data.total_pages || 1);
        } catch (err) {
            console.error('Failed to fetch cards:', err);
            showToast('Error loading cards from server.', 'error');
        } finally {
            state.isLoadingCards = false;
            updateCardsDisplayVisibility();
        }
    }

    async function checkForNewCards(countryCode, targetBtn = null) {
        if (state.isCheckingNew) return;
        state.isCheckingNew = true;

        if (targetBtn) {
            targetBtn.classList.add('loading');
            targetBtn.disabled = true;
        }
        elements.checkNewCardsBtn.classList.add('loading');
        elements.checkNewCardsBtn.disabled = true;
        elements.checkNewBtnText.textContent = 'Checking BMET Portal...';

        try {
            const targetYear = state.selectedYear && state.selectedYear !== 'all' ? state.selectedYear : 'auto';
            const res = await fetch('/api/check-new-cards', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    country_code: countryCode,
                    year: targetYear
                })
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            // Refresh country list & years to sync counts
            await fetchYears();
            await fetchCountries();

            if (state.currentCountry && state.currentCountry.country_code === countryCode) {
                const updated = state.countries.find(c => c.country_code === countryCode);
                if (updated) {
                    state.currentCountry = updated;
                    updateExplorerHeader();
                }

                // Show Status Banner
                elements.updateStatusBanner.classList.remove('hidden', 'success', 'info');
                if (data.new_cards_count > 0) {
                    elements.updateStatusBanner.classList.add('success');
                    elements.statusBannerIcon.textContent = '🎉';
                    elements.statusBannerTitle.textContent = 'New Cards Retrieved & Saved Permanently';
                    elements.statusBannerMsg.textContent = `${data.message} Stored in ${updated ? updated.output_file : 'JSON file'}. Latest confirmed serial: ${data.latest_serial_number}. Checked at ${data.check_time}.`;
                    showToast(`Found ${data.new_cards_count} new card(s) for ${data.country_name}!`, 'success');
                    state.page = 1;
                    fetchCards();
                } else {
                    elements.updateStatusBanner.classList.add('info');
                    elements.statusBannerIcon.textContent = 'ℹ️';
                    elements.statusBannerTitle.textContent = 'No New Cards';
                    elements.statusBannerMsg.textContent = 'No new cards found.';
                    showToast('No new cards found.', 'info');
                }
            } else {
                showToast(data.message, data.new_cards_count > 0 ? 'success' : 'info');
            }
        } catch (err) {
            console.error('Error checking new cards:', err);
            showToast(`Connection failed: ${err.message}`, 'error');
            if (state.currentCountry && state.currentCountry.country_code === countryCode) {
                elements.updateStatusBanner.classList.remove('hidden', 'success', 'info');
                elements.statusBannerIcon.textContent = '⚠️';
                elements.statusBannerTitle.textContent = 'Check Failed';
                elements.statusBannerMsg.textContent = `Could not reach BMET verification portal: ${err.message}`;
            }
        } finally {
            state.isCheckingNew = false;
            if (targetBtn) {
                targetBtn.classList.remove('loading');
                targetBtn.disabled = false;
            }
            elements.checkNewCardsBtn.classList.remove('loading');
            elements.checkNewCardsBtn.disabled = false;
            elements.checkNewBtnText.textContent = 'Check for New Cards';
        }
    }

    // ==========================================================================
    // Rendering: Directory View
    // ==========================================================================

    function updateGlobalStats() {
        const total = state.countries.reduce((acc, c) => acc + (c.total_valid_records || 0), 0);
        elements.globalTotalCards.textContent = formatNum(total);
        elements.heroTotalCards.textContent = formatNum(total);
    }

    function renderCountriesGrid() {
        const query = elements.countrySearchInput.value.trim().toLowerCase();
        const filtered = state.countries.filter(c => {
            return c.country_name.toLowerCase().includes(query) || c.country_code.toLowerCase().includes(query);
        });

        elements.countriesGrid.innerHTML = '';
        if (filtered.length === 0) {
            elements.countriesGrid.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1;">
                    <div class="empty-icon">🔍</div>
                    <h3>No Matching Destination</h3>
                    <p>No country matched "${query}".</p>
                </div>
            `;
            return;
        }

        filtered.forEach(c => {
            const card = document.createElement('div');
            card.className = 'country-card';
            card.innerHTML = `
                <div>
                    <div class="country-card-header">
                        <div class="country-identity">
                            <span class="country-flag-icon">${c.flag || '🌐'}</span>
                            <div>
                                <div class="country-name-text">${c.country_name}</div>
                                <span class="country-code-badge">${c.country_code}</span>
                            </div>
                        </div>
                    </div>

                    <div class="country-stat-box" style="margin-top: 1rem;">
                        <div class="country-stat-item">
                            <span class="stat-item-label">Total Verified</span>
                            <span class="stat-item-val highlight">${formatNum(c.total_valid_records)}</span>
                        </div>
                        <div class="country-stat-item">
                            <span class="stat-item-label">Latest Serial</span>
                            <span class="stat-item-val">${c.highest_confirmed_serial || '—'}</span>
                        </div>
                    </div>

                    <div class="country-latest-strip">
                        <div>Latest Card: <span class="latest-holder">${c.last_record_details?.candidate_name || 'N/A'}</span></div>
                        <div>Date: ${c.last_record_details?.ec_date || 'N/A'}</div>
                    </div>
                </div>

                <div class="country-card-actions">
                    <button class="btn btn-primary btn-open-dir" data-code="${c.country_code}">
                        <span>Browse Cards</span>
                        <span class="btn-icon">→</span>
                    </button>
                    <button class="btn btn-secondary btn-sm btn-quick-sync" data-code="${c.country_code}" title="Check BMET portal for newly issued cards">
                        <span class="sync-icon">🔄</span>
                        <span>Check New</span>
                    </button>
                </div>
            `;

            // Action: Browse directory
            card.querySelector('.btn-open-dir').addEventListener('click', (e) => {
                e.stopPropagation();
                openCountryExplorer(c.country_code);
            });

            // Action: Check for new cards
            const quickSyncBtn = card.querySelector('.btn-quick-sync');
            quickSyncBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                checkForNewCards(c.country_code, quickSyncBtn);
            });

            // Card click also opens directory
            card.addEventListener('click', () => {
                openCountryExplorer(c.country_code);
            });

            elements.countriesGrid.appendChild(card);
        });
    }

    // ==========================================================================
    // Rendering: Explorer View
    // ==========================================================================

    function openCountryExplorer(countryCode) {
        const country = state.countries.find(c => c.country_code === countryCode);
        if (!country) return;

        state.currentCountry = country;
        state.page = 1;
        state.searchQuery = '';
        state.searchField = 'all';
        elements.cardSearchInput.value = '';
        elements.filterFieldSelect.value = 'all';
        elements.clearSearchBtn.classList.add('hidden');
        elements.updateStatusBanner.classList.add('hidden');

        updateExplorerHeader();
        switchView('explorer');
        fetchCards();
    }

    function updateExplorerHeader() {
        const c = state.currentCountry;
        if (!c) return;

        elements.explorerCountryBreadcrumb.textContent = c.country_name;
        elements.explorerFlag.textContent = c.flag || '🌐';
        elements.explorerCode.textContent = c.country_code;
        elements.explorerCountryName.textContent = c.country_name;

        const yearLabel = state.selectedYear && state.selectedYear !== 'all'
            ? ` in ${state.selectedYear}`
            : ' across all years';

        elements.explorerCardSummary.textContent = `${formatNum(c.total_valid_records)} verified clearance cards issued${yearLabel} • Latest serial: ${c.highest_confirmed_serial || '—'}`;
    }

    function updateCardsDisplayVisibility() {
        if (state.isLoadingCards) {
            elements.cardsLoadingState.classList.remove('hidden');
            elements.cardsEmptyState.classList.add('hidden');
            elements.cardsTableContainer.classList.add('hidden');
            elements.cardsGridContainer.classList.add('hidden');
            elements.paginationBar.classList.add('hidden');
        } else if (state.cards.length === 0) {
            elements.cardsLoadingState.classList.add('hidden');
            elements.cardsEmptyState.classList.remove('hidden');
            elements.cardsTableContainer.classList.add('hidden');
            elements.cardsGridContainer.classList.add('hidden');
            elements.paginationBar.classList.add('hidden');
            elements.emptyStateMsg.textContent = state.searchQuery
                ? `No cards match "${state.searchQuery}". Try different keywords or reset filter.`
                : 'No cards available for this country.';
        } else {
            elements.cardsLoadingState.classList.add('hidden');
            elements.cardsEmptyState.classList.add('hidden');
            elements.paginationBar.classList.remove('hidden');

            if (state.viewMode === 'table') {
                elements.cardsTableContainer.classList.remove('hidden');
                elements.cardsGridContainer.classList.add('hidden');
            } else {
                elements.cardsTableContainer.classList.add('hidden');
                elements.cardsGridContainer.classList.remove('hidden');
            }
        }
    }

    function renderCards() {
        // Meta bar info
        const start = (state.page - 1) * state.limit + 1;
        const end = Math.min(state.page * state.limit, state.totalMatching);
        elements.resultsCountText.textContent = state.totalMatching > 0
            ? `Showing ${formatNum(start)} – ${formatNum(end)} of ${formatNum(state.totalMatching)} cards`
            : '0 cards found';

        if (state.searchQuery) {
            elements.activeQueryTag.textContent = `Filtered: "${state.searchQuery}" (${state.searchField})`;
            elements.activeQueryTag.classList.remove('hidden');
        } else {
            elements.activeQueryTag.classList.add('hidden');
        }

        // Render Table View
        elements.cardsTableBody.innerHTML = '';
        state.cards.forEach(card => {
            const tr = document.createElement('tr');
            const employer = card.employment?.employer || card.employer || '—';
            const agency = card.recruiting_agency || {};
            const agencyName = agency.name || '—';
            const agencyDetails = agency.license_no ? `${agencyName} (${agency.license_no})` : agencyName;
            const cardYear = getCardYear(card) || '—';

            tr.innerHTML = `
                <td>
                    <span class="sn-badge">${card.ec_no || card.serial_number}</span>
                </td>
                <td>
                    <span class="year-badge">${cardYear}</span>
                </td>
                <td class="candidate-name-cell">
                    ${card.candidate_name || '—'}
                </td>
                <td class="date-cell">
                    ${card.ec_date || '—'}
                </td>
                <td style="max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${employer}">
                    ${employer}
                </td>
                <td style="max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${agencyDetails}">
                    ${agencyDetails}
                </td>
                <td style="text-align: right;">
                    <button class="btn btn-secondary btn-sm btn-card-details" data-sn="${card.serial_number}">
                        View
                    </button>
                </td>
            `;

            tr.querySelector('.btn-card-details').addEventListener('click', () => openCardModal(card));
            tr.addEventListener('click', (e) => {
                if (!e.target.closest('button')) openCardModal(card);
            });
            tr.style.cursor = 'pointer';

            elements.cardsTableBody.appendChild(tr);
        });

        // Render Cards Grid View
        elements.cardsGridContainer.innerHTML = '';
        state.cards.forEach(card => {
            const item = document.createElement('div');
            item.className = 'card-item-box';
            const employer = card.employment?.employer || card.employer || '—';
            const agency = card.recruiting_agency || {};
            const agencyName = agency.name || '—';
            const agencyDetails = agency.license_no ? `${agencyName} (${agency.license_no})` : agencyName;
            const cardYear = getCardYear(card);
            const initials = getCandidateInitials(card.candidate_name);

            item.innerHTML = `
                <div class="card-item-top">
                    <div class="card-avatar-pill">${initials}</div>
                    <div class="card-item-main-info">
                        <div class="card-item-name" title="${card.candidate_name || ''}">${card.candidate_name || '—'}</div>
                        <div class="card-item-meta">
                            <div>
                                <span class="sn-badge" style="font-size: 0.72rem;">${card.ec_no || card.serial_number}</span>
                                ${cardYear ? `<span class="grid-year-badge">${cardYear}</span>` : ''}
                            </div>
                            <div>Date: <strong>${card.ec_date || '—'}</strong></div>
                        </div>
                    </div>
                </div>
                <div style="font-size: 0.8rem; color: var(--text-muted); border-top: 1px dashed var(--border-subtle); padding-top: 0.6rem; display: flex; flex-direction: column; gap: 0.25rem;">
                    <div>Employer: <strong style="color: var(--text-main);">${employer}</strong></div>
                    <div>Agency: <strong style="color: var(--text-main);">${agencyDetails}</strong></div>
                </div>
                <button class="btn btn-secondary btn-sm" style="width: 100%; margin-top: 0.25rem;">View Clearance Details</button>
            `;

            item.addEventListener('click', () => openCardModal(card));
            elements.cardsGridContainer.appendChild(item);
        });
    }

    function renderPagination(totalPages) {
        elements.paginationInfo.textContent = `Page ${state.page} of ${formatNum(totalPages)}`;
        elements.paginationControls.innerHTML = '';

        if (totalPages <= 1) return;

        // First & Prev Buttons
        const createBtn = (text, targetPage, disabled = false, isActive = false) => {
            const btn = document.createElement('button');
            btn.className = `page-btn ${isActive ? 'active' : ''}`;
            btn.textContent = text;
            btn.disabled = disabled;
            btn.addEventListener('click', () => {
                state.page = targetPage;
                fetchCards();
                window.scrollTo({ top: elements.countryHeaderCard ? elements.countryHeaderCard.offsetTop : 0, behavior: 'smooth' });
            });
            return btn;
        };

        // First
        elements.paginationControls.appendChild(createBtn('«', 1, state.page === 1));
        // Prev
        elements.paginationControls.appendChild(createBtn('‹', state.page - 1, state.page === 1));

        // Window of page numbers
        const maxButtons = 5;
        let startPage = Math.max(1, state.page - Math.floor(maxButtons / 2));
        let endPage = Math.min(totalPages, startPage + maxButtons - 1);
        if (endPage - startPage + 1 < maxButtons) {
            startPage = Math.max(1, endPage - maxButtons + 1);
        }

        for (let p = startPage; p <= endPage; p++) {
            elements.paginationControls.appendChild(createBtn(String(p), p, false, p === state.page));
        }

        // Next
        elements.paginationControls.appendChild(createBtn('›', state.page + 1, state.page === totalPages));
        // Last
        elements.paginationControls.appendChild(createBtn('»', totalPages, state.page === totalPages));
    }

    // ==========================================================================
    // Modal Details Rendering
    // ==========================================================================

    function renderDetailItem(label, val) {
        if (!val || val === 'null' || val === 'None') val = '—';
        return `
            <div class="detail-item">
                <span class="detail-label">${label}</span>
                <span class="detail-val">${val}</span>
            </div>
        `;
    }

    function openCardModal(card) {
        state.activeCardModal = card;

        const code = getCardCountryCode(card);
        const cardYear = getCardYear(card);
        const meta = state.countries.find(c => c.country_code === code) || state.currentCountry;
        const cName = meta?.country_name || code || 'Europe';

        // Modal Flag & Title
        elements.modalFlag.textContent = meta?.flag || '🌐';
        elements.modalTitle.textContent = `${cName} Emigration Clearance`;
        elements.modalEcNo.textContent = card.ec_no || `${code}-I-${cardYear}-${card.serial_number}`;

        // Header Info
        if (elements.modalAvatarIcon) {
            elements.modalAvatarIcon.textContent = getCandidateInitials(card.candidate_name);
        }
        elements.modalCandidateName.textContent = card.candidate_name || 'N/A';
        elements.modalEcDate.textContent = `EC Date: ${card.ec_date || 'N/A'}`;
        elements.modalCountryBadge.textContent = `${meta?.flag || '🌐'} ${cName}${cardYear ? ` • Year ${cardYear}` : ''}`;

        // Section 1: Clearance Details
        const emp = card.employment || {};
        const employer = emp.employer || card.employer || '—';

        elements.modalClearanceGrid.innerHTML = `
            ${renderDetailItem('Candidate Name', card.candidate_name)}
            ${renderDetailItem('Destination Country', `${cName} (${code})`)}
            ${renderDetailItem('Serial Number', card.serial_number)}
            ${renderDetailItem('Issuance Year', cardYear || '—')}
            ${renderDetailItem('EC No', card.ec_no)}
            ${renderDetailItem('EC Date', card.ec_date)}
            ${renderDetailItem('Employer', employer)}
        `;

        // Section 2: Recruiting Agency
        const ra = card.recruiting_agency || {};
        elements.modalAgencyGrid.innerHTML = `
            ${renderDetailItem('Agency Name', ra.name)}
            ${renderDetailItem('RL License No', ra.license_no)}
            ${renderDetailItem('Contact Phone', ra.phone)}
        `;

        // Official Verify URL
        const verifyUrl = card.verification_url || `https://raims.oep.gov.bd/ec-card/verify/${code}-I-${cardYear}-${card.serial_number}`;
        elements.modalVerifyUrlBtn.href = verifyUrl;

        elements.cardDetailModal.classList.remove('hidden');
    }

    function closeCardModal() {
        elements.cardDetailModal.classList.add('hidden');
        state.activeCardModal = null;
    }

    // ==========================================================================
    // View Switcher & Event Listeners
    // ==========================================================================

    function switchView(viewName) {
        state.view = viewName;
        if (viewName === 'directory') {
            elements.viewDirectory.classList.add('active');
            elements.viewCountryExplorer.classList.remove('active');
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } else {
            elements.viewDirectory.classList.remove('active');
            elements.viewCountryExplorer.classList.add('active');
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    }

    // Debounce helper
    function debounce(func, wait) {
        let timeout;
        return function (...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    // Setup Listeners
    function setupEventListeners() {
        // Nav actions
        elements.navHomeBtn.addEventListener('click', () => switchView('directory'));
        elements.navViewAllBtn.addEventListener('click', () => switchView('directory'));
        elements.explorerBackBtn.addEventListener('click', () => switchView('directory'));

        // Global and Explorer Year Select
        if (elements.globalYearSelect) {
            elements.globalYearSelect.addEventListener('change', (e) => onYearChanged(e.target.value));
        }
        if (elements.explorerYearSelect) {
            elements.explorerYearSelect.addEventListener('change', (e) => onYearChanged(e.target.value));
        }

        // Country search in directory
        elements.countrySearchInput.addEventListener('input', renderCountriesGrid);

        // Check for new cards in explorer
        elements.checkNewCardsBtn.addEventListener('click', () => {
            if (state.currentCountry) {
                checkForNewCards(state.currentCountry.country_code);
            }
        });

        elements.statusDismissBtn.addEventListener('click', () => {
            elements.updateStatusBanner.classList.add('hidden');
        });

        // Search in Explorer
        const debouncedSearch = debounce(() => {
            state.page = 1;
            fetchCards();
        }, 280);

        elements.cardSearchInput.addEventListener('input', (e) => {
            state.searchQuery = e.target.value.trim();
            elements.clearSearchBtn.classList.toggle('hidden', !state.searchQuery);
            debouncedSearch();
        });

        elements.clearSearchBtn.addEventListener('click', () => {
            elements.cardSearchInput.value = '';
            state.searchQuery = '';
            elements.clearSearchBtn.classList.add('hidden');
            state.page = 1;
            fetchCards();
        });

        elements.resetSearchBtn.addEventListener('click', () => {
            elements.cardSearchInput.value = '';
            state.searchQuery = '';
            elements.clearSearchBtn.classList.add('hidden');
            state.page = 1;
            fetchCards();
        });

        // Field filter
        elements.filterFieldSelect.addEventListener('change', (e) => {
            state.searchField = e.target.value;
            if (state.searchQuery) {
                state.page = 1;
                fetchCards();
            }
        });

        // Sort by
        elements.sortBySelect.addEventListener('change', (e) => {
            state.sortBy = e.target.value;
            state.page = 1;
            fetchCards();
        });

        // Page limit
        elements.pageLimitSelect.addEventListener('change', (e) => {
            state.limit = parseInt(e.target.value, 10);
            state.page = 1;
            fetchCards();
        });

        // View toggle
        elements.viewTableBtn.addEventListener('click', () => {
            state.viewMode = 'table';
            elements.viewTableBtn.classList.add('active');
            elements.viewGridBtn.classList.remove('active');
            updateCardsDisplayVisibility();
        });

        elements.viewGridBtn.addEventListener('click', () => {
            state.viewMode = 'grid';
            elements.viewGridBtn.classList.add('active');
            elements.viewTableBtn.classList.remove('active');
            updateCardsDisplayVisibility();
        });

        // Modal actions
        elements.modalCloseBtn.addEventListener('click', closeCardModal);

        elements.cardDetailModal.addEventListener('click', (e) => {
            if (e.target === elements.cardDetailModal) {
                closeCardModal();
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !elements.cardDetailModal.classList.contains('hidden')) {
                closeCardModal();
            }
        });
    }

    // Initialization
    async function init() {
        setupEventListeners();
        await fetchYears();
        await fetchCountries();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
