"""
Cross-Modal Evidence Correlation Engine for Sovereign Industrial Diagnostics.
INDUSAI-X / CLORA Sovereign Multimodal Intelligence Subsystem.

Binds:
1. Photograph Visual Evidence (defects, wear patterns, nameplate specifications)
2. Quantitative DuckDB SCADA / Telemetry Evidence (vibration RMS, temperatures, pressures)
3. Authoritative Standard Operating Procedure (SOP) Evidence from RAG
"""

import hashlib
import logging
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from indusai.multimodal.photo_schema import (
    DefectClass,
    PhotographInspectionResult,
    SeverityLevel,
)
from indusai.multimodal.engineering_policy import (
    EngineeringPolicyGate,
    POLICY_REGISTRY,
)

logger = logging.getLogger("indusai.verification.cross_correlation")


class CrossCorrelationResult(BaseModel):
    """
    Deterministic cross-modal correlation outcome fusing visual, telemetry, and SOP evidence.
    """
    finding: str
    equipment_tag: str
    visual_support: bool = False
    telemetry_support: bool = False
    sop_support: bool = False
    corroboration: Literal["STRONG", "MODERATE", "PARTIAL", "UNSUPPORTED", "CONFLICTING"] = "PARTIAL"
    visual_evidence_id: Optional[str] = None
    telemetry_evidence_id: Optional[str] = None
    sop_evidence_id: Optional[str] = None
    corroborating_metrics: Dict[str, Any] = Field(default_factory=dict)
    applicable_standard: str = "ISO 10816-3"
    recommended_action: str = ""
    summary: str = ""


class CrossModalCorrelator:
    """
    Correlates physical visual evidence against time-series telemetry and operational SOPs.
    Fulfills Phase 11: Cross-Modal Correlation.
    """

    @classmethod
    def correlate(
        cls,
        visual_result: Optional[PhotographInspectionResult] = None,
        telemetry_context: Optional[Dict[str, Any]] = None,
        sop_evidence: Optional[List[Dict[str, Any]]] = None,
        equipment_tag: Optional[str] = None,
        sop_context: Optional[Any] = None,
    ) -> CrossCorrelationResult:
        """
        Executes cross-modal corroboration across visual, telemetry, and SOP domains.
        """
        tag = equipment_tag or (visual_result.equipment_tag if visual_result else "UNKNOWN")
        t = telemetry_context or {}
        
        # Support either sop_evidence or sop_context
        raw_sops = sop_evidence or sop_context or []
        if isinstance(raw_sops, dict):
            sops = [raw_sops]
        elif isinstance(raw_sops, list):
            sops = raw_sops
        else:
            sops = []

        # 1. Visual Support Analysis
        visual_support = False
        vis_ev_id = None
        defect_class = DefectClass.UNKNOWN
        finding_text = f"Assessment of {tag}"

        if visual_result and visual_result.defect_detected:
            visual_support = True
            vis_ev_id = f"ev_vis_{visual_result.inspection_id}"
            defect_class = visual_result.defect_class
            finding_text = f"{tag} {defect_class.value.replace('_', ' ').title()}"
        elif visual_result:
            visual_support = True
            vis_ev_id = f"ev_vis_{visual_result.inspection_id}"
            finding_text = f"{tag} Visual Condition Verification"

        # 2. Telemetry Support Analysis
        telemetry_support = False
        telem_ev_id = None
        corroborating_metrics = {}

        vib_rms = t.get("vibration_rms", t.get("vibration_velocity_rms", t.get("vibration_velocity_rms_mm_s", t.get("vibration"))))
        temp_c = t.get("bearing_temp_c", t.get("bearing_temperature_c", t.get("temperature_c", t.get("stator_temp_c", t.get("temp_c")))))

        # Item 6: Equipment matching and schema validation
        telem_eq = str(t.get("equipment_id", t.get("equipment_tag", ""))).strip().upper()
        norm_tag = str(tag).strip().upper()
        equipment_mismatch = bool(
            telem_eq and norm_tag and norm_tag != "UNKNOWN" and telem_eq not in norm_tag and norm_tag not in telem_eq
        )

        vib_val = None
        temp_val = None
        if vib_rms is not None:
            try:
                vib_val = float(vib_rms)
                corroborating_metrics["vibration_velocity_rms_mm_s"] = vib_val
            except (ValueError, TypeError):
                pass
        if temp_c is not None:
            try:
                temp_val = float(temp_c)
                corroborating_metrics["bearing_temperature_c"] = temp_val
            except (ValueError, TypeError):
                pass

        # Corroborate against engineering profile
        profile = EngineeringPolicyGate.resolve_profile(
            proposal=visual_result.validated_proposal if visual_result else None  # type: ignore
        ) if visual_result else POLICY_REGISTRY["P101_BEARING_PROFILE"]

        # Item 13: Expose dynamic thresholds in corroborating_metrics for frontend display
        corroborating_metrics["thresholds"] = {
            "vibration_velocity_warning_mms": profile.vibration_velocity_warning_mms,
            "vibration_velocity_critical_mms": profile.vibration_velocity_critical_mms,
            "bearing_temp_warning_c": profile.bearing_temp_warning_c,
            "bearing_temp_critical_c": profile.bearing_temp_critical_c,
        }

        vib_exceeded = vib_val is not None and vib_val >= profile.vibration_velocity_warning_mms
        temp_exceeded = temp_val is not None and temp_val >= profile.bearing_temp_warning_c

        # Telemetry only supports claim if equipment matches and threshold was actually exceeded
        if not equipment_mismatch and (vib_exceeded or temp_exceeded):
            telemetry_support = True
            # Item 5: Cryptographically bind telemetry evidence ID to actual equipment, metric values, and timestamp
            telem_payload = f"{norm_tag}:{vib_val}:{temp_val}:{t.get('timestamp', '')}:{t.get('file_id', '')}"
            telem_hash = hashlib.sha256(telem_payload.encode("utf-8")).hexdigest()[:8].upper()
            telem_ev_id = f"TELEM-{norm_tag.replace(' ', '_')}-{telem_hash}"

        # 3. SOP Support Analysis
        # Item 7: Require genuine external SOP citation with document ID/source, not self-reinforcing recommendations
        sop_support = False
        sop_ev_id = None
        sop_rec = ""

        for sop in sops:
            if not isinstance(sop, dict):
                continue
            content = (sop.get("content") or sop.get("text") or sop.get("snippet") or "").strip()
            sop_id = (sop.get("sop_id") or sop.get("evidence_id") or sop.get("file_id") or "").strip()
            doc_name = (sop.get("source_document") or sop.get("filename") or sop.get("source") or sop.get("title") or "").strip()

            c_combined = f"{content} {doc_name} {sop_id}".lower()
            sop_triggers = ["sop", "procedure", "maintenance", "section 4", "bearing replacement", "api 610", "iso 10816"]
            if (sop_id or doc_name) and any(k in c_combined for k in sop_triggers):
                sop_support = True
                sop_ev_id = sop_id or f"SOP-{hashlib.sha256(doc_name.encode('utf-8')).hexdigest()[:8].upper()}"
                sop_rec = content[:180] or doc_name
                break

        # 4. Synthesize Corroboration Strength
        if visual_support and telemetry_support and sop_support:
            corroboration = "STRONG"
            summary = (
                f"Multi-modal cross-correlation confirms {finding_text}. "
                f"Visual spalling is strongly corroborated by operating telemetry "
                f"(Vibration: {vib_rms} mm/s RMS, Temp: {temp_c} °C) exceeding {profile.governing_standard} limits, "
                f"and aligns with authorized maintenance procedure ({sop_ev_id})."
            )
        elif visual_support and telemetry_support:
            corroboration = "MODERATE"
            summary = (
                f"Visual observation and telemetry excursion strongly corroborate {finding_text}. "
                f"Vibration ({vib_rms} mm/s) confirms physical raceway degradation."
            )
        elif visual_support or telemetry_support:
            corroboration = "PARTIAL"
            summary = f"Single-channel evidence detected for {finding_text}. Awaiting independent operational cross-validation."
        else:
            corroboration = "UNSUPPORTED"
            summary = f"Insufficient visual or quantitative telemetry evidence to corroborate {finding_text}."

        recommended_action = ""
        if visual_result:
            _, _, _, rec = EngineeringPolicyGate.evaluate(
                proposal=visual_result.validated_proposal,
                telemetry_context=t,
                sop_context=sop_rec,
                profile=profile,
            )
            recommended_action = rec or visual_result.evidence_bound_recommendation or ""
        else:
            recommended_action = "Initiate mechanical inspection and vibration analysis per site standard."


        return CrossCorrelationResult(
            finding=finding_text,
            equipment_tag=tag,
            visual_support=visual_support,
            telemetry_support=telemetry_support,
            sop_support=sop_support,
            corroboration=corroboration,
            visual_evidence_id=vis_ev_id,
            telemetry_evidence_id=telem_ev_id,
            sop_evidence_id=sop_ev_id,
            corroborating_metrics=corroborating_metrics,
            applicable_standard=profile.governing_standard,
            recommended_action=recommended_action or "",
            summary=summary,
        )
