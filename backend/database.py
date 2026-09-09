import sqlite3
import os
import json
import numpy as np

DB_PATH = os.path.join(os.path.dirname(__file__), 'documents.db')


def init_db():
    """Initialize the database with all required tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Main documents table — expanded schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            verdict TEXT,
            confidence REAL,
            risk_score REAL,
            risk_level TEXT,
            forgery_score REAL,
            doc_type TEXT,
            extracted_text TEXT,
            extracted_fields TEXT,
            validation_result TEXT,
            tampering_details TEXT,
            face_result TEXT,
            flags TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Blacklist table for flagged document numbers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_number TEXT UNIQUE NOT NULL,
            doc_type TEXT,
            reason TEXT,
            added_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Secondary Inspection Referral (SIR) cases table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sir_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER,
            officer_badge TEXT,
            interrogation_notes TEXT,
            disposition TEXT,
            qna_data TEXT,
            supervisor_id TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(doc_id) REFERENCES documents(id)
        )
    ''')

    # Biometric index table for Cross-Checkpoint Sybil & Fraud Ring Detection
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS biometric_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER,
            doc_number TEXT,
            passenger_name TEXT,
            face_vector TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(doc_id) REFERENCES documents(id)
        )
    ''')

    # Seed some demo blacklist entries
    demo_entries = [
        ('A1234567', 'Passport', 'Reported stolen - Interpol Red Notice'),
        ('ABCDE9999Z', 'PAN', 'Linked to financial fraud investigation'),
        ('999988887777', 'Aadhaar', 'Flagged for identity duplication'),
        ('XYZ1234567', 'Voter ID', 'Deceased individual - registry mismatch'),
        ('DL-9999999999999', 'Driving Licence', 'Suspended - court order'),
    ]
    for doc_number, doc_type, reason in demo_entries:
        try:
            cursor.execute(
                'INSERT OR IGNORE INTO blacklist (doc_number, doc_type, reason) VALUES (?, ?, ?)',
                (doc_number, doc_type, reason)
            )
        except sqlite3.IntegrityError:
            pass

    # Migrate old table if columns are missing
    _migrate_table(cursor)

    conn.commit()
    conn.close()


def _migrate_table(cursor):
    """Add new columns to existing documents table if they don't exist."""
    existing_cols = set()
    try:
        cursor.execute("PRAGMA table_info(documents)")
        for row in cursor.fetchall():
            existing_cols.add(row[1])
    except Exception:
        return

    new_columns = {
        'risk_score': 'REAL',
        'risk_level': 'TEXT',
        'extracted_fields': 'TEXT',
        'validation_result': 'TEXT',
        'tampering_details': 'TEXT',
        'face_result': 'TEXT',
        'flags': 'TEXT',
    }

    for col_name, col_type in new_columns.items():
        if col_name not in existing_cols:
            try:
                cursor.execute(f'ALTER TABLE documents ADD COLUMN {col_name} {col_type}')
            except sqlite3.OperationalError:
                pass


def _clean_json_dump(obj):
    if obj is None:
        return None
    try:
        return json.dumps(obj, default=lambda o: bool(o) if isinstance(o, (np.bool_, np.bool)) else (float(o) if isinstance(o, np.floating) else (int(o) if isinstance(o, np.integer) else str(o))))
    except Exception:
        return json.dumps(str(obj))


def save_document_result(filename, verdict, confidence, risk_score, risk_level,
                         forgery_score, doc_type, extracted_text,
                         extracted_fields=None, validation_result=None,
                         tampering_details=None, face_result=None, flags=None):
    """Save a complete document analysis result to the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO documents (
                filename, verdict, confidence, risk_score, risk_level,
                forgery_score, doc_type, extracted_text,
                extracted_fields, validation_result,
                tampering_details, face_result, flags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            filename, verdict, confidence, risk_score, risk_level,
            forgery_score, doc_type, extracted_text,
            _clean_json_dump(extracted_fields),
            _clean_json_dump(validation_result),
            _clean_json_dump(tampering_details),
            _clean_json_dump(face_result),
            _clean_json_dump(flags),
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database error: {e}")


def get_history():
    """Retrieve scan history with all fields."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM documents ORDER BY timestamp DESC LIMIT 50')
        rows = cursor.fetchall()
        col_names = [description[0] for description in cursor.description]
        conn.close()

        history = []
        for row in rows:
            entry = {}
            for i, col in enumerate(col_names):
                val = row[i]
                # Parse JSON fields back to dicts/lists
                if col in ('extracted_fields', 'validation_result', 'tampering_details', 'face_result', 'flags'):
                    if val:
                        try:
                            val = json.loads(val)
                        except (json.JSONDecodeError, TypeError):
                            pass
                entry[col] = val
            history.append(entry)
        return history
    except Exception as e:
        print(f"Database error: {e}")
        return []


def get_document_by_id(doc_id):
    """Retrieve a single document result by ID."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM documents WHERE id = ?', (doc_id,))
        row = cursor.fetchone()
        col_names = [description[0] for description in cursor.description]
        conn.close()

        if not row:
            return None

        entry = {}
        for i, col in enumerate(col_names):
            val = row[i]
            if col in ('extracted_fields', 'validation_result', 'tampering_details', 'face_result', 'flags'):
                if val:
                    try:
                        val = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
            entry[col] = val
        return entry
    except Exception as e:
        print(f"Database error: {e}")
        return None


def get_stats():
    """Get dashboard statistics."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM documents')
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM documents WHERE verdict LIKE '%Fake%' OR verdict LIKE '%Suspicious%'")
        flagged = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM documents WHERE verdict LIKE '%Genuine%'")
        genuine = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(risk_score) FROM documents WHERE risk_score IS NOT NULL")
        avg_risk = cursor.fetchone()[0] or 0

        cursor.execute("SELECT doc_type, COUNT(*) FROM documents GROUP BY doc_type ORDER BY COUNT(*) DESC")
        type_breakdown = {row[0]: row[1] for row in cursor.fetchall() if row[0]}

        cursor.execute("SELECT risk_level, COUNT(*) FROM documents WHERE risk_level IS NOT NULL GROUP BY risk_level")
        risk_breakdown = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()
        return {
            'total_scans': total,
            'flagged': flagged,
            'genuine': genuine,
            'avg_risk_score': round(avg_risk, 2),
            'doc_type_breakdown': type_breakdown,
            'risk_breakdown': risk_breakdown,
        }
    except Exception as e:
        print(f"Database error: {e}")
        return {'total_scans': 0, 'flagged': 0, 'genuine': 0, 'avg_risk_score': 0}


def check_blacklist(doc_number):
    """Check if a document number is in the blacklist."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT doc_type, reason FROM blacklist WHERE doc_number = ?', (doc_number,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return True, row[1]
        return False, None
    except Exception as e:
        print(f"Blacklist check error: {e}")
        return False, None


def save_sir_case(doc_id, officer_badge, interrogation_notes, disposition, qna_data=None, supervisor_id=None):
    """File a Secondary Inspection Referral (SIR) case result."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sir_cases (
                doc_id, officer_badge, interrogation_notes, disposition, qna_data, supervisor_id
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            doc_id,
            officer_badge,
            interrogation_notes,
            disposition,
            json.dumps(qna_data) if qna_data else None,
            supervisor_id
        ))
        case_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return case_id
    except Exception as e:
        print(f"Error saving SIR case: {e}")
        return None


def get_sir_cases(doc_id=None):
    """Retrieve filed SIR cases, optionally filtered by document ID."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        if doc_id:
            cursor.execute('SELECT * FROM sir_cases WHERE doc_id = ? ORDER BY timestamp DESC', (doc_id,))
        else:
            cursor.execute('SELECT * FROM sir_cases ORDER BY timestamp DESC LIMIT 50')
        rows = cursor.fetchall()
        col_names = [description[0] for description in cursor.description]
        conn.close()

        cases = []
        for r in rows:
            case = dict(zip(col_names, r))
            if case.get('qna_data'):
                try:
                    case['qna_data'] = json.loads(case['qna_data'])
                except Exception:
                    pass
            cases.append(case)
        return cases
    except Exception as e:
        print(f"Error fetching SIR cases: {e}")
        return []


def index_face_biometrics(doc_id, face_vector, doc_number, passenger_name):
    """Save normalized face vector to biometric index for Sybil fraud ring detection."""
    if not face_vector:
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO biometric_index (doc_id, doc_number, passenger_name, face_vector)
            VALUES (?, ?, ?, ?)
        ''', (doc_id, doc_number, passenger_name, json.dumps(face_vector)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error indexing biometric face: {e}")


def check_sybil_fraud_ring(current_face_vector, current_doc_number, current_name, threshold=0.86):
    """
    Search biometric index to detect Sybil attacks:
    If this face matches a prior scan with a DIFFERENT name or DIFFERENT document number.
    Returns: dict with sybil_detected, matched_records, and security flags.
    """
    if not current_face_vector:
        return {'sybil_detected': False, 'flags': [], 'matches': []}

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT doc_id, doc_number, passenger_name, face_vector, timestamp FROM biometric_index')
        rows = cursor.fetchall()
        conn.close()

        curr_vec = np.array(current_face_vector, dtype=np.float32)
        curr_norm = np.linalg.norm(curr_vec)
        if curr_norm == 0:
            return {'sybil_detected': False, 'flags': [], 'matches': []}
        curr_vec /= curr_norm

        suspicious_matches = []
        flags = []

        curr_doc_clean = (current_doc_number or "").replace(" ", "").upper()
        curr_name_clean = (current_name or "").strip().upper()

        for doc_id, doc_num, name, vec_json, ts in rows:
            if not vec_json:
                continue
            try:
                hist_vec = np.array(json.loads(vec_json), dtype=np.float32)
                hist_norm = np.linalg.norm(hist_vec)
                if hist_norm == 0:
                    continue
                hist_vec /= hist_norm

                similarity = float(np.dot(curr_vec, hist_vec))

                if similarity >= threshold:
                    hist_doc_clean = (doc_num or "").replace(" ", "").upper()
                    hist_name_clean = (name or "").strip().upper()

                    # Same face, but different name or different document number!
                    is_different_identity = (
                        (curr_name_clean and hist_name_clean and curr_name_clean != hist_name_clean) or
                        (curr_doc_clean and hist_doc_clean and curr_doc_clean != hist_doc_clean)
                    )

                    if is_different_identity:
                        suspicious_matches.append({
                            'doc_id': doc_id,
                            'matched_name': name,
                            'matched_doc_number': doc_num,
                            'similarity': round(similarity * 100, 1),
                            'previous_scan_date': ts,
                        })

            except Exception:
                continue

        if suspicious_matches:
            flags.append('SYBIL_FRAUD_RING_DETECTED')
            return {
                'sybil_detected': True,
                'flags': flags,
                'matches': suspicious_matches,
                'summary': f"CRITICAL BIOMETRIC ALERT: This traveler's facial biometrics match {len(suspicious_matches)} previous scan(s) under different names or document numbers!"
            }

        return {'sybil_detected': False, 'flags': [], 'matches': []}

    except Exception as e:
        print(f"Sybil check error: {e}")
        return {'sybil_detected': False, 'flags': [], 'matches': []}
