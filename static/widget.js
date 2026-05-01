(function () {
	const WIDGET_ID = "student-support-chatbot-widget";
	const STYLE_ID = "student-support-chatbot-widget-styles";
	const SCRIPT_SRC = document.currentScript && document.currentScript.src ? document.currentScript.src : "";
	const SCRIPT_BASE = SCRIPT_SRC ? new URL(".", SCRIPT_SRC).href : "https://prototype-student-support-chatbot.onrender.com/static/";
	const API_BASE = SCRIPT_SRC ? new URL(".", SCRIPT_SRC).origin : "https://prototype-student-support-chatbot.onrender.com";
	const SCRIPT_TAG = document.currentScript;
	const MODULE_KEY = SCRIPT_TAG ? (SCRIPT_TAG.getAttribute("data-module-key") || "") : "";
	const DEBUG_STATUS = SCRIPT_TAG ? (SCRIPT_TAG.getAttribute("data-debug-status") || "") : "";

	function assetUrl(path) {
		return new URL(path, SCRIPT_BASE).href;
	}

	function shouldInit() {
		const pageContains = SCRIPT_TAG && SCRIPT_TAG.getAttribute("data-page-contains");
		const pageEquals = SCRIPT_TAG && SCRIPT_TAG.getAttribute("data-page-equals");
		const pathname = window.location.pathname + window.location.search;

		if (pageContains && !pathname.includes(pageContains)) {
			return false;
		}

		if (pageEquals && pathname !== pageEquals) {
			return false;
		}

		return true;
	}

	function ensureStylesheet() {
		if (document.getElementById(STYLE_ID)) return;

		const link = document.createElement("link");
		link.id = STYLE_ID;
		link.rel = "stylesheet";
		link.href = assetUrl("styles.css");
		document.head.appendChild(link);
	}

	async function renderStatusPill(root) {
		if (!DEBUG_STATUS || !MODULE_KEY) return;

		const status = document.createElement("div");
		status.className = "widget-status-pill";
		status.textContent = "Checking module content...";
		root.querySelector(".widget-header").appendChild(status);

		try {
			const res = await fetch(new URL(`/module-status/${encodeURIComponent(MODULE_KEY)}`, API_BASE).href);
			const data = await res.json();
			if (data && data.exists && data.file_count > 0) {
				status.textContent = `Module markdown ready: ${data.file_count} file(s)`;
				status.classList.add("is-ready");
			} else {
				status.textContent = "No module markdown found yet";
				status.classList.add("is-empty");
			}
		} catch (err) {
			status.textContent = "Module status unavailable";
			status.classList.add("is-error");
		}
	}

	function createHtml() {
		return `
			<div class="widget-launcher">
				<button id="widgetToggle" class="widget-button" type="button" aria-expanded="false" aria-controls="chatWidgetPanel">
					<span class="widget-button-icon"><i class="fa-solid fa-comments"></i></span>
					<span class="widget-button-text">Module Assistant</span>
				</button>
			</div>

			<section class="chat-widget" id="chatWidgetPanel" aria-label="Student support chatbot">
				<header class="widget-header">
					<div class="widget-brand">
						<img src="${assetUrl("kent-logo.png")}" alt="University of Kent" class="widget-logo" />
						<div>
							<h1>Module Assistant</h1>
							<p>Prototype chatbot - not an official university system</p>
						</div>
					</div>
					<div class="widget-actions">
						<button id="themeToggle" class="widget-icon-button" type="button" aria-label="Toggle theme">
							<i class="fa-solid fa-moon"></i>
						</button>
						<button id="accessibilityToggle" class="widget-icon-button" type="button" aria-label="Toggle accessibility mode">
							<i class="fa-solid fa-universal-access"></i>
						</button>
						<button id="widgetClose" class="widget-icon-button" type="button" aria-label="Close chatbot">
							<i class="fa-solid fa-xmark"></i>
						</button>
					</div>
				</header>

				<div class="widget-body">
					<p class="note">
						This chatbot provides guidance based on university support content. Please avoid sharing personal or sensitive information. Always check official sources for confirmation.
					</p>

					<div id="chatBox" class="chat-box">
						<div id="chatStarter" class="chat-starter">
							<p class="starter-text">
								Ask about admissions, assessments, deadlines, wellbeing, or general student support.
							</p>
							<div class="suggestions">
								<button class="pill-button" data-suggestion="How do I apply for an extension?">How do I apply for an extension?</button>
								<button class="pill-button" data-suggestion="Where can I get wellbeing support?">Where can I get wellbeing support?</button>
								<button class="pill-button" data-suggestion="How do I contact admissions?">How do I contact admissions?</button>
							</div>
						</div>
					</div>

					<div class="input-row">
						<input id="messageInput" type="text" placeholder="Ask a student support question..." />
						<span class="info-icon">
							<i class="fa-solid fa-circle-info"></i>
							<span class="tooltip-text">
								Avoid sharing personal, medical, or identifying information.
							</span>
						</span>
						<button class="send-button" id="sendButton" type="button">Send</button>
					</div>
				</div>
			</section>
		`;
	}

	function escapeHtml(text) {
		const div = document.createElement("div");
		div.innerText = text;
		return div.innerHTML;
	}

	function escapeAttribute(text) {
		const div = document.createElement("div");
		div.innerText = text;
		return div.innerHTML;
	}

	function hideChatStarter() {
		const starter = document.getElementById("chatStarter");
		if (starter) starter.style.display = "none";
	}

	async function sendMessage(prefill = null) {
		const input = document.getElementById("messageInput");
		const chatBox = document.getElementById("chatBox");
		const message = prefill || input.value.trim();

		if (!message) return;
		hideChatStarter();

		chatBox.innerHTML += `<div class="msg user"><strong>You:</strong> ${escapeHtml(message)}</div>`;
		input.value = "";

		const res = await fetch(new URL("/chat", API_BASE).href, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				message,
				module_key: MODULE_KEY || null
			})
		});

		const data = await res.json();

		let sourcesHtml = "";
		if (data.sources && data.sources.length) {
			sourcesHtml = `
				<div class="sources">
					<strong>Top sources:</strong>
					<ul>
						${data.sources.map(s => `
							<li>
								<a href="${escapeAttribute(s.url || "#")}" target="_blank" rel="noopener noreferrer">
									${escapeHtml(s.title)}
								</a>
							</li>
						`).join("")}
					</ul>
				</div>
			`;
		}

		const fallbackWarning = data.fallback
			? `<div class="warning">This answer may be incomplete. Please check official sources.</div>`
			: "";

		chatBox.innerHTML += `
			<div class="msg bot">
				<strong>Assistant:</strong> ${escapeHtml(data.answer).replace(/\n/g, "<br>")}
				${fallbackWarning}
				<div class="meta">Category: ${escapeHtml(data.category || "general")} ${data.fallback ? " - Fallback used" : ""}</div>
				${sourcesHtml}
			</div>
		`;

		chatBox.scrollTop = chatBox.scrollHeight;
	}

	function toggleTheme() {
		const isDark = document.body.classList.contains("dark-mode");
		const newTheme = isDark ? "light" : "dark";
		localStorage.setItem("theme", newTheme);
		applyTheme(newTheme);
	}

	function applyTheme(theme) {
		const toggle = document.getElementById("themeToggle");
		if (theme === "dark") {
			document.body.classList.add("dark-mode");
			if (toggle) toggle.innerHTML = '<i class="fa-solid fa-sun"></i>';
		} else {
			document.body.classList.remove("dark-mode");
			if (toggle) toggle.innerHTML = '<i class="fa-solid fa-moon"></i>';
		}
	}

	function toggleAccessibilityMode() {
		const enabled = document.body.classList.contains("accessibility-mode");
		const newValue = !enabled;
		localStorage.setItem("accessibilityMode", newValue ? "on" : "off");
		applyAccessibilityMode(newValue);
	}

	function applyAccessibilityMode(enabled) {
		const toggle = document.getElementById("accessibilityToggle");
		if (enabled) {
			document.body.classList.add("accessibility-mode");
			if (toggle) toggle.setAttribute("aria-pressed", "true");
		} else {
			document.body.classList.remove("accessibility-mode");
			if (toggle) toggle.setAttribute("aria-pressed", "false");
		}
	}

	function closeWidget() {
		const panel = document.getElementById("chatWidgetPanel");
		const toggle = document.getElementById("widgetToggle");
		if (panel) panel.classList.remove("is-open");
		if (toggle) toggle.setAttribute("aria-expanded", "false");
	}

	function openWidget() {
		const panel = document.getElementById("chatWidgetPanel");
		const toggle = document.getElementById("widgetToggle");
		if (panel) panel.classList.add("is-open");
		if (toggle) toggle.setAttribute("aria-expanded", "true");
	}

	function toggleWidget() {
		const panel = document.getElementById("chatWidgetPanel");
		if (!panel) return;
		if (panel.classList.contains("is-open")) {
			closeWidget();
		} else {
			openWidget();
		}
	}

	function init() {
		if (!shouldInit()) return;

		ensureStylesheet();

		const existing = document.getElementById(WIDGET_ID);
		if (existing) return;

		const mount = document.body;
		const root = document.createElement("div");
		root.id = WIDGET_ID;
		root.innerHTML = createHtml();
		mount.appendChild(root);

		const widgetToggle = root.querySelector("#widgetToggle");
		const widgetClose = root.querySelector("#widgetClose");
		const themeToggle = root.querySelector("#themeToggle");
		const accessibilityToggle = root.querySelector("#accessibilityToggle");
		const sendButton = root.querySelector("#sendButton");
		const input = root.querySelector("#messageInput");

		if (widgetToggle) widgetToggle.addEventListener("click", toggleWidget);
		if (widgetClose) widgetClose.addEventListener("click", closeWidget);
		if (themeToggle) themeToggle.addEventListener("click", toggleTheme);
		if (accessibilityToggle) accessibilityToggle.addEventListener("click", toggleAccessibilityMode);
		if (sendButton) sendButton.addEventListener("click", () => sendMessage());
		if (input) {
			input.addEventListener("keydown", function (e) {
				if (e.key === "Enter") sendMessage();
			});
		}

		root.querySelectorAll("[data-suggestion]").forEach((button) => {
			button.addEventListener("click", () => sendMessage(button.getAttribute("data-suggestion")));
		});

		applyTheme(localStorage.getItem("theme") || "light");
		applyAccessibilityMode(localStorage.getItem("accessibilityMode") === "on");
		renderStatusPill(root);
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
