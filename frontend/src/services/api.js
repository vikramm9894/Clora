/**
 * CLORA Sovereign Backend API Integration Service
 * 100% On-Premise, Zero External Network Egress
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL !== undefined ? import.meta.env.VITE_API_BASE_URL : 'http://127.0.0.1:8000';

export async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, { method: 'GET' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    return { status: 'offline', error: err.message };
  }
}

// ============================================================================
// Workspaces & Files API
// ============================================================================

export async function getWorkspaces() {
  try {
    const res = await fetch(`${API_BASE}/api/workspaces`, {
      headers: { 'X-User-ID': 'eng_user_01', 'X-User-Role': 'maintenance_engineer' }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.items || [];
  } catch (err) {
    console.warn('Backend unavailable - Failed to fetch workspaces:', err);
    return [];
  }
}

export async function getWorkspaceFiles(workspaceId = 'default-workspace') {
  try {
    const res = await fetch(`${API_BASE}/api/workspaces/${workspaceId}/files`, {
      headers: { 'X-User-ID': 'eng_user_01', 'X-User-Role': 'maintenance_engineer' }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.items || [];
  } catch (err) {
    console.warn('Failed to fetch workspace files:', err);
    return [];
  }
}

export async function uploadFile(workspaceId = 'default-workspace', fileObject) {
  const formData = new FormData();
  formData.append('file', fileObject);

  const res = await fetch(`${API_BASE}/api/workspaces/${workspaceId}/files`, {
    method: 'POST',
    headers: {
      'X-User-ID': 'eng_user_01',
      'X-User-Role': 'maintenance_engineer'
    },
    body: formData
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Upload failed (HTTP ${res.status})`);
  }
  return await res.json();
}

export async function deleteFile(fileId) {
  const res = await fetch(`${API_BASE}/api/files/${fileId}`, {
    method: 'DELETE',
    headers: {
      'X-User-ID': 'eng_user_01',
      'X-User-Role': 'maintenance_engineer'
    }
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

// ============================================================================
// Multi-Agent Queries & Forensic Investigation
// ============================================================================

export async function executeQuery(question, workspaceId = 'default-workspace', userRole = 'maintenance_engineer', onProgress) {
  const res = await fetch(`${API_BASE}/api/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Role': userRole,
      'X-User-ID': 'eng_user_01'
    },
    body: JSON.stringify({
      workspace_id: workspaceId,
      question: question
    })
  });

  if (res.status === 202) {
    const data = await res.json();
    return await pollQueryStatus(data.query_id, onProgress);
  } else if (res.ok) {
    return await res.json();
  }
  
  const errData = await res.json().catch(() => ({}));
  throw new Error(errData.detail || `Query execution error: ${res.statusText}`);
}

export async function pollQuery(queryId) {
  const res = await fetch(`${API_BASE}/api/query/${queryId}`, {
    headers: { 'X-User-ID': 'eng_user_01', 'X-User-Role': 'maintenance_engineer' }
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

async function pollQueryStatus(queryId, onProgress, maxAttempts = 30) {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise((r) => setTimeout(r, 900));
    try {
      const query = await pollQuery(queryId);
      if (onProgress) {
        onProgress(query);
      }
      if (query.status === 'completed' || query.status === 'failed') {
        return query;
      }
    } catch (e) {
      // Continue polling
    }
  }
  return await pollQuery(queryId);
}

export async function getWorkspaceQueries(workspaceId = 'default-workspace') {
  try {
    const res = await fetch(`${API_BASE}/api/workspaces/${workspaceId}/queries`, {
      headers: { 'X-User-ID': 'eng_user_01', 'X-User-Role': 'maintenance_engineer' }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.items || [];
  } catch (err) {
    console.warn('Failed fetching workspace queries:', err);
    return [];
  }
}

export function downloadQueryDocx(queryId, filename = 'MRPL_Executive_Approval_Note.docx') {
  const url = `${API_BASE}/api/query/${queryId}/export-docx`;
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// ============================================================================
// Local LLM & Sandbox Models API
// ============================================================================

export async function getModels() {
  try {
    const res = await fetch(`${API_BASE}/api/models`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const rawList = data.available_models || [];
    const normalized = rawList.map(m => (typeof m === 'string' ? m : m?.name || 'qwen2.5:3b')).filter(Boolean);
    const standardModels = ['qwen2.5:3b', 'llama3.2:3b', 'phi3.5:latest'];
    const merged = Array.from(new Set([...normalized, ...standardModels]));

    return {
      ...data,
      status: data.status || 'online',
      active_model: typeof data.active_model === 'string' ? data.active_model : (merged[0] || 'None'),
      available_models: merged
    };
  } catch (err) {
    console.warn('Backend unavailable - Failed to fetch models status:', err);
    return {
      status: 'offline',
      active_model: 'None (Backend Offline)',
      available_models: [],
      error: err.message
    };
  }
}

export async function getRegisteredModels() {
  try {
    const res = await fetch(`${API_BASE}/api/models/profiles`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Failed to fetch registered model profiles:', err);
    return [];
  }
}

export async function getActiveModel() {
  try {
    const res = await fetch(`${API_BASE}/api/models/active`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    return { active_model: 'None', status: 'offline', error: err.message };
  }
}

export async function selectActiveModel(modelName) {
  const res = await fetch(`${API_BASE}/api/models/select`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model_name: modelName })
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function evaluateModelRoute(query, userRole = 'Operator') {
  const res = await fetch(`${API_BASE}/api/models/route`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: query,
      user_id: 'operator_01',
      user_role: userRole
    })
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function getSystemMetrics() {
  try {
    const res = await fetch(`${API_BASE}/api/system/metrics`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn('Failed to fetch system metrics:', err);
    return null;
  }
}


// ============================================================================
// Member 6: Data Intelligence, OCR, Topology & DOCX
// ============================================================================

export async function getKnowledgeGraphCytoscape() {
  const res = await fetch(`${API_BASE}/api/member6/knowledge-graph/cytoscape`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function getBlastRadius(equipmentId = 'P-102A', maxHops = 2) {
  const res = await fetch(`${API_BASE}/api/member6/knowledge-graph/blast-radius`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      equipment_id: equipmentId,
      max_hops: maxHops
    })
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function fetchOcrPreview(pdfPath, pageNumber = 1, dpi = 150, autoDeskew = true) {
  try {
    const res = await fetch(`${API_BASE}/api/member6/ocr/preview-page`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pdf_path: pdfPath,
        page_number: pageNumber,
        dpi: dpi,
        auto_deskew: autoDeskew
      })
    });
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn('OCR preview API error:', err);
  }
  return null;
}

export async function reprocessOcr(pdfPath, dpi = 250, autoDeskew = true, psmMode = 3) {
  const res = await fetch(`${API_BASE}/api/member6/ocr/re-process`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      pdf_path: pdfPath,
      dpi: dpi,
      auto_deskew: autoDeskew,
      psm_mode: psmMode
    })
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function executeTabularSql(sqlQuery, csvPath = 'samples/equipment_maintenance.csv') {
  const res = await fetch(`${API_BASE}/api/member6/query-tabular`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sql_query: sqlQuery,
      csv_path: csvPath
    })
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function generateApprovalNote(payload) {
  const res = await fetch(`${API_BASE}/api/member6/generate-approval-note`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

// ============================================================================
// Sovereignty, Air-Gap Sentinel & Cryptographic Proofs
// ============================================================================

export async function getEgressMetrics() {
  const res = await fetch(`${API_BASE}/api/sovereignty/metrics`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function getStartupValidation() {
  const res = await fetch(`${API_BASE}/api/sovereignty/startup-validation`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function getTrustBoundary() {
  const res = await fetch(`${API_BASE}/api/sovereignty/trust-boundary`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export function createSovereigntyEventSource(onBlock, onConnected, onError) {
  try {
    const es = new EventSource(`${API_BASE}/api/sovereignty/stream`);
    es.addEventListener('connected', (e) => {
      try {
        if (onConnected) onConnected(JSON.parse(e.data));
      } catch (err) {}
    });
    es.addEventListener('audit_block', (e) => {
      try {
        if (onBlock) onBlock(JSON.parse(e.data));
      } catch (err) {}
    });
    es.onerror = (err) => {
      if (onError) onError(err);
    };
    return es;
  } catch (err) {
    if (onError) onError(err);
    return null;
  }
}

export async function getSovereigntyStatus() {
  const res = await fetch(`${API_BASE}/api/sovereignty/status`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function getSovereigntyAuditTrail(limit = 30) {
  const res = await fetch(`${API_BASE}/api/sovereignty/audit-trail?limit=${limit}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function triggerInstantAudit() {
  const res = await fetch(`${API_BASE}/api/sovereignty/audit-now`, { method: 'POST' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function simulatePolicyViolation(targetIp = '1.1.1.1', targetPort = 443) {
  const res = await fetch(`${API_BASE}/api/sovereignty/simulate-violation?target_ip=${targetIp}&target_port=${targetPort}`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function changeSecurityProfile(profile, justification, userId = 'operator_admin') {
  const res = await fetch(`${API_BASE}/api/sovereignty/profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile, justification, user_id: userId })
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function downloadComplianceAttestation() {
  const res = await fetch(`${API_BASE}/api/sovereignty/attestation`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const text = await res.text();
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'CLORA_NETWORK_COMPLIANCE_ATTESTATION.txt';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

export async function getAttestationIdentity() {
  const res = await fetch(`${API_BASE}/api/sovereignty/attestation/identity`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function getSampleEvidenceProof() {
  const res = await fetch(`${API_BASE}/api/sovereignty/attestation/sample-proof`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function verifyEvidenceAttestation(proofPackage) {
  const res = await fetch(`${API_BASE}/api/sovereignty/attestation/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(proofPackage)
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function simulateAttestationTamper(proofPackage = null, modifiedText = null) {
  const body = {
    proof_package: proofPackage,
    modified_text: modifiedText || 'Inboard roller bearing temperature reached 199.9°C (CRITICAL EXCURSION)'
  };
  const res = await fetch(`${API_BASE}/api/sovereignty/attestation/simulate-tamper`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export function downloadCloraProofFile(proofPackage) {
  const jsonStr = JSON.stringify(proofPackage, null, 2);
  const blob = new Blob([jsonStr], { type: 'application/json' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const filename = `${proofPackage.canonical_payload?.report_id || 'CLORA-REPORT'}.clora-proof`;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

// ============================================================================
// Multimodal Vision & Physical Inspection API
// ============================================================================

export async function getVisionFixtures() {
  const res = await fetch(`${API_BASE}/api/vision/fixtures`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function ingestVisionFixture(fixtureId) {
  const res = await fetch(`${API_BASE}/api/vision/fixtures/${fixtureId}/ingest`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function uploadVisionPhotograph(file, equipmentTag = null, workspaceId = 'ws-sovereign-01') {
  const formData = new FormData();
  formData.append('file', file);
  if (equipmentTag) formData.append('equipment_tag', equipmentTag);
  if (workspaceId) formData.append('workspace_id', workspaceId);

  const res = await fetch(`${API_BASE}/api/vision/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || `Upload failed: ${res.status}`);
  }
  return await res.json();
}

export async function inspectPhotograph(payload) {
  const res = await fetch(`${API_BASE}/api/vision/inspect`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || `Inspection failed: ${res.status}`);
  }
  return await res.json();
}

export async function submitHitlReview(inspectionId, decision, notes = '', operatorId = 'operator_admin') {
  const res = await fetch(`${API_BASE}/api/vision/hitl/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      inspection_id: inspectionId,
      decision,
      notes,
      operator_id: operatorId,
    }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function getVisionBenchmark() {
  const res = await fetch(`${API_BASE}/api/vision/benchmark`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export function getArtifactImageUrl(artifactId) {
  return `${API_BASE}/api/vision/artifacts/${artifactId}`;
}

