"""
Multimodal Industrial Photograph Inspection Engine & Sovereign Provider Pipeline.
INDUSAI-X / CLORA Sovereign Multimodal Intelligence Subsystem.

Enforces:
1. Model-independent RawInspectionProposal from providers.
2. SHA-256 Hash-Fixture Registry for CalibratedTestProvider (no manufactured answers).
3. Deterministic Pre-Classifier for Drawing vs. Photo discrimination.
4. Domain Validation & Engineering Policy Gate (decoupled from VLM perception).
5. Immutable 11-factor execution provenance binding.
"""

import os
import io
import json
import base64
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Literal, Union
from PIL import Image

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
    ValidatedInspectionProposal,
    EngineeringAssessment,
    VisualFinding,
    RootCauseHypothesis,
    PhotographInspectionResult,
)
from indusai.multimodal.validators import (
    BoundingBoxValidator,
    SchemaValidator,
    DomainValidator,
)
from indusai.multimodal.engineering_policy import (
    EngineeringPolicyGate,
    EngineeringPolicyProfile,
    P101_BEARING_PROFILE,
    MOTOR_PROFILE,
    PUMP_PROFILE,
    FLANGE_PROFILE,
    POLICY_REGISTRY,
)

logger = logging.getLogger("indusai.multimodal.photo_inspector")


class BasePhotoProvider(ABC):
    """Abstract interface for photograph inspection providers."""

    @abstractmethod
    def propose_inspection(
        self,
        image: Image.Image,
        metadata: Dict[str, Any],
        query: Optional[str] = None
    ) -> RawInspectionProposal:
        """Emits a candidate observation proposal from an image."""
        pass


class CalibratedTestProvider(BasePhotoProvider):
    """
    Deterministic test and offline demonstration infrastructure.
    Holds a SHA-256 fixture registry of known benchmark images.
    Strictly refuses to fabricate answers for unknown image hashes.
    """

    # SHA-256 registry of known fixture keys
    FIXTURE_REGISTRY: Dict[str, str] = {}

    def __init__(self, registered_fixtures: Optional[Dict[str, str]] = None):
        self.registry = dict(registered_fixtures or self.FIXTURE_REGISTRY)
        self._load_manifest_fixtures()

    def _load_manifest_fixtures(self) -> None:
        """Loads golden vision fixtures from manifest.json if present."""
        possible_paths = [
            os.path.join("samples", "vision_fixtures", "manifest.json"),
            os.path.join(os.path.dirname(__file__), "..", "..", "samples", "vision_fixtures", "manifest.json"),
        ]
        for p in possible_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            for entry in data:
                                h = entry.get("sha256")
                                fid = entry.get("fixture_id")
                                if h and fid:
                                    self.registry[h] = fid
                    logger.info("CalibratedTestProvider loaded %d fixtures from %s", len(self.registry), p)
                    break
                except Exception as e:
                    logger.warning("Failed loading fixtures from %s: %s", p, e)

    def register_fixture(self, sha256_hash: str, scenario_key: str) -> None:
        """Registers a known image hash to a calibrated scenario key."""
        self.registry[sha256_hash] = scenario_key

    def propose_inspection(
        self,
        image: Image.Image,
        metadata: Dict[str, Any],
        query: Optional[str] = None
    ) -> RawInspectionProposal:
        # Check explicit content hash passed from artifact manager or metadata first
        img_hash = metadata.get("content_hash")
        if not img_hash:
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            img_bytes = buf.getvalue()
            img_hash = hashlib.sha256(img_bytes).hexdigest()

        scenario = self.registry.get(img_hash)

        # Only allow fixture_scenario override if running under explicit test mode
        is_test_mode = (
            metadata.get("execution_mode") == "test"
            or metadata.get("mode") == "test"
        )
        if not scenario and is_test_mode and metadata.get("fixture_scenario"):
            scenario = metadata["fixture_scenario"]

        if not scenario:
            # Honest engineering behavior: reject unknown photos with INCONCLUSIVE proposal
            logger.info("CalibratedTestProvider: Image hash %s not in test registry.", img_hash[:12])
            return RawInspectionProposal(
                provider_id="calibrated_test_provider",
                proposed_category=PhotoCategory.UNKNOWN,
                equipment_tag_candidate=metadata.get("equipment_tag", "UNKNOWN"),
                observed_defect_class=DefectClass.UNKNOWN,
                observed_regions=[],
                raw_findings=["Unrecognized image hash in test fixture registry; no calibrated fixture match."],
                proposed_hypothesis=None,
                hypothesis_confidence=0.0,
                confidence_vector=VisualConfidenceVector(
                    visual_confidence=0.1,
                    classification_confidence=0.1,
                    image_quality_score=0.5,
                )
            )

        # 1. Tier B Killer Scenario: P-101 Bearing Fatigue Spalling
        if scenario == "P101_BEARING_SPALLING":
            return RawInspectionProposal(
                provider_id="calibrated_test_provider",
                proposed_category=PhotoCategory.DEFECT_INSPECTION,
                equipment_tag_candidate="Pump P-101 (Inboard Bearing)",
                observed_defect_class=DefectClass.BEARING_FATIGUE_SPALLING,
                observed_regions=[
                    NormalizedRegion(
                        ymin=0.28, xmin=0.34, ymax=0.68, xmax=0.72,
                        label="Raceway Spalling & Surface Flaking",
                        confidence=0.92
                    )
                ],
                raw_findings=[
                    "Inner ring raceway exhibits progressive surface spalling and localized metallic flaking.",
                    "Discoloration bands around roller contact track indicate severe frictional heating.",
                    "Roller elements show micro-pitting consistent with lubricant starvation under high rotational load."
                ],
                proposed_hypothesis="Subsurface shear fatigue initiated micro-cracking, accelerated by lubricant breakdown.",
                hypothesis_confidence=0.74,
                confidence_vector=VisualConfidenceVector(
                    visual_confidence=0.92,
                    classification_confidence=0.88,
                    localization_confidence=0.89,
                    ocr_confidence=0.0,
                    extraction_confidence=0.85,
                    image_quality_score=0.94,
                )
            )

        # 2. Tier A Strongest Scenario: Sulzer BB2 Pump Nameplate OCR
        elif scenario == "SULZER_PUMP_NAMEPLATE":
            return RawInspectionProposal(
                provider_id="calibrated_test_provider",
                proposed_category=PhotoCategory.NAMEPLATE_OCR,
                equipment_tag_candidate="Pump P-101",
                observed_defect_class=DefectClass.CLEAN_NORMAL,
                observed_regions=[
                    NormalizedRegion(
                        ymin=0.15, xmin=0.12, ymax=0.88, xmax=0.88,
                        label="Sulzer API 610 Rating Plate",
                        confidence=0.98
                    )
                ],
                raw_findings=[
                    "Manufacturer: Sulzer Pumps Ltd. / API 610 Type BB2.",
                    "Legible stamped rating plate with operational performance design limits."
                ],
                raw_ocr_text=(
                    "SULZER PUMPS - API 610 11TH ED\n"
                    "MODEL: OH2-100-250 | S/N: SZ-2024-8841\n"
                    "RATED POWER: 315 kW | SPEED: 1480 RPM\n"
                    "DESIGN FLOW: 240 m3/h | MAX OP PRESS: 25.0 BAR\n"
                    "VOLTAGE: 415 V | PHASE: 3 | 50 HZ"
                ),
                nameplate_proposal={
                    "manufacturer": {"value": "Sulzer Pumps Ltd", "unit": None, "confidence": 0.99, "status": "FOUND", "region": [0.18, 0.15, 0.26, 0.70]},
                    "model_number": {"value": "OH2-100-250", "unit": None, "confidence": 0.98, "status": "FOUND", "region": [0.30, 0.15, 0.38, 0.55]},
                    "serial_number": {"value": "SZ-2024-8841", "unit": None, "confidence": 0.99, "status": "FOUND", "region": [0.30, 0.56, 0.38, 0.85]},
                    "rated_power_kw": {"value": 315.0, "unit": "kW", "confidence": 0.98, "status": "FOUND", "region": [0.42, 0.15, 0.50, 0.50]},
                    "rated_speed_rpm": {"value": 1480, "unit": "RPM", "confidence": 0.97, "status": "FOUND", "region": [0.42, 0.52, 0.50, 0.85]},
                    "design_flow_m3h": {"value": 240.0, "unit": "m³/h", "confidence": 0.96, "status": "FOUND", "region": [0.54, 0.15, 0.62, 0.50]},
                    "max_pressure_bar": {"value": 25.0, "unit": "bar", "confidence": 0.97, "status": "FOUND", "region": [0.54, 0.52, 0.62, 0.85]},
                    "voltage_v": {"value": 415.0, "unit": "V", "confidence": 0.98, "status": "FOUND", "region": [0.66, 0.15, 0.74, 0.45]},
                },
                proposed_hypothesis=None,
                hypothesis_confidence=0.0,
                confidence_vector=VisualConfidenceVector(
                    visual_confidence=0.98,
                    classification_confidence=0.95,
                    localization_confidence=0.97,
                    ocr_confidence=0.98,
                    extraction_confidence=0.97,
                    image_quality_score=0.96,
                )
            )

        # 3. Tier C Scenario: Cooling Line Flange Pitting Corrosion
        elif scenario == "FLANGE_PITTING_CORROSION":
            return RawInspectionProposal(
                provider_id="calibrated_test_provider",
                proposed_category=PhotoCategory.DEFECT_INSPECTION,
                equipment_tag_candidate="Lube Oil Cooler E-101 / Flange FL-104",
                observed_defect_class=DefectClass.PITTING_CORROSION,
                observed_regions=[
                    NormalizedRegion(
                        ymin=0.35, xmin=0.25, ymax=0.75, xmax=0.65,
                        label="Flange Neck Pitting Corrosion & Scale",
                        confidence=0.88
                    )
                ],
                raw_findings=[
                    "Localized pitting attack on the 4-inch ANSI 300# Carbon Steel flange neck.",
                    "Crevice corrosion and ferric oxide scale concentrated around lower bolt circle.",
                    "Gasket seating face appears partially compromised."
                ],
                proposed_hypothesis="Atmospheric moisture ingress and condensation under compromised thermal insulation.",
                hypothesis_confidence=0.68,
                confidence_vector=VisualConfidenceVector(
                    visual_confidence=0.88,
                    classification_confidence=0.86,
                    localization_confidence=0.84,
                    ocr_confidence=0.0,
                    extraction_confidence=0.80,
                    image_quality_score=0.90,
                )
            )

        # 4. Tier D Scenario: Motor Stator Thermal Scorch
        elif scenario == "MOTOR_STATOR_SCORCH":
            return RawInspectionProposal(
                provider_id="calibrated_test_provider",
                proposed_category=PhotoCategory.DEFECT_INSPECTION,
                equipment_tag_candidate="Motor M-101 (Drive End Winding)",
                observed_defect_class=DefectClass.THERMAL_DISCOLORATION,
                observed_regions=[
                    NormalizedRegion(
                        ymin=0.20, xmin=0.30, ymax=0.70, xmax=0.80,
                        label="Thermal Varnish Carbonization",
                        confidence=0.85
                    )
                ],
                raw_findings=[
                    "Stator winding phase insulation shows heavy dark discoloration and varnish carbonization.",
                    "Localized thermal hot spot visible on slot phase coil edges."
                ],
                proposed_hypothesis="Prolonged operational electrical overload or persistent cooling fan blockage.",
                hypothesis_confidence=0.65,
                confidence_vector=VisualConfidenceVector(
                    visual_confidence=0.85,
                    classification_confidence=0.82,
                    localization_confidence=0.80,
                    ocr_confidence=0.0,
                    extraction_confidence=0.75,
                    image_quality_score=0.88,
                )
            )

        # Fallback unknown
        return RawInspectionProposal(
            provider_id="calibrated_test_provider",
            proposed_category=PhotoCategory.DEFECT_INSPECTION,
            equipment_tag_candidate=metadata.get("equipment_tag", "UNKNOWN"),
            observed_defect_class=DefectClass.UNKNOWN,
            raw_findings=[f"Analyzed test photo fixture for query: '{query}'"],
            confidence_vector=VisualConfidenceVector(visual_confidence=0.5, image_quality_score=0.8)
        )


class OllamaPhotoProvider(BasePhotoProvider):
    """
    Local-first sovereign VLM provider using local Ollama daemon (Qwen2-VL, Qwen2.5, or Llama-3.2-Vision).
    Zero internet access required. Requests strictly observations and raw text.
    Resilient to markdown fences, malformed JSON, NaN/Inf, and missing keys.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model_name: Optional[str] = None
    ):
        self.base_url = base_url.rstrip("/")
        env_model = os.environ.get("CLORA_VISION_MODEL")
        self.model_name = model_name or env_model or "qwen3.5:latest"
        self._is_available: Optional[bool] = None

    def check_alive(self) -> bool:
        if self._is_available is not None:
            return self._is_available
        try:
            import httpx
            with httpx.Client(timeout=0.8) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    tags = resp.json().get("models", [])
                    available_names = [m.get("name") for m in tags if isinstance(m, dict)]
                    # Item 12: Strictly check for verified vision-capable architectures
                    KNOWN_VISION_MODELS = ["llava", "bakllava", "llama-3.2-vision", "qwen2-vl", "moondream", "minicpm-v", "cogvlm"]
                    if self.model_name not in available_names and available_names:
                        vision_candidates = [
                            n for n in available_names
                            if any(vm in n.lower() for vm in KNOWN_VISION_MODELS) or "vision" in n.lower()
                        ]
                        if vision_candidates:
                            self.model_name = vision_candidates[0]
                            self._is_available = True
                        else:
                            # Do not silently substitute a pure text LLM as a vision model
                            logger.warning("No vision-capable VLM installed in local Ollama daemon (available: %s)", available_names)
                            self._is_available = False
                            return False
                    else:
                        self._is_available = (self.model_name in available_names) if available_names else False
                else:
                    self._is_available = False
        except Exception:
            self._is_available = False
        return self._is_available

    def propose_inspection(
        self,
        image: Image.Image,
        metadata: Dict[str, Any],
        query: Optional[str] = None
    ) -> RawInspectionProposal:
        if not self.check_alive():
            raise RuntimeError(f"Local Ollama VLM daemon at {self.base_url} is unreachable.")

        import httpx
        import re

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        b64_img = base64.b64encode(buffer.getvalue()).decode("utf-8")

        prompt = (
            "You are an industrial forensic inspection assistant. Analyze this photograph.\n"
            "Return strictly valid JSON with no markdown wrapping and keys:\n"
            "{\n"
            "  \"category\": \"DEFECT_INSPECTION\" | \"NAMEPLATE_OCR\" | \"EQUIPMENT_SURVEY\",\n"
            "  \"equipment_tag\": string or null,\n"
            "  \"defect_class\": \"BEARING_FATIGUE_SPALLING\" | \"PITTING_CORROSION\" | \"FLANGE_LEAKAGE\" | \"THERMAL_DISCOLORATION\" | \"CLEAN_NORMAL\" | \"UNKNOWN\",\n"
            "  \"observations\": [string],\n"
            "  \"hypothesis\": string or null,\n"
            "  \"nameplate\": {\n"
            "     \"model\": string, \"serial\": string, \"power_kw\": float, \"speed_rpm\": float, \"pressure_bar\": float\n"
            "  },\n"
            "  \"bbox\": [ymin, xmin, ymax, xmax] (normalized 0.0 to 1.0) or null\n"
            "}"
        )

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "images": [b64_img],
                        "stream": False
                    }
                )
                if resp.status_code != 200:
                    raise RuntimeError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")

                out_text = resp.json().get("response", "").strip()

                # Clean possible markdown fence
                if "```" in out_text:
                    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", out_text)
                    if match:
                        out_text = match.group(1).strip()
                    else:
                        out_text = out_text.replace("```json", "").replace("```", "").strip()

                try:
                    parsed = json.loads(out_text)
                except Exception:
                    brace_match = re.search(r"\{[\s\S]*\}", out_text)
                    if brace_match:
                        parsed = json.loads(brace_match.group(0))
                    else:
                        raise ValueError(f"Unparseable response text: {out_text[:120]}")

                # Use SchemaValidator to validate and construct RawInspectionProposal
                return SchemaValidator.sanitize_raw_proposal(
                    raw_dict=parsed,
                    provider_id=f"ollama_{self.model_name}",
                    default_equipment_tag=metadata.get("equipment_tag")
                )

        except Exception as exc:
            logger.warning("Ollama provider error (%s). Emitting inconclusive proposal.", exc)
            return RawInspectionProposal(
                provider_id=f"ollama_{self.model_name}",
                proposed_category=PhotoCategory.UNKNOWN,
                equipment_tag_candidate=metadata.get("equipment_tag", "UNKNOWN"),
                observed_defect_class=DefectClass.UNKNOWN,
                observed_regions=[],
                raw_findings=[f"VLM inspection inconclusive: {exc}"],
                proposed_hypothesis=None,
                confidence_vector=VisualConfidenceVector(
                    visual_confidence=0.1,
                    classification_confidence=0.1,
                    image_quality_score=0.5,
                )
            )


class DeterministicPreClassifier:
    """
    Lightweight, deterministic pre-classifier that inspects image metadata,
    aspect ratio, file format, and color entropy to discriminate between
    engineering CAD drawings/schematics and physical field photographs
    WITHOUT circular dependencies on large VLMs.
    """

    @staticmethod
    def classify_visual_mode(
        image: Image.Image,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Literal["DRAWING_SCHEMATIC", "PHYSICAL_PHOTOGRAPH"]:
        meta = metadata or {}
        filename = (meta.get("filename") or "").lower()
        file_type = (meta.get("file_type") or "").lower()

        # 1. Obvious filename/type indicators
        if any(w in filename for w in ["pid", "p&id", "dwg", "cad", "schematic", "drawing", "circuit"]):
            return "DRAWING_SCHEMATIC"
        if any(w in filename for w in ["photo", "pic", "camera", "damage", "wear", "nameplate", "spalling", "corrosion"]):
            return "PHYSICAL_PHOTOGRAPH"

        # 2. Image heuristic inspection (Vector/drawing vs Natural photo)
        w, h = image.size
        aspect = w / max(1, h)

        # Sample colors if RGB
        if image.mode in ("RGB", "RGBA"):
            small = image.resize((64, 64)).convert("L")
            pixels = list(small.tobytes())
            near_white_count = sum(1 for p in pixels if p > 240)
            white_ratio = near_white_count / len(pixels)
            if white_ratio > 0.70 and aspect > 1.3:
                return "DRAWING_SCHEMATIC"

        return "PHYSICAL_PHOTOGRAPH"


class PhotographInspectionEngine:
    """
    Authoritative Orchestrator for Sovereign Multimodal Photograph Inspection.
    Binds the entire lifecycle:
    Image Artifact -> Pre-classifier -> Provider Proposal -> BBox Validation ->
    Provenance Binding -> Domain Validation -> Engineering Policy Gate -> Evidence Conversion.
    """

    def __init__(
        self,
        production_provider: Optional[BasePhotoProvider] = None,
        test_provider: Optional[CalibratedTestProvider] = None,
        force_mode: Optional[Literal["production", "test"]] = None,
    ):
        self.production_provider = production_provider or OllamaPhotoProvider()
        self.test_provider = test_provider or CalibratedTestProvider()
        self.force_mode = force_mode
        self.policy_gate = EngineeringPolicyGate()
        self.pre_classifier = DeterministicPreClassifier()

    def inspect_photograph(
        self,
        image_input: Union[str, bytes, Image.Image],
        artifact_id: str = "img_photo_01",
        metadata: Optional[Dict[str, Any]] = None,
        query: Optional[str] = None,
        telemetry_context: Optional[Dict[str, Any]] = None,
    ) -> PhotographInspectionResult:
        meta = metadata or {}

        # 1. Load image
        if isinstance(image_input, str):
            if os.path.exists(image_input):
                with open(image_input, "rb") as f:
                    raw_bytes = f.read()
                image = Image.open(io.BytesIO(raw_bytes))
            else:
                raise FileNotFoundError(f"Image path not found: {image_input}")
        elif isinstance(image_input, bytes):
            raw_bytes = image_input
            image = Image.open(io.BytesIO(raw_bytes))
        elif isinstance(image_input, Image.Image):
            image = image_input
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            raw_bytes = buf.getvalue()
        else:
            raise ValueError("Unsupported image input type")

        w, h = image.size
        content_hash = hashlib.sha256(raw_bytes).hexdigest()
        inspection_id = f"INSP-{content_hash[:8].upper()}"

        # 2. Compute 11-Factor Immutable Provenance
        norm_img = image.convert("RGB")
        p_buf = io.BytesIO()
        norm_img.save(p_buf, format="PNG")
        prep_hash = hashlib.sha256(p_buf.getvalue()).hexdigest()

        # 3. Cryptographic Deterministic Provider Selection (Phase 2)
        # Check if hash is in fixture registry
        is_known_fixture = (content_hash in self.test_provider.registry)
        is_test_mode = (
            self.force_mode in ("test", "demo")
            or meta.get("mode") in ("test", "demo")
            or meta.get("execution_mode") in ("test", "demo")
        )

        # Include content_hash in metadata passed to provider
        merged_meta = dict(meta)
        merged_meta["content_hash"] = content_hash

        # Item 3: In production, NEVER silently switch to test provider based on hash.
        # Production mode ALWAYS evaluates via production provider (Local Ollama VLM).
        # Calibrated test provider is strictly restricted to explicit controlled test / demo modes.
        if is_test_mode and is_known_fixture:
            provider = self.test_provider
        elif is_test_mode:
            provider = self.test_provider
        else:
            # Production execution mode -> Always production provider (Local Ollama VLM)
            provider = self.production_provider

        try:
            raw_proposal = provider.propose_inspection(norm_img, merged_meta, query=query)
        except Exception as prov_err:
            logger.warning("Provider failed (%s)", prov_err)
            if is_test_mode:
                raw_proposal = self.test_provider.propose_inspection(norm_img, merged_meta, query=query)
            else:
                # In production: Never fabricate when real VLM is unavailable. Emit INCONCLUSIVE proposal.
                raw_proposal = RawInspectionProposal(
                    provider_id="inconclusive_fallback",
                    proposed_category=PhotoCategory.UNKNOWN,
                    equipment_tag_candidate=meta.get("equipment_tag", "UNKNOWN"),
                    observed_defect_class=DefectClass.UNKNOWN,
                    observed_regions=[],
                    raw_findings=[f"Inspection inconclusive: Sovereign local VLM offline or encountered error ({prov_err})."],
                    confidence_vector=VisualConfidenceVector(
                        visual_confidence=0.0,
                        classification_confidence=0.0,
                        image_quality_score=0.5,
                    )
                )

        # 4. Schema & BoundingBox Validation (Phase 4)
        valid_regions = BoundingBoxValidator.filter_and_build_regions(raw_proposal.observed_regions)

        # 5. Deterministic Domain Validation (Phase 5)
        domain_val = DomainValidator.validate_proposal(raw_proposal)

        # Nameplate reconstruction if present
        nameplate_obj = None
        if raw_proposal.nameplate_proposal:
            np = raw_proposal.nameplate_proposal
            parsed_fields = {}
            for k, v in np.items():
                if isinstance(v, dict):
                    reg = None
                    if v.get("region") and len(v["region"]) == 4:
                        try:
                            reg = NormalizedRegion(ymin=v["region"][0], xmin=v["region"][1], ymax=v["region"][2], xmax=v["region"][3])
                        except Exception:
                            reg = None
                    f_status = FieldStatus.__members__.get(str(v.get("status", "FOUND")).upper(), FieldStatus.FOUND)
                    parsed_fields[k] = NameplateField(
                        field_name=k,
                        value=v.get("value"),
                        unit=v.get("unit"),
                        confidence=float(v.get("confidence", 0.9)),
                        source_region=reg,
                        status=f_status
                    )
            nameplate_obj = NameplateData(
                manufacturer=parsed_fields.get("manufacturer"),
                model_number=parsed_fields.get("model_number"),
                serial_number=parsed_fields.get("serial_number"),
                rated_power_kw=parsed_fields.get("rated_power_kw"),
                rated_speed_rpm=parsed_fields.get("rated_speed_rpm"),
                design_flow_m3h=parsed_fields.get("design_flow_m3h"),
                max_pressure_bar=parsed_fields.get("max_pressure_bar"),
                voltage_v=parsed_fields.get("voltage_v"),
                raw_fields=parsed_fields
            )

        # 6. Engineering Policy Gate (Phase 6)
        severity, req_imm, req_review, rec = self.policy_gate.evaluate(
            proposal=raw_proposal,
            telemetry_context=telemetry_context,
        )

        # 7. Uncertainty & Evidence Trust Gating (Phase 7)
        conf = raw_proposal.confidence_vector
        if conf.image_quality_score < 0.40 or conf.classification_confidence < 0.40 or raw_proposal.proposed_category == PhotoCategory.UNKNOWN:
            insp_status = InspectionStatus.INCONCLUSIVE
            ev_status = EvidenceStatus.UNVERIFIED
            req_review = True
        elif conf.classification_confidence >= 0.80 and domain_val.status == "VALID":
            insp_status = InspectionStatus.VERIFIED
            # Item 8: Presence != Corroboration.
            # Independent validation requires matching equipment and actual numeric threshold excursion.
            telemetry_corroborated = False
            if telemetry_context and isinstance(telemetry_context, dict):
                t_eq = str(telemetry_context.get("equipment_id", telemetry_context.get("equipment_tag", ""))).strip().upper()
                p_eq = str(raw_proposal.equipment_tag_candidate or "").strip().upper()
                same_eq = (not t_eq or not p_eq) or (t_eq in p_eq or p_eq in t_eq)

                vib = telemetry_context.get("vibration_velocity_rms_mm_s") or telemetry_context.get("vibration_velocity_rms") or telemetry_context.get("vibration_rms")
                temp = telemetry_context.get("bearing_temperature_c") or telemetry_context.get("bearing_temp_c") or telemetry_context.get("temperature_c")
                has_excursion = (vib is not None and float(vib) >= 4.5) or (temp is not None and float(temp) >= 80.0)

                if same_eq and has_excursion:
                    telemetry_corroborated = True

            ev_status = EvidenceStatus.CORROBORATED if telemetry_corroborated else EvidenceStatus.VERIFIED
        else:
            insp_status = InspectionStatus.REQUIRES_REVIEW
            ev_status = EvidenceStatus.REQUIRES_REVIEW

        # 8. Build Categorized Visual Findings
        findings = []
        for i, text in enumerate(raw_proposal.raw_findings):
            r = valid_regions[i] if i < len(valid_regions) else None
            findings.append(
                VisualFinding(
                    finding_id=f"f_{inspection_id}_{i+1}",
                    semantic_type=SemanticType.OBSERVATION,
                    description=text,
                    confidence=conf.visual_confidence,
                    region=r
                )
            )

        root_hypo = None
        if raw_proposal.proposed_hypothesis:
            root_hypo = RootCauseHypothesis(
                hypothesis=raw_proposal.proposed_hypothesis,
                confidence=raw_proposal.hypothesis_confidence,
                semantic_type=SemanticType.HYPOTHESIS,
                status="HYPOTHESIS"
            )

        # Immutable Provenance
        provenance = VisualProvenance(
            artifact_id=artifact_id,
            artifact_version="1.0.0",
            content_hash=content_hash,
            image_dimensions={"width": w, "height": h},
            mime_type=meta.get("mime_type", "image/png"),
            preprocessing_hash=prep_hash,
            model_id=raw_proposal.provider_id,
            model_version="1.0",
            prompt_version="v1.0_forensics",
            inspection_id=inspection_id,
            execution_id=f"exec_{inspection_id}"
        )

        eq_tag = raw_proposal.equipment_tag_candidate or meta.get("equipment_tag", "UNKNOWN")

        # Type Hierarchy Level 2: Validated Proposal
        val_proposal = ValidatedInspectionProposal(
            provider_id=raw_proposal.provider_id,
            photo_category=raw_proposal.proposed_category,
            equipment_tag=eq_tag,
            observed_defect_class=raw_proposal.observed_defect_class,
            valid_regions=valid_regions,
            findings=findings,
            nameplate_data=nameplate_obj,
            candidate_hypothesis=root_hypo,
            confidence_vector=conf,
        )

        # Type Hierarchy Level 3: Engineering Assessment
        eng_assessment = EngineeringAssessment(
            severity=severity,
            requires_immediate_action=req_imm,
            requires_human_review=req_review,
            inspection_status=insp_status,
            evidence_status=ev_status,
            evidence_bound_recommendation=rec,
            domain_validation=domain_val,
        )

        # Type Hierarchy Level 4: Authoritative Inspection Contract
        return PhotographInspectionResult(
            inspection_id=inspection_id,
            photo_category=raw_proposal.proposed_category,
            equipment_tag=eq_tag,
            defect_detected=(raw_proposal.observed_defect_class not in (DefectClass.CLEAN_NORMAL, DefectClass.UNKNOWN)),
            defect_class=raw_proposal.observed_defect_class,
            severity=severity,
            requires_immediate_action=req_imm,
            requires_human_review=req_review,
            inspection_status=insp_status,
            evidence_status=ev_status,
            confidence_vector=conf,
            domain_validation=domain_val,
            provenance=provenance,
            bounding_regions=valid_regions,
            findings=findings,
            nameplate_data=nameplate_obj,
            root_cause_hypothesis=root_hypo,
            evidence_bound_recommendation=rec,
            summary=(
                f"Visual analysis of {eq_tag} ({raw_proposal.proposed_category.value}): "
                f"Defect {raw_proposal.observed_defect_class.value} evaluated at {severity.value} severity."
            ),
            validated_proposal=val_proposal,
            engineering_assessment=eng_assessment,
        )
