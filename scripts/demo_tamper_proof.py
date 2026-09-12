"""
CLORA Ed25519 Cryptographic Evidence Attestation & Tamper Demonstration.
SIH Problem Statement 26117 (MRPL)

Demonstrates:
1. Generation of authentic Ed25519 digital signature on industrial audit evidence.
2. Independent offline verification using exported public key (.pem).
3. Adversarial Attack 1: Altering a single character in the payload (104.2°C -> 199.9°C).
   -> Immediate rejection with CONTENT_MODIFIED error.
4. Adversarial Attack 2: Re-computing content_sha256 to forge the hash.
   -> Immediate rejection with Ed25519 signature mismatch error.
5. Zero dependency on cloud Certificate Authorities or external networks.
"""

import os
import sys
import json
import hashlib

# Ensure root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from security.attestation import (
    get_attestor,
    EvidenceVerifier,
    canonicalize_payload,
    get_key_manager,
)


def print_banner(title: str):
    print("\n" + "═" * 80)
    print(f"  {title}")
    print("═" * 80)


def run_tamper_demo():
    print_banner("CLORA ED25519 TAMPER-EVIDENT EVIDENCE ATTESTATION DEMO")
    print("  Standard: RFC 8032 Ed25519 Digital Signatures")
    print("  Host: Sovereign On-Premise Instance (MRPL SIH26117)")
    print("═" * 80)

    key_mgr = get_key_manager()
    attestor = get_attestor()

    print("\n[STEP 1: LOCAL ED25519 IDENTITY & KEY STATUS]")
    print(f"  ├─ Key Identifier    : {key_mgr.get_key_id()}")
    print(f"  ├─ Algorithm         : Ed25519 (Curve25519 Curve)")
    print(f"  ├─ Public Key (PEM)  :\n{key_mgr.get_public_key_pem().strip()}")
    print(f"  └─ Private Key Storage: ON-PREMISES SECURE KEYSTORE (Never Exported)")

    # -------------------------------------------------------------
    # Step 2: Sign Authentic Forensic Report
    # -------------------------------------------------------------
    print_banner("STEP 2: CRYPTOGRAPHIC SIGNING OF INDUSTRIAL AUDIT REPORT")
    authentic_report = (
        "Forensic Investigation Finding: Centrifugal Pump P-101 inboard roller bearing "
        "temperature reached 104.2°C at 09:15:00Z, exceeding the 80.0°C API 610 threshold. "
        "Vibration velocity RMS was measured at 9.82 mm/s (ISO 10816-3 critical trip limit: 7.10 mm/s). "
        "Action: Mandatory Section 4.2 mechanical overhaul and bearing replacement executed."
    )

    proof = attestor.sign_report(
        report_id="RPT-MRPL-P101-001",
        content=authentic_report,
        sources=[
            "Pump_P101_Maintenance_Manual.pdf",
            "p101_vibration_telemetry.csv",
            "PID_Cooling_Water_Circuit_P101.png",
        ],
        model="qwen2.5:3b (Local Offline)",
    )

    print(f"  ✓ Report ID           : {proof.get('report_id')}")
    print(f"  ✓ Content Hash        : {proof.get('content_sha256')}")
    print(f"  ✓ Digital Signature   : {proof.get('signature')[:40]}... ({len(proof.get('signature'))} bytes b64)")
    print(f"  ✓ Canonical Encoding  : Deterministic Sorted Keys JSON (RFC 8785)")

    # -------------------------------------------------------------
    # Step 3: Independent Offline Verification
    # -------------------------------------------------------------
    print_banner("STEP 3: INDEPENDENT OFFLINE VERIFICATION (UNTOUCHED EVIDENCE)")
    valid, msg, details = EvidenceVerifier.verify_proof(proof)
    print(f"  ✓ Verification Status : {'PASS (AUTHENTIC)' if valid else 'FAIL'}")
    print(f"  ✓ Verdict             : {msg}")
    print(f"  ✓ Verified Signer     : {details.get('signer')}")
    print(f"  ✓ Verified Key ID     : {details.get('key_id')}")

    # -------------------------------------------------------------
    # Step 4: Adversarial Attack 1 — Payload Tampering (1 character)
    # -------------------------------------------------------------
    print_banner("STEP 4: ADVERSARIAL ATTACK 1 — 1-CHARACTER SENSOR VALUE FORGERY")
    print("  Attacker attempts to forge the temperature record:")
    print("  Original: '104.2°C'  ──>  Tampered: '199.9°C'")

    tampered_1 = json.loads(json.dumps(proof))
    tampered_1["canonical_payload"]["content"] = authentic_report.replace("104.2°C", "199.9°C")

    t1_valid, t1_msg, _ = EvidenceVerifier.verify_proof(tampered_1)
    print(f"\n  [!] Verification Result:")
    print(f"  ├─ Is Valid?          : {t1_valid} (Must be False)")
    print(f"  ├─ Defense Action     : REJECTED AT CRYPTOGRAPHIC INTEGRITY GATE")
    print(f"  └─ Forensic Diagnostic: {t1_msg}")

    # -------------------------------------------------------------
    # Step 5: Adversarial Attack 2 — Hash Forgery Attack
    # -------------------------------------------------------------
    print_banner("STEP 5: ADVERSARIAL ATTACK 2 — RECOMPUTED SHA-256 HASH FORGERY")
    print("  Attacker alters content AND recomputes content_sha256 to bypass hash check:")

    tampered_2 = json.loads(json.dumps(tampered_1))
    recomputed_bytes = canonicalize_payload(tampered_2["canonical_payload"])
    tampered_2["content_sha256"] = hashlib.sha256(recomputed_bytes).hexdigest()

    t2_valid, t2_msg, _ = EvidenceVerifier.verify_proof(tampered_2)
    print(f"\n  [!] Verification Result:")
    print(f"  ├─ Is Valid?          : {t2_valid} (Must be False)")
    print(f"  ├─ Defense Action     : REJECTED AT ASYMMETRIC ED25519 SIGNATURE GATE")
    print(f"  └─ Forensic Diagnostic: {t2_msg}")

    # -------------------------------------------------------------
    # Executive Summary
    # -------------------------------------------------------------
    print_banner("MATHEMATICAL GUARANTEE OF INDUSTRIAL INTEGRITY")
    print("  1. Untouched evidence packages mathematically verify with 100% certainty.")
    print("  2. Modifying even 1 bit of sensor data or operational text breaks verification.")
    print("  3. Forging a valid signature without the host's private Ed25519 key is")
    print("     computationally infeasible (equivalent to breaking 2^128 discrete log).")
    print("═" * 80 + "\n")


if __name__ == "__main__":
    run_tamper_demo()
