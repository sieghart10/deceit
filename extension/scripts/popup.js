// popup.js - Fake News Detector Extension Popup
document.addEventListener('DOMContentLoaded', async function() {
    
    // DOM Elements
    const currentSiteElement = document.getElementById('current-site');
    let statusTextElement = document.getElementById('status-text');
    const toggleButton = document.getElementById('toggle-btn');
    const facebookCheckbox = document.getElementById('facebook');
    const saveButton = document.getElementById('saveSettings');
    const linkInput = document.getElementById('link-input');
    const checkButton = document.getElementById('check-btn');
    const resultElement = document.getElementById('result');

    let extensionEnabled = true;
    let facebookEnabled = true;
    let currentTab = null;
    let serverStatus = { online: false, checking: false };
    
    async function initializePopup() {
        try {
            await loadSettings();
            await getCurrentTab();
            setupEventListeners();
            await checkServerConnection();
        } catch (error) {
            console.error('Error initializing popup:', error);
            showFeedback('Error initializing popup', 'error');
        }
    }
    
    function loadSettings() {
        return new Promise((resolve) => {
            chrome.storage.sync.get(['extensionEnabled', 'facebookEnabled'], function(result) {
                extensionEnabled = result.extensionEnabled !== false; // Default to true
                facebookEnabled = result.facebookEnabled !== false; // Default to true
                
                updateUI();
                resolve();
            });
        });
    }

    function getCurrentTab() {
        return new Promise((resolve) => {
            chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
                if (tabs && tabs.length > 0) {
                    currentTab = tabs[0];
                    updateCurrentSite();
                }
                resolve();
            });
        });
    }
    
    async function checkServerConnection() {
        if (serverStatus.checking) return;
        
        serverStatus.checking = true;
        updateServerStatusUI('Checking server...');
        
        try {
            const response = await sendMessageToBackground({ action: 'checkServerStatus' });
            
            if (response.success && response.data) {
                serverStatus = {
                    online: response.data.online,
                    checking: false,
                    data: response.data.data,
                    error: response.data.error,
                    modelLoaded: response.data.modelLoaded
                };
            } else {
                serverStatus = {
                    online: false,
                    checking: false,
                    error: response.error || 'Unknown error',
                    modelLoaded: false
                };
            }
        } catch (error) {
            console.error('Error checking server status:', error);
            serverStatus = {
                online: false,
                checking: false,
                error: error.message,
                modelLoaded: false
            };
        }
        
        updateServerStatusUI();
    }
    
    function sendMessageToBackground(message) {
        return new Promise((resolve, reject) => {
            chrome.runtime.sendMessage(message, (response) => {
                if (chrome.runtime.lastError) {
                    reject(new Error(chrome.runtime.lastError.message));
                } else {
                    resolve(response);
                }
            });
        });
    }

    function updateServerStatusUI(customMessage = null) {
        if (!statusTextElement) return;
        
        if (customMessage) {
            statusTextElement.textContent = customMessage;
            statusTextElement.style.color = '#f39c12';
            return;
        }
        
        if (serverStatus.online) {
            statusTextElement.textContent = 'Server: Connected';
            statusTextElement.style.color = '#27ae60';
        } else {
            const errorMsg = serverStatus.error ? ` (${serverStatus.error})` : '';
            statusTextElement.textContent = `Server: Disconnected${errorMsg}`;
            statusTextElement.style.color = '#e74c3c';
        }
    }
    
    function updateCurrentSite() {
        if (!currentTab) {
            currentSiteElement.textContent = 'Unknown';
            return;
        }
        
        try {
            const url = new URL(currentTab.url);
            const hostname = url.hostname;
            
            if (hostname.includes('facebook.com')) {
                if (facebookEnabled && extensionEnabled) {
                    currentSiteElement.textContent = 'www.facebook.com';
                    currentSiteElement.style.color = '#27ae60'; // Green
                } else {
                    currentSiteElement.textContent = 'www.facebook.com (Disabled)';
                    currentSiteElement.style.color = '#e74c3c'; // Red
                }
            } else {
                currentSiteElement.textContent = hostname;
                currentSiteElement.style.color = '#7f8c8d'; // Gray - not supported
            }
        } catch (error) {
            currentSiteElement.textContent = 'Invalid URL';
            currentSiteElement.style.color = '#e74c3c';
        }
    }
    
    function updateUI() {
        if (extensionEnabled) {
            statusTextElement.textContent = 'Active';
            statusTextElement.style.color = '#27ae60';
            toggleButton.textContent = 'Disable';
            toggleButton.className = 'toggle-btn active';
        } else {
            statusTextElement.textContent = 'Disabled';
            statusTextElement.style.color = '#e74c3c';
            toggleButton.textContent = 'Enable';
            toggleButton.className = 'toggle-btn disabled';
        }
        
        facebookCheckbox.checked = facebookEnabled;
        
        updateCurrentSite();
    }
    
    async function checkLink() {
        const url = linkInput.value.trim();
        
        if (!url) {
            showResult('Please enter a URL', 'error');
            return;
        }
        
        if (!serverStatus.online) {
            showResult('Server is offline', 'error');
            return;
        }
        
        checkButton.disabled = true;
        checkButton.textContent = 'Checking...';
        showResult('Analyzing...', 'loading');
        
        try {
            const response = await sendMessageToBackground({
                action: 'verifyLink',
                url: url
            });
            
            if (response.success && response.data && response.data.data) {
                const data = response.data.data;
                const isFake = data.prediction === 'fake';
                const confidence = (data.confidence * 100).toFixed(1);
                
                let resultClass = isFake ? 'fake' : 'real';
                let icon = isFake ? '⚠️' : '✓';
                let resultText = `${icon} ${data.message}`;
                
                showResult(resultText, resultClass);
            } else {
                showResult(`Error: ${response.error || 'Failed to analyze'}`, 'error');
            }
        } catch (error) {
            console.error('Link check error:', error);
            showResult(`Error: ${error.message}`, 'error');
        } finally {
            checkButton.disabled = false;
            checkButton.textContent = 'Check';
        }
    }
    
    function showResult(message, type = 'info') {
        if (!resultElement) return;
        
        resultElement.textContent = message;
        resultElement.className = 'result';
        
        switch(type) {
            case 'fake':
                resultElement.style.color = '#e74c3c';
                resultElement.style.backgroundColor = '#ffeaa7';
                break;
            case 'real':
                resultElement.style.color = '#27ae60';
                resultElement.style.backgroundColor = '#d1f2eb';
                break;
            case 'error':
                resultElement.style.color = '#e74c3c';
                resultElement.style.backgroundColor = '#fab1a0';
                break;
            case 'loading':
                resultElement.style.color = '#f39c12';
                resultElement.style.backgroundColor = '#ffeaa7';
                break;
            default:
                resultElement.style.color = '#2c3e50';
                resultElement.style.backgroundColor = '#ecf0f1';
        }
        
        resultElement.style.display = 'block';
        resultElement.style.padding = '10px';
        resultElement.style.marginTop = '10px';
        resultElement.style.borderRadius = '4px';
        resultElement.style.fontSize = '12px';
        resultElement.style.fontWeight = '500';
    }
    
    function setupEventListeners() {

        toggleButton.addEventListener('click', async function() {
            extensionEnabled = !extensionEnabled;
            await saveSettings();
            updateUI();
            
            showFeedback(extensionEnabled ? 'Extension Enabled' : 'Extension Disabled');
        });
        
        facebookCheckbox.addEventListener('change', function() {
            facebookEnabled = this.checked;
            updateCurrentSite(); // Update immediately for visual feedback
        });
        
        saveButton.addEventListener('click', async function() {
            await saveSettings();
            showFeedback('Settings Saved Successfully!');
        });
        
        if (checkButton) {
            checkButton.addEventListener('click', checkLink);
        }
        
        if (linkInput) {
            linkInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    checkLink();
                }
            });
        }
        
        saveButton.addEventListener('keypress', async function(e) {
            if (e.key === 'Enter') {
                await saveSettings();
                showFeedback('Settings Saved Successfully!');
            }
        });

        const uploadButton = document.getElementById("open-uploader");
        if (uploadButton) {
            uploadButton.addEventListener("click", () => {
                chrome.tabs.create({
                    url: chrome.runtime.getURL("extension/html/upload.html")
                });
            });
        }
        
        const refreshServerButton = document.getElementById('refresh-server');
        if (refreshServerButton) {
            refreshServerButton.addEventListener('click', async function() {
                await checkServerConnection();
                showFeedback('Server status refreshed');
            });
        }
        
        if (statusTextElement) {
            statusTextElement.addEventListener('click', async function() {
                await checkServerConnection();
            });
            statusTextElement.style.cursor = 'pointer';
            statusTextElement.title = 'Click to refresh server status';
        }
    }
    
    function saveSettings() {
        return new Promise((resolve, reject) => {
            const settings = {
                extensionEnabled: extensionEnabled,
                facebookEnabled: facebookEnabled
            };
            
            chrome.storage.sync.set(settings, function() {
                if (chrome.runtime.lastError) {
                    console.error('Error saving settings:', chrome.runtime.lastError);
                    showFeedback('Error saving settings', 'error');
                    reject(new Error(chrome.runtime.lastError.message));
                } else {
                    console.log('Settings saved successfully');
                    
                    if (currentTab && currentTab.id) {
                        chrome.tabs.sendMessage(currentTab.id, {
                            action: 'settingsChanged',
                            settings: settings
                        }, function() {
                            if (chrome.runtime.lastError) {
                                console.log('Content script not available:', chrome.runtime.lastError.message);
                            }
                        });
                    }
                    resolve();
                }
            });
        });
    }
    
    function showFeedback(message, type = 'success') {
        const existingFeedback = document.querySelector('.feedback-message');
        if (existingFeedback) {
            existingFeedback.remove();
        }
        
        const feedback = document.createElement('div');
        feedback.className = `feedback-message ${type}`;
        feedback.textContent = message;
        
        Object.assign(feedback.style, {
            position: 'fixed',
            top: '10px',
            left: '50%',
            transform: 'translateX(-50%)',
            padding: '8px 16px',
            borderRadius: '4px',
            fontSize: '12px',
            fontWeight: '600',
            zIndex: '10000',
            animation: 'fadeInOut 2.5s ease-in-out',
            backgroundColor: type === 'error' ? '#e74c3c' : '#27ae60',
            color: 'white',
            boxShadow: '0 2px 8px rgba(0,0,0,0.2)'
        });
        
        if (!document.querySelector('#feedback-style')) {
            const style = document.createElement('style');
            style.id = 'feedback-style';
            style.textContent = `
                @keyframes fadeInOut {
                    0% { opacity: 0; transform: translateX(-50%) translateY(-10px); }
                    20% { opacity: 1; transform: translateX(-50%) translateY(0); }
                    80% { opacity: 1; transform: translateX(-50%) translateY(0); }
                    100% { opacity: 0; transform: translateX(-50%) translateY(-10px); }
                }
            `;
            document.head.appendChild(style);
        }
        
        document.body.appendChild(feedback);
        
        setTimeout(() => {
            if (feedback.parentNode) {
                feedback.remove();
            }
        }, 2500);
    }
    
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            window.close();
        }
        
        if (e.key === 'Enter' && e.target.tagName !== 'BUTTON' && e.target.tagName !== 'INPUT' && saveButton) {
            saveButton.click();
        }
        
        // R key to refresh server status
        if ((e.key === 'r' || e.key === 'R') && !e.target.matches('input, textarea')) {
            e.preventDefault();
            checkServerConnection();
        }
    });
    
    chrome.storage.onChanged.addListener(function(changes, namespace) {
        if (namespace === 'sync') {
            if (changes.extensionEnabled) {
                extensionEnabled = changes.extensionEnabled.newValue;
            }
            if (changes.facebookEnabled) {
                facebookEnabled = changes.facebookEnabled.newValue;
            }
            updateUI();
        }
    });

    setInterval(async () => {
        await checkServerConnection();
    }, 300000);
    
    await initializePopup();
    
    function addInteractiveEffects() {
        const buttons = document.querySelectorAll('button');
        buttons.forEach(button => {
            button.addEventListener('mouseenter', function() {
                this.style.transform = 'translateY(-1px)';
            });
            
            button.addEventListener('mouseleave', function() {
                this.style.transform = 'translateY(0)';
            });
        });
        
        document.addEventListener('click', function(e) {
            if (e.target.tagName === 'BUTTON') {
                e.target.style.transform = 'translateY(0) scale(0.98)';
                setTimeout(() => {
                    e.target.style.transform = 'translateY(-1px) scale(1)';
                }, 100);
            }
        });
    }
    
    setTimeout(addInteractiveEffects, 100);
});