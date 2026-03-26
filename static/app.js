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
		if(toggle) toggle.textContent = "Accessibility Mode: On";
	}
	else {
		document.body.classList.remove("accessibility-mode");
		if(toggle) toggle.textContent = "Accessibility Mode: Off";
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
});