import requests
import csv
import time
import random


LM_STUDIO_BASE_URL = "http://nikhil-17425-ait.csez.zohocorpin.com:1234/v1"
PREFERRED_MODEL = "gemma-3-27b-it"

# Strict prompt template for Tanglish bilingual conversational paragraphs
PROMPT_TEMPLATE = """
Role: You are a high-quality synthetic data generator for a bilingual (Tamil-English) Speech Dataset.

Task: Generate 1 unique conversational paragraph. The paragraph should be approximately 20-30 seconds long when spoken (around 40-60 words).

Formatting Rules (Strict):
- Script: Use Tamil script (தமிழ்) for Tamil words and English script for English words.
- Suffixes: Attach English phonetic suffixes to Tamil or English words to reflect natural speech:
    - Use -ku for 'to/for' (e.g., lunch-ku, veetu-ku).
    - Use -aa for questions (e.g., deal-aa, polama-aa).
    - Use -u for casual endings (e.g., best-u, correct-u).
    - Use -la for 'in/at' (e.g., office-la, car-la).
    - Use -nu for 'that/as' (e.g., mudivu-nu, confusion-nu).
- Tone: Modern, urban, and casual. Use common daily scenarios (Office, Shopping, Tech, Travel, Food, Fitness, Movies).
- Structure: Single-person monologue or a smooth continuous conversation.

Example Pattern: "இன்னைக்கு office-la ரொம்ப work-u, செம்ம tiredness-aa இருக்கு. [pause] Evening ஒரு coffee குடிக்க polama-aa? அந்த புது cafe-ku போனா relax-aa இருக்கும். [pause] நீ okay-na சொல்லு, கிளம்பலாம். Deal-aa?"

Instructions for Variety:
- Vary the topics (e.g., someone complaining about a phone, someone excited about a trip, someone confused about a menu).
- Ensure the placement of English words feels natural for a 'Tanglish' speaker.

Output: Provide the result as a numbered list item, e.g., "1. ..."
"""

NUM_SAMPLES = 10
OUTPUT_CSV = "tamil_conversations.csv"


import re

def clean_conversation(text):
    # Remove [pause] (case-insensitive)
    text = re.sub(r'\[pause\]', '', text, flags=re.IGNORECASE)
    # Remove leading numbers and dots (e.g., '1. ' or '1. “')
    text = re.sub(r'^\s*\d+\.\s*', '', text)
    # Remove leading/trailing quotes (single, double, or Tamil quotes)
    text = text.strip('"“”‟‟‘’\'\n ')
    # Remove unwanted boilerplate lines
    boilerplate_patterns = [
        r'Here\'s a generated conversational paragraph[^\"]*:?',
        r'Here\'s a synthetic conversational paragraph[^\"]*:?',
        r'Here\'s a conversational paragraph[^\"]*:?',
        r'Here\'s a generated conversational paragraph following all specified rules:?',
        r'Here\'s a synthetic conversational paragraph following all specified rules:?',
    ]
    for pat in boilerplate_patterns:
        text = re.sub(pat, '', text, flags=re.IGNORECASE).strip()
    # Remove any repeated leading numbers/quotes after boilerplate
    text = re.sub(r'^\s*\d+\.\s*', '', text)
    text = text.strip('"“”‟‟‘’\'\n ')
    return text

samples = []



for i in range(NUM_SAMPLES):
    print(f"Generating sample {i+1}/{NUM_SAMPLES}... ({NUM_SAMPLES - i} left)")
    prompt = PROMPT_TEMPLATE
    payload = {
        "model": PREFERRED_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 512,
        "temperature": 0.9
    }
    try:
        response = requests.post(
            f"{LM_STUDIO_BASE_URL}/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"},
            stream=False
        )
        response.raise_for_status()
        data = response.json()
        # Extract and clean the generated text
        text = data["choices"][0]["message"]["content"].strip()
        cleaned = clean_conversation(text)
        samples.append([i+1, cleaned])
        print(f"Sample {i+1}: {cleaned}")
        # Optional: sleep to avoid rate limits
        time.sleep(random.uniform(0.5, 1.5))
    except Exception as e:
        print(f"Error for sample {i+1}: {e}")
        samples.append([i+1, "ERROR"])

# Write to CSV
with open(OUTPUT_CSV, "w", newline='', encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "conversation_text"])
    writer.writerows(samples)

print(f"Saved {NUM_SAMPLES} samples to {OUTPUT_CSV}")
