class TTSConverter {
    constructor() {
        this.initializeEventListeners();
        this.currentAudioUrl = null;
    }

    initializeEventListeners() {
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

        // Hide previous outputs and errors
        outputSection.style.display = 'none';
        errorMessage.style.display = 'none';

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
        }

        // Show loading state
        btnText.style.display = 'none';
        loader.style.display = 'flex';
        convertBtn.disabled = true;

        try {
            const formData = new FormData();

            if (activeTab === 'text') {
                formData.append('text', text);
            } else {
                formData.append('file', document.getElementById('fileInput').files[0]);
            }

            // Start asynchronous conversion job
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