document.addEventListener('DOMContentLoaded', function() {
    setupDragAndDrop();
    setupMobileMenu();
    setupThemeToggle();
    setupFileList();
});

function setupDragAndDrop() {
    const dropZones = document.querySelectorAll('.upload-area');
    
    dropZones.forEach(zone => {
        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('dragover');
        });

        zone.addEventListener('dragleave', () => {
            zone.classList.remove('dragover');
        });

        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            const input = zone.querySelector('input[type="file"]');
            if (input) {
                input.files = e.dataTransfer.files;
                if (input.onchange) {
                    input.onchange();
                }
            }
        });
    });
}

function setupMobileMenu() {
    const toggle = document.querySelector('.mobile-menu-toggle');
    const navbar = document.querySelector('.navbar .container');
    if (toggle && navbar) {
        toggle.addEventListener('click', () => {
            navbar.classList.toggle('nav-open');
        });
    }
}

function setupThemeToggle() {
    const toggleBtn = document.getElementById('themeToggle');
    if (!toggleBtn) return;

    const root = document.documentElement;
    const savedTheme = localStorage.getItem('pdfmaster-theme') || 'light';

    function applyTheme(theme) {
        root.setAttribute('data-theme', theme);
        toggleBtn.textContent = theme === 'dark' ? '☀️' : '🌙';
        toggleBtn.setAttribute('aria-label', theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
        localStorage.setItem('pdfmaster-theme', theme);
    }

    // Respect system preference if the user has never chosen a theme
    let initialTheme = savedTheme;
    if (!localStorage.getItem('pdfmaster-theme')) {
        initialTheme = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    applyTheme(initialTheme);

    toggleBtn.addEventListener('click', () => {
        const current = root.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
        applyTheme(current === 'dark' ? 'light' : 'dark');
    });
}

function setupFileList() {
    const fileInputs = document.querySelectorAll('input[type="file"][multiple]');
    fileInputs.forEach(input => {
        input.addEventListener('change', () => {
            const fileListEl = document.getElementById('fileList');
            if (!fileListEl) return;
            fileListEl.innerHTML = '';
            for (const file of input.files) {
                const item = document.createElement('div');
                item.className = 'file-item';
                item.innerHTML = '<span class="file-name">' + escapeHtml(file.name) + '</span>' +
                                 '<span class="file-size">' + formatFileSize(file.size) + '</span>';
                fileListEl.appendChild(item);
            }
        });
    });
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function updateFileName(input) {
    const fileNameEl = document.getElementById('fileName');
    if (fileNameEl && input.files.length > 0) {
        fileNameEl.textContent = input.files[0].name;
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function updateHomeFileName(input) {
    const fileNameEl = document.getElementById('homeFileName');
    const selector = document.getElementById('actionSelector');
    if (fileNameEl && input.files.length > 0) {
        fileNameEl.textContent = input.files[0].name;
    }
    if (selector) {
        selector.style.display = input.files && input.files.length > 0 ? 'block' : 'none';
    }
}

function goToSelectedTool() {
    const select = document.getElementById('homeAction');
    if (!select || !select.value) {
        alert('Please select a tool.');
        return;
    }
    window.location.href = select.value;
}