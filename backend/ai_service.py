"""
AI Service Module — OpenRouter LLM Integration
Uses vision-capable models for enhanced OCR, smart validation, and risk analysis.
"""

import os
import base64
import json
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
VISION_MODEL = "google/gemini-3.5-flash-lite"
TEXT_MODEL = "google/gemini-3.5-flash-lite"


def _image_to_base64(image_path):
    """Convert image file to base64 data URI."""
    ext = os.path.splitext(image_path)[1].lower()
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _call_openrouter(messages, model=None, max_tokens=500):
    """Make a call to OpenRouter API."""
    if not OPENROUTER_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "AI Document Screening System",
    }

    payload = {
        "model": model or TEXT_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }

    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"OpenRouter API Error: {e}")
        return None


# ─────────────────────────────────────────────
# 1. ENHANCED OCR — Vision-based field extraction
# ─────────────────────────────────────────────

def ai_extract_fields(image_path, doc_type_hint=None):
    """
    Use a vision model to extract structured fields from a document image.
    Returns a dict of extracted fields or None if API fails.
    """
    b64_image = _image_to_base64(image_path)

    type_hint = f"The document appears to be a {doc_type_hint}." if doc_type_hint else ""

    prompt = f"""You are an expert document analyst. Analyze this identity document image and extract ALL visible text fields.
{type_hint}

Return a JSON object with these fields (use null if not found):
- "doc_type": the type of document (Passport/Visa/Aadhaar/PAN/Voter ID/Driving Licence/Other)
- "name": full name
- "document_number": the main ID number (passport number, Aadhaar number, PAN number, etc.)
- "dob": date of birth (in DD/MM/YYYY format)
- "gender": gender
- "nationality": nationality or country
- "date_of_expiry": expiry date (in DD/MM/YYYY format)
- "date_of_issue": issue date (in DD/MM/YYYY format)
- "address": address if visible
- "fathers_name": father's name if visible
- "additional_fields": any other important fields as key-value pairs

IMPORTANT: Return ONLY valid JSON, no markdown, no explanation."""

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": b64_image}},
            ],
        }
    ]

    result = _call_openrouter(messages, model=VISION_MODEL, max_tokens=600)
    if not result:
        return None

    try:
        # Clean up response — strip markdown code fences if present
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

        return json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"AI OCR: Failed to parse JSON response: {result[:200]}")
        return None


# ─────────────────────────────────────────────
# 2. SMART VALIDATION — LLM-powered consistency check
# ─────────────────────────────────────────────

def ai_validate_document(extracted_fields, doc_type, validation_result=None):
    """
    Use LLM to reason about document field consistency and detect anomalies.
    Returns a dict with analysis or None if API fails.
    """
    fields_str = json.dumps(extracted_fields, indent=2, default=str)
    validation_str = json.dumps(validation_result, indent=2, default=str) if validation_result else "Not available"

    prompt = f"""You are a border security document expert. Analyze the following extracted data from a {doc_type} document and the automated validation results.

EXTRACTED FIELDS:
{fields_str}

AUTOMATED VALIDATION:
{validation_str}

Perform these checks:
1. Are the extracted fields internally consistent? (e.g., DOB matches apparent age, name format is normal)
2. Do you see any signs of a template or placeholder document? (e.g., "SPECIMEN", sequential numbers like 1234)
3. Are there any unusual patterns in the document number or other fields?
4. Does the document type match the fields present?
5. Any red flags that automated validation might miss?

Return a JSON object:
{{
    "ai_assessment": "GENUINE" or "SUSPICIOUS" or "LIKELY_FAKE",
    "confidence": 0.0 to 1.0,
    "findings": ["list of specific findings"],
    "anomalies": ["list of detected anomalies, empty if none"],
    "reasoning": "brief explanation of your assessment"
}}

IMPORTANT: Return ONLY valid JSON."""

    messages = [{"role": "user", "content": prompt}]
    result = _call_openrouter(messages, max_tokens=500)
    if not result:
        return None

    try:
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"AI Validation: Failed to parse JSON: {result[:200]}")
        return None


# ─────────────────────────────────────────────
# 3. AI RISK ANALYSIS — Natural language summary
# ─────────────────────────────────────────────

def ai_risk_analysis(report_data):
    """
    Generate a comprehensive natural language risk analysis from all module results.
    Returns a string summary or None if API fails.
    """
    # Build a compact summary for the LLM
    summary = {
        "verdict": report_data.get("verdict"),
        "risk_score": report_data.get("risk_score"),
        "risk_level": report_data.get("risk_level"),
        "doc_type": report_data.get("doc_type"),
        "confidence": report_data.get("confidence"),
        "flags": report_data.get("flags", []),
        "module_scores": {k: v.get("score") for k, v in report_data.get("module_scores", {}).items()},
        "forgery_score": report_data.get("forgery_score"),
        "validation_passed": report_data.get("validation", {}).get("is_valid"),
        "face_detected": report_data.get("face", {}).get("face_detected"),
        "extracted_fields_count": len([v for v in report_data.get("extracted_fields", {}).values() if v]),
    }

    prompt = f"""You are an AI assistant for border checkpoint security officers. Based on the following automated document screening results, provide a clear, actionable intelligence brief.

SCREENING RESULTS:
{json.dumps(summary, indent=2, default=str)}

Write a 3-5 sentence risk assessment brief that:
1. States the overall assessment clearly
2. Highlights the most important findings
3. Notes specific concerns if any flags were raised
4. Gives a clear recommendation (CLEAR / SECONDARY INSPECTION / DETAIN & ESCALATE)

Write in a professional, concise law enforcement style. Do NOT use markdown formatting. Keep it under 150 words."""

    messages = [{"role": "user", "content": prompt}]
    result = _call_openrouter(messages, max_tokens=500)
    return result.strip() if result else None


# ─────────────────────────────────────────────
# 4. AI VISION AUTHENTICITY — Direct image-level real/fake assessment
# ─────────────────────────────────────────────

def ai_assess_authenticity(image_path, doc_type_hint=None):
    """
    Use a vision model to directly assess whether a document image looks
    genuine or fake/tampered.  This is the PRIMARY classification signal
    that replaces the weak synthetic-data ML model.

    Returns:
        dict with keys: assessment (GENUINE|SUSPICIOUS|LIKELY_FAKE),
                        confidence (0.0-1.0),
                        reasoning (str),
                        flags (list)
        OR None if the API is unavailable / errors.
    """
    b64_image = _image_to_base64(image_path)
    type_hint = f"This document appears to be a {doc_type_hint}." if doc_type_hint else ""

    prompt = f"""You are a world-class forensic document examiner.
Carefully study this identity document image and determine whether it is a GENUINE government-issued document or a FAKE / tampered document.

{type_hint}

Analyze the following aspects:
1. Print quality, fonts, and text alignment — are they consistent with official documents?
2. Security features — holograms, microprinting, watermarks, guilloche patterns (if visible)
3. Photo quality — is the photograph properly affixed / printed? Any signs of photo substitution?
4. Color consistency — are colors uniform and consistent with genuine specimens?
5. Layout and design — does the overall layout match known genuine templates?
6. Signs of digital manipulation — blurring, pixelation, clone artifacts, inconsistent lighting/shadows
7. Paper/card texture cues — does the surface look like official document stock?

IMPORTANT RULES:
- Missing EXIF metadata alone is NOT suspicious — phone photos of real documents lack EXIF.
- Noise variations alone are NOT suspicious — they depend on camera quality and compression.
- The presence of a face/photo is expected on identity documents.
- Focus on VISUAL forensic evidence in the image itself.
- A real document photographed with a phone camera is still GENUINE.
- If the document looks like a normal, properly printed government document, assess it as GENUINE.

Return ONLY a JSON object with NO markdown formatting:
{{
    "assessment": "GENUINE" or "SUSPICIOUS" or "LIKELY_FAKE",
    "confidence": 0.0 to 1.0,
    "reasoning": "2-3 sentence explanation of your assessment",
    "flags": ["list of specific forensic concerns, empty if document appears genuine"]
}}"""

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": b64_image}},
            ],
        }
    ]

    result = _call_openrouter(messages, model=VISION_MODEL, max_tokens=500)
    if not result:
        return None

    try:
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"AI Authenticity: Failed to parse JSON: {result[:200]}")
        return None


def is_available():
    """Check if AI service is configured and available."""
    return bool(OPENROUTER_API_KEY)
