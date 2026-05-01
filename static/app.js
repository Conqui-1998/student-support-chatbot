async function sendMessage(prefill = null) {
	const input = document.getElementById("messageInput");
	const chatBox = document.getElementById("chatBox");
	const message = prefill || input.value.trim();
	
	if (!message) return;
	hideChatStarter();
	
	chatBox.innerHTML += `<div class="msg user"><strong>You:</strong> ${escapeHtml(message)}</div>`;
	input.value = "";
	
	const res = await fetch("/chat", {
		method: "POST",
		headers: {"Content-Type": "application/json"},
		body: JSON.stringify({ message })
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
		? `<div class="warning"> This answer may be incomplete. Please check official sources.</div>`
		: "";
	
	chatBox.innerHTML += `
		<div class="msg bot">
			<strong>Assistant:</strong> ${escapeHtml(data.answer).replace(/\n/g, "<br>")}
			${fallbackWarning}
			<div class="meta">Category: ${escapeHtml(data.category || "general")} ${data.fallback ?" - Fallback used" : ""}</div>
			${sourcesHtml}
		</div>
		`;
		
		chatBox.scrollTop = chatBox.scrollHeight;
		requestFrameResize();
	}
	
	
function askSuggestion(text) {
	sendMessage(text);
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
	if (starter) {
		starter.style.display = "none";
	}
}

function getDocumentHeight() {
	return Math.max(
		document.body.scrollHeight,
		document.documentElement.scrollHeight,
		document.body.offsetHeight,
		document.documentElement.offsetHeight,
		document.documentElement.clientHeight
	);
}

function sendFrameResize(height) {
	const message = JSON.stringify({
		subject: "lti.frameResize",
		height: Math.ceil(height)
	});

	try {
		console.debug("[chatbot] sending frame resize", Math.ceil(height));
		window.parent.postMessage(message, "*");
	} catch (err) {
		// Ignore if the tool is not embedded or the host blocks messaging.
		console.debug("[chatbot] frame resize blocked", err);
	}
}

let resizeTimer = null;

function requestFrameResize() {
	if (resizeTimer) {
		clearTimeout(resizeTimer);
	}

	resizeTimer = setTimeout(() => {
		sendFrameResize(getDocumentHeight());
	}, 50);
}

function setupFrameResizeObserver() {
	requestFrameResize();
	addDebugBadge();

	if (typeof ResizeObserver !== "undefined") {
		const observer = new ResizeObserver(() => {
			requestFrameResize();
			addDebugBadge();
		});
		observer.observe(document.body);
	}

	window.addEventListener("load", requestFrameResize);
	window.addEventListener("resize", requestFrameResize);
	window.addEventListener("load", addDebugBadge);
	window.addEventListener("resize", addDebugBadge);
	setTimeout(requestFrameResize, 250);
	setTimeout(requestFrameResize, 1000);
	setTimeout(addDebugBadge, 250);
	setTimeout(addDebugBadge, 1000);
}

function applyEmbeddedMode() {
	try {
		if (window.self !== window.top) {
			document.body.classList.add("embedded-mode");
			document.body.setAttribute("data-embed-status", "embedded");
			console.debug("[chatbot] embedded mode detected");
		}
	} catch (err) {
		document.body.classList.add("embedded-mode");
		document.body.setAttribute("data-embed-status", "embedded");
		console.debug("[chatbot] embedded mode detected via cross-origin fallback");
	}
}

function addDebugBadge() {
	let badge = document.getElementById("embedDebugBadge");
	if (!badge) {
		badge = document.createElement("div");
		badge.id = "embedDebugBadge";
		badge.className = "embed-debug-badge";
		document.body.appendChild(badge);
	}

	const embedded = document.body.classList.contains("embedded-mode");
	const height = getDocumentHeight();
	badge.textContent = embedded
		? `EMBED MODE | height ${height}px | resize active`
		: `STANDALONE MODE | height ${height}px`;
}

function applyTheme(theme) {
	if (theme === "dark") {
		document.body.classList.add("dark-mode");
		const toggle = document.getElementById("themeToggle");
		if (toggle) toggle.textContent = "Light Mode";
	}
	else {
		document.body.classList.remove("dark-mode");
		const toggle = document.getElementById("themeToggle");
		if (toggle) toggle.textContent = "Dark Mode";
	}
}

function toggleTheme() {
	const isDark = document.body.classList.contains("dark-mode");
	const newTheme = isDark ? "light" : "dark";
	localStorage.setItem("theme", newTheme);
	applyTheme(newTheme);
}

function applyAccessibilityMode(enabled) {
	const toggle = document.getElementById("accessibilityToggle");
	
	if(enabled) {
		document.body.classList.add("accessibility-mode");
		if(toggle) toggle.textContent = "Accessibility: On";
	}
	else {
		document.body.classList.remove("accessibility-mode");
		if(toggle) toggle.textContent = "Accessibility: Off";
	}
}

function toggleAccessibilityMode() {
	const enabled = document.body.classList.contains("accessibility-mode");
	const newValue = !enabled;
	
	localStorage.setItem("accessibilityMode", newValue ? "on" : "off");
	applyAccessibilityMode(newValue);
}

window.sendMessage = sendMessage;
window.askSuggestion = askSuggestion;

document.addEventListener("DOMContentLoaded", function() {
	const input = document.getElementById("messageInput");
	if(input) {
		input.addEventListener("keydown", function(e) {
	if (e.key === "Enter") sendMessage();
		});
	}
	
	const toggle = document.getElementById("themeToggle");
	if(toggle) {
		toggle.addEventListener("click", toggleTheme);
	}
	
	const savedTheme = localStorage.getItem("theme") || "light";
	applyTheme(savedTheme);
	
	const accessibilityToggle = document.getElementById("accessibilityToggle");
	if(accessibilityToggle) {
		accessibilityToggle.addEventListener("click",toggleAccessibilityMode);
	}	
	const savedAccessibilityMode = localStorage.getItem("accessibilityMode") || "off";
	applyAccessibilityMode(savedAccessibilityMode === "on");

	applyEmbeddedMode();
	setupFrameResizeObserver();
});
