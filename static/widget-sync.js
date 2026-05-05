(function () {
	const WIDGET_ID = "student-support-chatbot-widget";
	const STYLE_ID = "student-support-chatbot-widget-styles";
	const SCRIPT_SRC = document.currentScript && document.currentScript.src ? document.currentScript.src : "";
	const SCRIPT_BASE = SCRIPT_SRC ? new URL(".", SCRIPT_SRC).href : "https://prototype-student-support-chatbot.onrender.com/static/";
	const API_BASE = SCRIPT_SRC ? new URL(".", SCRIPT_SRC).origin : "https://prototype-student-support-chatbot.onrender.com";
	const SCRIPT_TAG = document.currentScript;
	const MODULE_KEY = SCRIPT_TAG ? (SCRIPT_TAG.getAttribute("data-module-key") || "") : "";
	const DEBUG_STATUS = SCRIPT_TAG ? (SCRIPT_TAG.getAttribute("data-debug-status") || "") : "";
	const DEBUG_PANEL_ID = "student-support-chatbot-debug-panel";

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
		if (!MODULE_KEY || DEBUG_STATUS !== "true") return;

		const status = document.createElement("div");
		status.className = "widget-status-pill";
		status.textContent = "Checking Moodle module...";
		root.querySelector(".widget-header").appendChild(status);

		try {
			const res = await fetch(new URL(`/module-status/${encodeURIComponent(MODULE_KEY)}`, API_BASE).href);
			const data = await res.json();
			if (data && data.ok) {
				const courseText = data.course_id ? `course ${data.course_id}` : "no course mapping";
				const syncText = data.last_sync && data.last_sync.message ? data.last_sync.message : "no sync yet";
				if (data.exists && data.file_count > 0) {
					status.textContent = `Moodle sync ready: ${courseText}, ${data.file_count} file(s)`;
					status.classList.add("is-ready");
				} else {
					status.textContent = `Moodle sync missing: ${courseText}`;
					status.classList.add("is-empty");
				}
				if (!data.moodle_access) {
					status.textContent += " (Moodle access off)";
					status.classList.add("is-error");
				}
				if (data.last_sync && data.last_sync.message) {
					status.title = syncText;
				}
			} else {
				status.textContent = "Module status unavailable";
				status.classList.add("is-error");
			}
		} catch (err) {
			status.textContent = "Module status unavailable";
			status.classList.add("is-error");
		}
	}

	function createStatusDetail(root) {
		let detail = root.querySelector(".widget-status-detail");
		if (!detail) {
			detail = document.createElement("div");
			detail.className = "widget-status-detail";
			root.querySelector(".widget-body").insertBefore(detail, root.querySelector(".note"));
		}
		return detail;
	}

	async function renderStatusDetail(root) {
		if (!MODULE_KEY || DEBUG_STATUS !== "true") return;
		const detail = createStatusDetail(root);
		detail.textContent = "Loading Moodle module status...";

		try {
			const res = await fetch(new URL(`/module-status/${encodeURIComponent(MODULE_KEY)}`, API_BASE).href);
			const data = await res.json();
			if (data && data.ok) {
				const parts = [
					`module_key=${data.module_key}`,
					`course_id=${data.course_id ?? "none"}`,
					`files=${data.file_count}`,
					`moodle_access=${data.moodle_access ? "yes" : "no"}`
				];
				if (data.last_sync && data.last_sync.message) {
					parts.push(`last_sync=${data.last_sync.message}`);
				}
				detail.textContent = parts.join(" | ");
				if (!data.exists || data.file_count === 0) {
					detail.classList.add("is-empty");
				} else {
					detail.classList.add("is-ready");
				}
			} else {
				detail.textContent = "Module status unavailable";
				detail.classList.add("is-error");
			}
		} catch (err) {
			detail.textContent = "Module status unavailable";
			detail.classList.add("is-error");
		}
	}

	function createModuleBanner(root) {
		let banner = root.querySelector(".module-status-banner");
		if (!banner) {
			banner = document.createElement("div");
			banner.className = "module-status-banner";
			root.querySelector(".widget-body").insertBefore(banner, root.querySelector(".note"));
		}
		return banner;
	}

	async function renderModuleBanner(root) {
		if (!MODULE_KEY || DEBUG_STATUS !== "true") return;
		const banner = createModuleBanner(root);
		banner.textContent = "Checking module sync...";
		banner.className = "module-status-banner is-pending";

		try {
			const res = await fetch(new URL(`/module-status/${encodeURIComponent(MODULE_KEY)}`, API_BASE).href);
			const data = await res.json();
			if (data && data.ok) {
				const syncText = data.last_sync && data.last_sync.message ? data.last_sync.message : "no sync yet";
				if (data.exists && data.file_count > 0) {
					banner.textContent = `Module markdown synced: ${data.file_count} file(s) found for course ${data.course_id ?? "unknown"} (${syncText})`;
					banner.className = "module-status-banner is-ready";
				} else {
					banner.textContent = `Module markdown not found yet for course ${data.course_id ?? "unknown"} (${syncText})`;
					banner.className = "module-status-banner is-empty";
				}
			} else {
				banner.textContent = "Module sync status unavailable";
				banner.className = "module-status-banner is-error";
			}
		} catch (err) {
			banner.textContent = "Module sync status unavailable";
			banner.className = "module-status-banner is-error";
		}
	}

	function createDebugPanel() {
		let panel = document.getElementById(DEBUG_PANEL_ID);
		if (panel) return panel;

		panel = document.createElement("aside");
		panel.id = DEBUG_PANEL_ID;
		panel.className = "moodle-debug-panel";
		panel.innerHTML = `
			<div class="moodle-debug-panel-header">
				<strong>Moodle context</strong>
				<span>debug</span>
			</div>
			<pre class="moodle-debug-panel-body">Loading context...</pre>
		`;
		document.body.appendChild(panel);
		return panel;
	}

	function renderDebugPanel() {
		if (DEBUG_STATUS !== "true") return;

		const panel = createDebugPanel();
		const body = panel.querySelector(".moodle-debug-panel-body");
		const headings = Array.from(document.querySelectorAll("h1, h2, h3"))
			.map((el) => el.textContent.trim())
			.filter(Boolean)
			.slice(0, 12);
		const pageClasses = Array.from(document.body.classList).join(" ");
		const windowKeys = Object.getOwnPropertyNames(window)
			.filter((key) => /^(M|moodle|Moodle|requirejs|jQuery|Y|jQuery\$|_)([A-Z0-9_]|$)/.test(key) || key === "M" || key === "Moodle" || key === "requirejs")
			.slice(0, 80)
			.sort();
		const metaTags = Array.from(document.querySelectorAll("meta"))
			.slice(0, 40)
			.map((meta) => ({
				name: meta.getAttribute("name") || meta.getAttribute("property") || meta.getAttribute("charset") || "",
				content: meta.getAttribute("content") || meta.getAttribute("charset") || ""
			}))
			.filter((meta) => meta.name || meta.content);
		const links = Array.from(document.querySelectorAll("link[rel]"))
			.slice(0, 40)
			.map((link) => ({
				rel: link.getAttribute("rel") || "",
				href: link.getAttribute("href") || ""
			}))
			.filter((link) => link.rel || link.href);
		const scripts = Array.from(document.querySelectorAll("script[src]"))
			.slice(0, 40)
			.map((script) => script.getAttribute("src"))
			.filter(Boolean);
		const data = {
			url: window.location.href,
			title: document.title,
			body_classes: pageClasses || "(none)",
			headings: headings.length ? headings : ["(none found)"],
			module_key: MODULE_KEY || "(none)",
			script_src: SCRIPT_TAG && SCRIPT_TAG.src ? SCRIPT_TAG.src : "(unknown)",
			window_M: typeof window.M !== "undefined",
			window_Moodle: typeof window.Moodle !== "undefined",
			window_requirejs: typeof window.requirejs !== "undefined",
			window_keys: windowKeys.length ? windowKeys : ["(none found)"],
			meta: metaTags.length ? metaTags : ["(none found)"],
			links: links.length ? links : ["(none found)"],
			scripts: scripts.length ? scripts : ["(none found)"]
		};
		body.textContent = JSON.stringify(data, null, 2);
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
								You can ask me for any administrative information and guidance pertaining to this module.
							</p>
							<div class="suggestions">
								<button class="pill-button" data-suggestion="How should I prepare for my next seminar?">How should I prepare for my next seminar?</button>
								<button class="pill-button" data-suggestion="Where can I find next week's essential reading?">Where can I find next week's essential reading?</button>
								<button class="pill-button" data-suggestion="Could you give me a study plan to prepare for my next assignment?">Could you give me a study plan to prepare for my next assignment?</button>
								<button class="pill-button" data-suggestion="Could you summarise the essay marking criteria?">Could you summarise the essay marking criteria?</button>
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
								${s.url ? `<a href="${escapeAttribute(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.title)}</a>` : `<span>${escapeHtml(s.title)}</span>`}
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
		renderStatusDetail(root);
		renderModuleBanner(root);
		renderDebugPanel();
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", init);
	} else {
		init();
	}
})();
