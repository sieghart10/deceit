// content.js - Fake News Detector Extension
class FakeNewsDetector {
    constructor() {
        this.isExtensionEnabled = true;
        this.isFacebookEnabled = true;
        this.isFacebook = window.location.hostname.includes("facebook.com");
        this.observer = null;

        this.initialize();
    }

    async initialize() {
        console.log("Content script loaded: Fake News Detector");

        await this.loadSettings();

        // Initialize API connection (via background)
        try {
            const status = await this.sendApiMessage("checkServerStatus");
            console.log("API server status:", status);
        } catch (err) {
            console.error("API not reachable:", err.message);
        }

        if (this.isExtensionEnabled && this.isFacebookEnabled && this.isFacebook) {
            this.initializeDetector();
        }

        // Watch for settings changes
        chrome.storage.onChanged.addListener((changes, namespace) => {
            if (namespace === "sync") {
                if (changes.extensionEnabled) {
                    this.isExtensionEnabled = changes.extensionEnabled.newValue;
                }
                if (changes.facebookEnabled) {
                    this.isFacebookEnabled = changes.facebookEnabled.newValue;
                }

                if (this.isExtensionEnabled && this.isFacebookEnabled && this.isFacebook) {
                    this.initializeDetector();
                } else {
                    this.removeExistingButtons();
                }
            }
        });
    }

    async loadSettings() {
        return new Promise((resolve) => {
            chrome.storage.sync.get(
                ["extensionEnabled", "facebookEnabled"],
                (result) => {
                    this.isExtensionEnabled = result.extensionEnabled !== false;
                    this.isFacebookEnabled = result.facebookEnabled !== false;
                    resolve();
                }
            );
        });
    }

    initializeDetector() {
        console.log("Initializing Fake News Detector on Facebook...");

        this.removeExistingButtons();
        setTimeout(() => this.addVerifyButtons(), 1000);

        this.setupObserver();

        setInterval(() => {
            if (this.isExtensionEnabled && this.isFacebookEnabled) {
                this.addVerifyButtons();
            }
        }, 5000);
    }

    removeExistingButtons() {
        document
            .querySelectorAll(".fake-news-verify-btn")
            .forEach((btn) => btn.remove());
    }

    addVerifyButtons() {
        // Target the main post containers with class x1lliihq
        const postContainers = document.querySelectorAll('.x1lliihq');

        postContainers.forEach((container) => {
            // Check if this container actually contains a post (has content)
            const hasPostContent = container.querySelector('[data-ad-rendering-role="story_message"], [role="article"]');
            
            if (hasPostContent && !container.querySelector(".fake-news-verify-btn")) {
                // Make sure the container has relative positioning for absolute positioning of button
                const computedStyle = window.getComputedStyle(container);
                if (computedStyle.position === 'static') {
                    container.style.position = 'relative';
                }

                const button = this.createVerifyButton(container);
                container.appendChild(button);
            }
        });
    }

    createVerifyButton(container) {
        const button = document.createElement("button");
        button.className = "fake-news-verify-btn";
        button.innerHTML = `<span class="verify-icon">Verify</span>`;

        Object.assign(button.style, {
            position: "absolute",
            top: "15px",
            right: "90px",
            // background: "#A1DD70",
            color: "black",
            border: "none",
            borderRadius: "2px",
            padding: "6px 12px",
            fontSize: "12px",
            fontWeight: "600",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "4px",
            height: "32px",
            minWidth: "60px",
            zIndex: "1000",
            // boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
            transition: "all 0.2s ease",
        });

        // Hover effects
        button.addEventListener("mouseenter", () => {
            button.style.transform = "scale(1.05)";
            button.style.boxShadow = "0 4px 12px rgba(0,0,0,0.3)";
        });

        button.addEventListener("mouseleave", () => {
            button.style.transform = "scale(1)";
            button.style.boxShadow = "0 2px 8px rgba(0,0,0,0.2)";
        });

        button.addEventListener("click", (e) => {
            e.stopPropagation();
            e.preventDefault();
            this.verifyContent(button, container);
        });

        return button;
    }

    verifyContent(button, container) {
        button.disabled = true;
        button.style.opacity = "0.7";
        button.textContent = "Analyzing...";

        const text = container.innerText || "";

        // Call the API server check first
        this.sendApiMessage("checkServerStatus")
            .then((status) => {
                console.log("API server responded:", status);

                // Continue with fake news detection
                setTimeout(() => {
                    const fake = this.detectFakeNews(text);
                    this.showResult(button, fake);
                    button.disabled = false;
                    button.style.opacity = "1";
                    button.textContent = "Verify";
                }, 2000);
            })
            .catch((err) => {
                console.error("API check failed:", err.message);

                // Still fallback to local detection so button works
                setTimeout(() => {
                    const fake = this.detectFakeNews(text);
                    this.showResult(button, fake);
                    button.disabled = false;
                    button.style.opacity = "1";
                    button.textContent = "Verify";
                }, 2000);
            });
    }

    detectFakeNews(text) {
        const fakeKeywords = ["breaking", "shocking", "miracle cure", "secret"];
        return fakeKeywords.some((word) =>
            text.toLowerCase().includes(word)
        );
    }

    showResult(button, isFake) {
        const message = isFake ? "✗ Fake News Detected" : "✔ Real News";
        const bgColor = isFake ? "#A23131" : "#4CAF50";

        this.showToast(message, bgColor);
        
        // Also update button appearance temporarily
        const originalBg = button.style.background;
        button.style.background = bgColor;
        button.textContent = isFake ? "Fake" : "Real";
        
        setTimeout(() => {
            button.style.background = originalBg;
            button.textContent = "Verify";
        }, 3000);
    }

    showToast(message, bgColor = "#333") {
        let toast = document.createElement("div");
        toast.textContent = message;
        Object.assign(toast.style, {
            position: "fixed",
            bottom: "20px",
            left: "20px",
            background: bgColor,
            color: "white",
            padding: "10px 16px",
            borderRadius: "6px",
            fontSize: "13px",
            fontWeight: "500",
            zIndex: "9999",
            opacity: "10%",
            transition: "opacity 0.6s ease, transform 0.6s ease",
            transform: "translateY(20px)",
            boxShadow: "0 4px 12px rgba(0,0,0,0.3)"
        });

        document.body.appendChild(toast);

        // Trigger animation
        requestAnimationFrame(() => {
            toast.style.opacity = "1";
            toast.style.transform = "translateY(0)";
        });

        // Auto remove after 3s
        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(20px)";
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    setupObserver() {
        if (this.observer) this.observer.disconnect();

        this.observer = new MutationObserver(() => {
            if (this.isExtensionEnabled && this.isFacebookEnabled) {
                // Debounce the button addition to avoid too many calls
                clearTimeout(this.observerTimeout);
                this.observerTimeout = setTimeout(() => {
                    this.addVerifyButtons();
                }, 500);
            }
        });

        this.observer.observe(document.body, {
            childList: true,
            subtree: true,
        });
    }

    sendApiMessage(action, payload = {}) {
        return new Promise((resolve, reject) => {
            chrome.runtime.sendMessage({ action, payload }, (response) => {
                if (chrome.runtime.lastError) {
                    return reject(
                        new Error(chrome.runtime.lastError.message)
                    );
                }
                if (!response) {
                    return reject(new Error("No response from background"));
                }
                if (response.success) {
                    resolve(response.data);
                } else {
                    reject(new Error(response.error || "Unknown error"));
                }
            });
        });
    }
}

// --- Bootstrap ---
let detector = null;

function initializeDetector() {
    if (!detector) {
        detector = new FakeNewsDetector();
        window.fakeNewsDetector = detector; // expose for debugging
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeDetector);
} else {
    initializeDetector();
}

window.addEventListener("load", () => {
    setTimeout(() => {
        if (detector) {
            detector.addVerifyButtons();
        }
    }, 2000);
});