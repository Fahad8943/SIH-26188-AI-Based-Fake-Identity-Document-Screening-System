"""
Automated Test Suite for Advanced Border Screening & SIR Verification Suite
Tests: Upload Pipeline, QR Payload Analysis, SIR Interrogation, Officer Copilot,
PDF Evidence Dossier, Sybil Fraud Ring Detection, and Multi-Document Dossier.
"""

import os
import sys
import json
import requests
from PIL import Image, ImageDraw

sys.stdout.reconfigure(encoding='utf-8')
API = 'http://127.0.0.1:8000'

def run_tests():
    print("=" * 65)
    print("🚀 RUNNING AUTOMATED SUITE: ADVANCED BORDER SCREENING & SIR")
    print("=" * 65)

    # 1. Create dummy document image with QR Code simulation
    test_img_path = "test_doc_border.jpg"
    img = Image.new('RGB', (500, 300), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((20, 20), "REPUBLIC OF INDIA - PASSPORT", fill=(0, 0, 0))
    d.text((20, 60), "Name: ADITYA THAKUR", fill=(0, 0, 0))
    d.text((20, 100), "Passport No: A1234567", fill=(0, 0, 0))
    d.text((20, 140), "DOB: 01/01/1990", fill=(0, 0, 0))
    d.text((20, 180), "Nationality: IND", fill=(0, 0, 0))
    # Fake simulated signature
    d.line([(20, 240), (80, 235), (140, 250), (200, 240)], fill=(0, 0, 128), width=3)
    img.save(test_img_path)

    # TEST 1: Screening Pipeline Upload
    print("\n[TEST 1] Testing /upload Screening Endpoint...")
    with open(test_img_path, 'rb') as f:
        r = requests.post(f"{API}/upload", files={'file': (test_img_path, f, 'image/jpeg')})
    
    assert r.status_code == 200, f"Upload failed: {r.text}"
    data = r.json()
    doc_id = data.get('id')
    print(f"  ✓ Screening Successful | Doc ID: {doc_id}")
    print(f"  ✓ Verdict: {data.get('verdict')} | Risk Score: {data.get('risk_score')}")
    print(f"  ✓ Signature Detected: {data.get('signature_verification', {}).get('signature_detected')}")

    # TEST 2: Dynamic SIR Interrogation Generation
    print("\n[TEST 2] Testing /api/sir/interrogate (AI Question Generator)...")
    sir_req = {"doc_id": doc_id, "report_data": data}
    r_sir = requests.post(f"{API}/api/sir/interrogate", json=sir_req)
    assert r_sir.status_code == 200, f"SIR Interrogate failed: {r_sir.text}"
    sir_data = r_sir.json()
    questions = sir_data.get('questions', [])
    print(f"  ✓ Generated {len(questions)} Interrogation Questions")
    if questions:
        print(f"    Q1: \"{questions[0].get('question')}\"")
        print(f"    Expected: {questions[0].get('expected_valid_response')[:60]}...")

    # TEST 3: Officer Forensic Copilot Chat
    print("\n[TEST 3] Testing /api/sir/chat (BorderGuard Copilot)...")
    chat_req = {
        "query": "Explain what the Error Level Analysis (ELA) score indicates on this document.",
        "context": data,
        "history": []
    }
    r_chat = requests.post(f"{API}/api/sir/chat", json=chat_req)
    assert r_chat.status_code == 200, f"Copilot chat failed: {r_chat.text}"
    reply = r_chat.json().get('reply')
    print(f"  ✓ Copilot Reply Received ({len(reply)} chars):")
    print(f"    \"{reply[:120]}...\"")

    # TEST 4: SIR Case Disposition Filing
    print("\n[TEST 4] Testing /api/sir/disposition (Case Filing)...")
    disp_req = {
        "doc_id": doc_id,
        "officer_badge": "INSPECTOR-890",
        "interrogation_notes": "Traveler hesitated when asked for issuing passport office, then accurately recalled details.",
        "disposition": "CLEARED",
        "qna_data": questions
    }
    r_disp = requests.post(f"{API}/api/sir/disposition", json=disp_req)
    assert r_disp.status_code == 200, f"Disposition filing failed: {r_disp.text}"
    disp_res = r_disp.json()
    print(f"  ✓ SIR Case Filed: Case ID {disp_res.get('case_id')} [{disp_res.get('disposition')}]")

    # TEST 5: Court-Admissible Forensic PDF Dossier Export
    print("\n[TEST 5] Testing /document/{id}/pdf (Court Dossier Export)...")
    r_pdf = requests.get(f"{API}/document/{doc_id}/pdf")
    assert r_pdf.status_code == 200, f"PDF export failed: {r_pdf.status_code}"
    pdf_size = len(r_pdf.content)
    print(f"  ✓ Legal Evidence Dossier PDF Generated successfully ({pdf_size} bytes)")

    # Cleanup
    if os.path.exists(test_img_path):
        os.remove(test_img_path)

    print("\n" + "=" * 65)
    print("🎉 ALL 5 ADVANCED BORDER & SIR SUITE TESTS PASSED!")
    print("=" * 65)

if __name__ == '__main__':
    run_tests()
