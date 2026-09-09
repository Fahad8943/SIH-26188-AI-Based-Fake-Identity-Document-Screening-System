import os
import cv2
import numpy as np
from PIL import Image, ImageChops
import exifread
import uuid

def generate_filename(prefix, ext):
    """Generate a unique filename to avoid overwriting existing images."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}"

def perform_ela(image_path, heatmap_dir, quality=90):
    """
    Error Level Analysis (ELA)
    Re-saves the image at a known quality and compares it to the original.
    Regions with different compression histories will stand out.
    """
    try:
        if not os.path.exists(heatmap_dir):
            os.makedirs(heatmap_dir)
            
        original = Image.open(image_path).convert('RGB')
        
        temp_filename = os.path.join(heatmap_dir, generate_filename('temp_ela', 'jpg'))
        original.save(temp_filename, 'JPEG', quality=quality)
        
        compressed = Image.open(temp_filename)
        
        # Calculate pixel difference
        orig_arr = np.array(original, dtype=np.float32)
        comp_arr = np.array(compressed, dtype=np.float32)
        
        diff_arr = np.abs(orig_arr - comp_arr)
        
        # Enhance difference image for better visibility
        max_val = np.max(diff_arr)
        if max_val > 0:
            enhanced = (diff_arr / max_val) * 255.0
        else:
            enhanced = diff_arr
            
        enhanced = enhanced.astype(np.uint8)
        
        heatmap_filename = generate_filename('ela_heatmap', 'jpg')
        heatmap_path = os.path.join(heatmap_dir, heatmap_filename)
        
        # Save heatmap
        cv2.imwrite(heatmap_path, cv2.cvtColor(enhanced, cv2.COLOR_RGB2BGR))
        os.remove(temp_filename)
        
        # Regional scoring: divide image into 4x4 grid
        gray_diff = cv2.cvtColor(enhanced, cv2.COLOR_RGB2GRAY)
        h, w = gray_diff.shape
        grid_h, grid_w = max(1, h // 4), max(1, w // 4)
        
        region_means = []
        for i in range(4):
            for j in range(4):
                region = gray_diff[i*grid_h:(i+1)*grid_h, j*grid_w:(j+1)*grid_w]
                if region.size > 0:
                    region_means.append(np.mean(region))
                
        variance = np.var(region_means) if region_means else 0.0
        
        # High variance between regions is suspicious
        score = min(variance / 300.0, 1.0)
        
        return score, heatmap_filename
        
    except Exception as e:
        print(f"ELA error: {e}")
        return 0.0, ""

def analyze_metadata(image_path):
    """
    EXIF/Metadata Analysis
    Checks for missing EXIF data, software tags indicating editors, and timestamp anomalies.
    """
    result = {'score': 0.0, 'software_detected': None, 'has_exif': False, 'flags': [], 'details': {}}
    try:
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f)
            
        result['has_exif'] = len(tags) > 0
        
        suspicious_software = ['photoshop', 'gimp', 'lightroom', 'premiere', 'illustrator', 'canva']
        
        for tag, value in tags.items():
            val_str = str(value)
            # Store some key tags in details without overwhelming the output
            if any(k in tag.lower() for k in ['datetime', 'model', 'make', 'software']):
                result['details'][tag] = val_str
                
            if 'software' in tag.lower():
                val_lower = val_str.lower()
                for sw in suspicious_software:
                    if sw in val_lower:
                        result['software_detected'] = val_str
                        result['flags'].append(f"Editing software detected: {val_str}")
                        result['score'] = 1.0
                        
        if not result['has_exif']:
            result['flags'].append("Missing EXIF data (common for phone-captured documents)")
            result['score'] = max(result['score'], 0.15)  # Low penalty — phone photos lack EXIF
            
        return result
    except Exception as e:
        print(f"Metadata error: {e}")
        return result

def detect_copy_move(image_path, heatmap_dir):
    """
    Copy-Move Detection
    Detects duplicated regions within the same image by matching feature points.
    """
    try:
        if not os.path.exists(heatmap_dir):
            os.makedirs(heatmap_dir)
            
        img = cv2.imread(image_path)
        if img is None:
            return 0.0, ""
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        orb = cv2.ORB_create(nfeatures=1000)
        keypoints, descriptors = orb.detectAndCompute(gray, None)
        
        if descriptors is None or len(descriptors) < 10:
            return 0.0, ""
            
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        # Find 2 nearest matches
        matches = bf.knnMatch(descriptors, descriptors, k=2)
        
        suspicious_matches = []
        for m, n in matches:
            # Lowe's ratio test and spatial distance threshold
            if m.distance < 0.75 * n.distance:
                pt1 = keypoints[m.queryIdx].pt
                pt2 = keypoints[m.trainIdx].pt
                dist = np.sqrt((pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2)
                
                if dist > 20.0:  # Matches must be spatially distant
                    suspicious_matches.append(m)
                    
        # Visualize matches
        vis_img = cv2.drawMatches(
            img, keypoints, img, keypoints, 
            suspicious_matches[:50], None, 
            flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS
        )
        
        vis_filename = generate_filename('copymove', 'jpg')
        cv2.imwrite(os.path.join(heatmap_dir, vis_filename), vis_img)
        
        # Calculate score based on ratio of suspicious matches
        score = min(len(suspicious_matches) / 20.0, 1.0)
        return score, vis_filename
        
    except Exception as e:
        print(f"Copy move error: {e}")
        return 0.0, ""

def analyze_noise(image_path):
    """
    Noise Analysis
    Evaluates noise consistency across the image. Spliced regions often have different noise patterns.
    """
    result = {'score': 0.0, 'noise_std': 0.0, 'suspicious_blocks': 0, 'total_blocks': 64}
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return result
            
        h, w = img.shape
        grid_h, grid_w = max(1, h // 8), max(1, w // 8)
        
        block_variances = []
        for i in range(8):
            for j in range(8):
                block = img[i*grid_h:(i+1)*grid_h, j*grid_w:(j+1)*grid_w]
                if block.size > 0:
                    laplacian = cv2.Laplacian(block, cv2.CV_64F)
                    block_variances.append(laplacian.var())
                
        if not block_variances:
            return result
            
        noise_std = float(np.std(block_variances))
        mean_var = float(np.mean(block_variances))
        
        suspicious = sum(1 for v in block_variances if abs(v - mean_var) > 2 * noise_std)
                
        result['noise_std'] = noise_std
        result['suspicious_blocks'] = suspicious
        result['total_blocks'] = len(block_variances)
        
        # Normalize score
        result['score'] = min(noise_std / 500.0, 1.0)
        
        return result
    except Exception as e:
        print(f"Noise analysis error: {e}")
        return result

def analyze_edges(image_path):
    """
    Edge Consistency Analysis
    Analyzes sharpness of boundaries. Unusually sharp edges may indicate pasting/splicing.
    """
    result = {'score': 0.0, 'details': ''}
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return result
            
        sobelx = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=3)
        
        magnitude = np.sqrt(sobelx**2 + sobely**2)
        
        mean_mag = np.mean(magnitude)
        std_mag = np.std(magnitude)
        
        if std_mag > mean_mag * 2:
            result['score'] = min(std_mag / 200.0, 1.0)
            result['details'] = 'Unusually sharp boundaries detected.'
        else:
            result['score'] = 0.1
            result['details'] = 'Edges appear consistent.'
            
        return result
    except Exception as e:
        print(f"Edge analysis error: {e}")
        return result

def analyze_image(image_path, heatmap_dir):
    """
    Master Analysis Function
    Runs all 5 techniques and computes a combined weighted score.
    """
    result = {
        'combined_score': 0.0,
        'ela': {'score': 0.0, 'heatmap': ''},
        'metadata': {'score': 0.0, 'software_detected': None, 'has_exif': False, 'flags': []},
        'copy_move': {'score': 0.0, 'visualization': ''},
        'noise': {'score': 0.0, 'noise_std': 0.0, 'suspicious_blocks': 0},
        'edge': {'score': 0.0, 'details': ''},
        'heatmap_filename': ''
    }
    
    # Run all analyses safely
    ela_score, ela_heatmap = perform_ela(image_path, heatmap_dir)
    metadata_res = analyze_metadata(image_path)
    cm_score, cm_vis = detect_copy_move(image_path, heatmap_dir)
    noise_res = analyze_noise(image_path)
    edge_res = analyze_edges(image_path)
    
    # Populate comprehensive result dictionary
    result['ela'] = {'score': ela_score, 'heatmap': ela_heatmap}
    
    result['metadata'] = {
        'score': metadata_res['score'],
        'software_detected': metadata_res['software_detected'],
        'has_exif': metadata_res['has_exif'],
        'flags': metadata_res['flags']
    }
    
    result['copy_move'] = {'score': cm_score, 'visualization': cm_vis}
    
    result['noise'] = {
        'score': noise_res['score'],
        'noise_std': noise_res['noise_std'],
        'suspicious_blocks': noise_res['suspicious_blocks']
    }
    
    result['edge'] = {'score': edge_res['score'], 'details': edge_res['details']}
    
    # Legacy support
    result['heatmap_filename'] = ela_heatmap
    
    # Calculate weighted combined score
    # Weights: ELA (30%), Metadata (20%), Copy-Move (20%), Noise (15%), Edge (15%)
    combined = (
        (ela_score * 0.30) + 
        (metadata_res['score'] * 0.20) + 
        (cm_score * 0.20) + 
        (noise_res['score'] * 0.15) + 
        (edge_res['score'] * 0.15)
    )
    
    result['combined_score'] = min(combined, 1.0)
    
    return result
