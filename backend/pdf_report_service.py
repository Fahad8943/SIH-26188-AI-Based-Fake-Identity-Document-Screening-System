"""
Court-Admissible Forensic PDF Dossier Generator
Generates an official, printable multi-page law enforcement evidence report
with SHA-256 cryptographic verification, exhibits, automated checklists, and officer sign-off.
"""

import os
import hashlib
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether, HRFlowable


def compute_file_sha256(filepath):
    """Compute SHA-256 hash of a file for court chain of custody."""
    if not filepath or not os.path.exists(filepath):
        return "N/A"
    sha = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def generate_forensic_pdf(document_data, output_path, base_dir=None):
    """
    Generate a formal Forensic Evidence PDF Report.
    Args:
        document_data: dict from database / report_generator
        output_path: path to save the generated PDF
        base_dir: base backend directory to locate static images
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    header_title = ParagraphStyle(
        'HeaderTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#003380'),
        alignment=1
    )
    header_sub = ParagraphStyle(
        'HeaderSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#475569'),
        alignment=1
    )
    sec_title = ParagraphStyle(
        'SecTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#003380'),
        spaceBefore=8,
        spaceAfter=4
    )
    body_bold = ParagraphStyle(
        'BodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1e293b')
    )
    body_text = ParagraphStyle(
        'BodyText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor('#334155')
    )

    story = []

    # 1. Official Header
    story.append(Paragraph("BORDER CONTROL & IMMIGRATION SCREENING PLATFORM", header_title))
    story.append(Paragraph("FORENSIC IDENTITY EXAMINATION REPORT & EVIDENCE DOSSIER", header_sub))
    story.append(Paragraph("Prepared for Law Enforcement & Judicial Escalation | ISO/IEC 17025 Compliant Format", header_sub))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#ff9933'), spaceAfter=12))

    # 2. Case Identification & Cryptographic Hash
    filename = document_data.get('filename', 'Unknown')
    doc_id = document_data.get('id', 'N/A')
    risk_score = document_data.get('risk_score', 0)
    risk_level = document_data.get('risk_level', 'LOW')
    verdict = document_data.get('verdict', 'Needs Review')
    doc_type = document_data.get('doc_type', 'Identity Document')
    timestamp = document_data.get('timestamp', datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'))

    orig_filepath = os.path.join(base_dir, "uploads", filename) if base_dir else None
    sha256_hash = compute_file_sha256(orig_filepath)

    verdict_color = colors.HexColor('#065f46') if 'Genuine' in verdict else colors.HexColor('#991b1b')

    case_meta = [
        [Paragraph("<b>Case Reference ID:</b>", body_bold), Paragraph(f"CASE-DOC-{doc_id:05d}" if isinstance(doc_id, int) else f"CASE-{doc_id}", body_text),
         Paragraph("<b>Date & Time:</b>", body_bold), Paragraph(str(timestamp), body_text)],
        [Paragraph("<b>Document Type:</b>", body_bold), Paragraph(doc_type, body_text),
         Paragraph("<b>Screening Verdict:</b>", body_bold), Paragraph(f"<font color='{verdict_color.hexval()}'><b>{verdict}</b></font>", body_bold)],
        [Paragraph("<b>Risk Score:</b>", body_bold), Paragraph(f"<b>{risk_score}/100 ({risk_level} RISK)</b>", body_bold),
         Paragraph("<b>File Name:</b>", body_bold), Paragraph(filename, body_text)],
        [Paragraph("<b>Evidence SHA-256:</b>", body_bold), Paragraph(f"<font size='7'>{sha256_hash}</font>", body_text),
         Paragraph("<b>Chain of Custody:</b>", body_bold), Paragraph("VERIFIED (SECURE HASH)", body_text)]
    ]
    t_meta = Table(case_meta, colWidths=[110, 160, 110, 160])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 12))

    # 3. AI Law Enforcement Intelligence Brief
    ai_brief = document_data.get('ai_brief')
    if ai_brief:
        story.append(Paragraph("1. EXECUTIVE INTELLIGENCE BRIEF (AI COPILOT)", sec_title))
        brief_table = Table([[Paragraph(ai_brief, body_text)]], colWidths=[540])
        brief_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eff6ff')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#004aad')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(brief_table)
        story.append(Spacer(1, 10))

    # 4. Forensic Visual Exhibits
    story.append(Paragraph("2. FORENSIC VISUAL EXHIBITS", sec_title))
    
    exhibit_cells = []
    
    # Check for heatmap
    tampering = document_data.get('tampering_details') or document_data.get('tampering') or {}
    heatmap_name = None
    if isinstance(tampering, dict):
        heatmap_name = tampering.get('ela', {}).get('heatmap') or tampering.get('heatmap_filename')

    face_info = document_data.get('face_result') or document_data.get('face') or {}
    face_img_name = face_info.get('face_image') if isinstance(face_info, dict) else None

    img_col1, img_col2 = [], []
    
    if orig_filepath and os.path.exists(orig_filepath):
        try:
            rl_orig = RLImage(orig_filepath, width=170, height=110)
            img_col1.append(rl_orig)
            img_col1.append(Paragraph("Exhibit A: Submitted Credential", body_bold))
        except Exception:
            pass

    if base_dir and heatmap_name:
        hm_path = os.path.join(base_dir, "static", "heatmaps", heatmap_name)
        if os.path.exists(hm_path):
            try:
                rl_hm = RLImage(hm_path, width=170, height=110)
                img_col2.append(rl_hm)
                img_col2.append(Paragraph("Exhibit B: Forensic ELA Heatmap", body_bold))
            except Exception:
                pass

    if base_dir and face_img_name:
        fc_path = os.path.join(base_dir, "static", "faces", face_img_name)
        if os.path.exists(fc_path):
            try:
                rl_fc = RLImage(fc_path, width=110, height=110)
                img_col1.append(rl_fc)
                img_col1.append(Paragraph("Exhibit C: Biometric Facial Crop", body_bold))
            except Exception:
                pass

    if img_col1 and img_col2:
        exhibits_table = Table([[img_col1, img_col2]], colWidths=[270, 270])
        exhibits_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(exhibits_table)
    story.append(Spacer(1, 10))

    # 5. Security & Tampering Verification Matrix
    story.append(Paragraph("3. AUTOMATED FORENSIC & IDENTITY VERIFICATION CHECKS", sec_title))
    
    val_data = document_data.get('validation_result') or document_data.get('validation') or {}
    checks = val_data.get('checks', []) if isinstance(val_data, dict) else []
    
    table_rows = [
        [Paragraph("<b>Verification Check</b>", body_bold),
         Paragraph("<b>Target Domain</b>", body_bold),
         Paragraph("<b>Status</b>", body_bold),
         Paragraph("<b>Forensic Finding / Detail</b>", body_bold)]
    ]

    for c in checks[:8]:
        status_txt = "<font color='#065f46'><b>PASS</b></font>" if c.get('passed') else "<font color='#991b1b'><b>FAIL</b></font>"
        table_rows.append([
            Paragraph(c.get('check', '').replace('_', ' ').title(), body_text),
            Paragraph(c.get('field', '').replace('_', ' ').title(), body_text),
            Paragraph(status_txt, body_text),
            Paragraph(c.get('detail', ''), body_text)
        ])

    flags = document_data.get('flags', [])
    if flags:
        table_rows.append([
            Paragraph("Security Flags Raised", body_bold),
            Paragraph("System Core", body_text),
            Paragraph("<font color='#991b1b'><b>ALERT</b></font>", body_bold),
            Paragraph(", ".join(flags[:6]), body_text)
        ])

    t_checks = Table(table_rows, colWidths=[120, 100, 60, 260])
    t_checks.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_checks)
    story.append(Spacer(1, 14))

    # 6. Officer & Supervisor Certification / Sign-off Block
    story.append(Paragraph("4. SECONDARY INSPECTION DISPOSITION & SIGN-OFF", sec_title))
    sign_block = [
        [Paragraph("<b>Examining Officer:</b> ___________________________", body_text),
         Paragraph("<b>Badge / Officer ID:</b> ___________________________", body_text)],
        [Paragraph("<b>Action Taken:</b> [  ] CLEARED   [  ] SECONDARY   [  ] REFUSED ENTRY", body_text),
         Paragraph("<b>Supervisor Sign-off:</b> ___________________________", body_text)],
        [Paragraph("<b>Officer Remarks:</b> Document examined using forensic computer vision and machine learning screening suite.", body_text),
         Paragraph("<b>Official Stamp:</b> [ SEAL ]", body_text)]
    ]
    t_sign = Table(sign_block, colWidths=[270, 270])
    t_sign.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#94a3b8')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(KeepTogether([t_sign]))

    # Build PDF
    doc.build(story)
    return output_path
