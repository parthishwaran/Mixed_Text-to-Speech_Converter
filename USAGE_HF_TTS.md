# Usage: Hugging Face TTS in Web UI

## How to use the ai4bharat/indic-parler-tts model from the web interface

1. **Start the backend servers:**
   - Run your main backend (for default TTS):
     ```bash
     python3 backend/main.py
     ```
   - Run the Hugging Face TTS backend:
     ```bash
     python3 backend/hf_tts.py
     ```

2. **Open the web UI:**
   - Open `frontend/index.html` in your browser (or use your preferred local server).

3. **Convert text to speech:**
   - Enter your text in the input box (supports mixed Tamil and English).
   - **To use the Hugging Face model:** Check the box labeled:
     > Use Hugging Face ai4bharat/indic-parler-tts (high quality, slower)
   - Click **Convert to Speech**.
   - Wait for the audio to be generated (may take a few seconds).
   - When ready, you can play or download the MP3.

4. **Notes:**
   - The Hugging Face model is slower but produces higher quality speech.
   - Make sure your `.env` file contains a valid `TTS_HF_TOKEN`.
   - If you see errors, check the terminal for backend logs.

---

For any issues, ensure both backend servers are running and accessible at the correct ports (default: 5000 for main, 5010 for HF TTS).
