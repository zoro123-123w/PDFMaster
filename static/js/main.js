document.addEventListener('DOMContentLoaded', function() {
    setupDragAndDrop();
    setupMobileMenu();
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
    if (toggle) {
        toggle.addEventListener('click', () => {
            alert('Mobile menu - implement as needed');
        });
    }
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