import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './App.css';

const API = 'http://localhost:8000';

function App() {
  const [file, setFile] = useState(null);
  const [selfie, setSelfie] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('overview');
  const [history, setHistory] = useState([]);
  const [maskPII, setMaskPII] = useState(false);

  // Kiosk Camera Modal
  const [kioskOpen, setKioskOpen] = useState(false);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [cameraStream, setCameraStream] = useState(null);

  // SIR State
  const [sirQuestions, setSirQuestions] = useState([]);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [copilotMessages, setCopilotMessages] = useState([
    { role: 'assistant', content: 'Officer, I am your Border Forensic Copilot. Ask me any technical questions about the ELA heatmap, detected flags, or recommended interrogation tactics.' }
  ]);
  const [copilotInput, setCopilotInput] = useState('');
  const [copilotLoading, setCopilotLoading] = useState(false);

  // Disposition form
  const [officerBadge, setOfficerBadge] = useState('OFFICER-742');
  const [officerNotes, setOfficerNotes] = useState('');
  const [dispositionAction, setDispositionAction] = useState('CLEARED');
  const [dispositionStatus, setDispositionStatus] = useState('');

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await axios.get(`${API}/history`);
      setHistory(res.data.history || []);
    } catch (e) { /* ignore */ }
  };

  const handleScan = async (overrideFile) => {
    const fileToUpload = overrideFile || file;
    if (!fileToUpload) {
      setError('Please select or capture a document to screen.');
      return;
    }
    setLoading(true);
    setError('');
    setResult(null);
    setActiveTab('overview');
    setSirQuestions([]);
    setDispositionStatus('');

    const formData = new FormData();
    formData.append('file', fileToUpload);

    try {
      const response = await axios.post(`${API}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      if (response.data.error) {
        setError(response.data.error);
      } else {
        setResult(response.data);
        fetchHistory();
        // If risk is high or critical, auto-fetch SIR questions
        if (response.data.risk_score >= 30 || response.data.flags?.length > 0) {
          fetchSirQuestions(response.data);
        }
      }
    } catch (err) {
      if (err.response && err.response.data && err.response.data.detail) {
        setError(`Server error: ${err.response.data.detail}`);
      } else if (err.response && err.response.data && err.response.data.error) {
        setError(`Server error: ${err.response.data.error}`);
      } else {
        setError('Screening server unreachable. Make sure the backend is active on port 8000.');
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchSirQuestions = async (data) => {
    setLoadingQuestions(true);
    try {
      const res = await axios.post(`${API}/api/sir/interrogate`, {
        doc_id: data.id,
        report_data: data
      });
      setSirQuestions(res.data.questions || []);
    } catch (e) {
      console.error("Failed to load SIR questions", e);
    } finally {
      setLoadingQuestions(false);
    }
  };

  const handleSendCopilot = async (e) => {
    e.preventDefault();
    if (!copilotInput.trim() || !result) return;
    const userText = copilotInput.trim();
    setCopilotInput('');
    const newHistory = [...copilotMessages, { role: 'user', content: userText }];
    setCopilotMessages(newHistory);
    setCopilotLoading(true);

    try {
      const res = await axios.post(`${API}/api/sir/chat`, {
        query: userText,
        context: result,
        history: newHistory
      });
      setCopilotMessages([...newHistory, { role: 'assistant', content: res.data.reply }]);
    } catch (e) {
      setCopilotMessages([...newHistory, { role: 'assistant', content: 'Connection to Forensic Copilot timed out.' }]);
    } finally {
      setCopilotLoading(false);
    }
  };

  const handleSubmitDisposition = async (e) => {
    e.preventDefault();
    if (!result || !result.id) return;
    try {
      const res = await axios.post(`${API}/api/sir/disposition`, {
        doc_id: result.id,
        officer_badge: officerBadge,
        interrogation_notes: officerNotes,
        disposition: dispositionAction,
        qna_data: sirQuestions
      });
      setDispositionStatus(`Case filed successfully! Disposition ID: CASE-${res.data.case_id} [${res.data.disposition}]`);
    } catch (e) {
      setDispositionStatus('Failed to submit disposition.');
    }
  };

  // Camera Kiosk handlers
  const openKiosk = async () => {
    setKioskOpen(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment', width: 1280, height: 720 } });
      setCameraStream(stream);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch (err) {
      setError("Unable to access checkpoint webcam.");
      setKioskOpen(false);
    }
  };

  const closeKiosk = () => {
    if (cameraStream) {
      cameraStream.getTracks().forEach(t => t.stop());
    }
    setCameraStream(null);
    setKioskOpen(false);
  };

  const captureSnapshot = () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob((blob) => {
      const capturedFile = new File([blob], `kiosk_scan_${Date.now()}.jpg`, { type: 'image/jpeg' });
      setFile(capturedFile);
      closeKiosk();
      handleScan(capturedFile);
    }, 'image/jpeg', 0.95);
  };

  const formatPII = (text, fieldName) => {
    if (!maskPII || !text) return text;
    const str = String(text);
    if (str.length <= 4) return '****';
    return str.slice(0, 2) + '****' + str.slice(-2);
  };

  const getVerdictClass = (verdict) => {
    if (!verdict) return '';
    const v = verdict.toLowerCase();
    if (v.includes('genuine')) return 'genuine';
    if (v.includes('fake') || v.includes('counterfeit')) return 'fake';
    if (v.includes('suspicious')) return 'suspicious';
    if (v.includes('review')) return 'review';
    return '';
  };

  const getRiskClass = (level) => {
    if (!level) return '';
    return level.toLowerCase();
  };

  return (
    <>
      <div className="header">
        <div className="header-left">
          <h1>🛡️ AI-Based Border Checkpoint Identity Screening System</h1>
          <p>Powered by Forensic Computer Vision, Machine Learning & Secondary Inspection Referral (SIR)</p>
        </div>
        <div className="header-actions">
          <label className="pii-toggle">
            <input
              type="checkbox"
              checked={maskPII}
              onChange={(e) => setMaskPII(e.target.checked)}
            />
            <span>🔒 Mask PII (Compliance Mode)</span>
          </label>
        </div>
      </div>

      <div className="container">
        {/* Upload & Kiosk Controls */}
        <div className="upload-section">
          <h2>📄 Primary Document Inspection</h2>
          <p className="upload-desc">
            Directly screen <strong>Passport, Visa, Aadhaar, PAN, Voter ID, and Driving Licence</strong> documents.
          </p>

          <div className="file-inputs">
            <div className="file-input-group">
              <label>Upload Document File *</label>
              <input
                type="file"
                accept=".jpg,.jpeg,.png,.pdf"
                onChange={(e) => { setFile(e.target.files[0]); setResult(null); setError(''); }}
              />
            </div>
            <div className="file-input-group">
              <label>Optional Traveler Live Selfie (Biometric Match)</label>
              <input
                type="file"
                accept=".jpg,.jpeg,.png"
                onChange={(e) => setSelfie(e.target.files[0])}
              />
            </div>
          </div>

          <div className="btn-row">
            <button className="scan-btn" onClick={() => handleScan()} disabled={loading || !file}>
              {loading ? '⏳ Analyzing Core Forensic Modules...' : '🔍 Run Primary Screening'}
            </button>
            <button className="scan-btn secondary" onClick={openKiosk}>
              📷 Open Checkpoint Kiosk Camera
            </button>
          </div>
        </div>

        {/* Live Camera Modal */}
        {kioskOpen && (
          <div className="modal-overlay">
            <div className="kiosk-modal">
              <div className="kiosk-header">
                <h3>📷 Live Checkpoint Document Scanner</h3>
                <button className="close-btn" onClick={closeKiosk}>✕</button>
              </div>
              <div className="kiosk-body">
                <div className="camera-frame">
                  <video ref={videoRef} autoPlay playsInline muted className="kiosk-video" />
                  <div className="card-guide-overlay">
                    <div className="guide-box">
                      <span>ALIGN DOCUMENT HERE</span>
                    </div>
                  </div>
                </div>
                <canvas ref={canvasRef} style={{ display: 'none' }} />
              </div>
              <div className="kiosk-footer">
                <button className="scan-btn" onClick={captureSnapshot}>
                  📸 Snap & Auto-Screen
                </button>
                <button className="scan-btn secondary" onClick={closeKiosk}>
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Loading Spinner */}
        {loading && (
          <div className="loading">
            <span className="spinner"></span>
            <div className="loading-steps">
              <div className="loading-step active">🔍 Running OCR text & MRZ extraction...</div>
              <div className="loading-step">🔲 Scanning QR code payload & signature zone...</div>
              <div className="loading-step">✅ Executing calendar format & blacklist validation...</div>
              <div className="loading-step">🔬 Forensic ELA heatmap, EXIF & copy-move detection...</div>
              <div className="loading-step">👤 Detecting face & cross-checking Sybil fraud graph...</div>
              <div className="loading-step">🤖 OpenRouter AI intelligence briefing...</div>
            </div>
          </div>
        )}

        {error && <div className="error-message">❌ {error}</div>}

        {/* Screening Results Dashboard */}
        {result && (
          <div className="results">
            {/* Top Critical Alerts */}
            {result.sybil_alert?.sybil_detected && (
              <div className="sybil-alert-banner">
                <h3>🚨 CRITICAL ALERT: SYBIL FRAUD RING DETECTED</h3>
                <p>{result.sybil_alert.summary}</p>
                <div className="sybil-matches">
                  {result.sybil_alert.matches.map((m, idx) => (
                    <div key={idx} className="sybil-match-item">
                      Match: <strong>{m.matched_name}</strong> | ID: <strong>{m.matched_doc_number}</strong> ({m.similarity}% match) | Prior Date: {m.previous_scan_date}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {result.qr_verification?.is_tampered && (
              <div className="sybil-alert-banner warning">
                <h3>⚠️ CRYPTOGRAPHIC TAMPERING DETECTED IN QR CODE</h3>
                <p>{result.qr_verification.summary}</p>
              </div>
            )}

            {/* Overview Card */}
            <div className="overview-card">
              <div className="overview-left">
                <div className={`verdict ${getVerdictClass(result.verdict)}`}>
                  {result.verdict}
                </div>
                <div className="badge-row">
                  <span className={`risk-level ${getRiskClass(result.risk_level)}`}>
                    {result.risk_level} RISK
                  </span>
                  <span className="doc-type-badge">{result.doc_type}</span>
                </div>

                {/* PDF Export Button */}
                {result.id && (
                  <div style={{ marginTop: '8px' }}>
                    <a
                      href={`${API}/document/${result.id}/pdf`}
                      target="_blank"
                      rel="noreferrer"
                      className="pdf-download-btn"
                    >
                      📑 Export Court-Admissible Forensic Dossier (PDF)
                    </a>
                  </div>
                )}
              </div>

              <div className="overview-right">
                <div className="risk-gauge">
                  <svg viewBox="0 0 120 120" className="gauge-svg">
                    <circle cx="60" cy="60" r="50" fill="none" stroke="#e5e7eb" strokeWidth="10" />
                    <circle
                      cx="60" cy="60" r="50" fill="none"
                      stroke={result.risk_score >= 70 ? '#ef4444' : result.risk_score >= 50 ? '#f97316' : result.risk_score >= 30 ? '#f59e0b' : '#10b981'}
                      strokeWidth="10"
                      strokeDasharray={`${(result.risk_score / 100) * 314} 314`}
                      strokeLinecap="round"
                      transform="rotate(-90 60 60)"
                    />
                  </svg>
                  <div className="gauge-text">
                    <span className="gauge-value">{result.risk_score}</span>
                    <span className="gauge-label">Risk Index</span>
                  </div>
                </div>
                <div className="confidence-text">
                  AI Confidence: <strong>{result.confidence}%</strong>
                </div>
              </div>
            </div>

            {/* Module Score Progress */}
            {result.module_scores && (
              <div className="module-scores">
                {Object.entries(result.module_scores).map(([key, mod]) => (
                  <div className="module-score-card" key={key}>
                    <div className="module-label">{mod.label}</div>
                    <div className="module-value">{mod.score.toFixed(1)}</div>
                    <div className="score-bar">
                      <div
                        className={`score-bar-fill ${mod.status.toLowerCase()}`}
                        style={{ width: `${Math.min(mod.score, 100)}%` }}
                      ></div>
                    </div>
                    <span className={`risk-level small ${mod.status.toLowerCase()}`}>{mod.status}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Raised Flags */}
            {result.flags && result.flags.length > 0 && (
              <div className="flags-section">
                <h3>🚩 Automated Security Flags</h3>
                <div className="flags-list">
                  {result.flags.map((flag, i) => (
                    <span key={i} className={`flag-item ${flag.includes('CRITICAL') || flag.includes('TAMPERING') || flag.includes('SYBIL') ? 'critical' : 'warning'}`}>
                      {flag.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Multi-Tab Navigation */}
            <div className="tabs">
              {[
                { id: 'overview', label: '📊 Overview' },
                { id: 'sir', label: '🚨 SIR & Interrogation', badge: result.risk_score >= 30 ? 'Action Req' : null },
                { id: 'ocr', label: '📝 OCR & QR Code' },
                { id: 'validation', label: '✅ Validation Matrix' },
                { id: 'tampering', label: '🔬 Forensic Tampering' },
                { id: 'face', label: '👤 Face & Biometrics' },
              ].map(tab => (
                <button
                  key={tab.id}
                  className={`tab ${activeTab === tab.id ? 'active' : ''} ${tab.badge ? 'has-badge' : ''}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                  {tab.badge && <span className="tab-pill">{tab.badge}</span>}
                </button>
              ))}
            </div>

            <div className="tab-content">
              {/* TAB 1: OVERVIEW */}
              {activeTab === 'overview' && (
                <div>
                  {result.ai_authenticity && (
                    <div className={`section-box ai-authenticity-box ${
                      result.ai_authenticity.assessment === 'GENUINE' ? 'genuine-box' :
                      result.ai_authenticity.assessment === 'LIKELY_FAKE' ? 'fake-box' : 'suspicious-box'
                    }`}>
                      <h3>
                        <span>{result.ai_authenticity.assessment === 'GENUINE' ? '✅' :
                               result.ai_authenticity.assessment === 'LIKELY_FAKE' ? '❌' : '⚠️'}</span>
                        {' '}AI Vision Forensic Assessment
                      </h3>
                      <div className="ai-auth-verdict">
                        <span className={`verdict-badge ${result.ai_authenticity.assessment?.toLowerCase()}`}>
                          {result.ai_authenticity.assessment}
                        </span>
                        <span className="ai-conf">
                          Confidence: {(result.ai_authenticity.confidence * 100).toFixed(1)}%
                        </span>
                      </div>
                      <p className="ai-auth-reasoning">{result.ai_authenticity.reasoning}</p>
                      {result.ai_authenticity.flags && result.ai_authenticity.flags.length > 0 && (
                        <div className="ai-auth-flags">
                          <strong>Forensic Concerns:</strong>
                          <ul>
                            {result.ai_authenticity.flags.map((f, i) => (
                              <li key={i}>{f}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}

                  {result.ai_brief && (
                    <div className="section-box ai-brief-box">
                      <h3><span>🤖</span> AI Intelligence Assessment Brief (Law Enforcement)</h3>
                      <p>{result.ai_brief}</p>
                    </div>
                  )}

                  {result.recommendations && result.recommendations.length > 0 && (
                    <div className="recommendations">
                      <h3>📋 Checkpoint Protocol Recommendations</h3>
                      {result.recommendations.map((rec, i) => (
                        <div key={i} className="recommendation-item">{rec}</div>
                      ))}
                    </div>
                  )}

                  {result.risk_score >= 30 && (
                    <div className="sir-referral-banner">
                      <h4>⚠️ Referred to Secondary Inspection Referral (SIR)</h4>
                      <p>
                        Automated score of {result.risk_score} warrants traveler interrogation. 
                        Click the <strong>🚨 SIR & Interrogation</strong> tab above to view dynamic questioning and consult the Officer Copilot.
                      </p>
                      <button className="scan-btn" onClick={() => setActiveTab('sir')} style={{ marginTop: '10px' }}>
                        Open SIR Interrogation Console →
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: SECONDARY INSPECTION REFERRAL (SIR) & COPILOT */}
              {activeTab === 'sir' && (
                <div className="sir-tab-container">
                  <div className="sir-left-pane">
                    <h3>🎯 Dynamic Interrogation Questioning</h3>
                    <p className="tab-subtext">
                      Targeted oral questions generated by AI based on this document's flagged discrepancies to verify recall and detect impostors.
                    </p>

                    {loadingQuestions ? (
                      <div className="loading"><span className="spinner"></span> Generating questions...</div>
                    ) : (
                      <div className="sir-questions-list">
                        {sirQuestions.map((q, idx) => (
                          <div className="sir-question-card" key={idx}>
                            <div className="q-badge">Question {idx + 1}</div>
                            <div className="q-title">"{q.question}"</div>
                            <div className="q-meta">
                              <strong>Target Anomaly:</strong> {q.target_issue}
                            </div>
                            <div className="q-valid">
                              <strong>Expected Authentic Response:</strong> {q.expected_valid_response}
                            </div>
                            <div className="q-redflag">
                              <strong>Red Flag Reaction:</strong> {q.red_flag_indicator}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Officer Disposition Filing */}
                    <div className="disposition-section">
                      <h4>📝 File Secondary Inspection Report (SIR)</h4>
                      <form onSubmit={handleSubmitDisposition}>
                        <div className="form-row">
                          <label>Officer Badge ID:</label>
                          <input
                            type="text"
                            value={officerBadge}
                            onChange={(e) => setOfficerBadge(e.target.value)}
                            required
                          />
                        </div>
                        <div className="form-row">
                          <label>Disposition Action:</label>
                          <select
                            value={dispositionAction}
                            onChange={(e) => setDispositionAction(e.target.value)}
                          >
                            <option value="CLEARED">CLEARED (Admit Traveler)</option>
                            <option value="ESCORT_TO_HOLDING">ESCORT TO HOLDING (Detain for Forensics)</option>
                            <option value="REFUSED_ENTRY">REFUSED ENTRY (Turnaround / Deport)</option>
                          </select>
                        </div>
                        <div className="form-row">
                          <label>Interrogation Notes & Responses:</label>
                          <textarea
                            rows={3}
                            placeholder="Document traveler answers, body language, or evasive remarks..."
                            value={officerNotes}
                            onChange={(e) => setOfficerNotes(e.target.value)}
                            required
                          />
                        </div>
                        <button type="submit" className="scan-btn">
                          💾 Save Official SIR Disposition
                        </button>
                        {dispositionStatus && (
                          <p className="disposition-alert">{dispositionStatus}</p>
                        )}
                      </form>
                    </div>
                  </div>

                  {/* SIR Right Pane: Officer Copilot Chat */}
                  <div className="sir-right-pane">
                    <h3>💬 BorderGuard Copilot</h3>
                    <p className="tab-subtext">Ask questions about evidence, heatmaps, or passport security protocols.</p>

                    <div className="copilot-chat-box">
                      <div className="copilot-messages">
                        {copilotMessages.map((m, idx) => (
                          <div key={idx} className={`copilot-msg ${m.role}`}>
                            <span className="msg-sender">{m.role === 'assistant' ? 'Copilot' : 'Officer'}</span>
                            <div className="msg-text">{m.content}</div>
                          </div>
                        ))}
                        {copilotLoading && (
                          <div className="copilot-msg assistant">
                            <span className="msg-sender">Copilot</span>
                            <div className="msg-text">Analyzing forensic parameters...</div>
                          </div>
                        )}
                      </div>
                      <form className="copilot-input-bar" onSubmit={handleSendCopilot}>
                        <input
                          type="text"
                          placeholder="e.g. Why is the ELA score elevated?"
                          value={copilotInput}
                          onChange={(e) => setCopilotInput(e.target.value)}
                        />
                        <button type="submit" disabled={copilotLoading || !copilotInput.trim()}>
                          Send
                        </button>
                      </form>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 3: OCR & QR CODE */}
              {activeTab === 'ocr' && (
                <div>
                  {/* QR Code Payload Card */}
                  <div className="section-box" style={{ background: '#f8fafc', marginBottom: '20px' }}>
                    <h4>🔲 QR Code Payload Analysis</h4>
                    {result.qr_raw?.qr_detected ? (
                      <div>
                        <p>Status: <strong>✅ Readable QR Code Detected</strong> ({result.qr_raw.payload_type})</p>
                        <div className="fields-table" style={{ marginTop: '10px' }}>
                          {Object.entries(result.qr_raw.parsed_data || {}).map(([k, v]) => (
                            <div className="field-row" key={k}>
                              <span className="field-label">QR {k.toUpperCase()}</span>
                              <span className="field-value">{formatPII(v, k)}</span>
                            </div>
                          ))}
                        </div>
                        <p style={{ marginTop: '8px', fontSize: '13px', color: result.qr_verification?.is_tampered ? '#b91c1c' : '#047857' }}>
                          {result.qr_verification?.summary}
                        </p>
                      </div>
                    ) : (
                      <p style={{ color: '#6b7280', fontSize: '13px' }}>
                        No QR code detected or card format does not embed machine-readable codes.
                      </p>
                    )}
                  </div>

                  {/* Signature Crop Card */}
                  {result.signature_verification?.signature_detected && (
                    <div className="section-box" style={{ marginBottom: '20px' }}>
                      <h4>✍️ Extracted Signature Zone</h4>
                      <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
                        {result.signature_url && (
                          <img
                            src={`${API}${result.signature_url}`}
                            alt="Signature"
                            style={{ maxHeight: '80px', border: '1px solid #cbd5e1', borderRadius: '4px', background: 'white', padding: '4px' }}
                          />
                        )}
                        <div>
                          <p>Presence: <strong>Detected</strong></p>
                          <p>Stroke Density: {(result.signature_verification.stroke_density * 100).toFixed(1)}% ({result.signature_verification.quality})</p>
                        </div>
                      </div>
                    </div>
                  )}

                  <h3>📝 Extracted Visual Fields — {result.doc_type}</h3>
                  {result.extracted_fields && Object.keys(result.extracted_fields).length > 0 ? (
                    <div className="fields-table">
                      {Object.entries(result.extracted_fields).map(([key, val]) => {
                        if (key === 'mrz' || typeof val === 'object') return null;
                        return (
                          <div className="field-row" key={key}>
                            <span className="field-label">{key.replace(/_/g, ' ').toUpperCase()}</span>
                            <span className={`field-value ${!val ? 'missing' : ''}`}>
                              {formatPII(val, key) || 'Not detected'}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p>No structured fields extracted.</p>
                  )}

                  {result.extracted_fields?.mrz && (
                    <div className="section-box" style={{ marginTop: '16px' }}>
                      <h4>🔖 ICAO 9303 Machine Readable Zone (MRZ)</h4>
                      <div className="fields-table">
                        {Object.entries(result.extracted_fields.mrz).map(([key, val]) => (
                          <div className="field-row" key={key}>
                            <span className="field-label">{key.replace(/_/g, ' ').toUpperCase()}</span>
                            <span className="field-value">{formatPII(val, key) || '—'}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="section-box" style={{ marginTop: '16px' }}>
                    <h4>📄 Raw OCR Text Dump</h4>
                    <div className="extracted-text">{result.extracted_text || 'No text detected.'}</div>
                  </div>
                </div>
              )}

              {/* TAB 4: VALIDATION MATRIX */}
              {activeTab === 'validation' && (
                <div>
                  <h3>✅ Document Security & Format Validation Checks</h3>
                  {result.validation?.score !== undefined && (
                    <div className="validation-score">
                      Pass Rate: <strong>{(result.validation.score * 100).toFixed(1)}%</strong>
                      {' '} — {result.validation.is_valid ? '✅ Core security rules verified' : '❌ Validation anomalies flagged'}
                    </div>
                  )}

                  {result.validation?.checks && result.validation.checks.length > 0 ? (
                    <div className="validation-checks">
                      {result.validation.checks.map((check, i) => (
                        <div className="check-item" key={i}>
                          <span className={`check-icon ${check.passed ? 'pass' : 'fail'}`}>
                            {check.passed ? '✅' : '❌'}
                          </span>
                          <span className="check-field">{(check.field || '').replace(/_/g, ' ')}</span>
                          <span className="check-type">{(check.check || '').replace(/_/g, ' ')}</span>
                          <span className="check-detail">{check.detail}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p>No validation checks available.</p>
                  )}
                </div>
              )}

              {/* TAB 5: TAMPERING FORENSICS */}
              {activeTab === 'tampering' && (
                <div>
                  <h3>🔬 Advanced Forensic Tampering Analysis</h3>
                  <div className="tampering-grid">
                    <div className="tampering-card">
                      <h4>1. Error Level Analysis (ELA)</h4>
                      <p className="tamper-score">Score: <strong>{(result.tampering?.ela?.score || 0).toFixed(3)}</strong></p>
                      {result.heatmap_url && (
                        <div className="heatmap">
                          <img src={`${API}${result.heatmap_url}`} alt="ELA Heatmap" />
                          <p className="heatmap-caption">Bright zones indicate non-uniform re-compression and modified pixel clusters.</p>
                        </div>
                      )}
                    </div>

                    <div className="tampering-card">
                      <h4>2. EXIF Metadata Inspection</h4>
                      <p className="tamper-score">Score: <strong>{(result.tampering?.metadata?.score || 0).toFixed(3)}</strong></p>
                      <p>EXIF Header: {result.tampering?.metadata?.has_exif ? '✅ Present' : '❌ Missing / Stripped'}</p>
                      {result.tampering?.metadata?.software_detected && (
                        <p className="flag-item warning">⚠️ Editor: {result.tampering.metadata.software_detected}</p>
                      )}
                    </div>

                    <div className="tampering-card">
                      <h4>3. Copy-Move Forgery</h4>
                      <p className="tamper-score">Score: <strong>{(result.tampering?.copy_move?.score || 0).toFixed(3)}</strong></p>
                      {result.copy_move_url && (
                        <div className="heatmap">
                          <img src={`${API}${result.copy_move_url}`} alt="Copy Move Matches" />
                        </div>
                      )}
                    </div>

                    <div className="tampering-card">
                      <h4>4. Sensor Noise Consistency</h4>
                      <p className="tamper-score">Score: <strong>{(result.tampering?.noise?.score || 0).toFixed(3)}</strong></p>
                      {result.tampering?.noise?.suspicious_blocks !== undefined && (
                        <p>Inconsistent Blocks: {result.tampering.noise.suspicious_blocks}/{result.tampering.noise.total_blocks}</p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 6: FACE & BIOMETRICS */}
              {activeTab === 'face' && (
                <div>
                  <h3>👤 Facial Recognition & Biometric Verification</h3>
                  {result.face?.face_detected ? (
                    <div className="face-section">
                      <div className="face-top">
                        {result.face_image_url && (
                          <div className="face-image">
                            <img src={`${API}${result.face_image_url}`} alt="Detected Face" />
                            <p>Extracted Portrait</p>
                          </div>
                        )}
                        <div className="face-details">
                          <p>Faces Located: <strong>{result.face.num_faces}</strong></p>

                          {result.face.quality && (
                            <div className="face-quality">
                              <h4>Quality Metrics</h4>
                              <p>Overall Quality: <strong>{(result.face.quality.quality_score * 100).toFixed(1)}%</strong></p>
                              {result.face.quality.checks && Object.entries(result.face.quality.checks).map(([k, v]) => (
                                <p key={k}>{v ? '✅' : '❌'} {k.replace(/_/g, ' ')}</p>
                              ))}
                            </div>
                          )}

                          {result.face.tampering && (
                            <div className="face-tampering">
                              <h4>Photo Splicing / Replacement Check</h4>
                              <p>Tampering Discrepancy: <strong>{(result.face.tampering.tampering_score * 100).toFixed(1)}%</strong></p>
                              {result.face.tampering.flags?.map((f, i) => (
                                <p key={i} className="flag-item warning">🚩 {f}</p>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>

                      {result.face.comparison && (
                        <div className="face-match section-box" style={{ marginTop: '16px' }}>
                          <h4>🆔 Live Selfie Biometric Comparison</h4>
                          <div className={`verdict ${result.face.comparison.match_verdict === 'Match' ? 'genuine' : 'fake'}`}>
                            {result.face.comparison.match_verdict}
                          </div>
                          <p>Match Score: <strong>{(result.face.comparison.match_score * 100).toFixed(1)}%</strong></p>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p>No facial portrait was detected on this credential.</p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Scan Audit Trail */}
        {history.length > 0 && (
          <div className="history-section">
            <h3>📜 Checkpoint Scan Audit Log</h3>
            <div className="history-list">
              {history.slice(0, 10).map((item, i) => (
                <div className="history-item" key={i}>
                  <span className="history-filename">{item.filename}</span>
                  <span className={`history-verdict ${getVerdictClass(item.verdict)}`}>{item.verdict}</span>
                  <span className={`risk-level small ${getRiskClass(item.risk_level)}`}>{item.risk_level || '—'}</span>
                  <span className="history-type">{item.doc_type}</span>
                  {item.id && (
                    <a href={`${API}/document/${item.id}/pdf`} target="_blank" rel="noreferrer" className="history-pdf-link">
                      PDF Dossier ↗
                    </a>
                  )}
                  <span className="history-time">{item.timestamp}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  );
}

export default App;
