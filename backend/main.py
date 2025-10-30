from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from gtts import gTTS
import edge_tts
import asyncio
import os
import tempfile
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

def detect_language(text):
    """Detect if text is Tamil or English"""
    try:
        # For short texts, use character-based detection
        if len(text.strip()) < 10:
            tamil_chars = re.findall(r'[\u0B80-\u0BFF]', text)
            return 'ta' if len(tamil_chars) > len(text) * 0.3 else 'en'
        
        lang = detect(text)
        return lang
    except LangDetectException:
        # Fallback to character-based detection
        tamil_chars = re.findall(r'[\u0B80-\u0BFF]', text)
        return 'ta' if len(tamil_chars) > len(text) * 0.3 else 'en'

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
            
            if current_lang is None:
                current_lang = word_lang
                current_segment = word
            elif current_lang == word_lang:
                current_segment += " " + word
            else:
                # Language change detected
                if current_segment.strip():
                    segments.append((current_segment.strip(), current_lang))
                current_lang = word_lang
                current_segment = word
        
        if current_segment.strip():
            segments.append((current_segment.strip(), current_lang))
    
    return segments

async def generate_english_audio(text, voice="en-US-AriaNeural"):
    """Generate English audio using Edge TTS"""
    try:
        communicate = edge_tts.Communicate(text, voice)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir=TEMP_DIR) as tmp_file:
            tmp_path = tmp_file.name
            await communicate.save(tmp_path)
            
        # Load and process audio
        audio = AudioSegment.from_mp3(tmp_path)
        # Add small pause at the end
        audio = audio + AudioSegment.silent(duration=200)
        
        return audio
    except Exception as e:
        print(f"Error generating English audio: {e}")
        # Fallback to gTTS
        return generate_tamil_audio(text, 'en')  # gTTS can handle English too

def generate_tamil_audio(text, lang='ta'):
    """Generate Tamil audio using gTTS"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3', dir=TEMP_DIR) as tmp_file:
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(tmp_file.name)
            
        audio = AudioSegment.from_mp3(tmp_file.name)
        # Add small pause at the end
        audio = audio + AudioSegment.silent(duration=200)
        
        return audio
    except Exception as e:
        print(f"Error generating Tamil audio: {e}")
        # Return silent audio as fallback
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
                audio_segment = generate_tamil_audio(segment_text)
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