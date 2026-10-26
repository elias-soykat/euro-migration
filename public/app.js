/**
 * BMET Clearance Card Directory — Application Script
 * European Migration 2026
 */

(function () {
    'use strict';

    // Application State
    const state = {
        view: 'directory',            // 'directory' | 'explorer'
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
        modalPhoto: document.getElementById('modalPhoto'),
        modalCandidateName: document.getElementById('modalCandidateName'),
        modalEcDate: document.getElementById('modalEcDate'),
        modalCountryBadge: document.getElementById('modalCountryBadge'),
        modalClearanceGrid: document.getElementById('modalClearanceGrid'),
        modalAgencyGrid: document.getElementById('modalAgencyGrid'),
        modalBmetGrid: document.getElementById('modalBmetGrid'),
        modalAddressGrid: document.getElementById('modalAddressGrid'),
        modalEmergencyGrid: document.getElementById('modalEmergencyGrid'),
        modalVerifyUrlBtn: document.getElementById('modalVerifyUrlBtn'),
        modalCopyUrlBtn: document.getElementById('modalCopyUrlBtn'),
        modalDownloadJsonBtn: document.getElementById('modalDownloadJsonBtn')
    };

    // Helper: Format Number with commas
    function formatNum(num) {
        if (num === null || num === undefined) return '0';
        return Number(num).toLocaleString();
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

    async function fetchCountries() {
        try {
            const res = await fetch('/api/countries');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            state.countries = data.countries || [];
            updateGlobalStats();
            renderCountriesGrid();
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
            const res = await fetch('/api/check-new-cards', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ country_code: countryCode })
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            // Refresh country list to sync counts
            await fetchCountries();

            if (state.currentCountry && state.currentCountry.country_code === countryCode) {
                // Update local country reference
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
                    // Reset to first page & re-fetch to view new cards immediately
                    state.page = 1;
                    fetchCards();
                } else {
                    elements.updateStatusBanner.classList.add('info');
                    elements.statusBannerIcon.textContent = 'ℹ️';
                    elements.statusBannerTitle.textContent = 'No New Cards Available';
                    elements.statusBannerMsg.textContent = `${data.message} Verified up to serial ${data.latest_serial_number}. Checked at ${data.check_time}.`;
                    showToast(data.message, 'info');
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
        elements.explorerCardSummary.textContent = `${formatNum(c.total_valid_records)} verified clearance cards issued in 2026 • Latest serial: ${c.highest_confirmed_serial || '—'}`;
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
            const photoUrl = card.photo_url || '';
            const passportNo = card.passport?.passport_no || card.emigration_clearance?.['Passport No'] || '—';
            const visaNo = card.visa?.visa_no || card.emigration_clearance?.['Visa No'] || '—';
            const employer = card.employment?.employer || card.emigration_clearance?.['Employer'] || '—';
            const agencyName = card.recruiting_agency?.name || card.recruiting_agency?.Name || '—';

            tr.innerHTML = `
                <td>
                    <img src="${photoUrl}" class="table-photo-thumb" alt="Photo" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'42\\' height=\\'48\\' viewBox=\\'0 0 24 24\\' fill=\\'%2364748b\\'><path d=\\'M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z\\'/></svg>'">
                </td>
                <td>
                    <span class="sn-badge">${card.ec_no || card.serial_number}</span>
                </td>
                <td class="candidate-name-cell">
                    ${card.candidate_name || '—'}
                </td>
                <td class="passport-cell">
                    ${passportNo}
                </td>
                <td class="date-cell">
                    ${card.ec_date || '—'}
                </td>
                <td style="font-family: var(--font-mono); font-size: 0.8rem;">
                    ${visaNo}
                </td>
                <td style="max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${employer}">
                    ${employer}
                </td>
                <td style="max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${agencyName}">
                    ${agencyName}
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
            const photoUrl = card.photo_url || '';
            const passportNo = card.passport?.passport_no || card.emigration_clearance?.['Passport No'] || '—';
            const employer = card.employment?.employer || card.emigration_clearance?.['Employer'] || '—';

            item.innerHTML = `
                <div class="card-item-top">
                    <img src="${photoUrl}" class="card-item-photo" alt="Photo" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'55\\' height=\\'65\\' viewBox=\\'0 0 24 24\\' fill=\\'%2364748b\\'><path d=\\'M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z\\'/></svg>'">
                    <div class="card-item-main-info">
                        <div class="card-item-name" title="${card.candidate_name || ''}">${card.candidate_name || '—'}</div>
                        <div class="card-item-meta">
                            <div><span class="sn-badge" style="font-size: 0.72rem;">${card.ec_no || card.serial_number}</span></div>
                            <div>Passport: <strong>${passportNo}</strong></div>
                            <div>Date: ${card.ec_date || '—'}</div>
                        </div>
                    </div>
                </div>
                <div style="font-size: 0.78rem; color: var(--text-muted); border-top: 1px dashed var(--border-subtle); padding-top: 0.5rem;">
                    <div>Employer: <strong>${employer}</strong></div>
                </div>
                <button class="btn btn-secondary btn-sm" style="width: 100%;">View Clearance Details</button>
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

        elements.paginationControls.appendChild(createBtn('«', 1, state.page === 1));
        elements.paginationControls.appendChild(createBtn('‹', state.page - 1, state.page === 1));

        // Window of numbers
        let startPage = Math.max(1, state.page - 2);
        let endPage = Math.min(totalPages, state.page + 2);
        if (state.page <= 3) endPage = Math.min(5, totalPages);
        if (state.page >= totalPages - 2) startPage = Math.max(1, totalPages - 4);

        for (let p = startPage; p <= endPage; p++) {
            elements.paginationControls.appendChild(createBtn(p, p, false, p === state.page));
        }

        elements.paginationControls.appendChild(createBtn('›', state.page + 1, state.page === totalPages));
        elements.paginationControls.appendChild(createBtn('»', totalPages, state.page === totalPages));
    }

    // ==========================================================================
    // Card Detail Modal
    // ==========================================================================

    function openCardModal(card) {
        state.activeCardModal = card;
        const pass = card.passport || {};
        const visa = card.visa || {};
        const emp = card.employment || {};
        const agency = card.recruiting_agency || {};
        const addr = card.permanent_address || {};
        const emergency = card.emergency_contact || {};

        // Fallbacks for legacy fields if ever present
        const cl = card.emigration_clearance || {};
        const bm = card.bmet_registration || {};

        const passportNo = pass.passport_no || cl['Passport No'] || '—';
        const passIssue = pass.issue_date || cl['Passport Issue Date'] || '—';
        const passExpire = pass.expire_date || cl['Passport Expire Date'] || '—';
        const prevPassports = pass.previous_passports || [];

        const visaNo = visa.visa_no || cl['Visa No'] || '—';
        const visaIssue = visa.issue_date || cl['Visa Issue Date'] || '—';
        const visaExpire = visa.expire_date || cl['Visa Expire Date'] || '—';

        const employer = emp.employer || cl['Employer'] || '—';
        const referralNo = emp.referral_no || cl['Referral No'] || '—';

        const birthDate = card.birth_date || cl['Birth Date'] || bm['Birth Date'] || '—';
        const bloodGroup = card.blood_group || cl['Blood Group'] || '—';
        const gender = card.gender || bm['Gender'] || '—';
        const nid = card.nid || bm['NID'] || '—';
        const bmetNo = card.bmet_no || bm['BMET No'] || '—';

        const agencyName = agency.name || agency.Name || 'Direct / None';
        const agencyLic = agency.license_no || agency['License No'] || '—';
        const agencyPhone = agency.phone || agency['Phone'] || '—';

        const houseRoad = addr.house_vill_road || addr['House/Vill/Road'] || '—';
        const postOffice = addr.post_office || addr['Post Office'] || '—';
        const policeStation = addr.police_station || addr['Police Station'] || '—';
        const upazila = addr.upazila || addr['Upazila'] || '—';
        const district = addr.district || addr['District'] || '—';
        const division = addr.division || addr['Division'] || '—';

        const emgName = emergency.name || emergency.Name || '—';
        const emgRel = emergency.relation || emergency.Relation || '—';
        const emgMob = emergency.mobile || emergency.Mobile || '—';
        const emgAddr = emergency.address || emergency.Address || '—';

        elements.modalFlag.textContent = state.currentCountry?.flag || '🇪🇺';
        elements.modalTitle.textContent = `${state.currentCountry?.country_name || card.country} Clearance Record`;
        elements.modalEcNo.textContent = card.ec_no || `Serial #${card.serial_number}`;
        elements.modalPhoto.src = card.photo_url || '';
        elements.modalCandidateName.textContent = card.candidate_name || 'N/A';
        elements.modalEcDate.textContent = `EC Date: ${card.ec_date || 'N/A'}`;
        elements.modalCountryBadge.textContent = card.country || state.currentCountry?.country_name || 'Europe';

        // Prev passports snippet
        let prevPassportsHtml = '';
        if (prevPassports && prevPassports.length > 0) {
            prevPassportsHtml = `<div class="grid-field-row" style="grid-column: 1 / -1;"><span class="field-label">Prior Registered Passports:</span><span class="field-val" style="color: #0284c7;">${prevPassports.join(', ')}</span></div>`;
        }

        // Section 1: Clearance & Passport & Visa
        elements.modalClearanceGrid.innerHTML = `
            <div class="grid-field-row"><span class="field-label">Passport No:</span><span class="field-val"><strong>${passportNo}</strong></span></div>
            <div class="grid-field-row"><span class="field-label">Birth Date:</span><span class="field-val">${birthDate}</span></div>
            <div class="grid-field-row"><span class="field-label">Passport Issue:</span><span class="field-val">${passIssue}</span></div>
            <div class="grid-field-row"><span class="field-label">Passport Expire:</span><span class="field-val">${passExpire}</span></div>
            ${prevPassportsHtml}
            <div class="grid-field-row"><span class="field-label">Visa No:</span><span class="field-val">${visaNo}</span></div>
            <div class="grid-field-row"><span class="field-label">Blood Group:</span><span class="field-val">${bloodGroup}</span></div>
            <div class="grid-field-row"><span class="field-label">Visa Issue Date:</span><span class="field-val">${visaIssue}</span></div>
            <div class="grid-field-row"><span class="field-label">Visa Expire Date:</span><span class="field-val">${visaExpire}</span></div>
            <div class="grid-field-row" style="grid-column: 1 / -1;"><span class="field-label">Employer:</span><span class="field-val">${employer}</span></div>
            <div class="grid-field-row"><span class="field-label">Destination Country:</span><span class="field-val">${card.country}</span></div>
            <div class="grid-field-row"><span class="field-label">Referral No:</span><span class="field-val">${referralNo}</span></div>
        `;

        // Section 2: Recruiting Agency
        elements.modalAgencyGrid.innerHTML = `
            <div class="grid-field-row"><span class="field-label">Agency Name:</span><span class="field-val">${agencyName}</span></div>
            <div class="grid-field-row"><span class="field-label">License No:</span><span class="field-val">${agencyLic}</span></div>
            <div class="grid-field-row" style="grid-column: 1 / -1;"><span class="field-label">Contact Phone:</span><span class="field-val">${agencyPhone}</span></div>
        `;

        // Section 3: BMET Registration
        elements.modalBmetGrid.innerHTML = `
            <div class="grid-field-row"><span class="field-label">BMET Reg No:</span><span class="field-val">${bmetNo}</span></div>
            <div class="grid-field-row"><span class="field-label">NID:</span><span class="field-val">${nid}</span></div>
            <div class="grid-field-row"><span class="field-label">Gender:</span><span class="field-val">${gender}</span></div>
            <div class="grid-field-row"><span class="field-label">Birth Date:</span><span class="field-val">${birthDate}</span></div>
        `;

        // Section 4: Address
        elements.modalAddressGrid.innerHTML = `
            <div class="grid-field-row"><span class="field-label">House/Village/Road:</span><span class="field-val">${houseRoad}</span></div>
            <div class="grid-field-row"><span class="field-label">Post Office:</span><span class="field-val">${postOffice}</span></div>
            <div class="grid-field-row"><span class="field-label">Police Station:</span><span class="field-val">${policeStation}</span></div>
            <div class="grid-field-row"><span class="field-label">District:</span><span class="field-val">${district}</span></div>
            <div class="grid-field-row" style="grid-column: 1 / -1;"><span class="field-label">Division:</span><span class="field-val">${division}</span></div>
        `;

        // Section 5: Emergency Contact
        elements.modalEmergencyGrid.innerHTML = `
            <div class="grid-field-row"><span class="field-label">Contact Name:</span><span class="field-val">${emgName}</span></div>
            <div class="grid-field-row"><span class="field-label">Relation:</span><span class="field-val">${emgRel}</span></div>
            <div class="grid-field-row"><span class="field-label">Mobile:</span><span class="field-val">${emgMob}</span></div>
            <div class="grid-field-row"><span class="field-label">Address:</span><span class="field-val">${emgAddr}</span></div>
        `;

        // Official Verify URL
        const verifyUrl = card.verification_url || `https://raims.oep.gov.bd/ec-card/verify/${card.country_code}-I-2026-${card.serial_number}`;
        elements.modalVerifyUrlBtn.href = verifyUrl;

        elements.cardDetailModal.classList.remove('hidden');
    }

    function closeCardModal() {
        elements.cardDetailModal.classList.add('hidden');
        state.activeCardModal = null;
    }

    function copyVerificationUrl() {
        if (!state.activeCardModal) return;
        const url = state.activeCardModal.verification_url;
        navigator.clipboard.writeText(url).then(() => {
            showToast('Verification URL copied to clipboard!', 'success');
        }).catch(() => {
            showToast('Failed to copy URL.', 'error');
        });
    }

    function downloadCardJson() {
        if (!state.activeCardModal) return;
        const card = state.activeCardModal;
        const filename = `bmet_${card.country_code}_${card.serial_number}.json`;
        const blob = new Blob([JSON.stringify(card, null, 2)], { type: 'application/json' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
        URL.revokeObjectURL(a.href);
        showToast(`Saved ${filename}`, 'success');
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
        elements.modalCopyUrlBtn.addEventListener('click', copyVerificationUrl);
        elements.modalDownloadJsonBtn.addEventListener('click', downloadCardJson);

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
    function init() {
        setupEventListeners();
        fetchCountries();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
