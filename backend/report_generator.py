def generate_report(forgery_result, ml_confidence, extracted_text, doc_type,
                    extracted_fields=None, validation_result=None,
                    face_result=None):
    """
    Generate a comprehensive risk assessment report combining all module outputs.

    Args:
        forgery_result: dict from forgery_detection.analyze_image() with combined_score and sub-scores
                       OR a float (backward compat with old forgery_score)
        ml_confidence: float 0-1, ML classifier confidence of being genuine
        extracted_text: str, raw OCR text
        doc_type: str, detected document type
        extracted_fields: dict, structured fields from OCR (optional)
        validation_result: dict from document_validator (optional)
        face_result: dict from face_verification (optional)

    Returns:
        Comprehensive report dict
    """

    # Handle both old (float) and new (dict) forgery_result format
    if isinstance(forgery_result, dict):
        forgery_score = forgery_result.get('combined_score', 0.0)
        tampering_details = forgery_result
    else:
        forgery_score = float(forgery_result)
        tampering_details = {'combined_score': forgery_score}

    # --- Compute individual module risk scores (0-100, higher = riskier) ---

    # Tampering risk
    tampering_risk = min(forgery_score * 100, 100)

    # ML risk (ml_confidence is confidence of genuine, so risk = 1 - confidence)
    ml_risk = (1.0 - ml_confidence) * 100

    # Validation risk
    validation_risk = 0
    validation_flags = []
    if validation_result:
        val_score = validation_result.get('score', 1.0)
        validation_risk = (1.0 - val_score) * 100
        validation_flags = validation_result.get('flags', [])

    # Face risk
    face_risk = 0
    face_flags = []
    if face_result:
        if not face_result.get('face_detected', True):
            face_risk = 10  # Low penalty — face detectors often miss on phone-captured docs
            face_flags.append('NO_FACE_DETECTED')
        else:
            face_tampering = face_result.get('tampering', {})
            face_risk = face_tampering.get('tampering_score', 0) * 100
            face_flags = face_tampering.get('flags', [])

            quality = face_result.get('quality', {})
            if quality.get('quality_score', 1.0) < 0.5:
                face_risk = min(face_risk + 15, 100)
                face_flags.append('LOW_FACE_QUALITY')

    # --- Compute overall risk score ---
    # Weighted combination
    weights = {
        'tampering': 0.30,
        'ml': 0.25,
        'validation': 0.25,
        'face': 0.20,
    }

    # If some modules didn't run, redistribute weights
    active_weights = {}
    if tampering_details:
        active_weights['tampering'] = weights['tampering']
    if ml_confidence is not None:
        active_weights['ml'] = weights['ml']
    if validation_result:
        active_weights['validation'] = weights['validation']
    if face_result:
        active_weights['face'] = weights['face']

    # Normalize weights
    total_weight = sum(active_weights.values()) or 1.0
    for k in active_weights:
        active_weights[k] /= total_weight

    risk_score = 0
    if 'tampering' in active_weights:
        risk_score += tampering_risk * active_weights['tampering']
    if 'ml' in active_weights:
        risk_score += ml_risk * active_weights['ml']
    if 'validation' in active_weights:
        risk_score += validation_risk * active_weights['validation']
    if 'face' in active_weights:
        risk_score += face_risk * active_weights['face']

    risk_score = round(min(risk_score, 100), 2)

    # --- Determine verdict and risk level ---
    if risk_score >= 70:
        verdict = "Likely Fake"
        risk_level = "CRITICAL"
    elif risk_score >= 50:
        verdict = "Suspicious"
        risk_level = "HIGH"
    elif risk_score >= 30:
        verdict = "Needs Review"
        risk_level = "MEDIUM"
    else:
        verdict = "Likely Genuine"
        risk_level = "LOW"

    # --- Collect all flags ---
    all_flags = []
    all_flags.extend(validation_flags)
    all_flags.extend(face_flags)

    # Tampering flags
    if isinstance(tampering_details, dict):
        meta = tampering_details.get('metadata', {})
        if meta.get('flags'):
            all_flags.extend(meta['flags'])
        if tampering_details.get('ela', {}).get('score', 0) > 0.6:
            all_flags.append('HIGH_ELA_SCORE')
        if tampering_details.get('copy_move', {}).get('score', 0) > 0.3:
            all_flags.append('COPY_MOVE_DETECTED')
        if tampering_details.get('noise', {}).get('score', 0) > 0.7:
            all_flags.append('NOISE_INCONSISTENCY')

    # ML flag
    if ml_confidence < 0.4:
        all_flags.append('ML_CLASSIFIER_FLAGGED')

    # Deduplicate
    all_flags = list(dict.fromkeys(all_flags))

    # --- Build module breakdown ---
    module_scores = {
        'tampering': {
            'score': round(tampering_risk, 2),
            'label': 'Tampering Detection',
            'status': _risk_label(tampering_risk),
        },
        'ml_classifier': {
            'score': round(ml_risk, 2),
            'label': 'ML Classification',
            'status': _risk_label(ml_risk),
        },
    }

    if validation_result:
        module_scores['validation'] = {
            'score': round(validation_risk, 2),
            'label': 'Document Validation',
            'status': _risk_label(validation_risk),
            'checks': validation_result.get('checks', []),
        }

    if face_result:
        module_scores['face'] = {
            'score': round(face_risk, 2),
            'label': 'Face Verification',
            'status': _risk_label(face_risk),
        }

    # --- Build final report ---
    report = {
        'verdict': verdict,
        'confidence': round(ml_confidence * 100, 2),
        'risk_score': risk_score,
        'risk_level': risk_level,
        'forgery_score': round(forgery_score, 4),
        'doc_type': doc_type,
        'extracted_text': extracted_text[:500] + ('...' if len(extracted_text) > 500 else ''),
        'extracted_fields': extracted_fields or {},
        'validation': validation_result or {},
        'tampering': _sanitize_tampering(tampering_details),
        'face': _sanitize_face(face_result) if face_result else {},
        'module_scores': module_scores,
        'flags': all_flags,
        'recommendations': _generate_recommendations(risk_level, all_flags),
    }

    return report


def _risk_label(score):
    """Convert a 0-100 risk score to a label."""
    if score >= 70:
        return 'CRITICAL'
    elif score >= 50:
        return 'HIGH'
    elif score >= 30:
        return 'MEDIUM'
    else:
        return 'LOW'


def _sanitize_tampering(tampering_details):
    """Ensure tampering details are JSON-serializable."""
    if not isinstance(tampering_details, dict):
        return {'combined_score': float(tampering_details) if tampering_details else 0.0}

    result = {}
    for key, val in tampering_details.items():
        if isinstance(val, dict):
            result[key] = {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in val.items()}
        elif isinstance(val, (int, float)):
            result[key] = float(val)
        else:
            result[key] = val
    return result


def _sanitize_face(face_result):
    """Ensure face result is JSON-serializable, strip non-essential fields."""
    if not face_result:
        return {}
    sanitized = {}
    for key, val in face_result.items():
        if isinstance(val, dict):
            sanitized[key] = val
        elif isinstance(val, list):
            sanitized[key] = val
        elif isinstance(val, (int, float, bool, str, type(None))):
            sanitized[key] = val
        else:
            sanitized[key] = str(val)
    return sanitized


def _generate_recommendations(risk_level, flags):
    """Generate actionable recommendations for border personnel."""
    recs = []

    if risk_level == 'CRITICAL':
        recs.append('⛔ HOLD: Document shows critical signs of forgery. Detain for manual expert review.')
    elif risk_level == 'HIGH':
        recs.append('⚠️ ALERT: Document requires thorough secondary inspection.')
    elif risk_level == 'MEDIUM':
        recs.append('🔍 REVIEW: Some anomalies detected. Perform additional verification.')
    else:
        recs.append('✅ PASS: Document appears authentic. Proceed with standard processing.')

    if 'EXPIRED_DOCUMENT' in flags:
        recs.append('📅 Document has expired. Check for valid renewal or extension.')
    if 'BLACKLISTED' in flags:
        recs.append('🚨 Document number found in watchlist database. Escalate immediately.')
    if 'EDITING_SOFTWARE_DETECTED' in flags:
        recs.append('🖥️ Image metadata indicates editing software was used. Request original document.')
    if 'NO_FACE_DETECTED' in flags:
        recs.append('👤 No face detected on document. Verify document has a valid photograph.')
    if 'COPY_MOVE_DETECTED' in flags:
        recs.append('📋 Copy-move forgery detected. Examine document under UV light.')
    if 'HIGH_ELA_SCORE' in flags:
        recs.append('🔬 Error Level Analysis indicates potential digital manipulation.')
    if 'FORMAT_INVALID' in flags or 'INVALID_FORMAT' in flags:
        recs.append('📝 Document number format does not match expected standard. Cross-check with issuing authority.')

    return recs
