from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from gtts import gTTS
import edge_tts
import asyncio
import os
import tempfile
import json
from langdetect import detect, LangDetectException
from pydub import AudioSegment
from pydub.silence import detect_silence
import docx
import io
import re
import uuid
import threading
import time
# Try to import Azure and Google Cloud SDKs
try:
    import azure.cognitiveservices.speech as speechsdk
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    speechsdk = None

try:
    from google.cloud import texttospeech as google_tts_client
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    google_tts_client = None


app = Flask(__name__)
CORS(app)

# Create temp directory for audio files
TEMP_DIR = tempfile.mkdtemp()

# In-memory job progress tracking
JOBS = {}

# TTS Engine Configuration Priority: azure > google > edge > gtts
TTS_CONFIG = {
    'azure_key': os.getenv('AZURE_SPEECH_KEY'),
    'azure_region': os.getenv('AZURE_SPEECH_REGION', 'centralindia'),
    'google_credentials': os.getenv('GOOGLE_APPLICATION_CREDENTIALS'),
    'preferred_engine': os.getenv('TTS_ENGINE', 'auto'),  # auto, azure, google, edge, gtts
}

# Azure voices - Superior quality for Indian languages
AZURE_VOICES = {
    'ta': 'ta-IN-PallaviNeural',  # Tamil female
    'en': 'en-IN-NeerjaNeural',   # Indian English female
}

# Google Cloud voices - Excellent quality
GOOGLE_VOICES = {
    'ta': {'language_code': 'ta-IN', 'name': 'ta-IN-Standard-A'},
    'en': {'language_code': 'en-IN', 'name': 'en-IN-Wavenet-D'},
}

# Edge TTS voices - Free, good quality
EDGE_VOICES = {
    'ta': 'ta-IN-PallaviNeural',
    'en': 'en-IN-NeerjaNeural',
}

def _init_job(job_id: str):
    JOBS[job_id] = {
        'status': 'queued',
        'percent': 0,
        'message': 'Queued',
        'output_path': None,
        'error': None,
        'updated': time.time(),
    }

def _set_progress(job_id: str, percent: int, message: str = None):
    job = JOBS.get(job_id)
    if not job:
        return
    job['percent'] = max(0, min(100, int(percent)))
    if message is not None:
        job['message'] = message
    job['updated'] = time.time()

def _set_status(job_id: str, status: str, message: str = None):
    job = JOBS.get(job_id)
    if not job:
        return
    job['status'] = status
    if message is not None:
        job['message'] = message
    job['updated'] = time.time()

def extract_text_from_docx(file_stream):
    """Extract text from DOCX file"""
    doc = docx.Document(io.BytesIO(file_stream.read()))
    full_text = []
    for paragraph in doc.paragraphs:
        full_text.append(paragraph.text)
    return '\n'.join(full_text)

# Common Tamil words written in English (Tanglish)
TANGLISH_WORDS = {
    'romba', 'nalla', 'enna', 'epdi', 'enga', 'inga', 'anga', 'ippo', 'appo',
    'thaan', 'than', 'illa', 'illai', 'iruku', 'irukku', 'iruken', 'irukken',
    'panna', 'pannunga', 'sollu', 'sollungo', 'vaanga', 'ponga', 'vanga',
    'aamam', 'aama', 'seri', 'sariya', 'konjam', 'koncham', 'kastam',
    'bore', 'adikkudhu', 'adikuthu', 'podhu', 'pothum', 'venum', 'vendum',
    'theriyum', 'therla', 'theriyala', 'puriyala', 'puriyuthu', 'mudiala',
    'mudiyum', 'mudiyathu', 'paravala', 'parava', 'nandri', 'vanakkam',
    'poi', 'vaa', 'va', 'pa', 'da', 'di', 'ma', 'ya', 'ya', 'la', 'le',

def generate_azure_audio(text, lang='en'):
    """Generate audio using Azure Cognitive Services (Highest Quality)"""
            if not AZURE_AVAILABLE:
                raise Exception("Azure SDK not installed")
    try:
        if not TTS_CONFIG['azure_key']:
            raise Exception("Azure API key not configured")
        
        speech_config = speechsdk.SpeechConfig(
            subscription=TTS_CONFIG['azure_key'],
            region=TTS_CONFIG['azure_region']
        )
        speech_config.speech_synthesis_voice_name = AZURE_VOICES[lang]
        
        # Use SSML for better prosody and naturalness
        ssml_text = f"""
        <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{lang}-IN'>
            <voice name='{AZURE_VOICES[lang]}'>
                <prosody rate='0.95' pitch='+0%'>
                    {text}
                </prosody>
            </voice>
        </speak>
        """
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav', dir=TEMP_DIR) as tmp_file:
            tmp_path = tmp_file.name
        
        audio_config = speechsdk.audio.AudioOutputConfig(filename=tmp_path)
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config,
            audio_config=audio_config
        )
        
        result = synthesizer.speak_ssml_async(ssml_text).get()
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            audio = AudioSegment.from_wav(tmp_path)
            audio = audio + AudioSegment.silent(duration=250)
            return audio, 'azure'
        else:
            raise Exception(f"Azure TTS failed: {result.reason}")
    
    except Exception as e:
        print(f"Azure TTS error: {e}")
        return None, None

def generate_google_audio(text, lang='en'):
    """Generate audio using Google Cloud Text-to-Speech (Excellent Quality)"""
            if not GOOGLE_AVAILABLE:
                raise Exception("Google Cloud SDK not installed")
    try:
        if not TTS_CONFIG['google_credentials']:
            raise Exception("Google credentials not configured")
        
        client = google_tts_client.TextToSpeechClient()
        
        synthesis_input = google_tts_client.SynthesisInput(text=text)
        
        voice_config = GOOGLE_VOICES[lang]
        voice = google_tts_client.VoiceSelectionParams(
            language_code=voice_config['language_code'],
            name=voice_config['name']
        )
        
        audio_config = google_tts_client.AudioConfig(
            audio_encoding=google_tts_client.AudioEncoding.MP3,
            speaking_rate=0.95,
            pitch=0.0
        )
        
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir=TEMP_DIR) as tmp_file:
            tmp_file.write(response.audio_content)
            tmp_path = tmp_file.name
        
        audio = AudioSegment.from_mp3(tmp_path)
        audio = audio + AudioSegment.silent(duration=250)
        return audio, 'google'
    
    except Exception as e:
        print(f"Google TTS error: {e}")
        return None, None

    'kku', 'ku', 'thala', 'anna', 'akka', 'amma', 'appa', 'thangachi',
    'thambi', 'macha', 'machan', 'machaan', 'nanba', 'nanban', 'dei', 'dey',
    'apdiya', 'apdi', 'ipdiya', 'ipdi', 'yenda', 'yenada', 'yen', 'yaar',
    'evlo', 'evalavu', 'etna', 'ethana', 'eppadi', 'yepdi', 'yenge', 'enga',
    'kaasu', 'panam', 'velai', 'vela', 'venum', 'venaam', 'thevai',
    'saptu', 'sapadu', 'saapdu', 'kudikka', 'kudicha', 'poyiten', 'vandhuten',
    'solluren', 'keluren', 'parkuren', 'paakuren', 'poren', 'poidren',
    'super', 'mass', 'thara', 'level', 'mokka', 'jolly', 'cool', 'vera',
    'ooru', 'oor', 'veedu', 'veetu', 'kadai', 'office', 'school', 'college',
    'friend', 'friends', 'guys', 'bro', 'bha', 'ji'
}

def detect_language(text):
    """Detect if text is Tamil or English with Tanglish support"""
    try:
        text_lower = text.lower().strip()
        
        # Check for Tamil Unicode characters
        tamil_chars = re.findall(r'[\u0B80-\u0BFF]', text)
        if tamil_chars:
            return 'ta'
        
        # Check if it's a known Tanglish word
        word_clean = re.sub(r'[^\w]', '', text_lower)
        if word_clean in TANGLISH_WORDS:
            return 'ta-en'  # Tanglish - Tamil word in English script
        
        # For short texts, default to English
        if len(text.strip()) < 3:
            return 'en'
        
        lang = detect(text)
        return lang
    except LangDetectException:
        return 'en'

def split_mixed_text(text):
    """Split text into segments based on language"""
    # Split by sentences while preserving punctuation
    sentences = re.split(r'([.!?]+[\s]*)', text)
    
    # Reconstruct sentences with their punctuation
    reconstructed = []
    i = 0
    while i < len(sentences):
        if i + 1 < len(sentences) and re.match(r'[.!?]+[\s]*', sentences[i+1]):
            reconstructed.append(sentences[i] + sentences[i+1])
            i += 2
        else:
            if sentences[i].strip():
                reconstructed.append(sentences[i])
            i += 1
    
    segments = []
    for sentence in reconstructed:
        if not sentence.strip():
            continue
            
        # Further split by language boundaries within sentence
        current_segment = ""
        current_lang = None
        
        words = sentence.split()
        for word in words:
            word_lang = detect_language(word)
            
            # Normalize language (treat ta-en as ta for grouping)
            normalized_lang = 'ta' if word_lang in ['ta', 'ta-en'] else 'en'
            
            if current_lang is None:
                current_lang = normalized_lang
                current_segment = word
            elif current_lang == normalized_lang:
                current_segment += " " + word
            else:
                # Language change detected
                if current_segment.strip():
                    segments.append((current_segment.strip(), current_lang))
                current_lang = normalized_lang
                current_segment = word
        
        if current_segment.strip():
            segments.append((current_segment.strip(), current_lang))
    
    return segments

async def generate_audio_with_retry(text, voice, max_retries=3):
    """Generate audio with retry logic for reliability"""
    last_error = None
    
    for attempt in range(max_retries):
        try:
            # Add slight rate adjustment for clarity
            communicate = edge_tts.Communicate(text, voice, rate="-5%", pitch="+0Hz")
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir=TEMP_DIR) as tmp_file:
                tmp_path = tmp_file.name
                await communicate.save(tmp_path)
                
            # Load and process audio
            audio = AudioSegment.from_mp3(tmp_path)
            # Add small pause at the end for natural speech flow
            audio = audio + AudioSegment.silent(duration=250)
            
            return audio
        except Exception as e:
            last_error = e
            print(f"Attempt {attempt + 1} failed for voice {voice}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5)  # Brief delay before retry
    
    raise last_error

async def generate_english_audio(text, voice="en-IN-NeerjaNeural"):
    """Generate English audio using Edge TTS with Indian English voice for better accent match"""
    try:
        return await generate_audio_with_retry(text, voice)
    except Exception as e:
        print(f"Error generating English audio: {e}")
        # Fallback to gTTS for English
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir=TEMP_DIR) as tmp_file:
                tts = gTTS(text=text, lang='en', slow=False)
                tts.save(tmp_file.name)
            audio = AudioSegment.from_mp3(tmp_file.name)
            audio = audio + AudioSegment.silent(duration=250)
            return audio
        except Exception as e2:
            print(f"Fallback gTTS also failed: {e2}")
            return AudioSegment.silent(duration=1000)

async def generate_tamil_audio(text, voice="ta-IN-PallaviNeural"):
    """Generate Tamil audio using Edge TTS for better pronunciation"""
    try:
        # Use slightly slower rate for Tamil clarity
        communicate = edge_tts.Communicate(text, voice, rate="-10%", pitch="+0Hz")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir=TEMP_DIR) as tmp_file:
            tmp_path = tmp_file.name
            await communicate.save(tmp_path)
            
        # Load and process audio
        audio = AudioSegment.from_mp3(tmp_path)
        # Add small pause at the end
        audio = audio + AudioSegment.silent(duration=250)
        
        return audio
    except Exception as e:
        print(f"Error generating Tamil audio with Edge TTS: {e}")
        # Fallback to gTTS if Edge TTS fails
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir=TEMP_DIR) as tmp_file:
                tts = gTTS(text=text, lang='ta', slow=True)  # Slow for clarity
                tts.save(tmp_file.name)
            audio = AudioSegment.from_mp3(tmp_file.name)
            audio = audio + AudioSegment.silent(duration=250)
            return audio
        except Exception as e2:
            print(f"Fallback gTTS also failed: {e2}")
            return AudioSegment.silent(duration=1000)

async def process_text_to_speech(text, job_id: str = None):
    """Main function to process text and generate mixed-language audio"""
    print(f"Processing text: {text[:100]}...")
    
    # Split text into language segments
    if job_id:
        _set_progress(job_id, 5, 'Splitting text into segments')
    segments = split_mixed_text(text)
    print(f"Detected {len(segments)} segments")
    if job_id:
        _set_progress(job_id, 10, f'Detected {len(segments)} segments')
    
    audio_segments = []
    
    total = max(1, len(segments))
    for i, (segment_text, lang) in enumerate(segments):
        print(f"Segment {i+1}: {lang} - {segment_text[:50]}...")
        
        try:
            if lang == 'ta':  # Tamil
                audio_segment = await generate_tamil_audio(segment_text)
            else:  # English
                audio_segment = await generate_english_audio(segment_text)
            
            audio_segments.append(audio_segment)
            
        except Exception as e:
            print(f"Error processing segment {i+1}: {e}")
            # Add silent segment as fallback
            audio_segments.append(AudioSegment.silent(duration=1000))
        finally:
            if job_id:
                # Allocate 80% of progress to segment processing
                cur = 10 + int(((i + 1) / total) * 80)
                _set_progress(job_id, cur, f'Processed segment {i+1}/{total}')
    
    if not audio_segments:
        raise Exception("No audio segments were generated")
    
    # Combine all audio segments
    print("Combining audio segments...")
    if job_id:
        _set_progress(job_id, 92, 'Combining audio segments')
    combined_audio = audio_segments[0]
    for segment in audio_segments[1:]:
        combined_audio = combined_audio + segment
    
    # Export final audio
    output_path = os.path.join(TEMP_DIR, "mixed_output.mp3")
    combined_audio.export(output_path, format="mp3", bitrate="192k")
    
    print("Audio generation completed successfully")
    if job_id:
        _set_progress(job_id, 100, 'Completed')
    return output_path

def _run_conversion_job(job_id: str, text: str):
    """Run the conversion job in a background thread using its own event loop."""
    try:
        _set_status(job_id, 'running', 'Starting conversion')
        # Run the async pipeline in this thread
        output_path = asyncio.run(process_text_to_speech(text, job_id=job_id))
        job = JOBS.get(job_id, {})
        job['output_path'] = output_path
        _set_status(job_id, 'finished', 'Conversion completed')
        _set_progress(job_id, 100, 'Completed')
    except Exception as e:
        job = JOBS.get(job_id, {})
        job['error'] = str(e)
        _set_status(job_id, 'error', f'Conversion failed: {e}')

@app.route('/convert', methods=['POST'])
async def convert_text_to_speech():
    """Main endpoint for text-to-speech conversion"""
    try:
        text = ""
        
        # Check if text was provided directly
        if 'text' in request.form and request.form['text'].strip():
            text = request.form['text'].strip()
        # Check if file was uploaded
        elif 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            filename = file.filename.lower()
            
            if filename.endswith('.txt'):
                text = file.read().decode('utf-8')
            elif filename.endswith('.docx'):
                text = extract_text_from_docx(file)
            else:
                return jsonify({'error': 'Unsupported file type. Use .txt or .docx'}), 400
        else:
            return jsonify({'error': 'No text or file provided'}), 400
        
        if not text.strip():
            return jsonify({'error': 'No text content found'}), 400
        
        # Process text and generate audio
        output_path = await process_text_to_speech(text)
        
        return send_file(
            output_path,
            as_attachment=True,
            download_name='mixed_tts_output.mp3',
            mimetype='audio/mpeg'
        )
        
    except Exception as e:
        print(f"Error in conversion: {str(e)}")
        return jsonify({'error': f'Conversion failed: {str(e)}'}), 500

@app.route('/convert_async', methods=['POST'])
def convert_text_to_speech_async():
    """Start an async conversion job and return a job_id for progress polling."""
    try:
        text = ""

        if 'text' in request.form and request.form['text'].strip():
            text = request.form['text'].strip()
        elif 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            filename = file.filename.lower()
            if filename.endswith('.txt'):
                text = file.read().decode('utf-8')
            elif filename.endswith('.docx'):
                text = extract_text_from_docx(file)
            else:
                return jsonify({'error': 'Unsupported file type. Use .txt or .docx'}), 400
        else:
            return jsonify({'error': 'No text or file provided'}), 400

        if not text.strip():
            return jsonify({'error': 'No text content found'}), 400

        job_id = uuid.uuid4().hex
        _init_job(job_id)

        # Start background thread
        t = threading.Thread(target=_run_conversion_job, args=(job_id, text), daemon=True)
        t.start()

        return jsonify({'job_id': job_id}), 202
    except Exception as e:
        print(f"Error starting async conversion: {e}")
        return jsonify({'error': f'Failed to start conversion: {str(e)}'}), 500

@app.route('/progress/<job_id>', methods=['GET'])
def get_progress(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    # Do not expose internal paths
    result = {k: v for k, v in job.items() if k != 'output_path'}
    return jsonify(result)

@app.route('/download/<job_id>', methods=['GET'])
def download_result(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    if job.get('status') != 'finished' or not job.get('output_path'):
        return jsonify({'error': 'Job not finished'}), 400
    return send_file(
        job['output_path'],
        as_attachment=True,
        download_name='mixed_tts_output.mp3',
        mimetype='audio/mpeg'
    )

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'TTS Service is running'})

if __name__ == '__main__':
    # Ensure temp directory exists
    os.makedirs(TEMP_DIR, exist_ok=True)
    app.run(debug=True, port=5000)