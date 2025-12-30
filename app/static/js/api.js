/**
 * API Utility Module
 * Centralized fetch API wrapper for all HTTP requests
 */

const API = (function () {
    'use strict';

    /**
     * Get CSRF token from cookie
     * @returns {string|null}
     */
    function getCsrfToken() {
        const match = document.cookie.split('; ')
            .find(row => row.startsWith('csrf_token='));
        return match ? decodeURIComponent(match.split('=')[1]) : null;
    }

    /**
     * Make a POST request with form data
     * @param {string} url - The endpoint URL
     * @param {FormData|Object} data - Form data or object to send
     * @returns {Promise<{ok: boolean, data: any, status: number}>}
     */
    async function post(url, data) {
        try {
            const formData = data instanceof FormData ? data : objectToFormData(data);

            const response = await fetch(url, {
                method: 'POST',
                body: formData,
                credentials: 'same-origin'
            });

            const contentType = response.headers.get('content-type') || '';
            let responseData;

            if (contentType.includes('application/json')) {
                responseData = await response.json();
            } else {
                responseData = await response.text();
            }

            return {
                ok: response.ok,
                data: responseData,
                status: response.status
            };
        } catch (error) {
            console.error('API.post error:', error);
            return {
                ok: false,
                data: null,
                status: 0,
                error: error.message
            };
        }
    }

    /**
     * Make a DELETE request
     * @param {string} url - The endpoint URL
     * @returns {Promise<{ok: boolean, data: any, status: number}>}
     */
    async function del(url) {
        try {
            const csrfToken = getCsrfToken();
            const headers = {
                'Accept': 'application/json'
            };
            if (csrfToken) {
                headers['X-CSRF-Token'] = csrfToken;
            }

            const response = await fetch(url, {
                method: 'DELETE',
                credentials: 'same-origin',
                headers: headers
            });

            const contentType = response.headers.get('content-type') || '';
            let responseData;

            if (contentType.includes('application/json')) {
                responseData = await response.json();
            } else {
                responseData = await response.text();
            }

            return {
                ok: response.ok,
                data: responseData,
                status: response.status
            };
        } catch (error) {
            console.error('API.delete error:', error);
            return {
                ok: false,
                data: null,
                status: 0,
                error: error.message
            };
        }
    }

    /**
     * Make a GET request
     * @param {string} url - The endpoint URL
     * @returns {Promise<{ok: boolean, data: any, status: number}>}
     */
    async function get(url) {
        try {
            const response = await fetch(url, {
                method: 'GET',
                credentials: 'same-origin',
                headers: {
                    'Accept': 'application/json, text/html'
                }
            });

            const contentType = response.headers.get('content-type') || '';
            let responseData;

            if (contentType.includes('application/json')) {
                responseData = await response.json();
            } else {
                responseData = await response.text();
            }

            return {
                ok: response.ok,
                data: responseData,
                status: response.status
            };
        } catch (error) {
            console.error('API.get error:', error);
            return {
                ok: false,
                data: null,
                status: 0,
                error: error.message
            };
        }
    }

    /**
     * Convert object to FormData
     */
    function objectToFormData(obj) {
        const formData = new FormData();
        for (const key in obj) {
            if (obj.hasOwnProperty(key)) {
                formData.append(key, obj[key]);
            }
        }
        return formData;
    }

    /**
     * Make a PUT request with JSON payload
     * @param {string} url - The endpoint URL
     * @param {Object} data - Object to send as JSON
     * @returns {Promise<{ok: boolean, data: any, status: number}>}
     */
    async function put(url, data) {
        try {
            const csrfToken = getCsrfToken();
            const headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            };
            if (csrfToken) {
                headers['X-CSRF-Token'] = csrfToken;
            }

            const response = await fetch(url, {
                method: 'PUT',
                credentials: 'same-origin',
                headers: headers,
                body: JSON.stringify(data)
            });

            const contentType = response.headers.get('content-type') || '';
            let responseData;

            if (contentType.includes('application/json')) {
                responseData = await response.json();
            } else {
                responseData = await response.text();
            }

            return {
                ok: response.ok,
                data: responseData,
                status: response.status
            };
        } catch (error) {
            console.error('API.put error:', error);
            return {
                ok: false,
                data: null,
                status: 0,
                error: error.message
            };
        }
    }

    // Public API
    return {
        post: post,
        delete: del,
        get: get,
        put: put
    };
})();
