"""
Secondary Inspection Referral (SIR) & Interrogation Copilot Service
Generates targeted interrogation questions for flagged travelers,
powers the interactive Officer Forensic Copilot chat, and handles SIR disposition.
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-3.5-flash-lite"


def _call_llm(messages, max_tokens=600):
    """Execute OpenRouter chat completion."""
    if not OPENROUTER_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "Border Secondary Inspection System",
    }

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json={
                "model": MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.2,
            },
            timeout=25
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"SIR LLM Error: {e}")
        return None


def generate_interrogation_questions(report_data):
    """
    Generate tailored interview / interrogation questions based on detected anomalies.
    Returns list of dicts with question, target_field, purpose, and red_flag_signs.
    """
    summary = {
        "doc_type": report_data.get("doc_type"),
        "verdict": report_data.get("verdict"),
        "risk_score": report_data.get("risk_score"),
        "risk_level": report_data.get("risk_level"),
        "flags": report_data.get("flags", []),
        "extracted_fields": {k: v for k, v in (report_data.get("extracted_fields") or {}).items() if v and k != "mrz"},
        "mismatches": [c.get("detail") for c in (report_data.get("validation", {}).get("checks") or []) if not c.get("passed")],
    }

    prompt = f"""You are a senior border control investigator and interrogation specialist.
A passenger's travel document was referred to Secondary Inspection Referral (SIR) due to automated security flags.

SCREENING ANOMALIES & EXTRACTED DATA:
{json.dumps(summary, indent=2, default=str)}

Generate 3 to 4 targeted, non-obvious oral interview questions for the officer to ask the traveler to verify their identity and test if they are an impostor or using a fraudulent credential.

Return a JSON array of objects with this schema:
[
  {{
    "question": "Exact phrasing for officer to speak out loud",
    "target_issue": "What specific discrepancy or flag this investigates",
    "expected_valid_response": "What an authentic holder would answer smoothly",
    "red_flag_indicator": "Specific signs of hesitation, contradiction, or rehearsed lies"
  }}
]

IMPORTANT: Return ONLY valid JSON array."""

    messages = [{"role": "user", "content": prompt}]
    result = _call_llm(messages, max_tokens=650)

    if not result:
        # High quality fallback if offline
        return _fallback_questions(summary)

    try:
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return parsed
        return _fallback_questions(summary)
    except Exception as e:
        print(f"Failed to parse SIR questions: {e}")
        return _fallback_questions(summary)


def copilot_chat(document_context, history, user_query):
    """
    Conversational Forensic Copilot for border officers.
    Answers technical questions about the forensic heatmap, flags, and checkpoint regulations.
    """
    context_str = json.dumps(document_context, indent=2, default=str) if isinstance(document_context, dict) else str(document_context)

    system_prompt = f"""You are 'BorderGuard Copilot', an AI forensic adviser assisting a law enforcement officer at a border checkpoint Secondary Inspection desk.
You have full access to the automated forensic analysis of the traveler's document:

DOCUMENT FORENSIC CONTEXT:
{context_str[:1500]}

Guidelines:
1. Provide concise, authoritative, law enforcement-style answers (under 120 words).
2. Explain technical details (ELA heatmaps, copy-move keypoints, EXIF metadata, MRZ checksums) clearly.
3. Recommend physical inspection techniques (e.g. UV lamp inspection, tactile watermark feeling, oblique light examination) when appropriate.
4. Keep answers professional and focused on border security protocol."""

    messages = [{"role": "system", "content": system_prompt}]

    # Append recent conversation history (up to last 6 turns)
    if history and isinstance(history, list):
        for msg in history[-6:]:
            if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                messages.append({'role': msg['role'], 'content': msg['content']})

    messages.append({"role": "user", "content": user_query})

    response = _call_llm(messages, max_tokens=350)
    return response or "Copilot currently offline. Please refer to standard checkpoint operating manual SOP-04."


def _fallback_questions(summary):
    """Fallback interrogation questions when offline."""
    return [
        {
            "question": "Can you state your full legal name, date of birth, and your mother or father's given name without looking at your document?",
            "target_issue": "Biographical consistency & memory recall",
            "expected_valid_response": "Immediate, natural response without hesitating or glancing at credentials.",
            "red_flag_indicator": "Pausing to remember details or glancing down at the document."
        },
        {
            "question": "What year was this specific document issued to you, and what was the issuing office or city?",
            "target_issue": "Issuance history and geographic validity",
            "expected_valid_response": "Correctly names the issuance year and issuing authority/passport office.",
            "red_flag_indicator": "Unable to name issuing location or provides contradictory year."
        },
        {
            "question": "What is the primary purpose of your travel today and how long do you intend to stay?",
            "target_issue": "Visa category and itinerary alignment",
            "expected_valid_response": "Clear itinerary, confirmed return travel or hotel details matching visa validity.",
            "red_flag_indicator": "Vague answers regarding accommodations or duration exceeding visa parameters."
        }
    ]
