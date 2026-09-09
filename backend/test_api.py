import requests
from PIL import Image, ImageDraw
import os
import time
import json

# Wait for server to start
time.sleep(1)

# Create a dummy image mimicking an ID
img = Image.new('RGB', (400, 200), color=(255, 255, 255))
d = ImageDraw.Draw(img)
d.text((10, 10), "GOVERNMENT OF INDIA", fill=(0, 0, 0))
d.text((10, 50), "Permanent Account Number: ABCDE1234F", fill=(0, 0, 0))
d.text((10, 90), "Name: ADITYA THAKUR", fill=(0, 0, 0))
d.text((10, 130), "DOB: 01/01/2000", fill=(0, 0, 0))

img_path = "test_dummy_id.jpg"
img.save(img_path)

print("--- Dummy Image Created ---")
print("Uploading to backend...\n")

try:
    with open(img_path, 'rb') as f:
        files = {'file': ('test_dummy_id.jpg', f, 'image/jpeg')}
        response = requests.post('http://localhost:8000/upload', files=files)

    data = response.json()
    
    if 'error' in data:
        print(f"ERROR: {data['error']}")
    else:
        print("=" * 60)
        print("  DOCUMENT SCREENING RESULTS")
        print("=" * 60)
        print(f"  Verdict:      {data.get('verdict', 'N/A')}")
        print(f"  Risk Score:   {data.get('risk_score', 'N/A')}/100")
        print(f"  Risk Level:   {data.get('risk_level', 'N/A')}")
        print(f"  Confidence:   {data.get('confidence', 'N/A')}%")
        print(f"  Doc Type:     {data.get('doc_type', 'N/A')}")
        print(f"  Forgery:      {data.get('forgery_score', 'N/A')}")
        print()
        
        # Module scores
        modules = data.get('module_scores', {})
        if modules:
            print("  MODULE SCORES:")
            for k, m in modules.items():
                print(f"    {m.get('label','')}: {m.get('score',0):.1f} ({m.get('status','')})")
        
        # Flags
        flags = data.get('flags', [])
        if flags:
            print(f"\n  FLAGS: {', '.join(flags)}")
        
        # Recommendations
        recs = data.get('recommendations', [])
        if recs:
            print(f"\n  RECOMMENDATIONS:")
            for r in recs:
                print(f"    {r}")
        
        # Face
        face = data.get('face', {})
        if face:
            print(f"\n  FACE: Detected={face.get('face_detected', False)}, Faces={face.get('num_faces', 0)}")
        
        # Validation
        val = data.get('validation', {})
        if val:
            print(f"  VALIDATION: Score={val.get('score', 'N/A')}, Valid={val.get('is_valid', 'N/A')}")
            checks = val.get('checks', [])
            for c in checks[:5]:
                icon = '✓' if c.get('passed') else '✗'
                print(f"    [{icon}] {c.get('field','')}: {c.get('detail','')}")
        
        print("\n" + "=" * 60)
        print("\nFull JSON response:")
        print(json.dumps(data, indent=2, default=str))

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    if os.path.exists(img_path):
        os.remove(img_path)
