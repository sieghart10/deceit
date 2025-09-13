// popup.js - Fake News Detector Extension Popup
document.addEventListener('DOMContentLoaded', function() {
    
    // DOM Elements
    const currentSiteElement = document.getElementById('current-site');
    const statusTextElement = document.getElementById('status-text');
    const toggleButton = document.getElementById('toggle-btn');
    const facebookCheckbox = document.getElementById('facebook');
    const saveButton = document.getElementById('saveSettings');
    
    // State variables
    let extensionEnabled = true;
    let facebookEnabled = true;
    let currentTab = null;
    
    // Initialize popup
    function initializePopup() {
        loadSettings();
        getCurrentTab();
        setupEventListeners();
    }
    
    // Load settings from storage
    function loadSettings() {
        chrome.storage.sync.get(['extensionEnabled', 'facebookEnabled'], function(result) {
            extensionEnabled = result.extensionEnabled !== false; // Default to true
            facebookEnabled = result.facebookEnabled !== false; // Default to true
            
            updateUI();
        });
    }
    
    // Get current tab information
    function getCurrentTab() {
        chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
            if (tabs && tabs.length > 0) {
                currentTab = tabs[0];
                updateCurrentSite();
            }
        });
    }
    
    // Update current site display
    function updateCurrentSite() {
        if (!currentTab) {
            currentSiteElement.textContent = 'Unknown';
            return;
        }
        
        try {
            const url = new URL(currentTab.url);
            const hostname = url.hostname;
            
            // Check if it's Facebook and extension is enabled for it
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
    
    // Update UI elements
    function updateUI() {
        // Update extension status
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
        
        // Update Facebook checkbox
        facebookCheckbox.checked = facebookEnabled;
        
        // Update current site display
        updateCurrentSite();
    }
    
    // Setup event listeners
    function setupEventListeners() {
        // Toggle button click
        toggleButton.addEventListener('click', function() {
            extensionEnabled = !extensionEnabled;
            saveSettings();
            updateUI();
            
            // Show feedback
            showFeedback(extensionEnabled ? 'Extension Enabled' : 'Extension Disabled');
        });
        
        // Facebook checkbox change
        facebookCheckbox.addEventListener('change', function() {
            facebookEnabled = this.checked;
            updateCurrentSite(); // Update immediately for visual feedback
        });
        
        // Save button click
        saveButton.addEventListener('click', function() {
            saveSettings();
            showFeedback('Settings Saved Successfully!');
        });
        
        // Enter key on save button
        saveButton.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                saveSettings();
                showFeedback('Settings Saved Successfully!');
            }
        });
    }
    
    // Save settings to storage
    function saveSettings() {
        const settings = {
            extensionEnabled: extensionEnabled,
            facebookEnabled: facebookEnabled
        };
        
        chrome.storage.sync.set(settings, function() {
            if (chrome.runtime.lastError) {
                console.error('Error saving settings:', chrome.runtime.lastError);
                showFeedback('Error saving settings', 'error');
            } else {
                console.log('Settings saved successfully');
                
                // Notify content scripts about the change
                if (currentTab && currentTab.id) {
                    chrome.tabs.sendMessage(currentTab.id, {
                        action: 'settingsChanged',
                        settings: settings
                    }, function() {
                        // Ignore errors if content script isn't loaded
                        if (chrome.runtime.lastError) {
                            console.log('Content script not available:', chrome.runtime.lastError.message);
                        }
                    });
                }
            }
        });
    }
    
    // Show feedback message
    function showFeedback(message, type = 'success') {
        // Remove existing feedback
        const existingFeedback = document.querySelector('.feedback-message');
        if (existingFeedback) {
            existingFeedback.remove();
        }
        
        // Create feedback element
        const feedback = document.createElement('div');
        feedback.className = `feedback-message ${type}`;
        feedback.textContent = message;
        
        // Style the feedback
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
        
        // Add CSS animation if not exists
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
        
        // Add to DOM
        document.body.appendChild(feedback);
        
        // Remove after animation
        setTimeout(() => {
            if (feedback.parentNode) {
                feedback.remove();
            }
        }, 2500);
    }
    
    // Handle keyboard navigation
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            window.close();
        }
        
        if (e.key === 'Enter' && e.target.tagName !== 'BUTTON' && saveButton) {
            saveButton.click();
        }
    });
    
    // Handle extension updates
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
    
    // Initialize everything when DOM is ready
    initializePopup();
    
    // Add some interactive effects
    function addInteractiveEffects() {
        // Add hover effects to buttons
        const buttons = document.querySelectorAll('button');
        buttons.forEach(button => {
            button.addEventListener('mouseenter', function() {
                this.style.transform = 'translateY(-1px)';
            });
            
            button.addEventListener('mouseleave', function() {
                this.style.transform = 'translateY(0)';
            });
        });
        
        // Add click animation
        document.addEventListener('click', function(e) {
            if (e.target.tagName === 'BUTTON') {
                e.target.style.transform = 'translateY(0) scale(0.98)';
                setTimeout(() => {
                    e.target.style.transform = 'translateY(-1px) scale(1)';
                }, 100);
            }
        });
    }
    
    // Add effects after initialization
    setTimeout(addInteractiveEffects, 100);
});