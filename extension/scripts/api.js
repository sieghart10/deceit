class API {
    constructor(baseUrl = 'http://127.0.0.1:8000') {
        this.baseUrl = baseUrl;
        this.initialized = false;

        this.initialize();
    }

    initialize() {
        if (this.initialized) return;
        
        this.initialized = true;
        console.log('API initialized successfully');
    }
        async call(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        
        const config = {
            timeout: 30000,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        console.log(`Making ${config.method || 'GET'} request to ${url}`);
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), config.timeout);

            const response = await fetch(url, {
                ...config,
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.text().catch(() => null);
                let errorMessage;

                if (response.status === 404) {
                    errorMessage = `Resource not found: ${errorData || 'Unknown error'}`;
                } else if (response.status === 500) {
                    errorMessage = `Server error: ${errorData || 'Internal server error'}`;
                } else if (response.status === 503) {
                    errorMessage = `Service unavailable: ${errorData || 'Extension disabled'}`;
                } else {
                    errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                }

                throw new Error(errorMessage);
            }

            return await response.json();
        } catch (error) {
            console.error('API Error:', error.message);
            
            if (error.name === 'AbortError') {
                throw new Error('Request timeout - server may be slow');
            } else if (error instanceof TypeError && error.message.includes('fetch')) {
                throw new Error('Network error - check if server is running');
            }
            throw error;
        }
    }

    async checkServerStatus() {
        try {
            console.log('Checking server status...');
            const data = await this.call('/');
            console.log('Server status response:', data);
            return { online: true, data };
        } catch (error) {
            console.error('Server status check failed:', error.message);
            return { online: false, error: error.message };
        }
    }

    async predict(data) {
        try {
            console.log('data', data)
        } catch (error) {
            console.error('Error:', error.message)            
        }

    }
}
