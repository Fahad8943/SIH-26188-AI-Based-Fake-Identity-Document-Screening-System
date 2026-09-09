import numpy as np
import pickle
import os
from sklearn.linear_model import LogisticRegression

# Expanded synthetic dataset with 12 features:
# [ela_score, text_length, keyword_count, metadata_score, copy_move_score,
#  noise_score, edge_score, validation_score, is_expired, face_detected,
#  face_quality, face_tampering_score]

# ---- GENUINE DOCUMENTS ----
# Low ELA, decent text, high keywords, clean metadata, no copy-move,
# consistent noise, good edges, valid fields, not expired, face present, good quality, no face tampering
X_genuine = np.array([
    [0.10, 150, 4, 0.05, 0.02, 0.10, 0.08, 0.95, 0, 1, 0.90, 0.05],
    [0.05, 120, 3, 0.00, 0.01, 0.08, 0.05, 1.00, 0, 1, 0.85, 0.03],
    [0.20, 200, 5, 0.10, 0.03, 0.12, 0.10, 0.90, 0, 1, 0.92, 0.08],
    [0.15, 180, 4, 0.05, 0.02, 0.09, 0.07, 0.85, 0, 1, 0.88, 0.04],
    [0.08, 140, 4, 0.00, 0.01, 0.11, 0.06, 1.00, 0, 1, 0.95, 0.02],
    [0.12, 160, 3, 0.08, 0.02, 0.10, 0.09, 0.90, 0, 1, 0.80, 0.06],
    [0.09, 130, 4, 0.03, 0.01, 0.07, 0.05, 0.95, 0, 1, 0.87, 0.03],
    [0.18, 190, 5, 0.12, 0.04, 0.13, 0.11, 0.85, 0, 1, 0.91, 0.07],
    [0.07, 110, 3, 0.02, 0.01, 0.09, 0.04, 1.00, 0, 1, 0.83, 0.02],
    [0.11, 145, 4, 0.06, 0.02, 0.08, 0.06, 0.90, 0, 1, 0.89, 0.05],
    [0.13, 170, 5, 0.04, 0.03, 0.11, 0.08, 0.95, 0, 1, 0.93, 0.04],
    [0.06, 135, 3, 0.01, 0.01, 0.07, 0.05, 1.00, 0, 1, 0.86, 0.03],
    [0.14, 155, 4, 0.07, 0.02, 0.10, 0.07, 0.90, 0, 1, 0.88, 0.06],
    [0.09, 165, 4, 0.03, 0.01, 0.09, 0.06, 0.95, 0, 1, 0.90, 0.04],
    [0.16, 185, 5, 0.09, 0.03, 0.12, 0.09, 0.85, 0, 1, 0.91, 0.05],
])
y_genuine = np.zeros(15)  # 0 = Genuine

# ---- FAKE DOCUMENTS ----
# Various combinations of suspicious signals
X_fake = np.array([
    # High ELA (tampered pixels)
    [0.80, 150, 4, 0.10, 0.05, 0.15, 0.12, 0.90, 0, 1, 0.85, 0.10],
    [0.90, 120, 2, 0.30, 0.10, 0.25, 0.20, 0.70, 0, 1, 0.70, 0.30],
    # Low text / missing keywords (blank or template)
    [0.20, 50, 1, 0.05, 0.02, 0.10, 0.08, 0.40, 0, 0, 0.00, 0.00],
    [0.15, 30, 0, 0.00, 0.01, 0.08, 0.06, 0.30, 0, 0, 0.00, 0.00],
    # High ELA + editing software metadata
    [0.70, 140, 4, 0.80, 0.08, 0.20, 0.15, 0.85, 0, 1, 0.82, 0.15],
    [0.85, 160, 2, 0.90, 0.12, 0.30, 0.25, 0.60, 0, 1, 0.75, 0.40],
    # Copy-move forgery
    [0.30, 130, 3, 0.20, 0.60, 0.35, 0.20, 0.80, 0, 1, 0.80, 0.20],
    [0.25, 155, 4, 0.15, 0.70, 0.40, 0.25, 0.75, 0, 1, 0.78, 0.25],
    # Expired document + validation failures
    [0.12, 145, 4, 0.05, 0.02, 0.10, 0.08, 0.30, 1, 1, 0.85, 0.05],
    [0.10, 160, 3, 0.08, 0.03, 0.12, 0.09, 0.20, 1, 1, 0.80, 0.08],
    # Face tampering (photo replaced)
    [0.35, 150, 4, 0.15, 0.05, 0.18, 0.12, 0.85, 0, 1, 0.60, 0.70],
    [0.40, 140, 3, 0.20, 0.08, 0.22, 0.15, 0.80, 0, 1, 0.55, 0.80],
    # Noise inconsistency (spliced document)
    [0.25, 170, 4, 0.10, 0.05, 0.65, 0.30, 0.85, 0, 1, 0.85, 0.10],
    # Everything suspicious
    [0.95, 130, 1, 0.95, 0.50, 0.60, 0.50, 0.10, 1, 0, 0.00, 0.00],
    # Moderate but combined signals
    [0.45, 100, 2, 0.40, 0.30, 0.35, 0.25, 0.50, 0, 1, 0.65, 0.35],
])
y_fake = np.ones(15)  # 1 = Fake

# Combine
X = np.vstack((X_genuine, X_fake))
y = np.concatenate((y_genuine, y_fake))

# Train
model = LogisticRegression(max_iter=1000)
model.fit(X, y)

# Save the model
model_path = os.path.join(os.path.dirname(__file__), 'saved_model.pkl')
with open(model_path, 'wb') as f:
    pickle.dump(model, f)

print(f"Model trained on {len(X)} samples with {X.shape[1]} features.")
print(f"Saved to {model_path}")

# Quick validation
preds = model.predict(X)
accuracy = (preds == y).mean()
print(f"Training accuracy: {accuracy * 100:.1f}%")
