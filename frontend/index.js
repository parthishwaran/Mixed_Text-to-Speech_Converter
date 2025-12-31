class TTSConverter {
    constructor() {
        this.initializeEventListeners();
        this.currentAudioUrl = null;
        this.apiKey = localStorage.getItem('openrouter_api_key') || '';
        this.chatHistory = [];
        this.lastAssistantResponse = '';
        
        // Initialize API key if saved
        if (this.apiKey) {
            document.getElementById('apiKeyInput').value = this.apiKey;
            this.showApiStatus('API key loaded from storage', 'success');
        }
    }

    initializeEventListeners() {
        // Section tab switching
        document.querySelectorAll('.section-tab').forEach(btn => {
            btn.addEventListener('click', (e) => this.switchSection(e.target));
        });

        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.switchTab(e.target));
        });

        // File input change
        document.getElementById('fileInput').addEventListener('change', (e) => this.handleFileSelect(e));

        // Convert button
        document.getElementById('convertBtn').addEventListener('click', () => this.convertTextToSpeech());

        // Download button
        document.getElementById('downloadBtn').addEventListener('click', () => this.downloadAudio());

        // API Key management
        document.getElementById('toggleApiKey').addEventListener('click', () => this.toggleApiKeyVisibility());
        document.getElementById('saveApiKey').addEventListener('click', () => this.saveApiKey());

        // Chat functionality
        document.getElementById('sendChatBtn').addEventListener('click', () => this.sendChatMessage());
        document.getElementById('chatInput').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendChatMessage();
            }
        });
        document.getElementById('clearChatBtn').addEventListener('click', () => this.clearChat());
        document.getElementById('speakResponseBtn').addEventListener('click', () => this.speakLastResponse());

        // AI Processing toggle
        document.getElementById('useAiProcessing').addEventListener('change', (e) => {
            const promptArea = document.getElementById('aiPromptArea');
            promptArea.style.display = e.target.checked ? 'block' : 'none';
        });
    }

    switchSection(clickedBtn) {
        // Update section tabs
        document.querySelectorAll('.section-tab').forEach(btn => btn.classList.remove('active'));
        clickedBtn.classList.add('active');

        // Update section content
        const sectionName = clickedBtn.getAttribute('data-section');
        document.querySelectorAll('.section-pane').forEach(pane => pane.classList.remove('active'));
        document.getElementById(`${sectionName}-section`).classList.add('active');
    }

    switchTab(clickedBtn) {
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        clickedBtn.classList.add('active');

        // Update tab content
        const tabName = clickedBtn.getAttribute('data-tab');
        document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
        document.getElementById(`${tabName}-tab`).classList.add('active');
    }

    handleFileSelect(event) {
        const file = event.target.files[0];
        const fileInfo = document.getElementById('fileInfo');
        const uploadArea = document.getElementById('fileUploadArea');

        if (file) {
            const fileName = file.name;
            const fileSize = (file.size / 1024 / 1024).toFixed(2); // MB

            fileInfo.innerHTML = `
                <strong>Selected File:</strong> ${fileName}<br>
                <strong>Size:</strong> ${fileSize} MB
            `;
            fileInfo.style.display = 'block';

            // Update upload area appearance
            uploadArea.style.borderColor = '#4facfe';
            uploadArea.style.background = '#f0f8ff';
        }
    }

    async convertTextToSpeech() {
        const convertBtn = document.getElementById('convertBtn');
        const btnText = convertBtn.querySelector('.btn-text');
        const loader = convertBtn.querySelector('.loader');
        const outputSection = document.getElementById('outputSection');
        const errorMessage = document.getElementById('errorMessage');
        const useAiProcessing = document.getElementById('useAiProcessing').checked;
        const useHfTts = document.getElementById('useHfTts') ? document.getElementById('useHfTts').checked : false;

        // Hide previous outputs and errors
        outputSection.style.display = 'none';
        errorMessage.style.display = 'none';
        
        // Remove previous AI result if exists
        const existingAiResult = document.getElementById('aiResultSection');
        if (existingAiResult) existingAiResult.remove();

        // Get input data based on active tab
        let text = '';
        const activeTab = document.querySelector('.tab-btn.active').getAttribute('data-tab');

        if (activeTab === 'text') {
            text = document.getElementById('textInput').value.trim();
            if (!text) {
                this.showError('Please enter some text to convert.');
                return;
            }
        } else {
            const fileInput = document.getElementById('fileInput');
            if (!fileInput.files[0]) {
                this.showError('Please select a file to upload.');
                return;
            }
            // Read file content for AI processing
            if (useAiProcessing) {
                text = await this.readFileContent(fileInput.files[0]);
            }
        }

        // Check if AI processing is enabled
        if (useAiProcessing) {
            if (!this.apiKey) {
                this.showError('Please save your OpenRouter API key in the AI Chat section first!');
                return;
            }
            const aiPrompt = document.getElementById('aiPromptInput').value.trim();
            if (!aiPrompt) {
                this.showError('Please enter instructions for the AI (e.g., "Summarize this text")');
                return;
            }
        }

        // Show loading state
        btnText.style.display = 'none';
        loader.style.display = 'flex';
        convertBtn.disabled = true;

        try {
            let textToConvert = text;

            // If AI processing is enabled, send to AI first
            if (useAiProcessing) {
                const aiPrompt = document.getElementById('aiPromptInput').value.trim();
                const progressText = document.getElementById('progressText');
                if (progressText) progressText.textContent = 'Processing with AI...';

                textToConvert = await this.processWithAI(text, aiPrompt);
                this.showAiResult(textToConvert);
            }

            if (useHfTts) {
                // Use Hugging Face TTS endpoint
                const formData = new FormData();
                formData.append('text', textToConvert);
                // Optionally, add language selection here if needed
                // formData.append('lang', 'en');
                const response = await fetch('http://localhost:5010/hf_tts', {
                    method: 'POST',
                    body: formData
                });
                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    throw new Error(err.error || 'HF TTS conversion failed');
                }
                const audioBlob = await response.blob();
                this.currentAudioUrl = URL.createObjectURL(audioBlob);
                const audioPlayer = document.getElementById('audioPlayer');
                audioPlayer.src = this.currentAudioUrl;
                outputSection.style.display = 'block';
                // Hide progress after a moment
                setTimeout(() => {
                    const progressContainer = document.getElementById('progressContainer');
                    if (progressContainer) progressContainer.style.display = 'none';
                }, 1200);
                return;
            }

            // Default: use async backend
            const formData = new FormData();
            if (activeTab === 'text' || useAiProcessing) {
                formData.append('text', textToConvert);
            } else {
                formData.append('file', document.getElementById('fileInput').files[0]);
            }
            const startRes = await fetch('http://localhost:5000/convert_async', {
                method: 'POST',
                body: formData
            });
            const startData = await startRes.json();
            if (!startRes.ok) {
                throw new Error(startData.error || 'Failed to start conversion');
            }
            const jobId = startData.job_id;
            // Show progress UI
            const progressContainer = document.getElementById('progressContainer');
            const progressFill = document.getElementById('progressFill');
            const progressLabel = document.getElementById('progressLabel');
            if (progressContainer) progressContainer.style.display = 'block';
            if (progressFill) progressFill.style.width = '0%';
            if (progressLabel) progressLabel.textContent = '0%';
            await this.trackJob(jobId, outputSection);
        } catch (error) {
            console.error('Conversion error:', error);
            this.showError(error.message || 'An error occurred during conversion. Please try again.');
        } finally {
            // Reset button state
            btnText.style.display = 'block';
            loader.style.display = 'none';
            convertBtn.disabled = false;
        }
    }

    async readFileContent(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = (e) => reject(new Error('Failed to read file'));
            reader.readAsText(file);
        });
    }

    async processWithAI(text, prompt) {
        const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.apiKey}`,
                'HTTP-Referer': window.location.origin,
                'X-Title': 'Mixed Language TTS Converter'
            },
            body: JSON.stringify({
                model: 'google/gemini-3-flash-preview',
                messages: [
                    {
                        role: 'user',
                        content: `${prompt}\n\nText to process:\n${text}`
                    }
                ]
            })
        });

        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error?.message || 'AI processing failed');
        }

        return data.choices[0].message.content;
    }

    showAiResult(text) {
        const aiProcessSection = document.querySelector('.ai-process-section');
        
        // Create result section
        const resultDiv = document.createElement('div');
        resultDiv.className = 'ai-result-section';
        resultDiv.id = 'aiResultSection';
        resultDiv.innerHTML = `
            <h4>🤖 AI Processed Result:</h4>
            <div class="ai-result-text">${this.escapeHtml(text)}</div>
        `;
        
        aiProcessSection.appendChild(resultDiv);
    }

    escapeHtml(text) {
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/\n/g, '<br>');
    }

    async trackJob(jobId, outputSection) {
        const progressText = document.getElementById('progressText');
        const progressFill = document.getElementById('progressFill');
        const progressLabel = document.getElementById('progressLabel');
        const pollIntervalMs = 1000;

        return new Promise((resolve, reject) => {
            const timer = setInterval(async () => {
                try {
                    const res = await fetch(`http://localhost:5000/progress/${jobId}`);
                    const data = await res.json();

                    if (progressText && typeof data.percent === 'number') {
                        progressText.textContent = `Processing... ${data.percent}%`;
                    }
                    if (progressFill && typeof data.percent === 'number') {
                        progressFill.style.width = `${data.percent}%`;
                    }
                    if (progressLabel && typeof data.percent === 'number') {
                        progressLabel.textContent = `${data.percent}%`;
                    }

                    if (data.status === 'finished') {
                        clearInterval(timer);
                        // Fetch final audio
                        const audioRes = await fetch(`http://localhost:5000/download/${jobId}`);
                        if (!audioRes.ok) {
                            const err = await audioRes.json().catch(() => ({}));
                            throw new Error(err.error || 'Failed to download audio');
                        }
                        const audioBlob = await audioRes.blob();
                        this.currentAudioUrl = URL.createObjectURL(audioBlob);
                        const audioPlayer = document.getElementById('audioPlayer');
                        audioPlayer.src = this.currentAudioUrl;
                        outputSection.style.display = 'block';
                        // Optionally hide progress a moment after completion
                        setTimeout(() => {
                            const progressContainer = document.getElementById('progressContainer');
                            if (progressContainer) progressContainer.style.display = 'none';
                        }, 1200);
                        resolve();
                    } else if (data.status === 'error') {
                        clearInterval(timer);
                        reject(new Error(data.error || 'Conversion failed'));
                    }
                } catch (err) {
                    clearInterval(timer);
                    reject(err);
                }
            }, pollIntervalMs);
        });
    }

    downloadAudio() {
        if (this.currentAudioUrl) {
            const a = document.createElement('a');
            a.href = this.currentAudioUrl;
            a.download = 'mixed_tts_output.mp3';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }
    }

    showError(message) {
        const errorElement = document.getElementById('errorMessage');
        errorElement.textContent = message;
        errorElement.style.display = 'block';
        
        // Scroll to error message
        errorElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    // ==================== API Key Management ====================
    
    toggleApiKeyVisibility() {
        const input = document.getElementById('apiKeyInput');
        const btn = document.getElementById('toggleApiKey');
        if (input.type === 'password') {
            input.type = 'text';
            btn.textContent = '🙈';
        } else {
            input.type = 'password';
            btn.textContent = '👁️';
        }
    }

    saveApiKey() {
        const input = document.getElementById('apiKeyInput');
        this.apiKey = input.value.trim();
        
        if (this.apiKey) {
            localStorage.setItem('openrouter_api_key', this.apiKey);
            this.showApiStatus('✓ API key saved successfully!', 'success');
        } else {
            localStorage.removeItem('openrouter_api_key');
            this.showApiStatus('API key cleared', 'error');
        }
    }

    showApiStatus(message, type) {
        const status = document.getElementById('apiStatus');
        status.textContent = message;
        status.className = 'api-status ' + type;
        
        // Auto-hide after 3 seconds
        setTimeout(() => {
            status.style.display = 'none';
        }, 3000);
    }

    // ==================== Chat Functionality ====================

    async sendChatMessage() {
        const input = document.getElementById('chatInput');
        const message = input.value.trim();
        
        if (!message) return;
        
        if (!this.apiKey) {
            this.showApiStatus('Please enter your API key first!', 'error');
            return;
        }

        // Clear input
        input.value = '';

        // Add user message to chat
        this.addMessageToChat(message, 'user');
        
        // Add to history
        this.chatHistory.push({ role: 'user', content: message });

        // Show typing indicator
        this.showTypingIndicator();

        // Disable send button
        const sendBtn = document.getElementById('sendChatBtn');
        sendBtn.disabled = true;

        try {
            const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.apiKey}`,
                    'HTTP-Referer': window.location.origin,
                    'X-Title': 'Mixed Language TTS Converter'
                },
                body: JSON.stringify({
                    model: 'google/gemini-3-flash-preview',
                    messages: this.chatHistory
                })
            });

            const data = await response.json();
            
            // Remove typing indicator
            this.hideTypingIndicator();

            if (!response.ok) {
                throw new Error(data.error?.message || 'API request failed');
            }

            const assistantMessage = data.choices[0].message.content;
            
            // Add assistant message to chat
            this.addMessageToChat(assistantMessage, 'assistant');
            
            // Save to history
            this.chatHistory.push({ role: 'assistant', content: assistantMessage });
            
            // Store last response for TTS
            this.lastAssistantResponse = assistantMessage;
            document.getElementById('speakResponseBtn').disabled = false;

        } catch (error) {
            this.hideTypingIndicator();
            this.addMessageToChat(`Error: ${error.message}`, 'assistant');
            console.error('Chat error:', error);
        } finally {
            sendBtn.disabled = false;
        }
    }

    addMessageToChat(message, role) {
        const chatMessages = document.getElementById('chatMessages');
        
        // Remove welcome message if present
        const welcome = chatMessages.querySelector('.chat-welcome');
        if (welcome) {
            welcome.remove();
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${role}`;
        
        // Format message (handle code blocks, etc.)
        messageDiv.innerHTML = this.formatMessage(message);
        
        chatMessages.appendChild(messageDiv);
        
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    formatMessage(message) {
        // Escape HTML
        let formatted = message
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        
        // Handle code blocks
        formatted = formatted.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
        
        // Handle inline code
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
        
        // Handle bold
        formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        
        // Handle line breaks
        formatted = formatted.replace(/\n/g, '<br>');
        
        return formatted;
    }

    showTypingIndicator() {
        const chatMessages = document.getElementById('chatMessages');
        const typingDiv = document.createElement('div');
        typingDiv.className = 'chat-message typing';
        typingDiv.id = 'typingIndicator';
        typingDiv.innerHTML = `
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
        chatMessages.appendChild(typingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    hideTypingIndicator() {
        const typing = document.getElementById('typingIndicator');
        if (typing) {
            typing.remove();
        }
    }

    clearChat() {
        const chatMessages = document.getElementById('chatMessages');
        chatMessages.innerHTML = `
            <div class="chat-welcome">
                <div class="welcome-icon">🤖</div>
                <h3>AI Assistant</h3>
                <p>Powered by Google Gemma 3n via OpenRouter</p>
                <p class="welcome-hint">Ask me anything! I can help with questions, writing, coding, and more.</p>
            </div>
        `;
        this.chatHistory = [];
        this.lastAssistantResponse = '';
        document.getElementById('speakResponseBtn').disabled = true;
    }

    async speakLastResponse() {
        if (!this.lastAssistantResponse) return;

        const speakBtn = document.getElementById('speakResponseBtn');
        speakBtn.disabled = true;
        speakBtn.textContent = '🔄 Converting...';

        try {
            const formData = new FormData();
            formData.append('text', this.lastAssistantResponse);

            const startRes = await fetch('http://localhost:5000/convert_async', {
                method: 'POST',
                body: formData
            });

            const startData = await startRes.json();
            if (!startRes.ok) {
                throw new Error(startData.error || 'Failed to start conversion');
            }

            const jobId = startData.job_id;

            // Poll for completion
            await this.waitForJobCompletion(jobId);

            // Fetch and play audio
            const audioRes = await fetch(`http://localhost:5000/download/${jobId}`);
            if (!audioRes.ok) {
                throw new Error('Failed to download audio');
            }
            
            const audioBlob = await audioRes.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            audio.play();

        } catch (error) {
            console.error('TTS Error:', error);
            alert('Failed to convert text to speech: ' + error.message);
        } finally {
            speakBtn.disabled = false;
            speakBtn.textContent = '🔊 Speak Last Response';
        }
    }

    async waitForJobCompletion(jobId) {
        return new Promise((resolve, reject) => {
            const timer = setInterval(async () => {
                try {
                    const res = await fetch(`http://localhost:5000/progress/${jobId}`);
                    const data = await res.json();

                    if (data.status === 'finished') {
                        clearInterval(timer);
                        resolve();
                    } else if (data.status === 'error') {
                        clearInterval(timer);
                        reject(new Error(data.error || 'Conversion failed'));
                    }
                } catch (err) {
                    clearInterval(timer);
                    reject(err);
                }
            }, 500);
        });
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new TTSConverter();
});

// Add some example text when the page loads
document.addEventListener('DOMContentLoaded', () => {
    const textInput = document.getElementById('textInput');
    if (textInput && !textInput.value) {
        textInput.value = `Hello! Welcome to our Mixed Language TTS Converter.

இது ஒரு mixed language example. This tool can seamlessly convert both Tamil and English text to speech.

How are you today? நலமாக இருக்கிறீர்களா? The audio will sound natural and clear in both languages.

Thank you for using our service! நன்றி!`;
    }
});