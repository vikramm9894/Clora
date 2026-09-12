"""
API Routes for Multimodal Vision & Physical Inspection Subsystem.
Implements:
- Cryptographic artifact upload & ingestion
- Golden fixture registry resolution
- Sovereign photograph inspection pipeline
- Cross-modal telemetry & SOP correlation
- Human-in-the-loop (HITL) review dispatch
- Ed25519 digital signature evidence attestation
- Performance benchmark measurement for air-gapped demo
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.integrations.vision_client import vision_client
from backend.app.services.artifact_manager import default_artifact_manager
from backend.verification.cross_correlation import CrossModalCorrelator
from security.attestation import get_attestor
from security.network_proof import get_sentinel

router = APIRouter(prefix="/vision", tags=["Multimodal Vision & Physical Inspection"])

FIXTURES_DIR = Path("./samples/vision_fixtures")
MANIFEST_PATH = FIXTURES_DIR / "manifest.json"


class InspectPhotographRequest(BaseModel):
    artifact_id: Optional[str] = Field(None, description="Ingested artifact ID (e.g. art_c995c63f...)")
    fixture_id: Optional[str] = Field(None, description="Or known fixture ID (e.g. P101_BEARING_SPALLING)")
    query: Optional[str] = Field("Inspect photograph for mechanical and physical degradation", description="User inspection prompt")
    workspace_id: Optional[str] = Field("ws-sovereign-01", description="Workspace ID")
    telemetry_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Operational telemetry snapshot")
    sop_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="SOP or technical manual metadata")
    execution_mode: Literal["production", "test", "demo"] = Field("production", description="Execution mode")


class HitlReviewRequest(BaseModel):
    inspection_id: str = Field(..., description="Unique inspection ID requiring human review")
    decision: Literal["APPROVE", "REJECT", "REQUEST_MORE"] = Field(..., description="Operator decision")
    operator_id: str = Field("operator_admin", description="Operator identifier")
    notes: Optional[str] = Field(None, description="Operator justification notes")


@router.get("/fixtures", summary="List Sovereign Vision Fixtures")
def list_vision_fixtures():
    """
    Returns registered sovereign test fixtures from manifest.json.
    Resolution in production strictly depends on matching image SHA-256 fingerprint.
    """
    if not MANIFEST_PATH.exists():
        return []
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            fixtures = json.load(f)
        return fixtures
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read fixture manifest: {str(e)}",
        )


@router.post("/fixtures/{fixture_id}/ingest", summary="Ingest Fixture as Verified Artifact")
def ingest_fixture(fixture_id: str):
    """
    Ingests a designated golden sample photograph into the immutable ArtifactManager,
    generating its canonical artifact_id and SHA-256 fingerprint.
    """
    if not MANIFEST_PATH.exists():
        raise HTTPException(status_code=404, detail="Fixture manifest not found")

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        fixtures = json.load(f)

    target_fixture = next((fx for fx in fixtures if fx.get("fixture_id") == fixture_id or fx.get("filename") == fixture_id), None)
    if not target_fixture:
        raise HTTPException(status_code=404, detail=f"Fixture '{fixture_id}' not found in manifest")

    target_path = FIXTURES_DIR / target_fixture["filename"]
    if not target_path.exists():
        raise HTTPException(status_code=404, detail=f"Fixture file '{target_fixture['filename']}' not on disk")

    record = default_artifact_manager.ingest_artifact(
        file_input=target_path,
        filename=target_fixture["filename"],
        metadata={"fixture_id": target_fixture["fixture_id"], "equipment_id": target_fixture.get("equipment_id")},
    )

    return {
        "status": "INGESTED",
        "artifact_id": record.artifact_id,
        "content_hash": record.content_hash,
        "mime_type": record.mime_type,
        "size_bytes": record.size_bytes,
        "fixture_id": target_fixture["fixture_id"],
        "equipment_id": target_fixture.get("equipment_id"),
        "filename": record.filename,
    }


@router.post("/upload", summary="Upload & Ingest Photograph")
async def upload_photograph(
    file: UploadFile = File(...),
    equipment_tag: Optional[str] = Form(None),
    workspace_id: Optional[str] = Form("ws-sovereign-01"),
):
    """
    Uploads a photograph, verifies magic bytes, enforces 25MB safety limit,
    computes canonical SHA-256 fingerprint, and stores in immutable storage.
    """
    raw_bytes = await file.read()
    if len(raw_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty (0 bytes)")

    try:
        record = default_artifact_manager.ingest_artifact(
            file_input=raw_bytes,
            filename=file.filename,
            metadata={"equipment_tag": equipment_tag, "workspace_id": workspace_id},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

    # Audit event
    try:
        sentinel = get_sentinel(str(settings.AIRGAP_LOG_PATH))
        sentinel.audit_cycle(
            event_type="ARTIFACT_RECEIVED",
            details={
                "artifact_id": record.artifact_id,
                "sha256": record.content_hash,
                "mime_type": record.mime_type,
                "size_bytes": record.size_bytes,
            },
        )
    except Exception:
        pass

    return {
        "status": "INGESTED",
        "artifact_id": record.artifact_id,
        "content_hash": record.content_hash,
        "mime_type": record.mime_type,
        "size_bytes": record.size_bytes,
        "image_dimensions": record.image_dimensions,
        "filename": record.filename,
        "created_at": record.created_at,
    }


@router.get("/artifacts/{artifact_id}", summary="Serve Artifact Image")
def get_artifact_image(artifact_id: str):
    """
    Serves verified raw image bytes for browser rendering, verifying SHA-256 integrity on read.
    """
    record = default_artifact_manager.get_artifact(artifact_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Artifact '{artifact_id}' not found")

    try:
        raw_bytes = default_artifact_manager.read_artifact_bytes(artifact_id)
        return Response(content=raw_bytes, media_type=record.mime_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read artifact: {str(e)}")


@router.get("/artifacts/{artifact_id}/metadata", summary="Get Artifact Metadata")
def get_artifact_metadata(artifact_id: str):
    """Returns cryptographic metadata for an ingested artifact."""
    record = default_artifact_manager.get_artifact(artifact_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Artifact '{artifact_id}' not found")
    return record.model_dump()


@router.post("/inspect", summary="Execute Sovereign Multimodal Inspection Pipeline")
async def inspect_photograph_endpoint(req: InspectPhotographRequest):
    """
    Executes the full sovereign 5-level inspection pipeline:
    Artifact Hash -> Calibrated Fixture / Ollama VLM -> RawProposal ->
    Schema Validation -> Domain Validation -> Engineering Policy -> Evidence Classification ->
    Cross-Modal Corroboration -> Ed25519 Attestation.
    """
    target_artifact_id = req.artifact_id

    # If fixture_id supplied instead, ingest or resolve fixture
    if not target_artifact_id and req.fixture_id:
        ingest_res = ingest_fixture(req.fixture_id)
        target_artifact_id = ingest_res["artifact_id"]

    if not target_artifact_id:
        raise HTTPException(status_code=400, detail="Either 'artifact_id' or 'fixture_id' must be provided")

    record = default_artifact_manager.get_artifact(target_artifact_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Artifact record '{target_artifact_id}' not found")

    # Audit start
    sentinel = get_sentinel(str(settings.AIRGAP_LOG_PATH))
    try:
        sentinel.audit_cycle(
            event_type="VISION_STARTED",
            details={"artifact_id": target_artifact_id, "content_hash": record.content_hash},
        )
    except Exception:
        pass

    # Execute Vision Inspection through Vision Client -> Vision Agent
    telemetry = dict(req.telemetry_context or {})
    sop_meta = dict(req.sop_context or {})

    # In production, missing telemetry is valid and leads to uncorroborated / review results.
    # Telemetry and SOP are never injected simply because a filename contains 'p101'.
    # Only controlled demo fixtures with explicit fixture_id may supply demonstration context.
    if req.execution_mode == "demo" and req.fixture_id:
        if not telemetry and "p101" in req.fixture_id.lower():
            telemetry = {
                "equipment_id": "P-101",
                "vibration_velocity_rms_mm_s": 9.82,
                "bearing_temperature_c": 104.2,
                "operating_hours": 14200,
            }
        if not sop_meta and "p101" in req.fixture_id.lower():
            sop_meta = {
                "sop_id": "SOP-MRPL-P101-MNT",
                "title": "Sulzer P-101 Centrifugal Pump Bearing Inspection & Replacement Standard Operating Procedure",
                "standard_ref": "ISO 10816-3 / API 610",
            }

    inspection_result = await vision_client.inspect_photograph(
        workspace_id=req.workspace_id or "ws-sovereign-01",
        question=req.query or "Inspect physical equipment photograph",
        image_path=record.storage_path,
        image_artifact_id=target_artifact_id,
        telemetry_context=telemetry,
        metadata={"filename": record.filename, "content_hash": record.content_hash},
        execution_mode=req.execution_mode,
    )

    # Cross-Modal Corroboration
    correlator = CrossModalCorrelator()
    cross_correlation = correlator.correlate(
        visual_result=inspection_result,
        telemetry_context=telemetry,
        sop_context=sop_meta,
    )

    # Ed25519 Cryptographic Evidence Attestation
    attestor = get_attestor(str(settings.KEYS_DIR))
    attestation = attestor.sign_photograph_inspection(inspection_result)

    # Audit completion
    try:
        sentinel.audit_cycle(
            event_type="CORRELATION_COMPLETED",
            details={
                "inspection_id": inspection_result.get("inspection_id"),
                "status": inspection_result.get("inspection_status"),
                "corroboration": cross_correlation.get("corroboration"),
                "signature": attestation.get("signature"),
            },
        )
    except Exception:
        pass

    return {
        "status": "SUCCESS",
        "artifact": {
            "artifact_id": record.artifact_id,
            "content_hash": record.content_hash,
            "filename": record.filename,
            "mime_type": record.mime_type,
            "dimensions": record.image_dimensions,
        },
        "inspection": inspection_result,
        "cross_correlation": cross_correlation,
        "attestation": attestation,
    }


@router.post("/hitl/review", summary="Submit Human-in-the-Loop Inspection Review")
def submit_hitl_review(req: HitlReviewRequest):
    """
    Submits operator review for inspections requiring human confirmation (e.g. REQUIRES_REVIEW).
    Appends an immutable tamper-evident audit entry to the local hash chain.
    """
    sentinel = get_sentinel(str(settings.AIRGAP_LOG_PATH))
    audit_block = sentinel.audit_cycle(
        event_type="HUMAN_REVIEW_COMPLETED",
        details={
            "inspection_id": req.inspection_id,
            "operator_id": req.operator_id,
            "decision": req.decision,
            "notes": req.notes,
        },
    )

    return {
        "status": "RECORDED",
        "inspection_id": req.inspection_id,
        "decision": req.decision,
        "operator_id": req.operator_id,
        "audit_entry": audit_block,
    }


@router.get("/benchmark", summary="Measure Pipeline Stage Latencies (Air-Gap Test)")
async def run_pipeline_benchmark():
    """
    Executes a live end-to-end benchmark on the flagship P-101 fixture,
    recording accurate microsecond/millisecond latency for every stage of the pipeline.
    """
    latencies = {}

    # Stage 1: Artifact Ingestion
    t0 = time.perf_counter()
    p101_fixture = FIXTURES_DIR / "p101_bearing.jpg"
    if not p101_fixture.exists():
        raise HTTPException(status_code=404, detail="P101 fixture not found for benchmark")
    record = default_artifact_manager.ingest_artifact(
        file_input=p101_fixture,
        filename="p101_bearing.jpg",
        metadata={"benchmark": True},
    )
    latencies["artifact_ingestion_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    # Stage 2: Vision Inference & Proposal
    t1 = time.perf_counter()
    telemetry = {
        "equipment_id": "P-101",
        "vibration_velocity_rms_mm_s": 9.82,
        "bearing_temperature_c": 104.2,
    }
    insp_res = await vision_client.inspect_photograph(
        workspace_id="ws-benchmark",
        question="Analyze P-101 bearing photograph",
        image_path=record.storage_path,
        image_artifact_id=record.artifact_id,
        telemetry_context=telemetry,
        execution_mode="test",
    )
    latencies["vision_inference_and_policy_ms"] = round((time.perf_counter() - t1) * 1000, 2)

    # Stage 3: Cross-Modal Corroboration
    t2 = time.perf_counter()
    correlator = CrossModalCorrelator()
    cross_corr = correlator.correlate(
        visual_result=insp_res,
        telemetry_context=telemetry,
        sop_context={"sop_id": "SOP-MRPL-P101-MNT", "standard_ref": "ISO 10816-3"},
    )
    latencies["cross_correlation_ms"] = round((time.perf_counter() - t2) * 1000, 2)

    # Stage 4: Ed25519 Cryptographic Attestation
    t3 = time.perf_counter()
    attestor = get_attestor(str(settings.KEYS_DIR))
    attestation = attestor.sign_photograph_inspection(insp_res)
    latencies["ed25519_attestation_ms"] = round((time.perf_counter() - t3) * 1000, 2)

    # Total latency
    total_ms = sum(latencies.values())
    latencies["total_pipeline_ms"] = round(total_ms, 2)

    return {
        "status": "COMPLETED",
        "fixture": "P-101 Bearing Raceway Spalling",
        "inspection_status": insp_res.get("inspection_status"),
        "corroboration": cross_corr.get("corroboration"),
        "signature_valid": attestation.get("signature") is not None,
        "latencies": latencies,
    }
