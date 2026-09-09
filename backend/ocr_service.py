import cv2
import numpy as np
import pytesseract
import re
import os
import tempfile

def preprocess_image(image_path: str) -> str:
    """
    Preprocess image for better OCR results.
    - Grayscale
    - Noise removal (Gaussian blur)
    - Adaptive thresholding
    - Morphological operations
    - Deskewing
    
    Returns the path to the preprocessed temporary image.
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            return image_path
        
        # Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Noise removal (Gaussian blur)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # Morphological operations to remove small noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        # Deskewing (basic implementation)
        coords = np.column_stack(np.where(opened > 0))
        if len(coords) > 0:
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
            (h, w) = opened.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(
                opened, M, (w, h), 
                flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
            )
        else:
            rotated = opened
            
        # Save preprocessed image to temporary file
        fd, temp_path = tempfile.mkstemp(suffix='.png')
        os.close(fd)
        cv2.imwrite(temp_path, rotated)
        
        return temp_path
    except Exception as e:
        print(f"Error in preprocess_image: {e}")
        return image_path

def extract_text(image_path: str) -> str:
    """Extract text from image using pytesseract."""
    try:
        text = pytesseract.image_to_string(image_path)
        return text
    except Exception as e:
        print(f"Error in extract_text (is tesseract installed?): {e}")
        return ""

def identify_document_type(text: str) -> str:
    """Identify document type using a weighted keyword scoring system."""
    if not text:
        return "Unknown"
        
    text_upper = text.upper()
    
    scoring = {
        "Passport": {"PASSPORT": 10, "REPUBLIC": 5, "MRZ": 2, "NATIONALITY": 3, "ISSUING": 4},
        "Visa": {"VISA": 10, "ENTRY": 5, "STAY": 4, "DURATION": 3},
        "Aadhaar": {"GOVERNMENT OF INDIA": 8, "AADHAAR": 10, "VID": 5, "MALE": 2, "FEMALE": 2},
        "PAN": {"INCOME TAX DEPARTMENT": 8, "GOVT. OF INDIA": 5, "PERMANENT ACCOUNT NUMBER": 10, "PAN": 5},
        "Voter ID": {"ELECTION COMMISSION OF INDIA": 10, "ELECTOR'S PHOTO IDENTITY CARD": 8, "VOTER": 5, "EPIC": 5},
        "Driving Licence": {"DRIVING LICENCE": 10, "TRANSPORT DEPARTMENT": 5, "VEHICLE": 4, "RTO": 3, "DL": 4}
    }
    
    max_score = 0
    best_match = "Unknown"
    
    for doc_type, keywords in scoring.items():
        score = sum(weight for word, weight in keywords.items() if word in text_upper)
        if score > max_score:
            max_score = score
            best_match = doc_type
            
    return best_match if max_score >= 5 else "Unknown"

def extract_fields(text: str, doc_type: str) -> dict:
    """Extract structured fields using regex patterns based on document type."""
    fields = {}
    if not text:
        return fields
        
    # Helper to safely get regex match
    def get_match(pattern, search_text):
        match = re.search(pattern, search_text)
        return match.group(0) if match else None

    # Base init for return dictionary structure per doc type
    if doc_type == "Passport":
        fields = {
            'name': None,
            'passport_number': get_match(r'\b[A-Z][0-9]{7}\b', text),
            'nationality': None,
            'dob': None,
            'date_of_expiry': None,
            'gender': None,
            'mrz_line1': None,
            'mrz_line2': None
        }
        # Extract MRZ lines if possible
        mrz_lines = re.findall(r'^[P<][A-Z0-9<]{43}$', text, re.MULTILINE)
        if len(mrz_lines) >= 2:
            fields['mrz_line1'] = mrz_lines[0]
            fields['mrz_line2'] = mrz_lines[1]
            
    elif doc_type == "Visa":
        fields = {
            'visa_number': None,
            'visa_type': None,
            'entry_date': None,
            'stay_duration': None
        }
    elif doc_type == "Aadhaar":
        fields = {
            'name': None,
            'aadhaar_number': get_match(r'\b\d{4}\s?\d{4}\s?\d{4}\b', text),
            'dob': None,
            'gender': None,
            'address': None
        }
    elif doc_type == "PAN":
        fields = {
            'name': None,
            'pan_number': get_match(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', text),
            'dob': None,
            'fathers_name': None
        }
    elif doc_type == "Voter ID":
        fields = {
            'name': None,
            'voter_id': get_match(r'\b[A-Z]{3}[0-9]{7}\b', text),
            'dob': None,
            'gender': None,
            'address': None
        }
    elif doc_type == "Driving Licence":
        fields = {
            'name': None,
            'dl_number': None,
            'dob': None,
            'validity': None,
            'address': None,
            'vehicle_class': None
        }
        
    return fields

def parse_mrz(text: str) -> dict:
    """Parse Type 3 MRZ lines (2x44 chars) commonly found in passports."""
    if not text:
        return None
        
    # Match exactly 44 chars that are uppercase alphanumeric or <
    mrz_lines = re.findall(r'^[A-Z0-9<]{44}$', text, re.MULTILINE)
    
    if len(mrz_lines) >= 2:
        line1 = mrz_lines[0]
        line2 = mrz_lines[1]
        
        # Passport MRZ (Type 3) starts with P
        if line1.startswith('P'):
            doc_type = line1[0:2].replace('<', '')
            country = line1[2:5].replace('<', '')
            
            names = line1[5:].split('<<')
            surname = names[0].replace('<', ' ').strip() if len(names) > 0 else ''
            given_names = names[1].replace('<', ' ').strip() if len(names) > 1 else ''
            
            doc_number = line2[0:9].replace('<', '')
            nationality = line2[10:13].replace('<', '')
            dob = line2[13:19]
            sex = line2[20]
            expiry_date = line2[21:27]
            
            return {
                'doc_type': doc_type,
                'country': country,
                'surname': surname,
                'given_names': given_names,
                'doc_number': doc_number,
                'nationality': nationality,
                'dob': dob,
                'sex': sex,
                'expiry_date': expiry_date
            }
            
    return None
