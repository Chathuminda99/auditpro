#!/usr/bin/env python
"""Idempotent seeder for PCI DSS Health Check framework and audit domain mappings."""

import sys
import json
import uuid
from pathlib import Path
from sqlalchemy.orm import Session

# Add app directory to path
sys.path.insert(0, "/home/lasitha/Documents/Projects/Themis-Revamp")

from app.database import SessionLocal, engine
from app.models import (
    BaseModel,
    Tenant,
    Framework,
    FrameworkSection,
    FrameworkControl,
    AuditDomainType,
    ControlToDomainMapping,
)


def seed_health_check():
    """Load PCI DSS framework, sections, controls, and audit domain mappings."""
    # Create all tables
    BaseModel.metadata.create_all(bind=engine)

    db: Session = SessionLocal()

    try:
        # Load JSON seed data
        json_path = Path(__file__).parent / "pci_dss_controls.json"
        with open(json_path, "r") as f:
            seed_data = json.load(f)

        # Get default tenant
        default_tenant = db.query(Tenant).filter(Tenant.slug == "demo-company").first()
        if not default_tenant:
            print("✗ Default tenant not found. Run main seed.py first.")
            return

        tenant_id = default_tenant.id
        framework_name = seed_data["framework_name"]
        framework_version = seed_data["framework_version"]

        # Find or create PCI DSS framework
        pci_framework = db.query(Framework).filter(
            Framework.tenant_id == tenant_id,
            Framework.name == framework_name,
            Framework.version == framework_version,
        ).first()

        if pci_framework:
            print(f"✓ {framework_name} {framework_version} already exists")
        else:
            pci_framework = Framework(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                name=framework_name,
                description=f"Payment Card Industry Data Security Standard {framework_version}",
                version=framework_version,
            )
            db.add(pci_framework)
            db.flush()
            print(f"✓ Created {framework_name} {framework_version} framework")

        framework_id = pci_framework.id

        # Create sections and controls (idempotent by control_id)
        section_cache = {}

        for section_def in seed_data["sections"]:
            section_id = section_def["section_id"]

            existing_section = db.query(FrameworkSection).filter(
                FrameworkSection.framework_id == framework_id,
                FrameworkSection.name == section_id,
            ).first()

            if existing_section:
                section_cache[section_id] = existing_section.id
            else:
                section_obj = FrameworkSection(
                    id=uuid.uuid4(),
                    framework_id=framework_id,
                    parent_section_id=None,
                    name=section_id,
                    description=section_def.get("name"),
                    order=0,
                )
                db.add(section_obj)
                db.flush()
                section_cache[section_id] = section_obj.id

        print(f"✓ Ensured {len(seed_data['sections'])} framework sections")

        # Create controls (idempotent by control_id)
        control_cache = {}

        for control_def in seed_data["controls"]:
            control_id_str = control_def["control_id"]
            section_id = control_def["section"]

            existing_control = db.query(FrameworkControl).filter(
                FrameworkControl.control_id == control_id_str,
                FrameworkControl.section.has(
                    FrameworkSection.framework_id == framework_id
                ),
            ).first()

            if existing_control:
                control_cache[control_id_str] = existing_control.id
            else:
                section_fk_id = section_cache.get(section_id)
                if not section_fk_id:
                    print(f"  ⚠ Section {section_id} not found for control {control_id_str}")
                    continue

                control_obj = FrameworkControl(
                    id=uuid.uuid4(),
                    framework_section_id=section_fk_id,
                    control_id=control_id_str,
                    name=control_def.get("name", ""),
                    description=control_def.get("description"),
                    implementation_guidance=None,
                    requirements_text=None,
                    testing_procedures_text=None,
                    check_points_text=None,
                    workflow_definition=None,
                    assessment_checklist=None,
                )
                db.add(control_obj)
                db.flush()
                control_cache[control_id_str] = control_obj.id

        db.commit()
        print(f"✓ Ensured {len(seed_data['controls'])} framework controls")

        # Create audit domain types (idempotent by name + framework_id)
        domain_type_cache = {}

        for domain_def in seed_data["domains"]:
            domain_name = domain_def["name"]
            sort_order = domain_def.get("sort_order", 0)

            existing_domain_type = db.query(AuditDomainType).filter(
                AuditDomainType.framework_id == framework_id,
                AuditDomainType.name == domain_name,
            ).first()

            if existing_domain_type:
                domain_type_cache[domain_name] = existing_domain_type.id
            else:
                domain_type_obj = AuditDomainType(
                    id=uuid.uuid4(),
                    framework_id=framework_id,
                    name=domain_name,
                    description=None,
                    sort_order=sort_order,
                )
                db.add(domain_type_obj)
                db.flush()
                domain_type_cache[domain_name] = domain_type_obj.id

        db.commit()
        print(f"✓ Ensured {len(seed_data['domains'])} audit domain types")

        # Create control-to-domain mappings (idempotent with UniqueConstraint)
        mapping_count = 0

        for domain_def in seed_data["domains"]:
            domain_name = domain_def["name"]
            domain_type_id = domain_type_cache[domain_name]
            control_ids = domain_def.get("control_ids", [])

            for control_id_str in control_ids:
                control_fk_id = control_cache.get(control_id_str)
                if not control_fk_id:
                    print(f"  ⚠ Control {control_id_str} not found for domain {domain_name}")
                    continue

                existing_mapping = db.query(ControlToDomainMapping).filter(
                    ControlToDomainMapping.audit_domain_type_id == domain_type_id,
                    ControlToDomainMapping.framework_control_id == control_fk_id,
                ).first()

                if not existing_mapping:
                    mapping_obj = ControlToDomainMapping(
                        id=uuid.uuid4(),
                        audit_domain_type_id=domain_type_id,
                        framework_control_id=control_fk_id,
                    )
                    db.add(mapping_obj)
                    mapping_count += 1

        db.commit()
        print(f"✓ Ensured {mapping_count} control-to-domain mappings")

        print("\n✅ PCI DSS Health Check seed data loaded successfully")

    except Exception as e:
        db.rollback()
        print(f"✗ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_health_check()
