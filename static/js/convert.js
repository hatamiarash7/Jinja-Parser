/* Jinja Parser — browser-native UI, with no library dependencies. */
(function () {
  "use strict";

  const template = document.getElementById("template");
  const values = document.getElementById("values");
  const output = document.getElementById("render");
  const outputPanel = document.querySelector(".panel-output");
  const status = document.getElementById("render-status");
  const renderButton = document.getElementById("convert");
  const copyButton = document.getElementById("copy");
  const copyLabel = document.getElementById("copy-label");
  const autoRun = document.getElementById("autorun");
  const whitespace = document.querySelector('input[name="whitespace"]');
  const form = document.getElementById("parser-form");
  let debounceTimer;
  let copyTimer;
  let inFlight = null;
  let lastOutput = null;

  function setStatus(message, state) {
    status.textContent = message;
    output.dataset.state = state;
  }

  function cancelRequest() {
    clearTimeout(debounceTimer);
    if (inFlight) {
      inFlight.abort();
      inFlight = null;
    }
    output.setAttribute("aria-busy", "false");
    renderButton.removeAttribute("aria-busy");
  }

  function resetCopy() {
    clearTimeout(copyTimer);
    copyLabel.textContent = "Copy";
    copyButton.dataset.state = "idle";
    copyButton.hidden = true;
  }

  function showPlaceholder() {
    lastOutput = null;
    outputPanel.removeAttribute("data-error");
    const placeholder = document.createElement("p");
    placeholder.className = "output-placeholder";
    placeholder.textContent = "Your rendered template will appear here.";
    output.replaceChildren(placeholder);
    resetCopy();
    setStatus("Ready to render", "empty");
  }

  function showError(message) {
    lastOutput = null;
    const error = document.createElement("p");
    error.className = "error";
    // Errors include user input: never interpret them as HTML.
    error.textContent = message;
    output.replaceChildren(error);
    outputPanel.setAttribute("data-error", "");
    resetCopy();
    setStatus("Could not render. Check the error in Output.", "error");
  }

  function showResult() {
    const result = document.createElement("div");
    if (whitespace.checked) {
      // Visual markers never change the underlying output or clipboard text.
      const parts = lastOutput.split(/( +)/);
      for (const part of parts) {
        if (part.startsWith(" ")) {
          const marker = document.createElement("span");
          marker.className = "whitespace";
          marker.textContent = "•".repeat(part.length);
          result.appendChild(marker);
        } else {
          result.appendChild(document.createTextNode(part));
        }
      }
    } else {
      result.textContent = lastOutput;
    }
    output.replaceChildren(result);
    outputPanel.removeAttribute("data-error");
    copyButton.hidden = false;
    setStatus(lastOutput ? "Rendered successfully" : "Rendered successfully · empty output", "ok");
  }

  async function convert() {
    cancelRequest();
    resetCopy();
    lastOutput = null;
    if (!template.value.trim() || !values.value.trim()) {
      showError(!template.value.trim()
        ? "Add a Jinja2 template to get started."
        : "Add JSON or YAML values. Use {} if your template has no variables.");
      return;
    }
    const controller = new AbortController();
    inFlight = controller;
    output.setAttribute("aria-busy", "true");
    renderButton.setAttribute("aria-busy", "true");
    setStatus("Rendering…", "loading");
    const timeout = setTimeout(() => controller.abort(), 35000);
    const body = new URLSearchParams({
      template: template.value,
      values: values.value,
      type: document.querySelector('input[name="type"]:checked').value,
      whitespaces: "0",
    });

    try {
      const response = await fetch(form.dataset.convertUrl, {
        method: "POST", body, signal: controller.signal,
      });
      const data = await response.json().catch(() => null);
      if (inFlight !== controller) return;
      if (!response.ok) {
        showError((data && data.error) || `Request failed (${response.status}). Try again.`);
      } else if (!data || typeof data.rendered_output !== "string") {
        showError("The server returned an unexpected response. Try rendering again.");
      } else {
        // Decode only the server's final escaping, retaining render-time
        // autoescaping. Display text through textContent, never live HTML.
        const decoder = document.createElement("div");
        decoder.innerHTML = data.rendered_output.replaceAll("<br />", "\n");
        lastOutput = decoder.textContent;
        showResult();
      }
    } catch (error) {
      if (inFlight !== controller) return;
      showError(error.name === "AbortError"
        ? "Rendering timed out. Try a smaller template or render again."
        : "Could not reach the server. Check your connection and try again.");
    } finally {
      clearTimeout(timeout);
      if (inFlight === controller) {
        inFlight = null;
        output.setAttribute("aria-busy", "false");
        renderButton.removeAttribute("aria-busy");
      }
    }
  }

  function onInputChanged() {
    cancelRequest();
    resetCopy();
    lastOutput = null;
    setStatus("Inputs changed · render to update", "stale");
    if (autoRun.checked && template.value.trim() && values.value.trim()) {
      debounceTimer = setTimeout(convert, 400);
    }
  }

  function legacyCopy(text) {
    const focused = document.activeElement;
    const helper = document.createElement("textarea");
    helper.value = text;
    helper.setAttribute("readonly", "");
    helper.style.position = "fixed";
    helper.style.opacity = "0";
    document.body.appendChild(helper);
    helper.select();
    let copied = false;
    try {
      copied = document.execCommand("copy");
    } finally {
      helper.remove();
      if (focused) focused.focus({ preventScroll: true });
    }
    return copied;
  }

  copyButton.addEventListener("click", async () => {
    if (lastOutput === null) return;
    const text = lastOutput;
    let copied = false;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        copied = true;
      } else {
        copied = legacyCopy(text);
      }
    } catch (_error) {
      try {
        copied = legacyCopy(text);
      } catch (_fallbackError) {
        copied = false;
      }
    }
    if (lastOutput !== text) return;
    clearTimeout(copyTimer);
    copyButton.dataset.state = copied ? "done" : "idle";
    copyLabel.textContent = copied ? "Copied" : "Try again";
    setStatus(copied ? "Output copied to clipboard" : "Copy unavailable. Select the output and copy it manually.", "ok");
    copyTimer = setTimeout(() => {
      copyButton.dataset.state = "idle";
      copyLabel.textContent = "Copy";
    }, 1500);
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    convert();
  });
  document.getElementById("clear").addEventListener("click", () => {
    if ((template.value.trim() || values.value.trim()) &&
        !window.confirm("Clear the template, values, and output? This cannot be undone.")) return;
    cancelRequest();
    template.value = "";
    values.value = "";
    showPlaceholder();
    template.focus();
  });
  template.addEventListener("input", onInputChanged);
  values.addEventListener("input", onInputChanged);
  document.querySelectorAll('input[name="type"]').forEach((radio) => {
    radio.addEventListener("change", onInputChanged);
  });
  autoRun.addEventListener("change", () => {
    cancelRequest();
    if (autoRun.checked) convert();
    else if (output.dataset.state === "loading") setStatus("Auto-render paused · render to update", "stale");
  });
  whitespace.addEventListener("change", () => {
    if (lastOutput !== null) showResult();
  });
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && !event.isComposing) {
      event.preventDefault();
      convert();
    }
  });
  // Keep Tab / Shift+Tab native so keyboard users can always leave editors.
  convert();
})();
