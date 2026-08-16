function getCSRFToken() {
    const name = 'csrftoken';
    const cookies = document.cookie ? document.cookie.split(';') : [];
    for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.indexOf(name + '=') === 0) {
            return decodeURIComponent(cookie.substring(name.length + 1));
        }
    }
    const tokenEl = document.querySelector('[name=csrfmiddlewaretoken]');
    return tokenEl ? tokenEl.value : '';
}

function csrfFetch(url, options) {
    const defaults = {
        credentials: 'same-origin',
        headers: {},
    };
    const token = getCSRFToken();
    if (token) {
        defaults.headers['X-CSRFToken'] = token;
    }
    const opts = Object.assign({}, defaults, options);
    opts.headers = Object.assign({}, defaults.headers, options.headers || {});
    return fetch(url, opts);
}

function csrfPost(url, formData) {
    return csrfFetch(url, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        },
    });
}

function showLoadingSpinner(container) {
    const spinner = document.createElement('div');
    spinner.className = 'ai-spinner-overlay';
    spinner.id = 'aiSpinner';
    spinner.innerHTML = `
        <div class="ai-spinner-content">
            <div class="spinner"></div>
            <p class="ai-processing-text">AI is processing your PDF…</p>
            <p class="ai-processing-sub">This usually takes a few seconds.</p>
        </div>
    `;
    container.appendChild(spinner);
    return spinner;
}

function hideLoadingSpinner() {
    const spinner = document.getElementById('aiSpinner');
    if (spinner) spinner.remove();
}

function displayAIResult(container, html, jobId, toolLabel) {
    let resultDiv = document.getElementById('aiResultOutput');
    if (!resultDiv) {
        resultDiv = document.createElement('div');
        resultDiv.id = 'aiResultOutput';
        resultDiv.className = 'ai-result-box';
        resultDiv.innerHTML = `
            <div class="ai-result-header">
                <h3>Result</h3>
                <div class="ai-result-actions">
                    <button type="button" class="btn btn-outline btn-sm" onclick="copyResult()">Copy</button>
                    ${jobId ? `<a href="/ai-tools/request/${jobId}/" class="btn btn-outline btn-sm">View Full Result</a>` : ''}
                </div>
            </div>
            <div class="ai-result-content" id="aiResultContent"></div>
        `;
        container.appendChild(resultDiv);
    }
    const contentEl = document.getElementById('aiResultContent');
    if (contentEl) {
        contentEl.innerHTML = html;
    }
}

function displayAIError(container, message) {
    let errorDiv = document.getElementById('aiErrorBox');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.id = 'aiErrorBox';
        errorDiv.className = 'message message-error ajax-error';
        container.appendChild(errorDiv);
    }
    errorDiv.textContent = message;
}

function clearAIOutput() {
    const out = document.getElementById('aiResultOutput');
    const err = document.getElementById('aiErrorBox');
    if (out) out.remove();
    if (err) err.remove();
}

function copyResult() {
    const el = document.getElementById('aiResultContent');
    if (!el) return;
    const text = el.innerText || el.textContent;
    navigator.clipboard.writeText(text).then(function() {
        alert('Copied to clipboard!');
    });
}


document.addEventListener('DOMContentLoaded', function() {
    setupDragAndDrop();
    setupMobileMenu();
    setupThemeToggle();
    setupFileList();
    setupCSRF();
    setupAIStudyAjax();
    setupAIPDFToolAjax();
});

function setupCSRF() {
    const token = getCSRFToken();
    if (token) {
        document.addEventListener('readystatechange', function() {
            if (typeof jQuery !== 'undefined') {
                jQuery.defaults.headers['X-CSRFToken'] = token;
            }
        });
    }
}

function setupAIStudyAjax() {
    const forms = document.querySelectorAll('form#studyForm, form#quizForm, form#flashcardForm');
    forms.forEach(function(form) {
        const container = form.closest('.tool-container');
        if (!container) return;

        form.addEventListener('submit', function(e) {
            e.preventDefault();
            clearAIOutput();
            const spinner = showLoadingSpinner(container);

            const formData = new FormData(form);
            // Ensure the submit button is disabled during the request
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) submitBtn.disabled = true;

            csrfPost(window.location.href, formData)
                .then(function(resp) {
                    hideLoadingSpinner();
                    if (submitBtn) submitBtn.disabled = false;

                    if (resp.ok && resp.redirected) {
                        window.location.href = resp.url;
                        return;
                    }
                    if (resp.ok) {
                        return resp.json().then(function(data) {
                            if (data.result) {
                                let html;
                                try {
                                    const parsed = JSON.parse(data.result);
                                    html = JSON.stringify(parsed, null, 2);
                                } catch (e) {
                                    html = escapeHtml(data.result);
                                }
                                displayAIResult(container, html, data.job_id, data.tool_label);
                            }
                            return;
                        });
                    }
                    if (resp.status === 400 || resp.status === 502 || resp.status === 500) {
                        return resp.json().then(function(data) {
                            displayAIError(container, data.error || 'Something went wrong.');
                        });
                    }
                    displayAIError(container, 'Unexpected response from server.');
                })
                .catch(function(err) {
                    hideLoadingSpinner();
                    if (submitBtn) submitBtn.disabled = false;
                    displayAIError(container, 'Connection error: ' + err.message);
                });
        });
    });
}

function setupAIPDFToolAjax() {
    const forms = document.querySelectorAll('form#aiToolForm');
    forms.forEach(function(form) {
        const container = form.closest('.tool-container');
        if (!container) return;

        form.addEventListener('submit', function(e) {
            e.preventDefault();
            clearAIOutput();
            const spinner = showLoadingSpinner(container);

            const formData = new FormData(form);
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) submitBtn.disabled = true;

            csrfPost(window.location.href, formData)
                .then(function(resp) {
                    hideLoadingSpinner();
                    if (submitBtn) submitBtn.disabled = false;

                    if (resp.ok && resp.redirected) {
                        window.location.href = resp.url;
                        return;
                    }
                    if (resp.ok) {
                        return resp.json().then(function(data) {
                            if (data.result) {
                                let html;
                                try {
                                    const parsed = JSON.parse(data.result);
                                    html = JSON.stringify(parsed, null, 2);
                                } catch (e) {
                                    html = escapeHtml(data.result);
                                }
                                displayAIResult(container, html, data.job_id, data.tool_label);
                            }
                            return;
                        });
                    }
                    if (resp.status === 400 || resp.status === 502 || resp.status === 500) {
                        return resp.json().then(function(data) {
                            displayAIError(container, data.error || 'Something went wrong.');
                        });
                    }
                    displayAIError(container, 'Unexpected response from server.');
                })
                .catch(function(err) {
                    hideLoadingSpinner();
                    if (submitBtn) submitBtn.disabled = false;
                    displayAIError(container, 'Connection error: ' + err.message);
                });
        });
    });
}

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