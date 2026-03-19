#!/usr/bin/env python
"""Seed PCI DSS Requirement 10 controls from Excel file."""

import sys
import uuid
import openpyxl
from pathlib import Path
from sqlalchemy.orm import Session

sys.path.insert(0, "/home/lasitha/Documents/Projects/Themis-Revamp")

from app.database import SessionLocal, engine
from app.models import BaseModel, Framework, FrameworkSection, FrameworkControl
from app.models.health_check import ReviewScopeType, ControlToReviewScopeMapping


EXCEL_PATH = Path(__file__).parent.parent / "sample_docs" / "PCI DSS 4.0_SN_v1.0_Automation.xlsx"

# Column indices (0-based)
COL_REQUIREMENT   = 1
COL_DESCRIPTION   = 3
COL_CONTROL_ID    = 4
COL_REQ_TEXT      = 5
COL_PROCEDURE     = 7
COL_GOOD_PRACTICE = 8
COL_CHECKLIST     = 11
COL_HARDENING     = 12
COL_SERVERS       = 13
COL_APPS          = 14
COL_DBS           = 15
COL_NETWORK       = 16
COL_SECURITY      = 17
COL_ENDUSER       = 18
COL_OTHER         = 19
COL_PROCESS       = 23
COL_DOCUMENTATION = 24
COL_PEOPLE        = 25
COL_OBSERVATION   = 29
COL_RECOMMENDATION= 30

# Map tech columns to ReviewScopeType names
TECH_SCOPE_MAP = {
    COL_SERVERS:  "Servers",
    COL_APPS:     "Applications",
    COL_DBS:      "Databases",
    COL_NETWORK:  "Network Devices",
    COL_SECURITY: "Security Tools",
    COL_ENDUSER:  "End User Devices",
}

REVIEW_SCOPE_TYPES = {
    "Servers":           "Physical and virtual servers",
    "Applications":      "Web and enterprise applications",
    "Databases":         "Database systems",
    "Network Devices":   "Routers, firewalls, switches",
    "Security Tools":    "SIEM, IDS/IPS, security appliances",
    "End User Devices":  "Workstations, laptops, terminals",
}

# R10 sub-sections
R10_SUB_SECTIONS = {
    "10.1": ("10.1", "Processes and mechanisms for logging and monitoring all access to system components and cardholder data are defined and documented."),
    "10.2": ("10.2", "Audit logs capture all individual user access to cardholder data."),
    "10.3": ("10.3", "Audit logs are protected from destruction and unauthorized modifications."),
    "10.4": ("10.4", "Audit logs are reviewed to identify anomalies or suspicious activity."),
    "10.5": ("10.5", "Audit log history is retained and available for analysis."),
    "10.6": ("10.6", "Time-synchronization mechanisms support consistent time settings across all systems."),
    "10.7": ("10.7", "Failures of critical security control systems are detected, reported, and responded to promptly."),
}


def val(row, col):
    """Safe value getter — returns stripped string or None."""
    v = row[col]
    if v is None:
        return None
    s = str(v).strip()
    return s if s and s.upper() not in ("NA", "N/A", "NAN") else None


def is_applicable(row, col):
    """Returns True if the tech column has a non-NA value (A = applicable)."""
    v = row[col]
    if v is None:
        return False
    s = str(v).strip()
    return bool(s) and s.upper() not in ("NA", "N/A", "NONE", "NAN")


def parse_r10():
    """Parse R10 sheet; return list of control dicts."""
    wb = openpyxl.load_workbook(EXCEL_PATH)
    ws = wb["R10"]

    rows = list(ws.iter_rows(values_only=True))

    controls = []
    for i, row in enumerate(rows):
        if i < 2:  # skip header rows
            continue

        control_id = val(row, COL_CONTROL_ID)
        if not control_id:
            continue

        # Only include R10 controls (control IDs starting with "10.")
        if not control_id.startswith("10."):
            continue

        description = val(row, COL_DESCRIPTION)
        req_text    = val(row, COL_REQ_TEXT)
        procedure   = val(row, COL_PROCEDURE)
        checklist   = val(row, COL_CHECKLIST)
        good_prac   = val(row, COL_GOOD_PRACTICE)
        hardening   = val(row, COL_HARDENING)
        process     = val(row, COL_PROCESS)
        documentation = val(row, COL_DOCUMENTATION)
        people      = val(row, COL_PEOPLE)
        observation = val(row, COL_OBSERVATION)
        recommendation = val(row, COL_RECOMMENDATION)

        # Build testing_procedures_text from procedure + checklist
        testing_parts = [p for p in [procedure, checklist] if p]
        testing_procedures_text = "\n\n".join(testing_parts) if testing_parts else None

        # Build check_points_text from hardening + process + documentation
        check_parts = []
        if hardening:
            check_parts.append(f"Hardening/Configuration:\n{hardening}")
        if process:
            check_parts.append(f"Process:\n{process}")
        if documentation:
            check_parts.append(f"Documentation:\n{documentation}")
        if people:
            check_parts.append(f"People:\n{people}")
        check_points_text = "\n\n".join(check_parts) if check_parts else None

        # Build assessment_checklist from observation/recommendation
        checklist_observations = []
        if observation and recommendation:
            checklist_observations.append({
                "id": "obs_1",
                "label": observation,
                "recommendation": recommendation,
            })

        assessment_checklist = (
            {"type": "observations", "observations": checklist_observations}
            if checklist_observations else None
        )

        # Applicable technologies
        applicable_scopes = [
            TECH_SCOPE_MAP[col]
            for col in TECH_SCOPE_MAP
            if is_applicable(row, col)
        ]

        controls.append({
            "control_id": control_id,
            "name": (description or req_text or control_id)[:255],
            "description": description or req_text or "",
            "requirements_text": req_text or description or "",
            "testing_procedures_text": testing_procedures_text,
            "check_points_text": check_points_text,
            "implementation_guidance": good_prac,
            "assessment_checklist": assessment_checklist,
            "applicable_scopes": applicable_scopes,
        })

    return controls


def get_sub_section_key(control_id: str) -> str:
    """Derive sub-section key from control_id. e.g. '10.2.1.1' -> '10.2'."""
    parts = control_id.split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    return control_id


def seed_r10():
    BaseModel.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # ── PCI DSS framework ──────────────────────────────────────────────────
        pci = db.query(Framework).filter(Framework.name.like("PCI DSS%")).first()
        if not pci:
            print("✗  PCI DSS framework not found. Run seed.py first.")
            return
        print(f"✓  Found PCI DSS framework: {pci.id}")

        # ── Requirement 10 parent section ──────────────────────────────────────
        r10 = db.query(FrameworkSection).filter(
            FrameworkSection.framework_id == pci.id,
            FrameworkSection.name.like("Requirement 10%"),
            FrameworkSection.parent_section_id.is_(None),
        ).first()

        if not r10:
            r10 = FrameworkSection(
                id=uuid.uuid4(),
                framework_id=pci.id,
                parent_section_id=None,
                name="Requirement 10: Logging and Monitoring",
                description=(
                    "Log and monitor all access to system components and cardholder data."
                ),
                order=10,
            )
            db.add(r10)
            db.commit()
            print(f"✓  Created Requirement 10 section: {r10.id}")
        else:
            print("⊘  Requirement 10 section already exists")

        # ── Sub-sections (10.1 – 10.7) ─────────────────────────────────────────
        sub_section_ids: dict[str, uuid.UUID] = {}

        for key, (label, desc) in R10_SUB_SECTIONS.items():
            existing = db.query(FrameworkSection).filter(
                FrameworkSection.parent_section_id == r10.id,
                FrameworkSection.name.like(f"{label}%"),
            ).first()

            if existing:
                sub_section_ids[key] = existing.id
                print(f"⊘  Sub-section {label} already exists")
            else:
                sub = FrameworkSection(
                    id=uuid.uuid4(),
                    framework_id=pci.id,
                    parent_section_id=r10.id,
                    name=f"{label}: {desc}",
                    description=desc,
                    order=int(label.split(".")[1]),
                )
                db.add(sub)
                db.flush()
                sub_section_ids[key] = sub.id
                print(f"✓  Created sub-section {label}")

        db.commit()

        # ── ReviewScopeTypes ───────────────────────────────────────────────────
        scope_type_ids: dict[str, uuid.UUID] = {}

        for name, desc in REVIEW_SCOPE_TYPES.items():
            existing = db.query(ReviewScopeType).filter(
                ReviewScopeType.framework_id == pci.id,
                ReviewScopeType.name == name,
            ).first()

            if existing:
                scope_type_ids[name] = existing.id
                print(f"⊘  ReviewScopeType '{name}' already exists")
            else:
                rst = ReviewScopeType(
                    id=uuid.uuid4(),
                    framework_id=pci.id,
                    name=name,
                    description=desc,
                )
                db.add(rst)
                db.flush()
                scope_type_ids[name] = rst.id
                print(f"✓  Created ReviewScopeType '{name}'")

        db.commit()

        # ── Parse Excel ────────────────────────────────────────────────────────
        controls = parse_r10()
        print(f"\n✓  Parsed {len(controls)} R10 controls from Excel")

        # Existing control_ids under R10 sub-sections to avoid duplicates
        existing_ids = set()
        for sid in sub_section_ids.values():
            rows = (
                db.query(FrameworkControl.control_id)
                .filter(FrameworkControl.framework_section_id == sid)
                .all()
            )
            existing_ids.update(r[0] for r in rows)

        # ── Create controls ────────────────────────────────────────────────────
        created = 0
        for ctrl in controls:
            cid = ctrl["control_id"]

            if cid in existing_ids:
                print(f"  ⊘  {cid} already exists, skipping")
                continue

            sub_key = get_sub_section_key(cid)
            section_id = sub_section_ids.get(sub_key)
            if not section_id:
                # Fall back to R10 parent section
                section_id = r10.id

            fc = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=section_id,
                control_id=cid,
                name=ctrl["name"],
                description=ctrl["description"],
                requirements_text=ctrl["requirements_text"],
                testing_procedures_text=ctrl["testing_procedures_text"],
                check_points_text=ctrl["check_points_text"],
                implementation_guidance=ctrl["implementation_guidance"],
                assessment_checklist=ctrl["assessment_checklist"],
            )
            db.add(fc)
            db.flush()
            created += 1
            print(f"  ✓  Created {cid}: {ctrl['name'][:60]}")

            # ── Control → ReviewScope mappings ─────────────────────────────
            for scope_name in ctrl["applicable_scopes"]:
                scope_id = scope_type_ids.get(scope_name)
                if not scope_id:
                    continue
                mapping = ControlToReviewScopeMapping(
                    review_scope_type_id=scope_id,
                    framework_control_id=fc.id,
                )
                db.add(mapping)

        db.commit()
        print(f"\n✅  Done — {created} new R10 controls seeded.")

    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        print(f"\n✗  Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_r10()
