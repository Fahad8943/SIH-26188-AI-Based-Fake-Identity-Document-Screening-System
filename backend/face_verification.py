import cv2
import os
import numpy as np

YUNET_PATH = os.path.join(os.path.dirname(__file__), 'yunet.onnx')


def detect_faces(image_path):
    """Detect faces using modern OpenCV FaceDetectorYN (YuNet) or legacy Haar."""
    try:
        if not os.path.exists(image_path):
            return []
        
        img = cv2.imread(image_path)
        if img is None:
            return []
            
        h, w = img.shape[:2]

        # 1. Modern OpenCV YuNet detector
        if os.path.exists(YUNET_PATH) and hasattr(cv2, 'FaceDetectorYN_create'):
            try:
                detector = cv2.FaceDetectorYN_create(YUNET_PATH, '', (w, h), score_threshold=0.55)
                _, faces = detector.detect(img)
                if faces is not None and len(faces) > 0:
                    results = []
                    for f in faces:
                        fx, fy, fw, fh = int(f[0]), int(f[1]), int(f[2]), int(f[3])
                        if fw > 15 and fh > 15:
                            results.append((max(0, fx), max(0, fy), min(w - max(0, fx), fw), min(h - max(0, fy), fh)))
                    if results:
                        return results
            except Exception:
                pass

        # 2. Legacy Haar Cascade fallback
        if hasattr(cv2, 'CascadeClassifier') and hasattr(cv2, 'data'):
            try:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
                if len(faces) > 0:
                    return [tuple(int(v) for v in face) for face in faces]
            except Exception:
                pass

        return []
    except Exception as e:
        print(f"Error in detect_faces: {e}")
        return []

def extract_face(image_path, output_dir):
    """Extract the largest face from the image with 20% padding and save it."""
    try:
        faces = detect_faces(image_path)
        if not faces:
            return None, None
            
        # Get largest face by area (w * h)
        largest_face = max(faces, key=lambda f: f[2] * f[3])
        x, y, w, h = largest_face
        
        img = cv2.imread(image_path)
        if img is None:
            return None, None
            
        # 20% padding
        pad_x = int(w * 0.2)
        pad_y = int(h * 0.2)
        
        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(img.shape[1], x + w + pad_x)
        y2 = min(img.shape[0], y + h + pad_y)
        
        face_img = img[y1:y2, x1:x2]
        
        os.makedirs(output_dir, exist_ok=True)
        filename = f"face_{os.path.basename(image_path)}"
        output_path = os.path.join(output_dir, filename)
        
        cv2.imwrite(output_path, face_img)
        
        return filename, largest_face
    except Exception as e:
        print(f"Error in extract_face: {e}")
        return None, None


def compute_face_vector(face_crop):
    """Compute normalized 128-d color/gradient biometric descriptor vector."""
    try:
        if face_crop is None or face_crop.size == 0:
            return None
        resized = cv2.resize(face_crop, (64, 64))
        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 4, 4], [0, 180, 0, 256, 0, 256])
        vec = hist.flatten().astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return [round(float(x), 5) for x in vec]
    except Exception as e:
        print(f"Error computing face vector: {e}")
        return None

def check_face_quality(image_path, face_bbox, image_shape):
    """Check the quality of the detected face region."""
    default_res = {
        'quality_score': 0.0,
        'checks': {'size_ok': False, 'position_ok': False, 'brightness_ok': False, 'sharpness_ok': False},
        'details': 'Error checking face quality'
    }
    
    if face_bbox is None or image_shape is None:
        return default_res
        
    try:
        x, y, w, h = face_bbox
        img_h, img_w = image_shape[:2]
        img_area = img_h * img_w
        
        if img_area == 0:
            return default_res
            
        face_area = w * h
        size_ratio = face_area / img_area
        
        # Check size (5% to 40%)
        size_ok = 0.05 <= size_ratio <= 0.40
        
        # Check position (not extreme edge)
        margin = 0.05
        position_ok = (x > img_w * margin) and (y > img_h * margin) and \
                      ((x + w) < img_w * (1 - margin)) and ((y + h) < img_h * (1 - margin))
                      
        img = cv2.imread(image_path)
        if img is None:
            return default_res
            
        face_roi = img[y:y+h, x:x+w]
        
        # Check brightness
        gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray_face)
        brightness_ok = 50 <= mean_brightness <= 200
        
        # Check sharpness (Laplacian variance)
        laplacian_var = cv2.Laplacian(gray_face, cv2.CV_64F).var()
        sharpness_ok = laplacian_var > 100
        
        # Calculate score based on passing checks
        checks = [size_ok, position_ok, brightness_ok, sharpness_ok]
        score = sum(checks) / len(checks)
        
        return {
            'quality_score': score,
            'checks': {
                'size_ok': size_ok,
                'position_ok': position_ok,
                'brightness_ok': brightness_ok,
                'sharpness_ok': sharpness_ok
            },
            'details': 'Quality checks completed'
        }
    except Exception as e:
        print(f"Error in check_face_quality: {e}")
        return default_res

def check_face_tampering(image_path, face_bbox):
    """Check for signs of tampering around the face region."""
    default_res = {
        'tampering_score': 0.0,
        'flags': [],
        'details': 'Error checking tampering'
    }
    
    if face_bbox is None:
        return default_res
        
    try:
        img = cv2.imread(image_path)
        if img is None:
            return default_res
            
        x, y, w, h = face_bbox
        img_h, img_w = img.shape[:2]
        
        # Surrounding region (e.g. 50% larger box)
        pad_x = int(w * 0.5)
        pad_y = int(h * 0.5)
        
        bg_x1, bg_y1 = max(0, x - pad_x), max(0, y - pad_y)
        bg_x2, bg_y2 = min(img_w, x + w + pad_x), min(img_h, y + h + pad_y)
        
        face_roi = img[y:y+h, x:x+w]
        bg_roi = img[bg_y1:bg_y2, bg_x1:bg_x2]
        
        flags = []
        tampering_score = 0.0
        
        # Basic ELA approximation - resave at 90% quality and find difference
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
        _, encimg = cv2.imencode('.jpg', bg_roi, encode_param)
        decimg = cv2.imdecode(encimg, 1)
        
        diff = cv2.absdiff(bg_roi, decimg)
        diff_max = np.max(diff, axis=2)
        ela_val = np.mean(diff_max)
        
        # Calculate noise consistency
        gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        gray_bg = cv2.cvtColor(bg_roi, cv2.COLOR_BGR2GRAY)
        
        noise_face = cv2.Laplacian(gray_face, cv2.CV_64F).var()
        noise_bg = cv2.Laplacian(gray_bg, cv2.CV_64F).var()
        
        noise_diff = abs(noise_face - noise_bg) / max(noise_face, noise_bg, 1)
        
        if noise_diff > 0.5:
            flags.append('Inconsistent noise between face and background')
            tampering_score += 0.5
            
        if ela_val > 15: # Arbitrary threshold for demo
            flags.append('High ELA difference near face')
            tampering_score += 0.5
            
        return {
            'tampering_score': min(1.0, tampering_score),
            'flags': flags,
            'details': 'Tampering checks completed'
        }
    except Exception as e:
        print(f"Error in check_face_tampering: {e}")
        return default_res

def compare_faces(doc_image_path, selfie_image_path):
    """Compare a face from document with a selfie."""
    default_res = {
        'match_score': 0.0,
        'histogram_score': 0.0,
        'structural_score': 0.0,
        'match_verdict': 'Uncertain'
    }
    try:
        doc_faces = detect_faces(doc_image_path)
        selfie_faces = detect_faces(selfie_image_path)
        
        if not doc_faces or not selfie_faces:
            return default_res
            
        doc_img = cv2.imread(doc_image_path)
        selfie_img = cv2.imread(selfie_image_path)
        
        if doc_img is None or selfie_img is None:
            return default_res
            
        d_x, d_y, d_w, d_h = max(doc_faces, key=lambda f: f[2]*f[3])
        s_x, s_y, s_w, s_h = max(selfie_faces, key=lambda f: f[2]*f[3])
        
        doc_face_roi = doc_img[d_y:d_y+d_h, d_x:d_x+d_w]
        selfie_face_roi = selfie_img[s_y:s_y+s_h, s_x:s_x+s_w]
        
        # Resize to 150x150
        doc_face_res = cv2.resize(doc_face_roi, (150, 150))
        selfie_face_res = cv2.resize(selfie_face_roi, (150, 150))
        
        doc_gray = cv2.cvtColor(doc_face_res, cv2.COLOR_BGR2GRAY)
        selfie_gray = cv2.cvtColor(selfie_face_res, cv2.COLOR_BGR2GRAY)
        
        # Histogram comparison
        hist_doc = cv2.calcHist([doc_gray], [0], None, [256], [0, 256])
        hist_selfie = cv2.calcHist([selfie_gray], [0], None, [256], [0, 256])
        cv2.normalize(hist_doc, hist_doc, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        cv2.normalize(hist_selfie, hist_selfie, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        
        hist_score = cv2.compareHist(hist_doc, hist_selfie, cv2.HISTCMP_CORREL)
        hist_score = max(0, hist_score) # Ensure >= 0
        
        # Structural similarity approximation (MSE based)
        err = np.sum((doc_gray.astype("float") - selfie_gray.astype("float")) ** 2)
        err /= float(doc_gray.shape[0] * doc_gray.shape[1])
        
        # Convert error to a 0-1 score roughly (max err is 255^2)
        ssim_approx = 1.0 - min(err / 10000.0, 1.0)
        
        match_score = (hist_score * 0.4) + (ssim_approx * 0.6)
        
        verdict = 'Match' if match_score > 0.6 else ('No Match' if match_score < 0.3 else 'Uncertain')
        
        return {
            'match_score': match_score,
            'histogram_score': hist_score,
            'structural_score': ssim_approx,
            'match_verdict': verdict
        }
        
    except Exception as e:
        print(f"Error in compare_faces: {e}")
        return default_res

def analyze_face(image_path, output_dir, selfie_path=None):
    """Master function to analyze face in a document image."""
    res = {
        'face_detected': False,
        'num_faces': 0,
        'face_bbox': None,
        'face_image': None,
        'quality': {'quality_score': 0.0, 'checks': {}},
        'tampering': {'tampering_score': 0.0, 'flags': []},
        'comparison': None,
        'flags': []
    }
    
    try:
        if not os.path.exists(image_path):
            res['flags'].append("Image not found")
            return res
            
        img = cv2.imread(image_path)
        if img is None:
            res['flags'].append("Failed to load image")
            return res
            
        faces = detect_faces(image_path)
        res['num_faces'] = len(faces)
        
        if not faces:
            res['flags'].append("No face detected")
            return res
            
        res['face_detected'] = True
        
        face_filename, face_bbox = extract_face(image_path, output_dir)
        res['face_image'] = face_filename
        res['face_bbox'] = face_bbox
        
        if face_bbox:
            res['quality'] = check_face_quality(image_path, face_bbox, img.shape)
            res['tampering'] = check_face_tampering(image_path, face_bbox)
            
            # Extract biometric feature vector for Sybil cross-matching
            fx, fy, fw, fh = face_bbox
            face_crop = img[fy:fy+fh, fx:fx+fw]
            res['face_vector'] = compute_face_vector(face_crop)
            
            if res['tampering']['flags']:
                res['flags'].extend(res['tampering']['flags'])
                
        if selfie_path and os.path.exists(selfie_path):
            res['comparison'] = compare_faces(image_path, selfie_path)
            
    except Exception as e:
        res['flags'].append(f"Analysis error: {str(e)}")
        
    return res
