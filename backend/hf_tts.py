from flask import Flask, request, send_file, jsonify
import tempfile
import os

app = Flask(__name__)

@app.route('/hf_tts', methods=['POST'])
def hf_tts_api():
    data = request.form or request.json or {}
    text = data.get('text')
    lang = data.get('lang', 'en')
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    try:
        audio = generate_hf_tts_audio(text, lang)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
            audio.export(tmp_file.name, format='mp3', bitrate='192k')
            tmp_file_path = tmp_file.name
        return send_file(tmp_file_path, as_attachment=True, download_name='tts_output.mp3', mimetype='audio/mpeg')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 1:
        app.run(debug=True, port=5010)
import os
import tempfile
import torch
import soundfile as sf
from pydub import AudioSegment

import torch
from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer
import soundfile as sf


HF_TTS_MODEL = "ai4bharat/indic-parler-tts"

def generate_hf_tts_audio(prompt, description=None, temp_dir=None):
    """
    Generate audio using ai4bharat/indic-parler-tts from Hugging Face.
    Returns a pydub.AudioSegment object.
    """
    hf_token = os.getenv('TTS_HF_TOKEN') or os.getenv('HF_TOKEN')
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = ParlerTTSForConditionalGeneration.from_pretrained(HF_TTS_MODEL, token=hf_token).to(device)
    tokenizer = AutoTokenizer.from_pretrained(HF_TTS_MODEL, token=hf_token)
    # Use model.config.text_encoder._name_or_path for description tokenizer
    description_tokenizer = AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path, token=hf_token)

    if not description:
        description = "A female speaker delivers a slightly expressive and animated speech with a moderate speed and pitch. The recording is of very high quality, with the speaker's voice sounding clear and very close up."

    description_input_ids = description_tokenizer(description, return_tensors="pt").to(device)
    prompt_input_ids = tokenizer(prompt, return_tensors="pt").to(device)

    generation = model.generate(
        input_ids=description_input_ids.input_ids,
        attention_mask=description_input_ids.attention_mask,
        prompt_input_ids=prompt_input_ids.input_ids,
        prompt_attention_mask=prompt_input_ids.attention_mask
    )
    audio_arr = generation.cpu().numpy().squeeze()
    if temp_dir is None:
        temp_dir = tempfile.gettempdir()
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav', dir=temp_dir) as tmp_file:
        sf.write(tmp_file.name, audio_arr, model.config.sampling_rate)
        audio = AudioSegment.from_wav(tmp_file.name)
    return audio

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python hf_tts.py <text> [description]")
        exit(1)
    prompt = sys.argv[1]
    description = sys.argv[2] if len(sys.argv) > 2 else None
    audio = generate_hf_tts_audio(prompt, description)
    out_path = f"output.wav"
    audio.export(out_path, format="wav")
    print(f"Audio saved to {out_path}")
