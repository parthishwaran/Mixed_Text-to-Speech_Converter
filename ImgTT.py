import argparse
import os
import sys
import json
import time
import re
import io
import torch
from transformers import pipeline
from PIL import Image

# ---------------------------------------------------------------------------
# CLI-only TrOCR + Morse decoder
# - Uses microsoft/trocr-large-printed to OCR image
# - Normalizes dot/dash variants and decodes Morse
# - Use: python ImgTT.py --ocr path/to/image.png
# ---------------------------------------------------------------------------

# Lazy-initialized TrOCR pipeline
trocr_pipe = None
TROCR_MODEL = "microsoft/trocr-large-printed"

# Morse code map
MORSE_CODE = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.',
    'F': '..-.', 'G': '--.', 'H': '....', 'I': '..', 'J': '.---',
    'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.', 'O': '---',
    'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-',
    'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--',
    'Z': '--..',
    '0': '-----', '1': '.----', '2': '..---', '3': '...--', '4': '....-',
    '5': '.....', '6': '-....', '7': '--...', '8': '---..', '9': '----.',
    '.': '.-.-.-', ',': '--..--', '?': '..--..', "'": '.----.',
    '!': '-.-.--', '/': '-..-.', '(': '-.--.', ')': '-.--.-', '&': '.-...',
    ':': '---...', ';': '-.-.-.', '=': '-...-', '+': '.-.-.', '-': '-....-',
    '_': '..--.-', '"': '.-..-.', '$': '...-..-', '@': '.--.-.',
}
MORSE_TO_CHAR = {v: k for k, v in MORSE_CODE.items()}


def normalize_morse_text(text: str) -> str:
    """Normalize OCR text to dots, dashes, slashes and spaces."""
    if not text:
        return ''
    s = text.strip()
    # Common dot variants
    s = s.replace('·', '.').replace('•', '.').replace('﹒', '.').replace('．', '.')
    # Common dash variants
    s = re.sub(r'[–—−]', '-', s)
    # Replace vertical bars with slash for word separators
    s = s.replace('|', '/')
    # Keep only relevant characters (dots, dashes, slash, letters, numbers and spaces)
    s = re.sub(r'[\.\-\/\sA-Za-z0-9]', ' ', s)
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def decode_morse_from_normalized(text: str) -> str:
    """Decode normalized morse text into readable text."""
    if not text:
        return ''
    parts = text.split(' ')
    decoded_parts = []
    current_word = []
    empty_count = 0

    for tok in parts:
        if tok == '':
            empty_count += 1
            if empty_count >= 2:
                if current_word:
                    decoded_parts.append(''.join(current_word))
                    current_word = []
                decoded_parts.append(' ')
            continue
        empty_count = 0
        if tok == '/':
            if current_word:
                decoded_parts.append(''.join(current_word))
                current_word = []
            decoded_parts.append(' ')
            continue
        # If token is alphanumeric (OCR sometimes already converted), append
        if re.match(r'^[A-Za-z0-9]+$', tok):
            current_word.append(tok)
            continue
        # Direct morse lookup
        char = MORSE_TO_CHAR.get(tok)
        if char is None:
            cleaned = re.sub(r'[^\.\-]', '', tok)
            char = MORSE_TO_CHAR.get(cleaned, '?') if cleaned else '?'
        current_word.append(char)

    if current_word:
        decoded_parts.append(''.join(current_word))

    result = ''.join(decoded_parts)
    result = re.sub(r'\s+', ' ', result).strip()
    return result


def ocr_image_to_text(image_bytes: bytes) -> str:
    """Run TrOCR on the input image and return text."""
    global trocr_pipe
    if trocr_pipe is None:
        device = 0 if torch.cuda.is_available() else -1
        print(f"Loading TrOCR model ({TROCR_MODEL}) on device {device}...")
        trocr_pipe = pipeline("image-to-text", model=TROCR_MODEL, device=device)

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    result = trocr_pipe(image)

    text = ''
    if result:
        if isinstance(result, list):
            first = result[0]
            if isinstance(first, dict):
                text = first.get('generated_text') or first.get('text') or ''
            elif isinstance(first, str):
                text = first
        elif isinstance(result, dict):
            text = result.get('generated_text') or result.get('text') or ''
        elif isinstance(result, str):
            text = result
    return text or ''


def decode_image_file(path: str):
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, 'rb') as f:
        b = f.read()
    start = time.time()
    ocr_raw = ocr_image_to_text(b)
    normalized = normalize_morse_text(ocr_raw)
    decoded = decode_morse_from_normalized(normalized)
    took = time.time() - start
    return {'ocr_raw': ocr_raw, 'morse_normalized': normalized, 'decoded_text': decoded, 'took': took}


def main():
    parser = argparse.ArgumentParser(description='TrOCR Morse decoder (CLI-only)')
    parser.add_argument('--ocr', metavar='IMAGE', help='Run OCR+Morse decode on IMAGE and print JSON to stdout')
    parser.add_argument('--decoded-only', action='store_true', help='When used with --ocr, print only the decoded text')
    parser.add_argument('--ocr-raw', action='store_true', help='When used with --ocr, print only the raw OCR text')
    parser.add_argument('--normalized-only', action='store_true', help='Print only the normalized morse string')
    args = parser.parse_args()

    if not args.ocr:
        parser.print_help()
        sys.exit(0)

    try:
        res = decode_image_file(args.ocr)
    except FileNotFoundError:
        print(json.dumps({'error': 'File not found', 'path': args.ocr}))
        sys.exit(2)
    except Exception as e:
        print(json.dumps({'error': str(e)}))
        sys.exit(1)

    if args.decoded_only:
        print(res['decoded_text'])
        return
    if args.ocr_raw:
        print(res['ocr_raw'])
        return
    if args.normalized_only:
        print(res['morse_normalized'])
        return

    out = {
        'ocr_raw': res['ocr_raw'],
        'morse_normalized': res['morse_normalized'],
        'decoded_text': res['decoded_text'],
        'took_seconds': round(res['took'], 3)
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
