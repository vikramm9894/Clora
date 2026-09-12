"""
AgentState definition for INDUSAI-X LangGraph workflow.
"""

from typing import TypedDict


class AgentState(TypedDict, total=False):
    user_query: str
    user_id: str
    user_role: str

    intent: str
    plan: list

    retrieved_docs: list
    evidence: list
    retrieved_evidence: list

    agent_outputs: dict

    draft_answer: str
    claims: list
    verification_results: list
    verification_status: str

    confidence: float
    guardrail_status: str

    final_answer: str
    audit_log: list
    airgap_proof_hash: str
    airgap_proof_hashes: list
    evidence_attestation: dict

    # Multi-Model Routing & Sandboxed Coding Task Extensions
    model_routing: dict
    code_task: dict
    code_verification_result: dict
    calculation_result: dict
    sandbox_output_files: list

    # Multimodal Visual Inspection Extensions (Phase 10)
    image_artifact_id: str
    visual_evidence_ids: list
    vision_evidence_ids: list
    visual_inspection_result: dict
    vision_inspection_id: str
    vision_status: str
    vision_evidence_status: str
    vision_requires_review: bool
    vision_provenance_ref: str
    cross_correlation: dict
    hitl_review_required: bool
    hitl_review_payload: dict
    visual_attestation: dict
    telemetry_context: dict
    execution_mode: str
    fixture_scenario: str

