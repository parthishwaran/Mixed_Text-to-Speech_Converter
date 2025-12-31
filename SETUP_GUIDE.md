# 🎤 Mixed Text-to-Speech Converter - Setup Guide

## TTS Engine Options

Your app now supports **4 TTS engines** with automatic fallback:

| Engine | Quality | Cost | Tamil Support | Setup Required |
|--------|---------|------|---------------|----------------|
| **Azure Cognitive Services** | ⭐⭐⭐⭐⭐ Excellent | Paid | Excellent | API Key |
| **Google Cloud TTS** | ⭐⭐⭐⭐ Excellent | Paid | Very Good | Credentials |
| **Edge TTS** | ⭐⭐⭐ Good | Free | Good | None |
| **gTTS** | ⭐⭐ Basic | Free | Basic | None |

---

## Quick Start (Free Engines Only)

Works out of the box with **Edge TTS** and **gTTS** - no configuration needed!

```bash
./start.sh
```

---

## Setup Premium Engines (Optional)

### Option 1: Azure Cognitive Services (Recommended for Best Quality)

**Why Azure?** Best Tamil pronunciation, natural prosody, SSML support

1. **Get API Key:**
   - Visit [Azure Portal](https://portal.azure.com)
   - Create a "Speech" resource
   - Copy your key and region

2. **Install SDK:**
   ```bash
   pip install azure-cognitiveservices-speech==1.34.0
   ```

3. **Configure:**
   ```bash
   export AZURE_SPEECH_KEY="your_key_here"
   export AZURE_SPEECH_REGION="centralindia"
   ```

4. **Pricing:** Free tier includes 500K chars/month

---

### Option 2: Google Cloud Text-to-Speech

**Why Google?** Excellent Wavenet voices, good Tamil support

1. **Get Credentials:**
   - Visit [Google Cloud Console](https://console.cloud.google.com)
   - Enable "Cloud Text-to-Speech API"
   - Create service account and download JSON key

2. **Install SDK:**
   ```bash
   pip install google-cloud-texttospeech==2.15.0
   ```

3. **Configure:**
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"
   ```

4. **Pricing:** Free tier includes 1M chars/month (WaveNet), 4M chars/month (Standard)

---

## Engine Selection

The system automatically uses the **best available engine**:

```
Azure (if configured) → Google (if configured) → Edge TTS → gTTS
```

**Force specific engine:**
```bash
export TTS_ENGINE=azure  # or: google, edge, gtts, auto
```

---

## Testing Engines

Check which engines are available:

```bash
curl http://localhost:5000/health
```

Response shows engine status:
```json
{
  "status": "healthy",
  "message": "TTS Service is running",
  "engines": {
    "azure": "configured",
    "google": "not configured",
    "edge": "available",
    "gtts": "available",
    "preferred_engine": "auto"
  }
}
```

---

## Voice Customization

Edit [backend/main.py](backend/main.py) to change voices:

```python
# Azure voices
AZURE_VOICES = {
    'ta': 'ta-IN-PallaviNeural',      # Female
    # 'ta': 'ta-IN-ValluvarNeural',   # Male
    'en': 'en-IN-NeerjaNeural',        # Female
    # 'en': 'en-IN-PrabhatNeural',    # Male
}

# Google voices
GOOGLE_VOICES = {
    'ta': {'language_code': 'ta-IN', 'name': 'ta-IN-Wavenet-A'},
    'en': {'language_code': 'en-IN', 'name': 'en-IN-Wavenet-D'},
}
```

[Browse all voices](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts)

---

## Cost Comparison (Monthly Free Tier)

- **Azure:** 500,000 characters (≈ 125,000 words)
- **Google:** 1M WaveNet + 4M Standard characters
- **Edge TTS:** Unlimited (free)
- **gTTS:** Unlimited (free)

For typical usage (10,000 words/month), **free tiers are sufficient**.

---

## Troubleshooting

**Azure not working?**
- Verify key: `echo $AZURE_SPEECH_KEY`
- Check region matches your Azure resource
- Ensure SDK installed: `pip show azure-cognitiveservices-speech`

**Google not working?**
- Verify credentials path: `echo $GOOGLE_APPLICATION_CREDENTIALS`
- Ensure API enabled in Google Cloud Console
- Check JSON file permissions: `ls -l /path/to/credentials.json`

**All engines failing?**
- Check logs in terminal for specific error messages
- Verify internet connection (all engines require online access)
- Test with simple text first

---

## Quality Comparison Example

Test the same text with different engines:

```bash
# Use Edge TTS (free)
export TTS_ENGINE=edge
curl -X POST http://localhost:5000/convert -F "text=வணக்கம் Hello" --output edge.mp3

# Use Azure (premium)
export TTS_ENGINE=azure
curl -X POST http://localhost:5000/convert -F "text=வணக்கம் Hello" --output azure.mp3
```

---

## Recommendations

- **For production/commercial:** Use **Azure** (best quality, reliable)
- **For hobbyist/free:** Use **Edge TTS** (good quality, unlimited)
- **For development:** Use **auto** mode (tries best available)
- **Offline needs:** Neither option works offline (all require internet)

---

## Need Help?

- Azure docs: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/
- Google docs: https://cloud.google.com/text-to-speech/docs
- Edge TTS: https://github.com/rany2/edge-tts
