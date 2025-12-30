/**
 * Translucent Toast Notification System
 * A modern, glassmorphism-styled toast notification system
 */

(function () {
    'use strict';

    // Toast container management
    let toastContainer = null;

    function getToastContainer() {
        if (!toastContainer) {
            toastContainer = document.getElementById('toast-container');
            if (!toastContainer) {
                toastContainer = document.createElement('div');
                toastContainer.id = 'toast-container';
                toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
                toastContainer.style.zIndex = '9999';
                document.body.appendChild(toastContainer);
            }
        }
        return toastContainer;
    }

    // Toast types with their colors and icons
    const toastTypes = {
        success: {
            icon: 'bi-check-circle-fill',
            bgClass: 'toast-success',
            gradient: 'linear-gradient(135deg, rgba(34, 197, 94, 0.9), rgba(22, 163, 74, 0.85))'
        },
        error: {
            icon: 'bi-x-circle-fill',
            bgClass: 'toast-error',
            gradient: 'linear-gradient(135deg, rgba(239, 68, 68, 0.9), rgba(220, 38, 38, 0.85))'
        },
        warning: {
            icon: 'bi-exclamation-triangle-fill',
            bgClass: 'toast-warning',
            gradient: 'linear-gradient(135deg, rgba(245, 158, 11, 0.9), rgba(217, 119, 6, 0.85))'
        },
        info: {
            icon: 'bi-info-circle-fill',
            bgClass: 'toast-info',
            gradient: 'linear-gradient(135deg, rgba(59, 130, 246, 0.9), rgba(37, 99, 235, 0.85))'
        }
    };

    /**
     * Show a toast notification
     * @param {string} message - The message to display
     * @param {string} type - Type of toast: 'success', 'error', 'warning', 'info'
     * @param {object} options - Additional options
     */
    function showToast(message, type = 'info', options = {}) {
        const config = {
            duration: options.duration || 4000,
            title: options.title || getDefaultTitle(type),
            dismissible: options.dismissible !== false
        };

        const typeConfig = toastTypes[type] || toastTypes.info;
        const container = getToastContainer();

        const toastEl = document.createElement('div');
        toastEl.className = 'toast-notification';
        toastEl.style.background = typeConfig.gradient;

        toastEl.innerHTML = `
            <div class="toast-content">
                <div class="toast-icon">
                    <i class="bi ${typeConfig.icon}"></i>
                </div>
                <div class="toast-body">
                    <div class="toast-title">${config.title}</div>
                    <div class="toast-message">${message}</div>
                </div>
                ${config.dismissible ? '<button class="toast-close" aria-label="Close"><i class="bi bi-x-lg"></i></button>' : ''}
            </div>
            <div class="toast-progress">
                <div class="toast-progress-bar" style="animation-duration: ${config.duration}ms"></div>
            </div>
        `;

        container.appendChild(toastEl);

        // Trigger entrance animation
        requestAnimationFrame(() => {
            toastEl.classList.add('toast-show');
        });

        // Close button handler
        const closeBtn = toastEl.querySelector('.toast-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => dismissToast(toastEl));
        }

        // Auto dismiss
        const dismissTimeout = setTimeout(() => {
            dismissToast(toastEl);
        }, config.duration);

        // Store timeout for cleanup
        toastEl._dismissTimeout = dismissTimeout;

        return toastEl;
    }

    function dismissToast(toastEl) {
        if (toastEl._dismissed) return;
        toastEl._dismissed = true;

        if (toastEl._dismissTimeout) {
            clearTimeout(toastEl._dismissTimeout);
        }

        toastEl.classList.add('toast-hide');
        toastEl.addEventListener('animationend', () => {
            toastEl.remove();
        });
    }

    function getDefaultTitle(type) {
        const titles = {
            success: 'Success',
            error: 'Error',
            warning: 'Warning',
            info: 'Info'
        };
        return titles[type] || 'Notification';
    }

    /**
     * Show a confirmation dialog (replaces browser confirm())
     * @param {string} message - The confirmation message
     * @param {object} options - Additional options
     * @returns {Promise<boolean>} - Resolves to true if confirmed, false if cancelled
     */
    function showConfirm(message, options = {}) {
        return new Promise((resolve) => {
            const config = {
                title: options.title || 'Confirm Action',
                confirmText: options.confirmText || 'Confirm',
                cancelText: options.cancelText || 'Cancel',
                type: options.type || 'warning'
            };

            const typeConfig = toastTypes[config.type] || toastTypes.warning;

            // Create overlay
            const overlay = document.createElement('div');
            overlay.className = 'toast-confirm-overlay';

            overlay.innerHTML = `
                <div class="toast-confirm-dialog">
                    <div class="toast-confirm-header" style="background: ${typeConfig.gradient}">
                        <i class="bi ${typeConfig.icon}"></i>
                        <span>${config.title}</span>
                    </div>
                    <div class="toast-confirm-body">
                        <p>${message}</p>
                    </div>
                    <div class="toast-confirm-footer">
                        <button class="toast-btn toast-btn-cancel">${config.cancelText}</button>
                        <button class="toast-btn toast-btn-confirm">${config.confirmText}</button>
                    </div>
                </div>
            `;

            document.body.appendChild(overlay);

            // Trigger entrance animation
            requestAnimationFrame(() => {
                overlay.classList.add('toast-confirm-show');
            });

            // Define escape handler first (before closeDialog references it)
            const escHandler = (e) => {
                if (e.key === 'Escape') {
                    closeDialog(false);
                }
            };
            document.addEventListener('keydown', escHandler);

            const closeDialog = (result) => {
                // Prevent multiple closes
                if (overlay._closed) return;
                overlay._closed = true;

                overlay.classList.add('toast-confirm-hide');

                // Use transitionend (not animationend) since CSS uses transitions
                const removeOverlay = () => {
                    if (overlay.parentNode) {
                        overlay.remove();
                    }
                };

                overlay.addEventListener('transitionend', removeOverlay, { once: true });

                // Fallback timeout in case transitionend doesn't fire
                setTimeout(removeOverlay, 400);

                // Clean up escape handler
                document.removeEventListener('keydown', escHandler);

                resolve(result);
            };

            // Button handlers
            overlay.querySelector('.toast-btn-confirm').addEventListener('click', () => closeDialog(true));
            overlay.querySelector('.toast-btn-cancel').addEventListener('click', () => closeDialog(false));

            // Close on overlay click
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) closeDialog(false);
            });
        });
    }

    /**
     * Show a prompt dialog (replaces browser prompt())
     * @param {string} message - The prompt message
     * @param {object} options - Additional options
     * @returns {Promise<string|null>} - Resolves to input value if confirmed, null if cancelled
     */
    function showPrompt(message, options = {}) {
        return new Promise((resolve) => {
            const config = {
                title: options.title || 'Input Required',
                confirmText: options.confirmText || 'OK',
                cancelText: options.cancelText || 'Cancel',
                defaultValue: options.defaultValue || '',
                type: options.type || 'info'
            };

            const typeConfig = toastTypes[config.type] || toastTypes.info;

            // Create overlay
            const overlay = document.createElement('div');
            overlay.className = 'toast-confirm-overlay';

            overlay.innerHTML = `
                <div class="toast-confirm-dialog">
                    <div class="toast-confirm-header" style="background: ${typeConfig.gradient}">
                        <i class="bi ${typeConfig.icon}"></i>
                        <span>${config.title}</span>
                    </div>
                    <div class="toast-confirm-body">
                        <p>${message}</p>
                        <input type="text" class="toast-prompt-input form-control" value="${config.defaultValue}" autofocus>
                    </div>
                    <div class="toast-confirm-footer">
                        <button class="toast-btn toast-btn-cancel">${config.cancelText}</button>
                        <button class="toast-btn toast-btn-confirm">${config.confirmText}</button>
                    </div>
                </div>
            `;

            document.body.appendChild(overlay);

            const inputEl = overlay.querySelector('.toast-prompt-input');

            // Trigger entrance animation
            requestAnimationFrame(() => {
                overlay.classList.add('toast-confirm-show');
                inputEl.focus();
                inputEl.select();
            });

            // Define escape handler first (before closeDialog references it)
            const escHandler = (e) => {
                if (e.key === 'Escape') {
                    closeDialog(null);
                }
            };
            document.addEventListener('keydown', escHandler);

            // Enter key submits
            const enterHandler = (e) => {
                if (e.key === 'Enter') {
                    closeDialog(inputEl.value);
                }
            };
            inputEl.addEventListener('keydown', enterHandler);

            const closeDialog = (result) => {
                // Prevent multiple closes
                if (overlay._closed) return;
                overlay._closed = true;

                overlay.classList.add('toast-confirm-hide');

                // Use transitionend (not animationend) since CSS uses transitions
                const removeOverlay = () => {
                    if (overlay.parentNode) {
                        overlay.remove();
                    }
                };

                overlay.addEventListener('transitionend', removeOverlay, { once: true });

                // Fallback timeout in case transitionend doesn't fire
                setTimeout(removeOverlay, 400);

                // Clean up event handlers
                document.removeEventListener('keydown', escHandler);

                resolve(result);
            };

            // Button handlers
            overlay.querySelector('.toast-btn-confirm').addEventListener('click', () => closeDialog(inputEl.value));
            overlay.querySelector('.toast-btn-cancel').addEventListener('click', () => closeDialog(null));

            // Close on overlay click
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) closeDialog(null);
            });
        });
    }

    // Note: HTMX confirm handler removed - vanilla JS now handles confirmations directly

    // Expose functions globally
    window.Toast = {
        show: showToast,
        success: (msg, opts) => showToast(msg, 'success', opts),
        error: (msg, opts) => showToast(msg, 'error', opts),
        warning: (msg, opts) => showToast(msg, 'warning', opts),
        info: (msg, opts) => showToast(msg, 'info', opts),
        confirm: showConfirm,
        prompt: showPrompt
    };

    // Legacy support - override window.alert
    const originalAlert = window.alert;
    window.alert = function (message) {
        showToast(message, 'info', { title: 'Notice' });
    };

    // Restore original alert if needed
    window.Toast.restoreAlert = function () {
        window.alert = originalAlert;
    };

})();
