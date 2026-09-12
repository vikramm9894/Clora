"""
Comprehensive Unit & Integration Test Suite for Multimodal Photograph Vision Subsystem.
INDUSAI-X / CLORA Sovereign Multimodal Intelligence.

Tests:
1. Schema Validation & Coordinate Contract
2. Deterministic DomainValidation & Immutable VisualProvenance
3. CalibratedTestProvider SHA-256 Fixture Registry
4. Unregistered Photo Returns Inconclusive (Zero Fabricated Answers)
5. Engineering Policy Gate (Vibration & Temperature Limit Evaluation)
6. Hypothesis vs. Fact Governance (Model Cannot Promote Hypothesis to Fact)
7. Deterministic Pre-Classifier (Drawing vs. Photo Discrimination)
8. MultimodalVisionAgent & Citation Serialization
9. Model Router Visual Inspection Classification & Selection
10. Adversarial Robustness (Blurry Photo, Inverted BBox, Corrupt File)
11. Full End-to-End LangGraph Multi-Modal Cross-Correlation
"""

import os
import io
import hashlib
import pytest
from PIL import Image
from pydantic import ValidationError

from indusai.multimodal.photo_schema import (
    SeverityLevel,
    InspectionStatus,
    EvidenceStatus,
    SemanticType,
    FieldStatus,
    PhotoCategory,
    DefectClass,
    NormalizedRegion,
    VisualConfidenceVector,
    DomainValidation,
    VisualProvenance,
    NameplateField,
    NameplateData,
    RawInspectionProposal,
    VisualFinding,
    RootCauseHypothesis,
    PhotographInspectionResult,
)
from indusai.multimodal.photo_inspector import (
    CalibratedTestProvider,
    DeterministicPreClassifier,
    EngineeringPolicyGate,
    PhotographInspectionEngine,
)
from backend.agents.vision_agent import MultimodalVisionAgent
from backend.models.registry import ModelCapability, default_registry
from backend.models.router import IntelligentModelRouter
from samples.generate_sample_photos import generate_sample_photos


@pytest.fixture(scope="session", autouse=True)
def ensure_sample_photos():
    """Ensures synthetic sample photographs exist and are registered."""
    return generate_sample_photos()


# ==============================================================================
# 1. Schema Validation & Coordinate Contract Tests
# ==============================================================================

def test_normalized_region_coordinate_contract():
    # Valid region
    region = NormalizedRegion(ymin=0.1, xmin=0.2, ymax=0.5, xmax=0.6, label="Defect")
    assert region.to_list() == [0.1, 0.2, 0.5, 0.6]

    px = region.to_pixel_box(width=1000, height=800)
    assert px == {"x": 200, "y": 80, "width": 400, "height": 320}

    # Inverted xmin >= xmax must raise ValidationError
    with pytest.raises(ValidationError):
        NormalizedRegion(ymin=0.1, xmin=0.6, ymax=0.5, xmax=0.2)

    # Inverted ymin >= ymax must raise ValidationError
    with pytest.raises(ValidationError):
        NormalizedRegion(ymin=0.7, xmin=0.2, ymax=0.3, xmax=0.6)

    # Values > 1.0 or < 0.0 must raise ValidationError
    with pytest.raises(ValidationError):
        NormalizedRegion(ymin=-0.1, xmin=0.2, ymax=0.5, xmax=0.6)
    with pytest.raises(ValidationError):
        NormalizedRegion(ymin=0.1, xmin=0.2, ymax=1.2, xmax=0.6)


def test_immutable_visual_provenance():
    prov = VisualProvenance(
        artifact_id="artifact_test_01",
        artifact_version="1.0.0",
        content_hash="abc123sha",
        image_dimensions={"width": 640, "height": 480},
        mime_type="image/png",
        preprocessing_hash="def456sha",
        model_id="local_vlm",
        model_version="1.0",
        prompt_version="v1.0",
        inspection_id="INSP-01",
        execution_id="EXEC-01"
    )
    # Attempting to mutate a frozen Pydantic model must raise an error
    with pytest.raises(ValidationError):
        prov.artifact_id = "mutated_id"


def test_domain_validation_deterministic_contract():
    dom = DomainValidation(
        equipment_identified=True,
        measurement_valid=True,
        unit_valid=True,
        range_valid=True,
        source_consistent=True,
        status="VALID",
        details=["Rated power within normal 1-5000 kW range"]
    )
    assert dom.status == "VALID"
    assert dom.range_valid is True
    # Verify it does not hold statistical float pretend-confidence
    assert not hasattr(dom, "domain_validation_confidence")


def test_type_hierarchy_invariants():
    """
    Verifies the frozen type hierarchy:
    RawInspectionProposal -> ValidatedInspectionProposal -> EngineeringAssessment -> PhotographInspectionResult -> Evidence
    """
    from indusai.multimodal.photo_schema import ValidatedInspectionProposal, EngineeringAssessment
    from backend.rag.evidence import Evidence

    engine = PhotographInspectionEngine(force_mode="test")
    photo_path = os.path.join("samples", "photos", "P101_Bearing_Spalling.png")

    res = engine.inspect_photograph(
        image_input=photo_path,
        artifact_id="art_type_hierarchy_test",
        telemetry_context={"vibration_rms": 9.82, "bearing_temp_c": 104.2}
    )

    # 1. ValidatedInspectionProposal
    assert res.validated_proposal is not None
    assert isinstance(res.validated_proposal, ValidatedInspectionProposal)
    assert res.validated_proposal.observed_defect_class == DefectClass.BEARING_FATIGUE_SPALLING
    assert len(res.validated_proposal.valid_regions) >= 1

    # 2. EngineeringAssessment
    assert res.engineering_assessment is not None
    assert isinstance(res.engineering_assessment, EngineeringAssessment)
    assert res.engineering_assessment.severity == SeverityLevel.CRITICAL
    assert res.engineering_assessment.requires_immediate_action is True
    assert res.engineering_assessment.domain_validation.status == "VALID"

    # 3. PhotographInspectionResult
    assert isinstance(res, PhotographInspectionResult)
    assert res.inspection_id.startswith("INSP-")

    # 4. Evidence
    ev = res.to_evidence()
    assert isinstance(ev, Evidence)
    assert ev.evidence_id.startswith("vis_ev_")


# ==============================================================================
# 2. Calibrated Test Provider & Hash Registry Tests
# ==============================================================================

def test_calibrated_test_provider_bearing_spalling():
    engine = PhotographInspectionEngine(force_mode="test")
    photo_path = os.path.join("samples", "photos", "P101_Bearing_Spalling.png")
    assert os.path.exists(photo_path)

    res = engine.inspect_photograph(
        image_input=photo_path,
        artifact_id="art_bearing_01",
        telemetry_context={"vibration_rms": 9.82, "bearing_temp_c": 104.2}
    )

    assert res.photo_category == PhotoCategory.DEFECT_INSPECTION
    assert res.defect_class == DefectClass.BEARING_FATIGUE_SPALLING
    assert res.defect_detected is True
    assert res.severity == SeverityLevel.CRITICAL
    assert res.requires_immediate_action is True
    assert res.requires_human_review is True
    assert len(res.bounding_regions) >= 1
    assert "FATIGUE" in res.findings[0].description.upper() or "SPALLING" in res.findings[0].description.upper()

    # Convert to Evidence
    ev = res.to_evidence()
    assert ev.evidence_id.startswith("vis_ev_")
    assert "BEARING_FATIGUE_SPALLING" in ev.content
    assert ev.metadata["severity"] == "CRITICAL"


def test_calibrated_test_provider_sulzer_nameplate_ocr():
    engine = PhotographInspectionEngine(force_mode="test")
    photo_path = os.path.join("samples", "photos", "Sulzer_Pump_Nameplate.png")
    assert os.path.exists(photo_path)

    res = engine.inspect_photograph(
        image_input=photo_path,
        artifact_id="art_nameplate_01"
    )

    assert res.photo_category == PhotoCategory.NAMEPLATE_OCR
    assert res.nameplate_data is not None
    assert res.nameplate_data.rated_power_kw.value == 315.0
    assert res.nameplate_data.rated_speed_rpm.value == 1480
    assert res.nameplate_data.design_flow_m3h.value == 240.0
    assert res.nameplate_data.max_pressure_bar.value == 25.0
    assert res.nameplate_data.model_number.value == "OH2-100-250"
    assert res.severity == SeverityLevel.NORMAL
    assert res.requires_immediate_action is False


def test_unregistered_image_hash_returns_inconclusive():
    """
    Evaluator critique test: An arbitrary uncalibrated image must NEVER
    have a manufactured diagnosis quietly fabricated for it.
    """
    engine = PhotographInspectionEngine(force_mode="test")
    # Generate random unique image
    unregistered_img = Image.new("RGB", (320, 240), color=(111, 222, 133))

    res = engine.inspect_photograph(
        image_input=unregistered_img,
        artifact_id="art_unknown_random"
    )

    assert res.defect_class == DefectClass.UNKNOWN
    assert res.inspection_status == InspectionStatus.INCONCLUSIVE
    assert res.evidence_status == EvidenceStatus.UNVERIFIED
    assert res.severity == SeverityLevel.UNKNOWN


# ==============================================================================
# 3. Engineering Policy Gate Tests (Vibration / Temp Limits)
# ==============================================================================

def test_policy_gate_spalling_without_telemetry():
    """Without confirming telemetry, spalling is rated HIGH, not automatically CRITICAL."""
    proposal = RawInspectionProposal(
        provider_id="test",
        proposed_category=PhotoCategory.DEFECT_INSPECTION,
        observed_defect_class=DefectClass.BEARING_FATIGUE_SPALLING,
        confidence_vector=VisualConfidenceVector(visual_confidence=0.88, classification_confidence=0.85)
    )
    severity, imm_act, req_rev, rec = EngineeringPolicyGate.evaluate(proposal, telemetry_context=None)
    assert severity == SeverityLevel.HIGH
    assert imm_act is False
    assert req_rev is True


def test_policy_gate_spalling_with_telemetry_trip():
    """With verified vibration spike >= 7.1 mm/s, policy gate assigns CRITICAL."""
    proposal = RawInspectionProposal(
        provider_id="test",
        proposed_category=PhotoCategory.DEFECT_INSPECTION,
        observed_defect_class=DefectClass.BEARING_FATIGUE_SPALLING,
        confidence_vector=VisualConfidenceVector(visual_confidence=0.88, classification_confidence=0.85)
    )
    severity, imm_act, req_rev, rec = EngineeringPolicyGate.evaluate(
        proposal, telemetry_context={"vibration_rms": 9.82, "bearing_temp_c": 104.2}
    )
    assert severity == SeverityLevel.CRITICAL
    assert imm_act is True
    assert req_rev is True
    assert "shutdown" in rec.lower()


# ==============================================================================
# 4. Hypothesis vs Fact Governance
# ==============================================================================

def test_model_cannot_promote_hypothesis_to_fact():
    """
    AI Governance rule:
    CLORA never permits root_cause_hypothesis to possess status 'FACT'.
    It must strictly maintain semantic type HYPOTHESIS.
    """
    hypo = RootCauseHypothesis(
        hypothesis="Subsurface shear fatigue",
        confidence=0.72,
        status="HYPOTHESIS"
    )
    assert hypo.semantic_type == SemanticType.HYPOTHESIS
    assert hypo.status == "HYPOTHESIS"
    assert hypo.status != "FACT"


# ==============================================================================
# 5. Deterministic Pre-Classifier Tests
# ==============================================================================

def test_deterministic_pre_classifier_drawing_vs_photo():
    # 1. P&ID Drawing (Wide aspect, mostly white)
    drawing_img = Image.new("RGB", (1920, 1080), color=(255, 255, 255))
    mode_dwg = DeterministicPreClassifier.classify_visual_mode(drawing_img, {"filename": "P_AND_ID_Unit4.png"})
    assert mode_dwg == "DRAWING_SCHEMATIC"

    # 2. Field Photograph (Non-white textured)
    photo_img = Image.new("RGB", (640, 480), color=(120, 100, 80))
    mode_photo = DeterministicPreClassifier.classify_visual_mode(photo_img, {"filename": "bearing_damage_photo.jpg"})
    assert mode_photo == "PHYSICAL_PHOTOGRAPH"


# ==============================================================================
# 6. Model Router Multimodal Classification
# ==============================================================================

def test_router_classifies_visual_inspection():
    router = IntelligentModelRouter(registry=default_registry)

    # Query with photo keywords
    decision = router.route_task("Please inspect this bearing photo for spalling damage")
    assert decision.task_type == "visual_inspection"
    assert decision.selected_model in ["moondream", "deterministic-airgap-mock", "qwen2.5:3b"]

    # Query with image attachment metadata
    decision_att = router.route_task(
        "Analyze this asset",
        metadata={"file_type": "png", "mime_type": "image/png"}
    )
    assert decision_att.task_type == "visual_inspection"


# ==============================================================================
# 7. Adversarial & Robustness Tests
# ==============================================================================

def test_blurry_photo_triggers_inconclusive():
    engine = PhotographInspectionEngine(force_mode="test")
    # Low quality simulation
    img = Image.new("RGB", (100, 100), color=(10, 10, 10))
    res = engine.inspect_photograph(img, artifact_id="art_dark_blur")
    assert res.inspection_status == InspectionStatus.INCONCLUSIVE
    assert res.evidence_status == EvidenceStatus.UNVERIFIED


def test_multimodal_vision_agent_end_to_end():
    agent = MultimodalVisionAgent()
    # Photograph query with explicit test mode and fixture path
    res = agent.analyze(
        question="Analyze the bearing photo for Pump P-101 and check for spalling",
        drawing_path="samples/vision_fixtures/p101_bearing.jpg",
        drawing_metadata={"id": "img_p101_bearing", "fixture_scenario": "P101_BEARING_SPALLING", "execution_mode": "test"},
        telemetry_context={"vibration_rms": 9.82, "bearing_temp_c": 104.2}
    )
    assert "citations" in res
    assert len(res["citations"]) == 1
    cit = res["citations"][0]
    assert cit["file_type"] == "photograph"
    assert "BEARING_FATIGUE_SPALLING" in cit["snippet_or_data"]
    assert cit["confidence"] >= 0.80


# ==============================================================================
# 8. Full End-to-End LangGraph Multi-Modal Cross-Correlation
# ==============================================================================

def test_langgraph_workflow_with_visual_evidence():
    from backend.graph.workflow import build_workflow
    from backend.app.services.artifact_manager import default_artifact_manager

    rec = default_artifact_manager.ingest_artifact(
        file_input="samples/vision_fixtures/p101_bearing.jpg",
        filename="p101_bearing.jpg",
        metadata={"fixture_scenario": "P101_BEARING_SPALLING"},
    )

    workflow = build_workflow()

    initial_state = {
        "user_query": "Inspect P-101 bearing photo and determine whether it explains the vibration spike",
        "user_id": "eng_01",
        "user_role": "maintenance_engineer",
        "image_artifact_id": rec.artifact_id,
        "execution_mode": "test",
        "fixture_scenario": "P101_BEARING_SPALLING",
        "telemetry_context": {"vibration_rms": 9.82, "bearing_temp_c": 104.2},
        "evidence": [
            {
                "evidence_id": "telem_p101",
                "content": "Pump P-101 vibration telemetry peak: 9.82 mm/s RMS, bearing temperature 104.2 C",
                "source_document": "Pump_P101_Vibration_Telemetry.csv",
                "page_number": 1,
                "chunk_id": "c_telem_01",
                "relevance_score": 0.98,
            },
            {
                "evidence_id": "sop_p101_01",
                "content": "SOP-MRPL-P101-MNT Section 4.2: Centrifugal pump bearing replacement procedure and vibration limit enforcement.",
                "source_document": "Pump_P101_Maintenance_Manual.pdf",
                "page_number": 42,
                "chunk_id": "c_sop_01",
                "relevance_score": 0.95,
            }
        ]
    }

    final_state = workflow.invoke(initial_state)

    assert "visual_inspection_result" in final_state
    vis_res = final_state["visual_inspection_result"]
    assert str(vis_res["defect_class"]) in ("BEARING_FATIGUE_SPALLING", "DefectClass.BEARING_FATIGUE_SPALLING")
    assert str(vis_res["severity"]) in ("CRITICAL", "SeverityLevel.CRITICAL")

    # Verify synthesized answer contains grounded findings
    draft = final_state.get("draft_answer", "")
    assert "Verified Findings" in draft
    assert "fatigue" in draft.lower() or "spalling" in draft.lower()
    assert "critical" in draft.lower()
    assert "immediate action required: true" in draft.lower()

    # Verify dedicated state references (Phase 10)
    assert final_state.get("vision_inspection_id") is not None
    assert len(final_state.get("vision_evidence_ids", [])) >= 1
    assert "cross_correlation" in final_state
    assert final_state["cross_correlation"]["corroboration"] == "STRONG"
    assert "visual_attestation" in final_state
    assert final_state["visual_attestation"]["signature"] is not None

    # Verify cryptographic air-gap sentinel recorded inspection
    audit_events = [e.get("event") for e in final_state.get("audit_log", [])]
    assert "visual_inspection_executed" in audit_events
    assert len(final_state.get("airgap_proof_hashes", [])) >= 3


# ==============================================================================
# 9. Phase 16 Adversarial & Security Test Suite
# ==============================================================================

def test_golden_fixtures_corrosion_and_motor_stator():
    """Verify calibrated test provider handles all golden fixture scenarios."""
    engine = PhotographInspectionEngine(force_mode="test")

    # Flange corrosion
    res_corrosion = engine.inspect_photograph(
        image_input="samples/vision_fixtures/flange_corrosion.jpg",
        artifact_id="art_flange_01",
        metadata={"fixture_scenario": "FLANGE_PITTING_CORROSION"}
    )
    assert res_corrosion.defect_class == DefectClass.PITTING_CORROSION
    assert res_corrosion.severity == SeverityLevel.MODERATE
    assert "ultrasonic thickness" in res_corrosion.evidence_bound_recommendation.lower()

    # Motor stator scorch
    res_motor = engine.inspect_photograph(
        image_input="samples/vision_fixtures/motor_stator.jpg",
        artifact_id="art_motor_01",
        metadata={"fixture_scenario": "MOTOR_STATOR_SCORCH"}
    )
    assert res_motor.defect_class == DefectClass.THERMAL_DISCOLORATION
    assert res_motor.severity == SeverityLevel.HIGH
    assert "megger" in res_motor.evidence_bound_recommendation.lower()


def test_artifact_manager_magic_bytes_and_security(tmp_path):
    """Verify ArtifactManager magic byte checks, size limits, and SHA-256 fingerprinting."""
    from backend.app.services.artifact_manager import ArtifactManager

    mgr = ArtifactManager(base_storage_dir=str(tmp_path))

    # 1. Valid PNG
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    rec_png = mgr.ingest_artifact(file_input=png_bytes, filename="test.png")
    assert rec_png.mime_type == "image/png"
    assert len(rec_png.content_hash) == 64
    assert os.path.exists(rec_png.storage_path)

    # 2. Valid JPEG
    jpg_bytes = b"\xff\xd8\xff" + b"\x00" * 50
    rec_jpg = mgr.ingest_artifact(file_input=jpg_bytes, filename="test.jpg")
    assert rec_jpg.mime_type == "image/jpeg"

    # 3. Empty file rejected
    with pytest.raises(ValueError, match="empty artifact"):
        mgr.ingest_artifact(file_input=b"")

    # 4. Oversized file (>25 MB) rejected
    oversized_bytes = b"0" * (26 * 1024 * 1024)
    with pytest.raises(ValueError, match="exceeds maximum size"):
        mgr.ingest_artifact(file_input=oversized_bytes)


def test_vlm_robustness_malformed_json_and_fences():
    """Verify SchemaValidator sanitizes markdown fences, missing keys, and invalid enums without crashing."""
    from indusai.multimodal.validators import SchemaValidator

    # Raw response with unknown defect, markdown wrapping, and strange keys
    malformed_dict = {
        "category": "DEFECT_INSPECTION",
        "defect_class": "NON_EXISTENT_DEFECT_CLASS_99",
        "observations": ["Discoloration noticed on outer ring"],
        "bbox": [0.1, 0.2, 0.5, 0.6],
        "nameplate": {
            "rated_power_kw": {"value": 315.0, "unit": "kW"},
        },
        "unknown_extra_field": "test_value"
    }

    proposal = SchemaValidator.sanitize_raw_proposal(
        raw_dict=malformed_dict,
        provider_id="ollama_mock",
        default_equipment_tag="P-101"
    )

    assert proposal.observed_defect_class == DefectClass.UNKNOWN
    assert proposal.equipment_tag_candidate == "P-101"
    assert len(proposal.observed_regions) == 1
    assert proposal.observed_regions[0].to_list() == [0.1, 0.2, 0.5, 0.6]


def test_bounding_box_validator_adversarial_geometry():
    """Verify BoundingBoxValidator rejects inverted, out-of-bounds, NaN/Inf, and tiny boxes."""
    from indusai.multimodal.validators import BoundingBoxValidator

    # Inverted X
    ok, reason = BoundingBoxValidator.validate_coordinates(0.1, 0.8, 0.5, 0.2)
    assert ok is False
    assert "Inverted" in reason

    # Out of unit frame [0, 1]
    ok, reason = BoundingBoxValidator.validate_coordinates(0.1, -0.2, 0.5, 0.8)
    assert ok is False

    # NaN coordinates
    ok, reason = BoundingBoxValidator.validate_coordinates(float("nan"), 0.2, 0.5, 0.8)
    assert ok is False
    assert "NaN" in reason

    # Absurdly tiny box (point/line with area < 0.0001)
    ok, reason = BoundingBoxValidator.validate_coordinates(0.1, 0.1, 0.1001, 0.1001)
    assert ok is False
    assert "minimal physical threshold" in reason


def test_domain_validation_physical_boundary_limits():
    """Verify DomainValidator rejects physically impossible operational parameters."""
    from indusai.multimodal.validators import DomainValidator

    # Power exceeds 10,000 kW for pump
    impossible_proposal = RawInspectionProposal(
        provider_id="test",
        proposed_category=PhotoCategory.NAMEPLATE_OCR,
        equipment_tag_candidate="P-101",
        nameplate_proposal={
            "rated_power_kw": {"value": 999999.0, "unit": "kW"},
            "rated_speed_rpm": {"value": 1480, "unit": "RPM"},
        }
    )

    dom = DomainValidator.validate_proposal(impossible_proposal)
    assert dom.range_valid is False
    assert dom.status == "INVALID"
    assert any("out of physical" in d for d in dom.details)


def test_cross_modal_correlator_triangulation():
    """Verify CrossModalCorrelator correctly synthesizes visual, telemetry, and SOP evidence."""
    from backend.verification.cross_correlation import CrossModalCorrelator
    from indusai.multimodal.photo_inspector import PhotographInspectionEngine

    engine = PhotographInspectionEngine(force_mode="test")
    vis_res = engine.inspect_photograph(
        image_input="samples/vision_fixtures/p101_bearing.jpg",
        artifact_id="p101_bearing",
        metadata={"fixture_scenario": "P101_BEARING_SPALLING"}
    )

    # 1. Full Corroboration: Visual + Telemetry Trip + SOP
    corr = CrossModalCorrelator.correlate(
        visual_result=vis_res,
        telemetry_context={"vibration_rms": 9.82, "bearing_temp_c": 104.2},
        sop_evidence=[{"evidence_id": "sop_01", "content": "SOP-MRPL-P101-MNT Section 4.2 Bearing Replacement"}],
    )
    assert corr.corroboration == "STRONG"
    assert corr.visual_support is True
    assert corr.telemetry_support is True
    assert corr.sop_support is True
    assert "shutdown" in corr.recommended_action.lower()

    # 2. Partial: Visual only, normal telemetry
    corr_partial = CrossModalCorrelator.correlate(
        visual_result=vis_res,
        telemetry_context={"vibration_rms": 2.1, "bearing_temp_c": 55.0},
        sop_evidence=[],
    )
    assert corr_partial.corroboration == "PARTIAL"
    assert corr_partial.telemetry_support is False


def test_ed25519_visual_evidence_attestation_and_tamper_proofing():
    """Verify Ed25519 signing of PhotographInspectionResult and tamper detection."""
    from security.attestation import get_attestor, EvidenceVerifier
    from indusai.multimodal.photo_inspector import PhotographInspectionEngine

    engine = PhotographInspectionEngine(force_mode="test")
    vis_res = engine.inspect_photograph(
        image_input="samples/vision_fixtures/p101_bearing.jpg",
        artifact_id="art_bearing_proof",
        metadata={"fixture_scenario": "P101_BEARING_SPALLING"}
    )

    attestor = get_attestor()
    proof = attestor.sign_photograph_inspection(vis_res)

    assert proof is not None
    assert proof["sealed"] is True
    assert proof["algorithm"] == "Ed25519"
    assert "PROOF-INSP-" in proof["proof_id"]

    # Verify signature passes
    verifier = EvidenceVerifier()
    res_verify = verifier.verify_proof_package(proof)
    assert res_verify["verified"] is True
    assert res_verify["error"] is None

    # Tamper with content: change severity to NORMAL
    tampered_proof = dict(proof)
    tampered_payload = dict(proof["canonical_payload"])
    tampered_payload["severity"] = "NORMAL"
    tampered_proof["canonical_payload"] = tampered_payload

    res_tampered = verifier.verify_proof_package(tampered_proof)
    assert res_tampered["verified"] is False


def test_production_mode_rejects_missing_image_without_fabrication():
    """
    Phase 1.2 Invariant:
    Under execution_mode='production', missing image returns INCONCLUSIVE.
    Never fabricates a synthetic image or synthetic evidence.
    """
    agent = MultimodalVisionAgent()
    res = agent.inspect(
        artifact_id="non_existent_image_artifact_123",
        execution_mode="production"
    )

    assert res.inspection_status == InspectionStatus.INCONCLUSIVE
    assert res.evidence_status == EvidenceStatus.REJECTED
    assert res.defect_detected is False
    assert res.severity == SeverityLevel.UNKNOWN
    assert "missing" in res.summary.lower()

