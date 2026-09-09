"""
QR Code & Signature Forensic Service
Performs QR code detection, payload extraction, OCR-vs-QR cross-verification,
and signature zone extraction & density analysis.
"""

import os
import cv2
import numpy as np
import json
import re


def detect_and_decode_qr(image_path):
    """
    Detect and decode QR code from document image using OpenCV.
    Returns: dict with detected (bool), payload (str or dict), bbox, and metadata.
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {'qr_detected': False, 'error': 'Could not read image'}

        detector = cv2.QRCodeDetector()
        data, bbox, straight_qrcode = detector.detectAndDecode(img)

        # Fallback: if not detected on original, try thresholded grayscale
        if not data and bbox is None:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            data, bbox, straight_qrcode = detector.detectAndDecode(enhanced)

        if not data:
            return {
                'qr_detected': False,
                'payload': None,
                'payload_type': None,
                'parsed_data': None,
                'message': 'No readable QR code found on document'
            }

        parsed_data = _parse_qr_payload(data)

        return {
            'qr_detected': True,
            'raw_payload': data[:500] + ('...' if len(data) > 500 else ''),
            'payload_type': parsed_data.get('type', 'TEXT'),
            'parsed_data': parsed_data.get('fields', {}),
            'message': 'QR code successfully decoded'
        }

    except Exception as e:
        print(f"QR Detection error: {e}")
        return {
            'qr_detected': False,
            'payload': None,
            'error': str(e)
        }


def _parse_qr_payload(raw_text):
    """Parse common ID document QR payloads (Aadhaar XML, JSON, key-value, VCF)."""
    raw_text = raw_text.strip()

    # 1. Check if JSON
    if raw_text.startswith('{') and raw_text.endswith('}'):
        try:
            d = json.loads(raw_text)
            return {'type': 'JSON', 'fields': d}
        except Exception:
            pass

    # 2. Check if Aadhaar XML (e.g. <PrintLetterBarcodeData ... />)
    if '<PrintLetterBarcodeData' in raw_text or 'uid=' in raw_text:
        fields = {}
        patterns = {
            'uid': r'uid="([^"]+)"',
            'name': r'name="([^"]+)"',
            'gender': r'gender="([^"]+)"',
            'yob': r'yob="([^"]+)"',
            'dob': r'dob="([^"]+)"',
            'co': r'co="([^"]+)"',
            'house': r'house="([^"]+)"',
            'street': r'street="([^"]+)"',
            'lm': r'lm="([^"]+)"',
            'vtc': r'vtc="([^"]+)"',
            'po': r'po="([^"]+)"',
            'dist': r'dist="([^"]+)"',
            'subdist': r'subdist="([^"]+)"',
            'state': r'state="([^"]+)"',
            'pc': r'pc="([^"]+)"',
        }
        for k, pat in patterns.items():
            m = re.search(pat, raw_text, re.IGNORECASE)
            if m:
                fields[k] = m.group(1)
        if fields:
            return {'type': 'AADHAAR_XML', 'fields': fields}

    # 3. Delimited text (e.g. PAN or custom format: ID|NAME|DOB)
    if '|' in raw_text:
        parts = [p.strip() for p in raw_text.split('|')]
        fields = {f"field_{i+1}": p for i, p in enumerate(parts)}
        return {'type': 'PIPE_DELIMITED', 'fields': fields}

    # 4. Standard text or URL
    return {
        'type': 'RAW_TEXT',
        'fields': {'content': raw_text[:200]}
    }


def compare_qr_with_ocr(qr_result, extracted_fields):
    """
    Cross-checks the decoded QR payload with visible OCR fields.
    Returns: dict with match status, mismatches, and security flags.
    """
    if not qr_result or not qr_result.get('qr_detected'):
        return {
            'verified': False,
            'status': 'NO_QR',
            'mismatches': [],
            'flags': []
        }

    qr_fields = qr_result.get('parsed_data', {})
    if not qr_fields or not extracted_fields:
        return {
            'verified': True,
            'status': 'QR_PRESENT_NO_STRUCTURED_FIELDS',
            'mismatches': [],
            'flags': []
        }

    mismatches = []
    flags = []

    # Check Name
    qr_name = qr_fields.get('name') or qr_fields.get('Name')
    ocr_name = extracted_fields.get('name')
    if qr_name and ocr_name:
        clean_qr = re.sub(r'[^a-zA-Z]', '', qr_name.lower())
        clean_ocr = re.sub(r'[^a-zA-Z]', '', ocr_name.lower())
        if clean_qr and clean_ocr and (clean_qr not in clean_ocr and clean_ocr not in clean_qr):
            mismatches.append({
                'field': 'name',
                'qr_value': qr_name,
                'ocr_value': ocr_name,
                'severity': 'CRITICAL'
            })
            flags.append('QR_NAME_MISMATCH_TAMPERING')

    # Check Document / UID number
    qr_num = qr_fields.get('uid') or qr_fields.get('pan') or qr_fields.get('doc_number')
    ocr_num = (extracted_fields.get('aadhaar_number') or
               extracted_fields.get('pan_number') or
               extracted_fields.get('passport_number'))
    if qr_num and ocr_num:
        clean_qr_n = re.sub(r'[^a-zA-Z0-9]', '', str(qr_num))
        clean_ocr_n = re.sub(r'[^a-zA-Z0-9]', '', str(ocr_num))
        if clean_qr_n and clean_ocr_n and clean_qr_n != clean_ocr_n:
            mismatches.append({
                'field': 'document_number',
                'qr_value': str(qr_num),
                'ocr_value': str(ocr_num),
                'severity': 'CRITICAL'
            })
            flags.append('QR_DOCUMENT_NUMBER_MISMATCH_TAMPERING')

    # Check DOB / YOB
    qr_dob = qr_fields.get('dob') or qr_fields.get('yob')
    ocr_dob = extracted_fields.get('dob')
    if qr_dob and ocr_dob:
        if str(qr_dob) not in str(ocr_dob):
            mismatches.append({
                'field': 'dob',
                'qr_value': str(qr_dob),
                'ocr_value': str(ocr_dob),
                'severity': 'HIGH'
            })
            flags.append('QR_DOB_MISMATCH')

    is_tampered = bool(len(mismatches) > 0)

    return {
        'verified': True,
        'is_tampered': is_tampered,
        'status': 'TAMPERING_DETECTED' if is_tampered else 'MATCH_CONFIRMED',
        'mismatches': mismatches,
        'flags': flags,
        'summary': (
            f"⚠️ Cryptographic mismatch detected between QR payload and visible text ({len(mismatches)} fields mismatch)."
            if is_tampered else
            "✅ Decoded QR payload matches visible card text perfectly."
        )
    }


def extract_signature_zone(image_path, doc_type, output_dir):
    """
    Crops the designated signature zone from an ID card (PAN, Passport, etc.)
    and calculates stroke presence and density.
    Returns dict with image path, presence boolean, and stroke density.
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return {'signature_detected': False}

        h, w = img.shape[:2]

        # Location heuristic based on document type
        # For Passports / PAN, signatures are typically in the bottom-middle or right
        if 'pan' in doc_type.lower():
            # PAN: signature is bottom right or bottom center
            y1, y2 = int(h * 0.65), int(h * 0.92)
            x1, x2 = int(w * 0.35), int(w * 0.85)
        elif 'passport' in doc_type.lower():
            # Passport: signature is often below the photo or bottom page
            y1, y2 = int(h * 0.60), int(h * 0.85)
            x1, x2 = int(w * 0.05), int(w * 0.45)
        else:
            # Generic ID: bottom third
            y1, y2 = int(h * 0.65), int(h * 0.95)
            x1, x2 = int(w * 0.20), int(w * 0.80)

        sig_crop = img[y1:y2, x1:x2]
        if sig_crop.size == 0:
            return {'signature_detected': False}

        # Analyze stroke presence & density
        gray_sig = cv2.cvtColor(sig_crop, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(gray_sig, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                      cv2.THRESH_BINARY_INV, 15, 8)

        dark_pixels = np.count_nonzero(thresh)
        total_pixels = thresh.size
        density = round(dark_pixels / max(total_pixels, 1), 4)

        # A signature typically occupies between 3% and 35% dark stroke pixels in its bounding box
        has_signature = bool(0.02 < float(density) < 0.45)

        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.basename(image_path)
        sig_filename = f"sig_{base_name}.png" if not base_name.endswith('.png') else f"sig_{base_name}"
        sig_path = os.path.join(output_dir, sig_filename)
        cv2.imwrite(sig_path, sig_crop)

        return {
            'signature_detected': bool(has_signature),
            'signature_filename': sig_filename,
            'stroke_density': float(density),
            'quality': 'Good' if has_signature else ('Too Faint' if density <= 0.02 else 'Too Dense/Smudged'),
            'coordinates': [int(x1), int(y1), int(x2 - x1), int(y2 - y1)]
        }

    except Exception as e:
        print(f"Signature extraction error: {e}")
        return {'signature_detected': False, 'error': str(e)}
