from typing import Dict, Any, List, Optional
from datetime import datetime
from mcp.server.fastmcp import FastMCP

# Create MCP server
mcp = FastMCP("AddressChangeMCP")

# In-memory "database"
cases: Dict[str, Dict[str, Any]] = {}

# -----------------
# Helper / mock data
# -----------------
DEMO_PAYLOAD = {
    "citizen_name": "John Doe",
    "citizen_dob": "1998-04-12",
    "old_address": "Altstrasse 5, 67655 Kaiserslautern",
    "new_address_raw": "Musterstr 12a KL 12345",
    "move_in_date_raw": "2025-10-01",
    "landlord_doc_path": "/tmp/landlord_confirmation.pdf",
    "id_doc_path": "/tmp/passport_scan.pdf",
}

def _audit(case_id: str, event: str, details: Any):
    cases[case_id]["audit"].append(
        {"ts": datetime.utcnow().isoformat(), "event": event, "details": details}
    )

# -----------------
# Tools (workflow)
# -----------------

@mcp.tool()
def ingest_case(data: Dict[str, Any] = DEMO_PAYLOAD) -> Dict[str, Any]:
    """Start new address-change case."""
    case_id = f"CASE-{len(cases)+1:04d}"
    cases[case_id] = {
        "data": data,
        "ocr": None,
        "status": "created",
        "audit": [],
        "overrides":{}, #overrides for HITL inputs
        "working":{},  #current working data (with overrides applied)
    }
    _audit(case_id, "ingest_case", "Case created with citizen data.")
    return {"case_id": case_id, "message": "Case created."}


@mcp.tool()
def run_ocr_extract(case_id: str) -> Dict[str, Any]:
    """Simulate OCR extraction."""
    case = cases[case_id]
    extracted = {
        "citizen_name": case["data"]["citizen_name"],
        "citizen_dob": case["data"]["citizen_dob"],
        "old_address": case["data"]["old_address"],
        "new_address": case["data"]["new_address_raw"],
        "move_in_date": case["data"]["move_in_date_raw"],
        "landlord_signature_found": True,
    }
    confidence = {"new_address": 0.73, "move_in_date": 0.9}
    case["ocr"] = {"fields": extracted, "confidence": confidence}
    case["working"] = {
        "new_address": extracted["new_address"],
        "move_in_date": extracted["move_in_date"],
    }

    _audit(case_id, "run_ocr_extract", {"low_conf": ["new_address"]})

    return {"extracted_fields": extracted, "confidence": confidence}


@mcp.tool()
def check_completeness(case_id: str) -> Dict[str, Any]:
    """Check for missing or low-confidence fields."""
    ocr = cases[case_id]["ocr"]
    low_conf = [k for k,v in ocr["confidence"].items() if v < 0.8]
    status = "hitl_required" if low_conf else "ok"
    _audit(case_id, "check_completeness", {"status": status, "low_conf": low_conf})
    return {"status": status, "low_conf_fields": low_conf}

@mcp.tool()
def resolve_hitl_update_address(case_id: str, corrected_address: str) -> Dict[str, Any]:
    """
    Human-in-the-Loop: officer provides corrected/verified new address.
    This updates the working address for the case so the workflow can continue.
    """
    case = cases[case_id]

    old_addr = case["working"]["new_address"]
    case["working"]["new_address"] = corrected_address
    case["overrides"]["new_address"] = corrected_address

    _audit(
        case_id,
        "resolve_hitl_update_address",
        {
            "old_address": old_addr,
            "corrected_address": corrected_address,
            "source": "human_officer"
        }
    )

    return {
        "message": "Address override applied",
        "case_id": case_id,
        "old_address": old_addr,
        "new_address": corrected_address,
        "next_step_hint": "You can now continue with match_registry_identity, etc."
    }



@mcp.tool()
def match_registry_identity(case_id: str) -> Dict[str, Any]:
    """Simulate identity match with registry."""
    score = 0.94
    status = "match" if score > 0.9 else "mismatch"
    _audit(case_id, "match_registry_identity", {"score": score, "status": status})
    return {"status": status, "score": score, "hitl_required": status != "match"}


@mcp.tool()
def validate_landlord_confirmation(case_id: str) -> Dict[str, Any]:
    """Check landlord confirmation validity."""
    valid = True
    status = "valid" if valid else "invalid"
    _audit(case_id, "validate_landlord_confirmation", {"status": status})
    return {"status": status, "hitl_required": not valid}


@mcp.tool()
def canonicalize_address(case_id: str) -> Dict[str, Any]:
    input_addr = cases[case_id]["working"]["new_address"]
    """Normalize address via API (simulated)."""
    canonical = {
        "input": input_addr,
        "street": "Musterstraße",
        "house_number": "12A",
        "postal_code": "12345",
        "city": "Kaiserslautern",
    }
    ambiguous = False
    status = "ok" if not ambiguous else "ambiguous"
    _audit(case_id, "canonicalize_address", {"status": status})
    return {"status": status, "canonical_address": canonical, "hitl_required": ambiguous}


@mcp.tool()
def check_business_rules(case_id: str) -> Dict[str, Any]:
    """Run policy validation."""
    violations: List[str] = []
    status = "pass" if not violations else "fail"
    _audit(case_id, "check_business_rules", {"status": status})
    return {"status": status, "violations": violations, "hitl_required": bool(violations)}


@mcp.tool()
def update_registry(case_id: str) -> Dict[str, Any]:
    """Update registry record (simulated)."""
    conflict = False
    status = "updated" if not conflict else "conflict"
    _audit(case_id, "update_registry", {"status": status})
    return {"status": status, "hitl_required": conflict}


@mcp.tool()
def generate_certificate(case_id: str) -> Dict[str, Any]:
    """Generate Meldebescheinigung PDF (mock)."""
    path = f"/tmp/{case_id}_meldebescheinigung.pdf"
    _audit(case_id, "generate_certificate", {"path": path})
    return {"status": "generated", "certificate_path": path}


@mcp.tool()
def notify_citizen(case_id: str) -> Dict[str, Any]:
    """Send email notification (simulated)."""
    _audit(case_id, "notify_citizen", {"sent_to": "citizen@example.com"})
    return {"status": "sent", "email": "citizen@example.com"}


@mcp.tool()
def close_case_and_audit(case_id: str) -> Dict[str, Any]:
    """Finalize and return audit log."""
    audit = cases[case_id]["audit"]
    _audit(case_id, "close_case_and_audit", "Case closed.")
    return {"status": "closed", "audit_log": audit}


# Debug helper
@mcp.tool()
def debug_get_all() -> Dict[str, Any]:
    """Return all cases (debug only)."""
    return cases


@mcp.prompt()
def hitl_escalation_prompt(case_id: str, field: str, problem: str) -> str:
    """
    Guidance text the agent can use when asking a human for help.
    """
    return (
        f"[HUMAN REVIEW REQUIRED]\n"
        f"Case: {case_id}\n"
        f"Issue: {field} needs manual verification ({problem}).\n\n"
        f"Please confirm or correct this field so processing can continue."
    )

@mcp.resource("policy://address-change")
def address_change_policy() -> str:
    """
    High-level policy notes the agent can reference.
    """
    return (
        "Address Change Policy (Demo):\n"
        "- Citizen must provide landlord confirmation (signed, recent).\n"
        "- Move-in date must be valid.\n"
        "- Address must be canonical and belong to a valid municipality.\n"
        "- If any check is low confidence, pause and involve an officer (HITL)."
    )


# -----------------
# Run MCP Server
# -----------------
if __name__ == "__main__":
    mcp.run()
