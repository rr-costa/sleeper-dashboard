import { loadPlayerStatus, initFindForPlayerTab, updateSearchSuggestions } from './ui.js';

function setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.dataset.tab;
            document.querySelectorAll('.tab-btn, .tab-content').forEach(el => el.classList.remove('active'));
            button.classList.add('active');
            document.getElementById(tabId).classList.add('active');
            if (tabId === 'find-player') {
                initFindForPlayerTab();
            } else if (tabId === 'status-player') {
                loadPlayerStatusWithToggle(); // Carrega com as configurações atuais do toggle
            }
        });
    });
}

function setupLogout() {
    const modal = document.getElementById('logout-modal');
    document.getElementById('logout-link').addEventListener('click', (e) => {
        e.preventDefault();
        modal.style.display = 'flex';
    });
    document.getElementById('cancel-logout').addEventListener('click', () => modal.style.display = 'none');
    document.getElementById('confirm-logout').addEventListener('click', () => window.location.href = '/logout');
}

function setupKofiModal() {
    const modal = document.getElementById('kofi-modal');
    const shouldShow = !localStorage.getItem('kofiModalDismissed');
    
    if (shouldShow) {
        modal.style.display = 'flex';
    }

    const close = () => {
        modal.style.display = 'none';
        localStorage.setItem('kofiModalDismissed', 'true');
    };

    document.getElementById('kofi-close').addEventListener('click', close);
    document.getElementById('kofi-support').addEventListener('click', () => {
        window.open('https://ko-fi.com/sleeperdashboard', '_blank');
        close();
    });
}

function setupBestBallToggle() {
    const bestballToggle = document.getElementById('bestball-toggle');
    if (bestballToggle) {
        bestballToggle.addEventListener('change', () => {
            loadPlayerStatusWithToggle();
        });
    }
}

function loadPlayerStatusWithToggle() {
    const bestballToggle = document.getElementById('bestball-toggle');
    const showBestBall = bestballToggle ? bestballToggle.checked : false;
    loadPlayerStatus(false, showBestBall);
}

function addEventListeners() {
    document.getElementById('reload-btn').addEventListener('click', () => {
        const bestballToggle = document.getElementById('bestball-toggle');
        const showBestBall = bestballToggle ? bestballToggle.checked : false;
        loadPlayerStatus(true, showBestBall);
    });
    
    document.getElementById('refresh-find-btn').addEventListener('click', initFindForPlayerTab);

    const searchInput = document.getElementById('player-search-input');
    searchInput.addEventListener('input', updateSearchSuggestions);
    searchInput.addEventListener('blur', () => {
        setTimeout(() => document.getElementById('search-suggestions').style.display = 'none', 200);
    });
}

async function initializeApp() {
    try {
        setupTabs();
        setupLogout();
        setupBestBallToggle(); // Configurar o toggle
        addEventListeners();
        
        await loadPlayerStatusWithToggle(); // Carrega a aba principal com as configurações do toggle
        
        document.getElementById('app-loading').style.display = 'none';
        document.getElementById('app-content').style.display = 'block';

        // O modal do Ko-fi só aparece depois que tudo carregou
        setupKofiModal();
    } catch (error) {
        console.error('Initialization error:', error);
        document.getElementById('app-loading').innerHTML = `
            <div class="error"><h3>Initialization Error</h3><p>${error.message}</p></div>`;
    }
}

// Inicia a aplicação
document.addEventListener('DOMContentLoaded', initializeApp);