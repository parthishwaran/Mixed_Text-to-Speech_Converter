from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
import torch
import soundfile as sf
# Add Hugging Face model config
HF_TTS_MODEL = "ai4bharat/indic-parler-tts"
HF_TTS_LANGS = {
    'ta': 'ta',
    'en': 'en',
}

# Load model and processor globally (lazy init)
hf_tts_model = None
hf_tts_processor = None
hf_tts_pipe = None

def generate_hf_tts_audio(text, lang='en'):
    """Generate audio using ai4bharat/indic-parler-tts from Hugging Face"""
    global hf_tts_model, hf_tts_processor, hf_tts_pipe
    if hf_tts_model is None or hf_tts_processor is None or hf_tts_pipe is None:
        hf_tts_model = AutoModelForSpeechSeq2Seq.from_pretrained(HF_TTS_MODEL)
        hf_tts_processor = AutoProcessor.from_pretrained(HF_TTS_MODEL)
        hf_tts_pipe = pipeline(
            "text-to-speech",
            model=hf_tts_model,
            tokenizer=hf_tts_processor,
            feature_extractor=hf_tts_processor,
            device=0 if torch.cuda.is_available() else -1
        )
    lang_code = HF_TTS_LANGS.get(lang, 'en')
    # The pipeline expects a dict with 'text' and 'lang'
    result = hf_tts_pipe({"text": text, "lang": lang_code})
    # Save to temp wav file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav', dir=TEMP_DIR) as tmp_file:
        sf.write(tmp_file.name, result["audio"], result["sampling_rate"])
        audio = AudioSegment.from_wav(tmp_file.name)
    return audio, 'hf-tts'
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

app = Flask(__name__)
CORS(app)

# Create temp directory for audio files
TEMP_DIR = tempfile.mkdtemp()

# In-memory job progress tracking
JOBS = {}

# TTS engine configuration priority: gtts > edge (gTTS is faster for most cases)
TTS_CONFIG = {
    'preferred_engine': os.getenv('TTS_ENGINE', 'gtts'),  # gtts, edge, auto
}

# Cache for language detection to avoid redundant detections
LANG_DETECT_CACHE = {}

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
    """Detect if text is Tamil or English with Tanglish support (cached)"""
    text_lower = text.lower().strip()
    
    # Check cache first
    if text_lower in LANG_DETECT_CACHE:
        return LANG_DETECT_CACHE[text_lower]
    
    try:
        # Check for Tamil Unicode characters
        tamil_chars = re.findall(r'[\u0B80-\u0BFF]', text)
        if tamil_chars:
            result = 'ta'
        else:
            # Check if it's a known Tanglish word
            word_clean = re.sub(r'[^\w]', '', text_lower)
            if word_clean in TANGLISH_WORDS:
                result = 'ta-en'  # Tanglish - Tamil word in English script
            # For short texts, default to English
            elif len(text.strip()) < 3:
                result = 'en'
            else:
                result = detect(text)
        
        # Cache the result
        LANG_DETECT_CACHE[text_lower] = result
        return result
    except LangDetectException:
        result = 'en'
        LANG_DETECT_CACHE[text_lower] = result
        return result

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

# ============================================================================
# TTS ENGINE IMPLEMENTATIONS
# ============================================================================

async def generate_edge_audio(text, lang='en'):
    """Generate audio using Edge TTS (Free, Good Quality)"""
    try:
        voice = EDGE_VOICES[lang]
        # Slightly faster playback for both languages
        rate = "-2%" if lang == 'ta' else "+5%"
        
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir=TEMP_DIR) as tmp_file:
            tmp_path = tmp_file.name
            await communicate.save(tmp_path)
        
        audio = AudioSegment.from_mp3(tmp_path)
        return audio, 'edge'
    
    except Exception as e:
        print(f"Edge TTS error: {e}")
        return None, None

def generate_gtts_audio(text, lang='en'):
    """Generate audio using gTTS (Fallback, Basic Quality)"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir=TEMP_DIR) as tmp_file:
            tmp_path = tmp_file.name
            # Use faster speed for all languages
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(tmp_path)
        
        audio = AudioSegment.from_mp3(tmp_path)
        return audio, 'gtts'
    
    except Exception as e:
        print(f"gTTS error: {e}")
        return None, None

async def generate_audio_smart(text, lang='en'):
    """Smart audio generation with automatic fallback cascade"""
    engines_tried = []
    
    # Determine engine priority based on config
    preferred = TTS_CONFIG['preferred_engine']
    
    # Try Hugging Face TTS first if set
    if preferred in ['hf-tts', 'auto']:
        try:
            audio, engine = generate_hf_tts_audio(text, lang)
            if audio:
                print(f"✓ Generated with HF TTS ({lang})")
                return audio, engine
            engines_tried.append('hf-tts')
        except Exception as e:
            print(f"HF TTS error: {e}")
            engines_tried.append('hf-tts')
    # Try gTTS
    if preferred in ['gtts', 'auto']:
        audio, engine = generate_gtts_audio(text, lang)
        if audio:
            print(f"✓ Generated with gTTS ({lang})")
            return audio, engine
        engines_tried.append('gtts')
    # Fallback to Edge TTS
    if preferred in ['edge', 'auto']:
        audio, engine = await generate_edge_audio(text, lang)
        if audio:
            print(f"✓ Generated with Edge TTS ({lang})")
            return audio, engine
        engines_tried.append('edge')
    raise Exception(f"All TTS engines failed. Tried: {', '.join(engines_tried)}")

async def generate_english_audio(text):
    """Generate English audio with smart engine selection"""
    audio, engine = await generate_audio_smart(text, 'en')
    return audio

async def generate_tamil_audio(text):
    """Generate Tamil audio with smart engine selection"""
    audio, engine = await generate_audio_smart(text, 'ta')
    return audio

# ============================================================================
# MAIN TTS PROCESSING
# ============================================================================

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
    
    total = max(1, len(segments))
    
    # Generate audio for all segments in parallel
    async def generate_segment_audio(i, segment_text, lang):
        """Generate audio for a single segment"""
        print(f"Segment {i+1}: {lang} - {segment_text[:50]}...")
        try:
            if lang == 'ta':  # Tamil
                audio = await generate_tamil_audio(segment_text)
            else:  # English
                audio = await generate_english_audio(segment_text)
            if job_id:
                cur = 10 + int(((i + 1) / total) * 80)
                _set_progress(job_id, cur, f'Processed segment {i+1}/{total}')
            return audio
        except Exception as e:
            print(f"Error processing segment {i+1}: {e}")
            if job_id:
                cur = 10 + int(((i + 1) / total) * 80)
                _set_progress(job_id, cur, f'Processed segment {i+1}/{total}')
            return AudioSegment.silent(duration=1000)
    
    # Run all segment generation tasks in parallel
    tasks = [generate_segment_audio(i, segment_text, lang) for i, (segment_text, lang) in enumerate(segments)]
    audio_segments = await asyncio.gather(*tasks)
    
    if not audio_segments:
        raise Exception("No audio segments were generated")
    
    # Combine all audio segments with minimal gap between language switches
    print("Combining audio segments...")
    if job_id:
        _set_progress(job_id, 92, 'Combining audio segments')
    combined_audio = audio_segments[0]
    for i, segment in enumerate(segments[1:], 1):
        # Add 5ms gap only when language changes, otherwise join directly
        prev_lang = segments[i-1][1]
        curr_lang = segment[1]
        if prev_lang != curr_lang:
            combined_audio = combined_audio + AudioSegment.silent(duration=0.005)
        combined_audio = combined_audio + audio_segments[i]
    
    # Speed up the final audio by 25%
    faster_audio = combined_audio.speedup(playback_speed=1.25, chunk_size=150, crossfade=25)
    output_path = os.path.join(TEMP_DIR, "mixed_output.mp3")
    faster_audio.export(output_path, format="mp3", bitrate="192k")
    
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

# ============================================================================
# API ROUTES
# ============================================================================

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
    """Health check endpoint with TTS engine status"""
    engines_status = {
        'edge': 'available',
        'gtts': 'available',
        'preferred_engine': TTS_CONFIG['preferred_engine']
    }
    return jsonify({
        'status': 'healthy',
        'message': 'TTS Service is running',
        'engines': engines_status
    })

if __name__ == '__main__':
    # Ensure temp directory exists
    os.makedirs(TEMP_DIR, exist_ok=True)
    print("\n" + "="*60)
    print("🎤 Mixed Text-to-Speech Converter - Enhanced Edition")
    print("="*60)
    print(f"Edge TTS: ✓ Available")
    print(f"gTTS: ✓ Available")
    print(f"Preferred Engine: {TTS_CONFIG['preferred_engine']}")
    print("="*60 + "\n")
    app.run(debug=True, port=5000)
