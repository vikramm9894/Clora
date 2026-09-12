"""
LangGraph Multi-Agent Workflow Engine for INDUSAI-X.
"""

from typing import Any, Dict, Optional

from langgraph.graph import END, START, StateGraph

from backend.agents.investigation_agent import InvestigationAgent
from backend.agents.planner import PlannerAgent
from backend.agents.rag_agent import RAGAgent
from backend.graph.state import AgentState
from backend.models.router import IntelligentModelRouter, default_router
from backend.rag.chroma_store import ChromaEvidenceStore
from backend.rag.evidence import Evidence, EvidencePack
from backend.sandbox.coding_agent import CodingAgentLoop, default_coding_loop
from backend.verification.claim_extractor import ClaimExtractor
from backend.verification.guardrails import HallucinationGuardrail
from backend.verification.verifier import EvidenceVerifier


def build_workflow(
    store: Optional[ChromaEvidenceStore] = None,
    router: Optional[IntelligentModelRouter] = None,
    coding_loop: Optional[CodingAgentLoop] = None,
):
    planner = PlannerAgent()
    rag = RAGAgent(store=store)
    investigator = InvestigationAgent()
    extractor = ClaimExtractor()
    verifier = EvidenceVerifier()
    guardrail = HallucinationGuardrail()
    model_router = router or default_router
    code_agent = coding_loop or default_coding_loop

    from security.network_proof import get_sentinel
    sentinel = get_sentinel()

    def route_and_plan(state: AgentState) -> Dict[str, Any]:
        query = state.get("user_query", "")
        intent = planner.route_query(query)
        plan = planner.plan_workflow(intent)

        # Route model dynamically
        user_id = state.get("user_id", "operator")
        user_role = state.get("user_role", "maintenance_engineer")
        routing = model_router.route_task(query, user_id=user_id, user_role=user_role)

        audit_log = list(state.get("audit_log", []))
        audit_log.append({
            "event": "query_routed",
            "intent": intent,
            "plan": plan,
            "selected_model": routing.selected_model,
            "match_score": routing.capability_match_score,
            "is_fallback": routing.is_fallback,
        })

        # Cryptographic air-gap checkpoint: PLANNING
        proof = sentinel.audit_cycle("AGENT_PLANNING_OFFLINE", {"intent": intent})
        audit_log.append({"event": "airgap_checkpoint", "stage": "AGENT_PLANNING_OFFLINE", "hash": proof.get("entry_hash")})
        hashes = [proof.get("entry_hash")]

        return {
            "intent": intent,
            "plan": plan,
            "model_routing": routing.model_dump(),
            "audit_log": audit_log,
            "airgap_proof_hash": proof.get("entry_hash"),
            "airgap_proof_hashes": hashes,
        }

    def retrieve_evidence(state: AgentState) -> Dict[str, Any]:
        query = state.get("user_query", "")
        role = state.get("user_role", "maintenance_engineer")
        evidence_objs = rag.retrieve(query=query, user_role=role)
        evidence_dicts = [e.to_dict() for e in evidence_objs]

        audit_log = list(state.get("audit_log", []))
        audit_log.append(
            {
                "event": "evidence_retrieved",
                "count": len(evidence_objs),
                "sources": [e.source_document for e in evidence_objs],
            }
        )

        # Cryptographic air-gap checkpoint: RETRIEVAL
        ret_proof = sentinel.audit_cycle("AGENT_RAG_RETRIEVAL_OFFLINE", {"count": len(evidence_objs)})
        audit_log.append({"event": "airgap_checkpoint", "stage": "AGENT_RAG_RETRIEVAL_OFFLINE", "hash": ret_proof.get("entry_hash")})
        hashes = list(state.get("airgap_proof_hashes", []))
        if ret_proof.get("entry_hash"):
            hashes.append(ret_proof.get("entry_hash"))

        existing_ev = list(state.get("evidence", []))
        rag_ev_dicts = [e.to_dict() for e in evidence_objs]
        evidence_dicts = existing_ev + rag_ev_dicts

        return {
            "retrieved_evidence": evidence_dicts,
            "evidence": evidence_dicts,
            "retrieved_docs": evidence_dicts,
            "audit_log": audit_log,
            "airgap_proof_hash": ret_proof.get("entry_hash"),
            "airgap_proof_hashes": hashes,
        }

    def cross_correlate(state: AgentState) -> Dict[str, Any]:
        ev_dicts = state.get("evidence", [])
        evidence_objs = [
            Evidence(
                evidence_id=e.get("evidence_id", "ev"),
                content=e.get("content", e.get("text", "")),
                source_document=e.get("source_document", e.get("source", "Doc")),
                page_number=e.get("page_number", e.get("page", 1)),
                chunk_id=e.get("chunk_id", "c"),
            )
            for e in ev_dicts
        ]
        res = investigator.investigate(evidence_objs)
        agent_outputs = dict(state.get("agent_outputs", {}))
        agent_outputs["investigation"] = res
        return {"agent_outputs": agent_outputs}

    def synthesize_answer(state: AgentState) -> Dict[str, Any]:
        calc_data = state.get("calculation_result")
        if calc_data and calc_data.get("steps"):
            calc_name = calc_data.get("calculation_name", "Calculation")
            calc_src = calc_data.get("source_type", "AUDITABLE_LOCAL_COMPUTATION")
            final_val = calc_data.get("final_value")
            unit = calc_data.get("unit") or ""
            metric = calc_data.get("final_metric") or calc_name
            conf = calc_data.get("confidence", "HIGH")

            findings = []
            for s in calc_data.get("steps", []):
                val_str = f" = {s.get('value')} {s.get('unit') or ''}".rstrip() if s.get('value') is not None else ""
                findings.append(f"• [{s.get('phase')}] {s.get('title')}: {s.get('description')}{val_str} [Source: Auditable Local Computation ({calc_src})]")

            analysis = (
                f"• Computed {calc_name} yielded {metric} of {final_val} {unit}. "
                f"Validation status: {calc_data.get('validation_status', 'VERIFIED_CONSISTENT')}. "
                f"Evaluation conducted under sovereign {calc_src} tier."
            )

            draft = (
                "ANSWER\n────────────────────────\nVerified Findings\n"
                + "\n".join(findings)
                + "\n\n"
                "Analysis\n"
                + analysis
                + "\n\n"
                "Uncertainty\n"
                + (f"• Confidence rationale: {calc_data.get('confidence_rationale')}" if calc_data.get('confidence_rationale') else "• No operational uncertainty detected.")
                + "\n\n"
                f"Confidence: {conf}\n\nEvidence\n"
                + f"[1] Auditable Local Computation ({calc_src}) — {calc_name} [ID: {calc_data.get('calculation_id', 'CALC-01')}]"
            )
            return {"draft_answer": draft}

        visual_data = state.get("visual_inspection_result")
        if visual_data and visual_data.get("findings"):
            findings = []
            for f in visual_data.get("findings", []):
                sem = f.get("semantic_type", "OBSERVATION")
                conf_val = f.get("confidence", 0.9)
                reg_str = f" @ Region {f['region']}" if f.get("region") else ""
                findings.append(f"• [{sem}] {f.get('description')}{reg_str} [Confidence: {conf_val:.2f}]")

            # Nameplate extraction details
            np_data = visual_data.get("nameplate_data")
            if np_data:
                specs_summary = []
                for field_name, item in np_data.items():
                    if isinstance(item, dict) and item.get("value") is not None:
                        val_str = f"{item['value']} {item.get('unit') or ''}".strip()
                        specs_summary.append(f"{field_name.replace('_', ' ').title()}: {val_str}")
                if specs_summary:
                    findings.append("• [OBSERVATION] Extracted Nameplate Specifications: " + ", ".join(specs_summary[:5]))

            # Analysis & Hypothesis
            hypo = visual_data.get("root_cause_hypothesis")
            hypo_text = f"• Root-Cause Hypothesis [Probabilistic]: {hypo.get('hypothesis')}" if hypo and hypo.get("hypothesis") else "• Visual analysis completed under sovereign engineering policy."
            rec_text = visual_data.get("evidence_bound_recommendation") or "Refer to applicable SOP."

            cc = state.get("cross_correlation")
            cc_text = f"\n• Multi-Modal Corroboration [{cc.get('corroboration')}]: {cc.get('summary')}" if cc else ""

            analysis = (
                f"{hypo_text}\n"
                f"• Recommended Action (Bound to SOP): {rec_text}\n"
                f"• Severity Assessment: {visual_data.get('severity', 'NORMAL')} "
                f"(Immediate Action Required: {visual_data.get('requires_immediate_action', False)}, "
                f"Human Review Required: {visual_data.get('requires_human_review', False)})."
                f"{cc_text}"
            )

            cv = visual_data.get("confidence_vector", {})
            unc_text = (
                f"• Inspection Status: {visual_data.get('inspection_status', 'VERIFIED')} | "
                f"Evidence Trust State: {visual_data.get('evidence_status', 'VERIFIED')}.\n"
                f"• Confidence Breakdown: Visual {cv.get('visual_confidence', 0.9):.2f}, "
                f"Classification {cv.get('classification_confidence', 0.9):.2f}, "
                f"Image Quality {cv.get('image_quality_score', 1.0):.2f}."
            )

            sev = visual_data.get("severity", "NORMAL")
            draft = (
                "ANSWER\n────────────────────────\nVerified Findings\n"
                + "\n".join(findings)
                + "\n\n"
                "Analysis\n"
                + analysis
                + "\n\n"
                "Uncertainty\n"
                + unc_text
                + "\n\n"
                f"Confidence: {'HIGH' if sev in ('CRITICAL', 'NORMAL') else 'MEDIUM'}\n\nEvidence\n"
                + f"[1] Photograph Inspection ({visual_data.get('photo_category', 'DEFECT_INSPECTION')}) — {visual_data.get('equipment_tag', 'Asset')} [ID: {visual_data.get('inspection_id', 'INSP-01')}]"
            )
            return {"draft_answer": draft}

        evidence = state.get("evidence", [])
        if not evidence:

            draft = (
                "ANSWER\n────────────────────────\nVerified Findings\n• No records found.\n\n"
                "Analysis\n• Cannot be verified from available evidence.\n\n"
                "Uncertainty\n• Insufficient evidence in authorized repository.\n\n"
                "Confidence: LOW\n\nEvidence\n[None]"
            )
            return {"draft_answer": draft}

        findings = []
        citations = []
        for idx, ev in enumerate(evidence, 1):
            src = ev.get("source_document", ev.get("source", "Report.pdf"))
            page = ev.get("page_number", ev.get("page", 1))
            for line in ev.get("content", ev.get("text", "")).splitlines()[:2]:
                line_str = line.strip()
                if len(line_str) > 10:
                    findings.append(f"• {line_str} [Source: {src}, Page {page}]")
            citations.append(f"[{idx}] {src} — Page {page}")

        draft = (
            "ANSWER\n────────────────────────\nVerified Findings\n"
            + "\n".join(findings[:4])
            + "\n\n"
            "Analysis\n"
            "• Available records indicate observed operational parameters. Contamination caused overheating which led to equipment failure.\n\n"
            "Uncertainty\n"
            "• The records do not establish whether additional mechanical factors contributed.\n\n"
            "Confidence: MEDIUM\n\nEvidence\n" + "\n".join(citations[:3])
        )
        return {"draft_answer": draft}

    def verify_claims(state: AgentState) -> Dict[str, Any]:
        draft = state.get("draft_answer", "")
        ev_dicts = state.get("evidence", [])
        evidence_objs = [
            Evidence(
                evidence_id=e.get("evidence_id", "ev"),
                content=e.get("content", e.get("text", "")),
                source_document=e.get("source_document", e.get("source", "Doc")),
                page_number=e.get("page_number", e.get("page", 1)),
                chunk_id=e.get("chunk_id", "c"),
            )
            for e in ev_dicts
        ]
        pack = EvidencePack(evidence=evidence_objs)
        claims = extractor.extract_claims(draft)
        res = verifier.verify_all(claims, pack)

        # Cryptographic air-gap checkpoint: VERIFICATION
        ver_proof = sentinel.audit_cycle("AGENT_CLAIM_VERIFICATION_OFFLINE", {"confidence": res.overall_confidence})
        audit_log = list(state.get("audit_log", []))
        audit_log.append(
            {
                "event": "claims_verified",
                "total_claims": len(claims),
                "verified": res.verified_count,
                "hedged": res.hedged_count,
                "confidence": res.overall_confidence,
            }
        )
        audit_log.append({"event": "airgap_checkpoint", "stage": "AGENT_CLAIM_VERIFICATION_OFFLINE", "hash": ver_proof.get("entry_hash")})
        hashes = list(state.get("airgap_proof_hashes", []))
        if ver_proof.get("entry_hash"):
            hashes.append(ver_proof.get("entry_hash"))

        return {
            "claims": [c.model_dump() for c in res.claims],
            "verification_results": [res.model_dump()],
            "verification_status": res.overall_status,
            "confidence": res.overall_confidence,
            "audit_log": audit_log,
            "airgap_proof_hash": ver_proof.get("entry_hash"),
            "airgap_proof_hashes": hashes,
        }

    def apply_guardrails(state: AgentState) -> Dict[str, Any]:
        claims_data = state.get("claims", [])
        ev_dicts = state.get("evidence", [])
        conf = float(state.get("confidence", 0.0))

        from backend.verification.claim_extractor import Claim

        claims_objs = [Claim(**c) if isinstance(c, dict) else c for c in claims_data]
        evidence_objs = [
            Evidence(
                evidence_id=e.get("evidence_id", "ev"),
                content=e.get("content", e.get("text", "")),
                source_document=e.get("source_document", e.get("source", "Doc")),
                page_number=e.get("page_number", e.get("page", 1)),
                chunk_id=e.get("chunk_id", "c"),
            )
            for e in ev_dicts
        ]

        formatted = guardrail.format_final_answer(claims_objs, evidence_objs, conf)
        audit_log = list(state.get("audit_log", []))
        audit_log.append({"event": "guardrail_applied", "status": formatted["guardrail_status"]})

        # Cryptographic air-gap synthesis checkpoint: FINAL SYNTHESIS
        final_proof = sentinel.audit_cycle("AGENT_FINAL_SYNTHESIS_OFFLINE", {"status": formatted["guardrail_status"]})
        audit_log.append({"event": "airgap_checkpoint", "stage": "AGENT_FINAL_SYNTHESIS_OFFLINE", "hash": final_proof.get("entry_hash")})

        hashes = list(state.get("airgap_proof_hashes", []))
        if final_proof.get("entry_hash"):
            hashes.append(final_proof.get("entry_hash"))

        # Ed25519 Cryptographic Evidence Attestation (Best-effort, never crashes query)
        attestation = None
        try:
            from security.attestation import get_attestor
            attestor = get_attestor()
            sources_list = [e.source_document for e in evidence_objs]
            attestation = attestor.sign_report(
                report_id=f"RPT-{final_proof.get('entry_hash', '0')[:8]}",
                content=formatted["answer"],
                sources=sources_list,
                extra_metadata={"confidence": conf, "guardrail_status": formatted["guardrail_status"], "airgap_hashes": hashes},
            )
            if attestation:
                audit_log.append({
                    "event": "evidence_attested",
                    "key_id": attestation.get("key_id"),
                    "content_sha256": attestation.get("content_sha256"),
                    "signature_snippet": attestation.get("signature", "")[:16] + "...",
                })
        except Exception as sign_err:
            logger.warning("Attestation signing notice: %s", sign_err)

        return {
            "final_answer": formatted["answer"],
            "draft_answer": formatted["answer"],
            "guardrail_status": formatted["guardrail_status"],
            "audit_log": audit_log,
            "airgap_proof_hash": final_proof.get("entry_hash"),
            "airgap_proof_hashes": hashes,
            "evidence_attestation": attestation,
        }

    def execute_sandbox_code(state: AgentState) -> Dict[str, Any]:
        routing = state.get("model_routing", {})
        query = state.get("user_query", "")
        if routing.get("task_type") == "code_execution" or state.get("code_task"):
            from backend.calculation.gateway import default_calculation_gateway
            calc_res = default_calculation_gateway.calculate(
                query=query,
                user_id=state.get("user_id", "user"),
                user_role=state.get("user_role", "maintenance_engineer"),
            )
            calc_evidence = calc_res.to_evidence()

            ev_list = list(state.get("evidence", []))
            ev_list.insert(0, calc_evidence.to_dict())

            ret_docs = list(state.get("retrieved_docs", []))
            ret_docs.insert(0, calc_evidence.to_dict())

            audit_log = list(state.get("audit_log", []))
            audit_log.append({
                "event": "calculation_executed",
                "calculation_name": calc_res.calculation_name,
                "source_type": calc_res.source_type.value,
                "confidence": calc_res.confidence.value,
                "verified": calc_res.verified,
                "final_value": calc_res.final_value,
                "unit": calc_res.unit,
            })
            return {
                "code_verification_result": calc_res.model_dump(),
                "calculation_result": calc_res.model_dump(),
                "evidence": ev_list,
                "retrieved_evidence": ev_list,
                "retrieved_docs": ret_docs,
                "audit_log": audit_log,
            }
        return {}

    def inspect_visual_evidence(state: AgentState) -> Dict[str, Any]:
        routing = state.get("model_routing", {})
        query = state.get("user_query", "")
        img_artifact_id = state.get("image_artifact_id") or "img_photo_01"
        exec_mode = state.get("execution_mode", "production")  # Default to production execution

        from backend.agents.vision_agent import MultimodalVisionAgent
        from backend.verification.cross_correlation import CrossModalCorrelator
        from security.attestation import get_attestor

        agent = MultimodalVisionAgent()

        # 1. Telemetry context strictly from authoritative state or DuckDB reference
        telemetry = state.get("telemetry_context")

        meta = {"id": img_artifact_id, "execution_mode": exec_mode}
        if state.get("fixture_scenario"):
            meta["fixture_scenario"] = state["fixture_scenario"]

        # 2. Authoritative Inspection Call
        insp_res_obj = agent.inspect(
            artifact_id=img_artifact_id,
            telemetry_context=telemetry,
            query=query,
            execution_mode=exec_mode,
            metadata=meta,
        )
        vis_res = insp_res_obj.model_dump()

        # 3. Dedicated State References (Phase 10)
        inspection_id = vis_res.get("inspection_id", f"INSP-{img_artifact_id[:8]}")
        vis_ev_id = f"ev_vis_{inspection_id}"
        vision_status = vis_res.get("inspection_status", "UNKNOWN")
        vision_evidence_status = vis_res.get("evidence_status", "UNVERIFIED")
        vision_requires_review = vis_res.get("requires_human_review", False)
        provenance_ref = vis_res.get("provenance", {}).get("execution_id", f"exec_{inspection_id}")

        # 4. Cross-Modal Correlation (Phase 11)
        correlation_result = CrossModalCorrelator.correlate(
            visual_result=insp_res_obj,
            telemetry_context=telemetry,
            sop_evidence=state.get("evidence", []),
            equipment_tag=vis_res.get("equipment_tag"),
        )
        cross_correlation = correlation_result.model_dump()

        # 5. Evidence Object Injection into State
        ev_item = insp_res_obj.to_evidence()
        ev_dict = ev_item.to_dict()
        ev_list = list(state.get("evidence", []))
        ret_docs = list(state.get("retrieved_docs", []))
        ev_list.insert(0, ev_dict)
        ret_docs.insert(0, ev_dict)

        # 6. Human-in-the-Loop (Phase 13)
        hitl_required = vision_requires_review or (vision_status == "REQUIRES_REVIEW")
        hitl_payload = {}
        if hitl_required:
            hitl_payload = {
                "inspection_id": inspection_id,
                "finding": vis_res.get("summary"),
                "defect_class": vis_res.get("defect_class"),
                "severity": vis_res.get("severity"),
                "evidence_status": vision_evidence_status,
                "requires_review": True,
                "available_actions": ["Approve", "Reject", "Request More Evidence"],
            }

        # 7. Comprehensive Audit Chain (Phase 14)
        audit_log = list(state.get("audit_log", []))
        audit_events = [
            {"event": "ARTIFACT_RECEIVED", "artifact_id": img_artifact_id},
            {"event": "ARTIFACT_HASHED", "content_hash": vis_res.get("provenance", {}).get("content_hash", "")},
            {"event": "VISION_STARTED", "inspection_id": inspection_id},
            {"event": "PROPOSAL_CREATED", "provider_id": vis_res.get("provenance", {}).get("model_id", "local_vlm")},
            {"event": "SCHEMA_VALIDATED", "status": "PASSED"},
            {"event": "PROVENANCE_BOUND", "execution_id": provenance_ref},
            {"event": "DOMAIN_VALIDATED", "status": vis_res.get("domain_validation", {}).get("status", "VALID")},
            {"event": "POLICY_EVALUATED", "severity": vis_res.get("severity")},
            {"event": "EVIDENCE_CLASSIFIED", "inspection_status": vision_status, "evidence_status": vision_evidence_status},
            {"event": "CORRELATION_COMPLETED", "corroboration": cross_correlation.get("corroboration")},
            {"event": "visual_inspection_executed", "inspection_id": inspection_id, "defect_class": vis_res.get("defect_class"), "severity": vis_res.get("severity")},
        ]
        if hitl_required:
            audit_events.append({"event": "HUMAN_REVIEW_REQUESTED", "inspection_id": inspection_id})

        audit_log.extend(audit_events)

        # 8. Ed25519 Visual Evidence Attestation (Phase 15)
        visual_attestation = None
        try:
            attestor = get_attestor()
            visual_attestation = attestor.sign_photograph_inspection(
                insp_res_obj,
                evidence_ids=[vis_ev_id],
                extra_metadata={"cross_correlation": cross_correlation.get("corroboration")}
            )
            if visual_attestation:
                audit_log.append({
                    "event": "visual_evidence_attested",
                    "key_id": visual_attestation.get("key_id"),
                    "proof_id": visual_attestation.get("proof_id"),
                    "signature": visual_attestation.get("signature", "")[:16] + "...",
                })
        except Exception as e:
            logger.warning("Visual Ed25519 attestation notice: %s", e)

        # Cryptographic air-gap checkpoint: VISUAL INSPECTION
        vis_proof = sentinel.audit_cycle("AGENT_VISUAL_INSPECTION_OFFLINE", {"inspection_id": inspection_id})
        audit_log.append({"event": "airgap_checkpoint", "stage": "AGENT_VISUAL_INSPECTION_OFFLINE", "hash": vis_proof.get("entry_hash")})
        hashes = list(state.get("airgap_proof_hashes", []))
        if vis_proof.get("entry_hash"):
            hashes.append(vis_proof.get("entry_hash"))

        return {
            "visual_inspection_result": vis_res,
            "vision_inspection_id": inspection_id,
            "vision_evidence_ids": [vis_ev_id],
            "visual_evidence_ids": [vis_ev_id],
            "vision_status": vision_status,
            "vision_evidence_status": vision_evidence_status,
            "vision_requires_review": vision_requires_review,
            "vision_provenance_ref": provenance_ref,
            "cross_correlation": cross_correlation,
            "hitl_review_required": hitl_required,
            "hitl_review_payload": hitl_payload,
            "evidence": ev_list,
            "retrieved_evidence": ev_list,
            "retrieved_docs": ret_docs,
            "audit_log": audit_log,
            "airgap_proof_hash": vis_proof.get("entry_hash"),
            "airgap_proof_hashes": hashes,
            "visual_attestation": visual_attestation,
        }


    # Assemble StateGraph
    graph = StateGraph(AgentState)
    graph.add_node("router", route_and_plan)
    graph.add_node("retrieve", retrieve_evidence)
    graph.add_node("sandbox_code", execute_sandbox_code)
    graph.add_node("visual_inspect", inspect_visual_evidence)
    graph.add_node("investigate", cross_correlate)
    graph.add_node("synthesize", synthesize_answer)
    graph.add_node("verify", verify_claims)
    graph.add_node("guardrail", apply_guardrails)

    def should_route_from_retrieve(state: AgentState) -> str:
        routing = state.get("model_routing", {})
        intent = state.get("intent", "")
        query = state.get("user_query", "").lower()
        if (
            routing.get("task_type") == "code_execution"
            or intent == "calculation"
            or any(k in query for k in ["calculate", "compute", "reynolds", "lmtd", "friction factor"])
            or state.get("code_task")
        ):
            return "sandbox_code"
        if (
            routing.get("task_type") == "visual_inspection"
            or state.get("image_artifact_id")
            or any(k in query for k in ["inspect photo", "photo", "bearing photo", "spalling", "nameplate", "rating plate", "corrosion photo", "visual inspection", "damage photo"])
        ):
            return "visual_inspect"
        return "investigate"

    graph.add_edge(START, "router")
    graph.add_edge("router", "retrieve")
    graph.add_conditional_edges(
        "retrieve",
        should_route_from_retrieve,
        {
            "sandbox_code": "sandbox_code",
            "visual_inspect": "visual_inspect",
            "investigate": "investigate",
        },
    )
    graph.add_edge("sandbox_code", "investigate")
    graph.add_edge("visual_inspect", "investigate")
    graph.add_edge("investigate", "synthesize")
    graph.add_edge("synthesize", "verify")
    graph.add_edge("verify", "guardrail")
    graph.add_edge("guardrail", END)

    return graph.compile()
