import os
import pandas as pd
import torch
from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer
import soundfile as sf
from pydub import AudioSegment
import tempfile

HF_TTS_MODEL = "ai4bharat/indic-parler-tts"
# Token must be provided via environment variable. Do NOT store secrets in the repository.
HF_TOKEN = os.getenv("TTS_HF_TOKEN") or os.getenv("HF_TOKEN")  # Read from environment


def generate_hf_tts_audio(prompt, description=None):
    """
    Generate audio using ai4bharat/indic-parler-tts from Hugging Face.
    Returns a pydub.AudioSegment object.
    """
    import logging
    logging.getLogger("transformers.configuration_utils").setLevel(logging.ERROR)
    logging.getLogger("transformers.modeling_utils").setLevel(logging.ERROR)
    logging.getLogger("transformers.tokenization_utils_base").setLevel(logging.ERROR)
    logging.getLogger("transformers").setLevel(logging.ERROR)
    logging.getLogger("parler_tts").setLevel(logging.ERROR)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = ParlerTTSForConditionalGeneration.from_pretrained(HF_TTS_MODEL, token=HF_TOKEN).to(device)
    tokenizer = AutoTokenizer.from_pretrained(HF_TTS_MODEL, token=HF_TOKEN)
    description_tokenizer = AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path, token=HF_TOKEN)

    if not description:
        description = (
            "A female speaker delivers a slightly expressive and animated speech with a moderate speed and pitch. "
            "The recording is of very high quality, with the speaker's voice sounding clear and very close up."
        )

    description_input_ids = description_tokenizer(description, return_tensors="pt").to(device)
    prompt_input_ids = tokenizer(prompt, return_tensors="pt").to(device)

    generation = model.generate(
        input_ids=description_input_ids.input_ids,
        attention_mask=description_input_ids.attention_mask,
        prompt_input_ids=prompt_input_ids.input_ids,
        prompt_attention_mask=prompt_input_ids.attention_mask
    )
    audio_arr = generation.cpu().numpy().squeeze()
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
        sf.write(tmp_file.name, audio_arr, model.config.sampling_rate)
        audio = AudioSegment.from_wav(tmp_file.name)
    os.unlink(tmp_file.name)  # Clean up temp file
    return audio

def main():
    # Adjust paths based on your directory structure
    # Assuming script is in the same directory as TaEN_con.csv and Audio folder
    csv_path = "TaEN_con.csv"
    audio_dir = "Audio"

    # Set to True to test with first 2 rows, False to process all
    TEST_MODE = True
    test_limit = 2

    # Read CSV
    df = pd.read_csv(csv_path)

    # Add audio_path column if not exists
    if 'audio_path' not in df.columns:
        df['audio_path'] = None

    # Determine how many rows to process
    if TEST_MODE:
        rows_to_process = df.head(test_limit)
        print(f"TEST MODE: Processing first {test_limit} rows only.")
    else:
        rows_to_process = df
        print("Processing all rows.")

    total = len(rows_to_process)
    converted = 0
    for idx, (index, row) in enumerate(rows_to_process.iterrows(), 1):
        id_num = row['Id']
        text = row['conversation_text']
        audio_path = f"{audio_dir}/{id_num}.mp3"

        print(f"[{idx}/{total}] Starting conversion for ID {id_num}...")

        try:
            audio = generate_hf_tts_audio(text)
            audio.export(audio_path, format='mp3', bitrate='192k')
            df.at[index, 'audio_path'] = audio_path
            converted += 1
            print(f"[{idx}/{total}] Success: Saved audio to {audio_path} | Converted: {converted} | Left: {total-converted}")
        except Exception as e:
            print(f"[{idx}/{total}] Error for ID {id_num}: {e} | Converted: {converted} | Left: {total-converted}")
            df.at[index, 'audio_path'] = f"Error: {e}"

    # Save updated CSV
    # Create a new CSV with only Id, conversation_text, audio_path
    new_df = df[['Id', 'conversation_text', 'audio_path']]
    new_csv_path = "TaEN_con_with_audio.csv"
    new_df.to_csv(new_csv_path, index=False)
    print(f"New CSV saved to {new_csv_path}.")

    if TEST_MODE:
        print("Test completed. Set TEST_MODE = False to process all rows.")

if __name__ == "__main__":
    main()