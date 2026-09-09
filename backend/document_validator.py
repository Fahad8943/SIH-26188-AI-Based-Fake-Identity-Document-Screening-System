import re
import datetime
import sqlite3
from typing import Dict, Any, List, Optional

# Format Validation Regex
REGEX_PATTERNS = {
    'passport': re.compile(r'^[A-Z][0-9]{7}$'),
    'aadhaar': re.compile(r'^[2-9][0-9]{11}$'),
    'pan': re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]$'),
    'voter_id': re.compile(r'^[A-Z]{3}[0-9]{7}$'),
    'dl': re.compile(r'^[A-Z]{2}[-\s]?[0-9a-zA-Z]{1,15}$'),
    'visa': re.compile(r'^[a-zA-Z0-9]{8,16}$')
}

VALID_GENDERS = {'M', 'F', 'MALE', 'FEMALE', 'TRANSGENDER'}

def validate_format(doc_number: str, doc_type: str) -> bool:
    """Validate document number format based on document type."""
    if doc_type not in REGEX_PATTERNS:
        return False
    
    # Strip spaces and hyphens — real documents print numbers with separators
    cleaned = doc_number.replace(' ', '').replace('-', '')
    
    if REGEX_PATTERNS[doc_type].match(cleaned):
        if doc_type == 'pan':
            return cleaned[3] in {'P', 'C', 'H', 'A', 'B', 'G', 'J', 'L', 'F', 'T'}
        return True
    return False

def parse_date(date_string: str) -> Optional[datetime.date]:
    """Parse date from string in multiple formats."""
    formats = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d.%m.%Y']
    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_string, fmt).date()
        except ValueError:
            pass
    return None

def validate_dob(dob_str: str) -> Dict[str, Any]:
    """Validate date of birth string."""
    dob = parse_date(dob_str)
    if not dob:
        return {'passed': False, 'detail': 'Invalid date format'}
    
    today = datetime.date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    
    if age < 0:
        return {'passed': False, 'detail': 'DOB is in the future'}
    if age > 120:
        return {'passed': False, 'detail': f'Age {age} exceeds maximum (120)'}
        
    return {'passed': True, 'detail': 'Valid date and age'}

def validate_expiry(expiry_str: str) -> Dict[str, Any]:
    """Validate expiry date string."""
    expiry = parse_date(expiry_str)
    if not expiry:
        return {'passed': False, 'detail': 'Invalid date format'}
        
    if expiry < datetime.date.today():
        return {'passed': False, 'detail': f'Document expired on {expiry}'}
        
    return {'passed': True, 'detail': 'Document is valid (not expired)'}

def validate_issue_expiry(issue_str: str, expiry_str: str) -> Dict[str, Any]:
    """Validate issue date is before expiry date."""
    issue = parse_date(issue_str)
    expiry = parse_date(expiry_str)
    
    if not issue or not expiry:
        return {'passed': False, 'detail': 'Invalid date format(s)'}
        
    if issue >= expiry:
        return {'passed': False, 'detail': 'Issue date is after or same as expiry date'}
        
    return {'passed': True, 'detail': 'Issue date is before expiry date'}

def check_blacklist(doc_number: str, db_path: str = 'database.db') -> Dict[str, Any]:
    """Check against 'blacklist' table in SQLite DB."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='blacklist';")
        if not cursor.fetchone():
            return {'passed': True, 'detail': 'Blacklist table not found, skipped check'}
            
        cursor.execute("SELECT reason FROM blacklist WHERE doc_number = ?", (doc_number,))
        result = cursor.fetchone()
        
        if result:
            return {'passed': False, 'detail': f'Blacklisted: {result[0]}'}
            
        return {'passed': True, 'detail': 'Not in blacklist'}
    except Exception as e:
        return {'passed': True, 'detail': f'Error checking blacklist: {str(e)}'}
    finally:
        if 'conn' in locals():
            conn.close()

def validate_gender(gender: str) -> bool:
    """Validate gender string."""
    return gender.strip().upper() in VALID_GENDERS

def validate_document(extracted_fields: Dict[str, Any], doc_type: str, db_path: str = 'database.db') -> Dict[str, Any]:
    """
    Main entry point for document validation.
    
    Args:
        extracted_fields: Dictionary containing extracted document fields.
        doc_type: Type of document (passport, aadhaar, pan, voter_id, dl, visa).
        db_path: Path to SQLite database for blacklist checking.
        
    Returns:
        Dictionary containing validation result.
    """
    checks = []
    flags = []
    
    doc_type = doc_type.lower().strip()
    
    # Normalize doc_type from AI OCR variants to internal keys
    doc_type_map = {
        'aadhaar': 'aadhaar', 'aadhaar card': 'aadhaar', 'aadhar': 'aadhaar',
        'aadhar card': 'aadhaar', 'uid': 'aadhaar',
        'passport': 'passport', 'indian passport': 'passport',
        'pan': 'pan', 'pan card': 'pan', 'permanent account number': 'pan',
        'voter id': 'voter_id', 'voter id card': 'voter_id', 'epic': 'voter_id',
        'driving licence': 'dl', 'driving license': 'dl', 'dl': 'dl',
        'visa': 'visa', 'travel visa': 'visa',
        'standard id document': 'aadhaar',  # fallback for unrecognized
    }
    doc_type = doc_type_map.get(doc_type, doc_type)
    
    # 1. Format validation
    doc_type_field = f"{doc_type}_number"
    doc_number = (extracted_fields.get(doc_type_field) or
                  extracted_fields.get('document_number') or
                  extracted_fields.get('doc_number'))
    
    if doc_number:
        passed = validate_format(doc_number, doc_type)
        checks.append({
            'field': doc_number_field,
            'check': 'format',
            'passed': passed,
            'detail': f"Valid {doc_type.upper()} format" if passed else f"Invalid {doc_type.upper()} format"
        })
        if not passed:
            flags.append('INVALID_FORMAT')
            
        # Blacklist check
        bl_check = check_blacklist(doc_number, db_path)
        checks.append({
            'field': doc_number_field,
            'check': 'blacklist',
            'passed': bl_check['passed'],
            'detail': bl_check['detail']
        })
        if not bl_check['passed']:
            flags.append('BLACKLISTED')
            
    # 2. Date validation
    dob_str = extracted_fields.get('dob')
    if dob_str:
        dob_check = validate_dob(dob_str)
        checks.append({
            'field': 'dob',
            'check': 'age_reasonable' if 'age' in dob_check['detail'].lower() else 'date_valid',
            'passed': dob_check['passed'],
            'detail': dob_check['detail']
        })
        if not dob_check['passed']:
            flags.append('UNREASONABLE_AGE' if 'age' in dob_check['detail'].lower() else 'INVALID_DOB')
            
    expiry_str = extracted_fields.get('expiry')
    if expiry_str:
        exp_check = validate_expiry(expiry_str)
        checks.append({
            'field': 'expiry',
            'check': 'expiry',
            'passed': exp_check['passed'],
            'detail': exp_check['detail']
        })
        if not exp_check['passed']:
            flags.append('EXPIRED_DOCUMENT')
            
    issue_str = extracted_fields.get('issue_date')
    if issue_str and expiry_str:
        issue_exp_check = validate_issue_expiry(issue_str, expiry_str)
        checks.append({
            'field': 'issue_date',
            'check': 'issue_before_expiry',
            'passed': issue_exp_check['passed'],
            'detail': issue_exp_check['detail']
        })
        if not issue_exp_check['passed']:
            flags.append('INVALID_ISSUE_EXPIRY')
            
    # 3. Cross-field consistency
    gender = extracted_fields.get('gender')
    if gender:
        gender_passed = validate_gender(gender)
        checks.append({
            'field': 'gender',
            'check': 'valid_value',
            'passed': gender_passed,
            'detail': 'Valid gender value' if gender_passed else 'Invalid gender value'
        })
        if not gender_passed:
            flags.append('INVALID_GENDER')
            
    mrz = extracted_fields.get('mrz')
    if mrz and doc_number:
        # Simple MRZ check: doc number should be in MRZ
        mrz_passed = doc_number in mrz
        checks.append({
            'field': 'mrz',
            'check': 'mrz_consistency',
            'passed': mrz_passed,
            'detail': 'MRZ consistent with visual zone' if mrz_passed else 'MRZ does not match visual zone'
        })
        if not mrz_passed:
            flags.append('MRZ_MISMATCH')
            
    # Calculate score
    total_checks = len(checks)
    passed_checks = sum(1 for check in checks if check['passed'])
    score = passed_checks / total_checks if total_checks > 0 else 0.0
    
    return {
        'is_valid': total_checks > 0 and total_checks == passed_checks,
        'score': round(score, 2),
        'checks': checks,
        'flags': flags
    }
