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

/* ---------------------------------------------------------------- */
/* Quiz rendering helpers                                            */
/* ---------------------------------------------------------------- */
let quizCounter = 0;

function injectQuizStyles() {
    if (document.getElementById('quizInlineStyles')) return;
    const style = document.createElement('style');
    style.id = 'quizInlineStyles';
    style.textContent = `
        .quiz-wrapper { display: flex; flex-direction: column; gap: 1.5rem; }
        .quiz-score { font-weight: 600; margin-bottom: .5rem; }
        .quiz-question { padding: 1rem; border: 1px solid rgba(128,128,128,.25); border-radius: 8px; }
        .quiz-question-text { margin-bottom: .75rem; }
        .quiz-options { display: flex; flex-direction: column; gap: .5rem; }
        .quiz-option { display: flex; align-items: center; gap: .5rem; text-align: left; padding: .6rem .8rem; border: 1px solid rgba(128,128,128,.35); border-radius: 6px; background: transparent; cursor: pointer; font: inherit; width: 100%; }
        .quiz-option:hover:not(:disabled) { border-color: #6366f1; }
        .quiz-option:disabled { cursor: default; }
        .quiz-option-letter { font-weight: 700; opacity: .7; margin-right: .4rem; }
        .quiz-correct { background: rgba(34,197,94,.15); border-color: #22c55e !important; }
        .quiz-incorrect { background: rgba(239,68,68,.15); border-color: #ef4444 !important; }
        .quiz-explanation { margin-top: .6rem; padding: .6rem .8rem; border-radius: 6px; background: rgba(99,102,241,.08); font-size: .9rem; }
    `;
    document.head.appendChild(style);
}

function buildQuizHTML(data, quizId) {
    if (!data || !Array.isArray(data.questions) || data.questions.length === 0) {
        return null;
    }
    let html = '<div class="quiz-wrapper" id="' + quizId + '">';
    html += '<div class="quiz-score">Score: <span id="' + quizId + '-score-val">0</span> / ' + data.questions.length + '</div>';
    data.questions.forEach(function(q, qIndex) {
        html += '<div class="quiz-question" data-qindex="' + qIndex + '">';
        html += '<p class="quiz-question-text"><strong>Q' + (qIndex + 1) + '.</strong> ' + escapeHtml(q.question) + '</p>';
        html += '<div class="quiz-options">';
        (q.options || []).forEach(function(opt, oIndex) {
            const letter = String.fromCharCode(97 + oIndex);
            html += '<button type="button" class="quiz-option" data-oletter="' + letter + '">' +
                    '<span class="quiz-option-letter">' + letter.toUpperCase() + '.</span>' +
                    '<span class="quiz-option-text">' + escapeHtml(opt) + '</span>' +
                    '</button>';
        });
        html += '</div><div class="quiz-explanation" style="display:none;"></div></div>';
    });
    html += '</div>';
    return html;
}

function attachQuizHandlers(container, data, quizId) {
    let score = 0;
    const quizEl = container.querySelector('#' + quizId);
    if (!quizEl) return;
    quizEl.querySelectorAll('.quiz-question').forEach(function(qEl) {
        const qIndex = parseInt(qEl.getAttribute('data-qindex'), 10);
        const qData = data.questions[qIndex];
        const optionBtns = qEl.querySelectorAll('.quiz-option');
        optionBtns.forEach(function(btn) {
            btn.addEventListener('click', function() {
                if (qEl.classList.contains('answered')) return;
                qEl.classList.add('answered');
                const chosen = btn.getAttribute('data-oletter');
                const correct = qData.answer;
                optionBtns.forEach(function(b) {
                    b.disabled = true;
                    if (b.getAttribute('data-oletter') === correct) b.classList.add('quiz-correct');
                    else if (b === btn) b.classList.add('quiz-incorrect');
                });
                if (chosen === correct) score++;
                const scoreVal = document.getElementById(quizId + '-score-val');
                if (scoreVal) scoreVal.textContent = score;
                const explEl = qEl.querySelector('.quiz-explanation');
                if (explEl && qData.explanation) {
                    explEl.textContent = qData.explanation;
                    explEl.style.display = 'block';
                }
            });
        });
    });
}

function renderAIStudyResult(container, data) {
    let parsed = null;
    try {
        parsed = JSON.parse(data.result);
    } catch (e) {
        parsed = null;
    }
    if (parsed && Array.isArray(parsed.questions)) {
        injectQuizStyles();
        quizCounter++;
        const quizId = 'quiz-' + quizCounter;
        const quizHtml = buildQuizHTML(parsed, quizId);
        displayAIResult(container, quizHtml, data.job_id, data.tool_label);
        attachQuizHandlers(container, parsed, quizId);
    } else {
        let html;
        try {
            html = JSON.stringify(parsed, null, 2);
        } catch (e) {
            html = escapeHtml(data.result);
        }
        displayAIResult(container, html, data.job_id, data.tool_label);
    }
}
/* ---------------------------------------------------------------- */

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
                                renderAIStudyResult(container, data);
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