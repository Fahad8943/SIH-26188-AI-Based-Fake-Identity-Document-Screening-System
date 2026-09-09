import pickle
import os
import numpy as np

model = None


def load_model():
    """Load the trained ML model from disk."""
    global model
    try:
        model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ml_model', 'saved_model.pkl')
        if os.path.exists(model_path):
            with open(model_path, 'rb') as f:
                model = pickle.load(f)
            print("ML model loaded successfully.")
        else:
            print(f"ML model not found at {model_path}. Run train_model.py first.")
    except Exception as e:
        print(f"Error loading model: {e}")


def predict_authenticity(ela_score, text_length, expected_keywords_count,
                         metadata_score=0.0, copy_move_score=0.0,
                         noise_score=0.0, edge_score=0.0,
                         validation_score=1.0, is_expired=0,
                         face_detected=1, face_quality=1.0,
                         face_tampering_score=0.0):
    """
    Predict document authenticity using the expanded feature vector.

    Args:
        ela_score: float 0-1, ELA tampering score
        text_length: int, number of characters extracted via OCR
        expected_keywords_count: int, keyword matches for document type
        metadata_score: float 0-1, EXIF metadata suspicion score
        copy_move_score: float 0-1, copy-move detection score
        noise_score: float 0-1, noise inconsistency score
        edge_score: float 0-1, edge consistency score
        validation_score: float 0-1, document validation pass rate
        is_expired: int 0 or 1, whether document is expired
        face_detected: int 0 or 1, whether a face was detected
        face_quality: float 0-1, face quality score
        face_tampering_score: float 0-1, face region tampering score

    Returns:
        float: confidence of document being genuine (0-1)
    """
    if model is None:
        return 0.5  # Fallback if model not loaded

    try:
        features = np.array([[
            ela_score,
            text_length,
            expected_keywords_count,
            metadata_score,
            copy_move_score,
            noise_score,
            edge_score,
            validation_score,
            is_expired,
            face_detected,
            face_quality,
            face_tampering_score,
        ]])

        probability_fake = model.predict_proba(features)[0][1]

        # We want confidence of it being *Genuine*
        confidence_genuine = 1.0 - probability_fake
        return confidence_genuine
    except Exception as e:
        print(f"Prediction Error: {e}")
        return 0.5
