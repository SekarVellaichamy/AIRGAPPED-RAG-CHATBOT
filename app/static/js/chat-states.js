/**
 * Chat States Manager
 * Handles loading indicators, typing animations, and error states
 */

const ChatStates = (function () {
    'use strict';

    // Configuration
    const config = {
        typingIndicatorId: 'chat-typing-indicator',
        sendingIndicatorId: 'chat-sending-indicator',
        chatContainerId: 'chat-history',
        chatFormClass: 'chat-form',
    };

    // State
    let isProcessing = false;
    let form = null;

    /**
     * Initialize the chat states manager
     */
    function init() {
        // Find the chat form
        form = document.getElementById('chat-form');
        if (!form) {
            console.warn('ChatStates: Chat form not found');
            return;
        }

        // Add class for styling hooks
        form.classList.add(config.chatFormClass);

        console.log('ChatStates: Initialized');
    }

    /**
     * Check if the event targets the chat
     */
    function isTargetingChat(evt) {
        const detail = evt.detail;
        if (!detail) return false;

        // Check if it's a chat form submission
        const elt = detail.elt || detail.target;
        if (!elt) return false;

        // Check for chat form
        return elt.closest('#chat-form') !== null;
    }

    /**
     * Handle when request starts
     */
    function handleRequestStart(evt) {
        if (isProcessing) return;
        isProcessing = true;

        // Get the message text before form resets
        const messageInput = form?.querySelector('input[name="message"]');
        const messageText = messageInput?.value || '';

        // Add sending state to form
        form?.classList.add('chat-form-sending');

        // Disable form inputs
        if (form) {
            const inputs = form.querySelectorAll('input, button');
            inputs.forEach(input => input.disabled = true);
        }

        // Show sending indicator with user's message preview
        showSendingIndicator(messageText);
    }

    /**
     * Handle when request ends
     */
    function handleRequestEnd(evt) {
        isProcessing = false;

        // Remove sending state
        form?.classList.remove('chat-form-sending');

        // Re-enable form inputs
        if (form) {
            const inputs = form.querySelectorAll('input, button');
            inputs.forEach(input => input.disabled = false);

            // Re-focus message input
            const messageInput = form.querySelector('input[name="message"]');
            messageInput?.focus();
        }

        // Remove indicators
        removeSendingIndicator();
        removeTypingIndicator();
    }

    /**
     * Handle request errors
     */
    function handleRequestError(evt) {
        isProcessing = false;

        // Remove other indicators
        removeSendingIndicator();
        removeTypingIndicator();

        // Remove sending state
        form?.classList.remove('chat-form-sending');

        // Re-enable form
        if (form) {
            const inputs = form.querySelectorAll('input, button');
            inputs.forEach(input => input.disabled = false);
        }

        // Show error message
        showErrorMessage('Failed to send message. Please try again.');
    }

    /**
     * Handle after content swap
     */
    function handleAfterSwap(evt) {
        // Add animation class to new messages
        const chatContainer = document.getElementById(config.chatContainerId);
        if (chatContainer) {
            const messages = chatContainer.querySelectorAll('.message-bubble:not(.message-new)');
            const lastMessages = Array.from(messages).slice(-2); // Last user + AI message
            lastMessages.forEach(msg => {
                msg.classList.add('message-new');
            });
        }
    }

    /**
     * Show sending indicator
     */
    function showSendingIndicator(messageText) {
        // Remove existing
        removeSendingIndicator();

        const chatContainer = document.getElementById(config.chatContainerId);
        if (!chatContainer) return;

        const indicator = document.createElement('div');
        indicator.id = config.sendingIndicatorId;
        indicator.className = 'message-sending';
        indicator.innerHTML = `
            <span class="message-sending-text">Sending</span>
            <div class="sending-spinner" role="status" aria-label="Sending message">
                <span class="visually-hidden">Sending...</span>
            </div>
        `;

        chatContainer.appendChild(indicator);
        scrollToBottom();
    }

    /**
     * Remove sending indicator
     */
    function removeSendingIndicator() {
        const indicator = document.getElementById(config.sendingIndicatorId);
        if (indicator) {
            indicator.remove();
        }
    }

    /**
     * Show typing indicator
     */
    function showTypingIndicator() {
        // Remove existing
        removeTypingIndicator();

        const chatContainer = document.getElementById(config.chatContainerId);
        if (!chatContainer) return;

        const indicator = document.createElement('div');
        indicator.id = config.typingIndicatorId;
        indicator.className = 'typing-indicator';
        indicator.setAttribute('aria-live', 'polite');
        indicator.innerHTML = `
            <div class="typing-dots">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
            </div>
            <span class="typing-text">AI is thinking...</span>
        `;

        chatContainer.appendChild(indicator);
        scrollToBottom();
    }

    /**
     * Remove typing indicator
     */
    function removeTypingIndicator() {
        const indicator = document.getElementById(config.typingIndicatorId);
        if (indicator) {
            indicator.remove();
        }
    }

    /**
     * Show error message
     */
    function showErrorMessage(text, retryCallback) {
        const chatContainer = document.getElementById(config.chatContainerId);
        if (!chatContainer) return;

        const errorDiv = document.createElement('div');
        errorDiv.className = 'message-error';
        errorDiv.innerHTML = `
            <i class="bi bi-exclamation-triangle-fill message-error-icon"></i>
            <span class="message-error-text">${text}</span>
            <button class="message-error-retry" onclick="this.parentElement.remove()">
                Dismiss
            </button>
        `;

        chatContainer.appendChild(errorDiv);
        scrollToBottom();

        // Auto-remove after 8 seconds
        setTimeout(() => {
            if (errorDiv.parentElement) {
                errorDiv.remove();
            }
        }, 8000);
    }

    /**
     * Scroll chat container to bottom
     */
    function scrollToBottom() {
        const chatContainer = document.getElementById(config.chatContainerId);
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    }

    // Public API
    return {
        init: init,
        showTypingIndicator: showTypingIndicator,
        removeTypingIndicator: removeTypingIndicator,
        showSendingIndicator: showSendingIndicator,
        removeSendingIndicator: removeSendingIndicator,
        showErrorMessage: showErrorMessage,
    };
})();

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function () {
    ChatStates.init();
});
