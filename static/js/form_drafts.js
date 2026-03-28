(function () {
    const STORAGE_PREFIX = "themis:draft:";
    const PENDING_CLEAR_KEY = "themis:draft:pending-clear";
    const FIELD_SELECTOR = "textarea, input[type='text'], input[type='search'], input[type='email'], input[type='url'], input[type='tel'], input[type='number'], input[type='hidden'][name]";
    const SAVE_DELAY_MS = 400;
    const SERVER_AUTOSAVE_INTERVAL_MS = 3 * 60 * 1000;
    const SERVER_DRAFT_LOAD_ENDPOINT = "/projects/drafts";
    const SERVER_DRAFT_AUTOSAVE_ENDPOINT = "/projects/drafts/autosave";
    const SERVER_DRAFT_CLEAR_ENDPOINT = "/projects/drafts/clear";
    const RESTORE_SUPPRESS_PREFIX = "themis:draft:suppress:";

    function getDraftKey(form) {
        const customKey = form.dataset.draftKey;
        if (customKey) {
            return STORAGE_PREFIX + customKey;
        }

        const action = form.getAttribute("action") || form.getAttribute("hx-post") || form.id || "form";
        return STORAGE_PREFIX + `${window.location.pathname}::${action}`;
    }

    function getRestoreSuppressKey(formOrDraftKey) {
        const draftKey = typeof formOrDraftKey === "string" ? formOrDraftKey : getDraftKey(formOrDraftKey);
        return RESTORE_SUPPRESS_PREFIX + draftKey;
    }

    function setRestoreSuppression(formOrDraftKey) {
        sessionStorage.setItem(getRestoreSuppressKey(formOrDraftKey), "1");
    }

    function isRestoreSuppressed(formOrDraftKey) {
        return sessionStorage.getItem(getRestoreSuppressKey(formOrDraftKey)) === "1";
    }

    function clearRestoreSuppression(formOrDraftKey) {
        sessionStorage.removeItem(getRestoreSuppressKey(formOrDraftKey));
    }

    function resolveDraftForm(elt) {
        if (elt instanceof HTMLFormElement) {
            return elt;
        }

        if (elt?.form instanceof HTMLFormElement) {
            return elt.form;
        }

        const closestForm = elt?.closest?.("form[data-draft-persist='true']");
        return closestForm instanceof HTMLFormElement ? closestForm : null;
    }

    function getLocalDraftPayload(form) {
        const raw = localStorage.getItem(getDraftKey(form));
        if (!raw) {
            return null;
        }

        try {
            return JSON.parse(raw);
        } catch {
            return null;
        }
    }

    function getDraftFields(form) {
        return Array.from(form.querySelectorAll(FIELD_SELECTOR)).filter((field) => {
            return getFieldKey(field) && !field.disabled;
        });
    }

    function getFieldKey(field) {
        return field.dataset.draftName || field.name;
    }

    function readFormValues(form) {
        const values = {};
        getDraftFields(form).forEach((field) => {
            values[getFieldKey(field)] = field.value || "";
        });
        return values;
    }

    function valuesEqual(left, right) {
        return JSON.stringify(left) === JSON.stringify(right);
    }

    function isBlank(values) {
        return Object.values(values).every((value) => typeof value === "string" && value.trim() === "");
    }

    function saveDraft(form) {
        if (!(form instanceof HTMLFormElement)) {
            return;
        }

        const key = getDraftKey(form);
        const baseline = form.__draftBaseline || readFormValues(form);
        const values = readFormValues(form);

        if (valuesEqual(values, baseline)) {
            localStorage.removeItem(key);
            form.__draftPayload = null;
            form.dataset.draftDirty = "false";
            return;
        }

        const payload = {
            version: 1,
            savedAt: Date.now(),
            baseline,
            values,
            path: window.location.pathname,
        };
        localStorage.setItem(key, JSON.stringify(payload));
        form.__draftPayload = payload;
        form.dataset.draftDirty = "true";
    }

    function scheduleSave(form) {
        window.clearTimeout(form.__draftTimer);
        form.__draftTimer = window.setTimeout(() => saveDraft(form), SAVE_DELAY_MS);
    }

    function refreshRichTextField(field) {
        if (typeof window.refreshRichTextEditor === "function" && field.dataset.richText === "true") {
            window.refreshRichTextEditor(field);
        }
    }

    function applyDraftValue(field, payload, refreshEditor = true) {
        const key = getFieldKey(field);
        if (!key || !payload?.values || !Object.prototype.hasOwnProperty.call(payload.values, key)) {
            return false;
        }

        const nextValue = payload.values[key] || "";
        if (field.value === nextValue) {
            return false;
        }

        field.value = nextValue;
        if (refreshEditor) {
            refreshRichTextField(field);
        }
        field.dispatchEvent(new Event("input", { bubbles: true }));
        if (field.type === "hidden") {
            field.dispatchEvent(new CustomEvent("draftrestore", {
                bubbles: true,
                detail: { name: key, value: nextValue },
            }));
        }
        return true;
    }

    function applyDraftValues(form, payload, refreshEditors = true) {
        if (!payload?.values) {
            return;
        }

        getDraftFields(form).forEach((field) => {
            applyDraftValue(field, payload, refreshEditors);
        });
    }

    function getDraftFieldsFromNode(node) {
        const fields = [];
        if (!(node instanceof Element)) {
            return fields;
        }

        if (node.matches(FIELD_SELECTOR) && getFieldKey(node) && !node.disabled) {
            fields.push(node);
        }

        node.querySelectorAll(FIELD_SELECTOR).forEach((field) => {
            if (getFieldKey(field) && !field.disabled) {
                fields.push(field);
            }
        });

        return fields;
    }

    function restoreDraft(form) {
        if (isRestoreSuppressed(form)) {
            form.__draftPayload = null;
            form.dataset.draftDirty = "false";
            form.dataset.draftRestored = "false";
            return;
        }

        const key = getDraftKey(form);
        const raw = localStorage.getItem(key);
        if (!raw) {
            form.__draftPayload = null;
            form.dataset.draftDirty = "false";
            return;
        }

        let payload;
        try {
            payload = JSON.parse(raw);
        } catch {
            localStorage.removeItem(key);
            form.__draftPayload = null;
            form.dataset.draftDirty = "false";
            return;
        }

        const currentValues = readFormValues(form);
        const baseline = payload.baseline || currentValues;
        const canRestore = valuesEqual(currentValues, baseline) || isBlank(currentValues);

        form.__draftBaseline = baseline;
        form.__draftPayload = payload;

        if (!canRestore || !payload.values || valuesEqual(payload.values, currentValues)) {
            form.dataset.draftDirty = valuesEqual(currentValues, baseline) ? "false" : "true";
            return;
        }

        applyDraftValues(form, payload);
        form.dataset.draftDirty = "true";
        form.dataset.draftRestored = "true";

        if (typeof window.showToast === "function") {
            window.showToast("Recovered unsaved draft for this form.", "info", 3500);
        }
    }

    function clearDraft(form) {
        const key = getDraftKey(form);
        localStorage.removeItem(key);
        form.dataset.draftDirty = "false";
        form.dataset.draftRestored = "false";
        form.__draftBaseline = readFormValues(form);
        form.__draftPayload = null;
        form.__lastServerDraftHash = null;
    }

    function getStoredDraftPayload(form) {
        if (!(form instanceof HTMLFormElement)) {
            return null;
        }

        if (form.__draftPayload) {
            return form.__draftPayload;
        }

        const raw = localStorage.getItem(getDraftKey(form));
        if (!raw) {
            return null;
        }

        try {
            return JSON.parse(raw);
        } catch {
            return null;
        }
    }

    async function hydrateDraftFromServer(form) {
        if (!(form instanceof HTMLFormElement) || form.__serverDraftHydrated === true) {
            return;
        }

        form.__serverDraftHydrated = true;
        if (isRestoreSuppressed(form)) {
            return;
        }
        if (getLocalDraftPayload(form)) {
            return;
        }

        try {
            const url = new URL(SERVER_DRAFT_LOAD_ENDPOINT, window.location.origin);
            url.searchParams.set("draft_key", getDraftKey(form));

            const response = await fetch(url.toString(), {
                headers: { Accept: "application/json" },
                credentials: "same-origin",
            });
            if (!response.ok) {
                return;
            }

            const data = await response.json();
            const payload = data?.draft?.payload;
            if (!payload?.values) {
                return;
            }

            const payloadJson = JSON.stringify(payload);
            localStorage.setItem(getDraftKey(form), payloadJson);
            form.__draftPayload = payload;
            form.__lastServerDraftHash = payloadJson;
            restoreDraft(form);
        } catch {
            // Ignore server draft fetch failures and keep local-only protection working.
        }
    }

    function formDraftHasUnsavedValue(form, fieldKey) {
        const payload = getStoredDraftPayload(form);
        if (!payload?.values || !Object.prototype.hasOwnProperty.call(payload.values, fieldKey)) {
            return false;
        }

        const draftValue = payload.values[fieldKey] || "";
        const baselineValue = payload.baseline?.[fieldKey] || "";
        return draftValue !== baselineValue;
    }

    async function syncDraftToServer(form) {
        if (!(form instanceof HTMLFormElement) || form.__serverSyncInFlight) {
            return;
        }

        saveDraft(form);

        if (form.dataset.draftDirty !== "true") {
            return;
        }

        const payload = getStoredDraftPayload(form);
        if (!payload?.values) {
            return;
        }

        const payloadJson = JSON.stringify(payload);
        if (form.__lastServerDraftHash === payloadJson) {
            return;
        }

        form.__serverSyncInFlight = true;

        try {
            const response = await fetch(SERVER_DRAFT_AUTOSAVE_ENDPOINT, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "application/json",
                },
                credentials: "same-origin",
                body: JSON.stringify({
                    draft_key: getDraftKey(form),
                    path: window.location.pathname,
                    form_action: form.getAttribute("action") || form.getAttribute("hx-post") || form.id || "",
                    payload,
                }),
            });

            if (response.ok) {
                form.__lastServerDraftHash = payloadJson;
            }
        } catch {
            // Keep local protection active even if server autosave is unavailable.
        } finally {
            form.__serverSyncInFlight = false;
        }
    }

    function startServerAutosave(form) {
        if (!(form instanceof HTMLFormElement) || form.__serverAutosaveTimer) {
            return;
        }

        form.__serverAutosaveTimer = window.setInterval(() => {
            if (!document.body.contains(form)) {
                window.clearInterval(form.__serverAutosaveTimer);
                form.__serverAutosaveTimer = null;
                return;
            }

            void syncDraftToServer(form);
        }, SERVER_AUTOSAVE_INTERVAL_MS);
    }

    async function clearServerDraftByKey(draftKey) {
        if (!draftKey) {
            return;
        }

        try {
            await fetch(SERVER_DRAFT_CLEAR_ENDPOINT, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "application/json",
                },
                credentials: "same-origin",
                body: JSON.stringify({ draft_key: draftKey }),
            });
        } catch {
            // Ignore cleanup failures; stale drafts can be overwritten later.
        }
    }

    function markPendingClear(form) {
        const entries = JSON.parse(sessionStorage.getItem(PENDING_CLEAR_KEY) || "[]");
        entries.push({ key: getDraftKey(form), path: window.location.pathname });
        sessionStorage.setItem(PENDING_CLEAR_KEY, JSON.stringify(entries));
    }

    function flushPendingClears() {
        const raw = sessionStorage.getItem(PENDING_CLEAR_KEY);
        if (!raw) {
            return;
        }

        let entries;
        try {
            entries = JSON.parse(raw);
        } catch {
            sessionStorage.removeItem(PENDING_CLEAR_KEY);
            return;
        }

        const remaining = [];
        entries.forEach((entry) => {
            if (entry.path !== window.location.pathname) {
                localStorage.removeItem(entry.key);
                void clearServerDraftByKey(entry.key);
            } else {
                remaining.push(entry);
            }
        });

        if (remaining.length) {
            sessionStorage.setItem(PENDING_CLEAR_KEY, JSON.stringify(remaining));
        } else {
            sessionStorage.removeItem(PENDING_CLEAR_KEY);
        }
    }

    function initDraftForm(form) {
        if (!(form instanceof HTMLFormElement) || form.dataset.draftInitialized === "true") {
            return;
        }

        form.dataset.draftInitialized = "true";
        form.__draftBaseline = readFormValues(form);
        restoreDraft(form);
        startServerAutosave(form);
        void hydrateDraftFromServer(form);
        clearRestoreSuppression(form);

        const saveHandler = () => scheduleSave(form);
        form.addEventListener("input", saveHandler);
        form.addEventListener("change", saveHandler);

        form.addEventListener("submit", function () {
            if (form.hasAttribute("hx-post")) {
                setRestoreSuppression(form);
            }
            saveDraft(form);
            if (!form.hasAttribute("hx-post")) {
                markPendingClear(form);
                // Clear the dirty flag so beforeunload doesn't prompt on normal form submission
                form.dataset.draftDirty = "false";
            }
        });
    }

    function initDraftForms(root) {
        const scope = root instanceof Element || root instanceof Document ? root : document;
        scope.querySelectorAll("form[data-draft-persist='true']").forEach((form) => {
            initDraftForm(form);
        });
    }

    function observeDraftFields() {
        if (window.__draftObserverStarted || !document.body) {
            return;
        }

        window.__draftObserverStarted = true;
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (!(node instanceof Element)) {
                        return;
                    }

                    initDraftForms(node);

                    getDraftFieldsFromNode(node).forEach((field) => {
                        const form = field.closest("form[data-draft-persist='true']");
                        if (!(form instanceof HTMLFormElement)) {
                            return;
                        }

                        const payload = getStoredDraftPayload(form);
                        if (!payload?.values) {
                            return;
                        }

                        applyDraftValue(field, payload, true);
                    });
                });
            });
        });

        observer.observe(document.body, { childList: true, subtree: true });
    }

    function anyDirtyDraftForms() {
        return Array.from(document.querySelectorAll("form[data-draft-persist='true']")).some((form) => {
            return form.dataset.draftDirty === "true";
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        flushPendingClears();
        initDraftForms(document);
        observeDraftFields();
    });

    window.addEventListener("beforeunload", function (event) {
        if (!anyDirtyDraftForms()) {
            return;
        }
        event.preventDefault();
        event.returnValue = "";
    });

    document.body.addEventListener("htmx:load", function (event) {
        initDraftForms(event.target);
    });

    document.body.addEventListener("htmx:afterSwap", function (event) {
        initDraftForms(event.target);
    });

    document.body.addEventListener("htmx:beforeSwap", function (event) {
        const elt = event.detail?.requestConfig?.elt || event.detail?.elt;
        const form = resolveDraftForm(elt);
        if (!form) {
            return;
        }

        const status = event.detail?.xhr?.status || 0;
        if (status >= 200 && status < 400) {
            setRestoreSuppression(form);
            clearDraft(form);
            void clearServerDraftByKey(getDraftKey(form));
        }
    });

    document.body.addEventListener("htmx:afterRequest", function (event) {
        const elt = event.detail?.elt;
        const form = resolveDraftForm(elt);
        if (!form) {
            return;
        }

        if (event.detail.successful) {
            clearDraft(form);
            void clearServerDraftByKey(getDraftKey(form));
        } else {
            clearRestoreSuppression(form);
            saveDraft(form);
        }
    });

    window.initDraftForms = initDraftForms;
    window.clearFormDraft = clearDraft;
    window.formDraftHasUnsavedValue = formDraftHasUnsavedValue;
})();
