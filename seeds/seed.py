#!/usr/bin/env python
"""Seed script to populate initial data."""

import sys
import uuid
from sqlalchemy.orm import Session

# Add app directory to path
sys.path.insert(0, "/home/lasitha/Documents/Projects/Themis-Revamp")

from app.database import SessionLocal, engine
from app.models import (
    BaseModel,
    Tenant,
    User,
    UserRole,
    Client,
    Framework,
    FrameworkSection,
    FrameworkControl,
    ChecklistItem,
    Project,
    ProjectStatus,
)
from app.models.user import UserRole
from app.utils.security import hash_password


def seed_database():
    """Create default tenant, admin user, clients, frameworks, and projects."""
    # Create all tables
    BaseModel.metadata.create_all(bind=engine)

    db: Session = SessionLocal()

    try:
        # Check if default tenant exists
        default_tenant = (
            db.query(Tenant).filter(Tenant.slug == "demo-company").first()
        )

        if default_tenant:
            print("✓ Default tenant already exists")
            tenant_id = default_tenant.id
        else:
            # Create default tenant
            tenant_id = uuid.uuid4()
            tenant = Tenant(
                id=tenant_id,
                name="Demo Company",
                slug="demo-company",
                logo_url=None,
                settings={},
            )
            db.add(tenant)
            db.commit()
            print("✓ Created default tenant: Demo Company")

        # Check if admin user exists
        admin_user = db.query(User).filter(User.email == "admin@themis.local").first()

        if admin_user:
            print("✓ Admin user already exists")
        else:
            # Create admin user
            admin_user = User(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                email="admin@themis.local",
                password_hash=hash_password("admin123"),
                full_name="Administrator",
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin_user)
            db.commit()
            print("✓ Created admin user: admin@themis.local / admin123")

        # Check if auditor user exists
        auditor_user = db.query(User).filter(User.email == "auditor@themis.local").first()
        if auditor_user:
            print("✓ Auditor user already exists")
        else:
            auditor_user = User(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                email="auditor@themis.local",
                password_hash=hash_password("auditor123"),
                full_name="Test Auditor",
                role=UserRole.AUDITOR,
                is_active=True,
            )
            db.add(auditor_user)
            db.commit()
            print("✓ Created auditor user: auditor@themis.local / auditor123")

        # Check if clients already exist
        existing_clients = db.query(Client).filter(
            Client.tenant_id == tenant_id
        ).count()

        if existing_clients == 0:
            # Create clients
            acme_id = uuid.uuid4()
            acme = Client(
                id=acme_id,
                tenant_id=tenant_id,
                name="Acme Corporation",
                industry="Technology",
                contact_name="John Doe",
                contact_email="john.doe@acme.com",
                notes="Leading tech company",
            )

            beta_id = uuid.uuid4()
            beta = Client(
                id=beta_id,
                tenant_id=tenant_id,
                name="Beta Ltd",
                industry="Finance",
                contact_name="Jane Smith",
                contact_email="jane.smith@beta.com",
                notes="Financial services provider",
            )

            db.add_all([acme, beta])
            db.commit()
            print("✓ Created 2 clients: Acme Corporation, Beta Ltd")
        else:
            acme = db.query(Client).filter(
                Client.tenant_id == tenant_id,
                Client.name == "Acme Corporation"
            ).first()
            beta = db.query(Client).filter(
                Client.tenant_id == tenant_id,
                Client.name == "Beta Ltd"
            ).first()
            acme_id = acme.id if acme else None
            beta_id = beta.id if beta else None
            print("✓ Clients already exist")

        # Check if PCI DSS exists specifically
        pci_exists = db.query(Framework).filter(
            Framework.tenant_id == tenant_id,
            Framework.name == "PCI DSS V4.0.1"
        ).first()

        if not pci_exists:
            # Create ISO 27001 framework
            iso_id = uuid.uuid4()
            iso = Framework(
                id=iso_id,
                tenant_id=tenant_id,
                name="ISO 27001:2022",
                description="Information security management standard",
                version="2022",
            )
            db.add(iso)
            db.flush()

            # Create ISO 27001 sections
            iso_a5_id = uuid.uuid4()
            iso_a5 = FrameworkSection(
                id=iso_a5_id,
                framework_id=iso_id,
                parent_section_id=None,
                name="A.5 Organizational Controls",
                description="Controls for organization-wide policies",
                order=1,
            )
            db.add(iso_a5)
            db.flush()

            iso_a8_id = uuid.uuid4()
            iso_a8 = FrameworkSection(
                id=iso_a8_id,
                framework_id=iso_id,
                parent_section_id=None,
                name="A.8 Technological Controls",
                description="Technical security controls",
                order=2,
            )
            db.add(iso_a8)
            db.flush()

            # Add controls to ISO A.5
            iso_a5_1 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=iso_a5_id,
                control_id="A.5.1",
                name="Policies for information security",
                description="Information security policies established",
            )
            iso_a5_2 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=iso_a5_id,
                control_id="A.5.2",
                name="Information security roles and responsibilities",
                description="Clear roles and responsibilities defined",
            )
            db.add_all([iso_a5_1, iso_a5_2])
            db.flush()

            # Add controls to ISO A.8
            iso_a8_1 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=iso_a8_id,
                control_id="A.8.1",
                name="User endpoint devices",
                description="Endpoint device security implemented",
            )
            db.add(iso_a8_1)
            db.flush()

            # Add checklist items
            db.add(ChecklistItem(
                id=uuid.uuid4(),
                framework_control_id=iso_a5_1.id,
                description="Information security policy document reviewed",
                is_mandatory=True,
            ))
            db.add(ChecklistItem(
                id=uuid.uuid4(),
                framework_control_id=iso_a5_2.id,
                description="CISO appointed and documented",
                is_mandatory=True,
            ))

            db.commit()
            iso_framework_id = iso_id
            print("✓ Created ISO 27001:2022 framework with sections and controls")

            # Create SOC 2 framework
            soc2_id = uuid.uuid4()
            soc2 = Framework(
                id=soc2_id,
                tenant_id=tenant_id,
                name="SOC 2 Type II",
                description="System and Organization Controls framework",
                version="2023",
            )
            db.add(soc2)
            db.flush()

            # Create SOC 2 sections
            soc2_cc1_id = uuid.uuid4()
            soc2_cc1 = FrameworkSection(
                id=soc2_cc1_id,
                framework_id=soc2_id,
                parent_section_id=None,
                name="CC1 Control Environment",
                description="Foundation for security controls",
                order=1,
            )
            db.add(soc2_cc1)
            db.flush()

            # Add controls to SOC 2
            soc2_cc1_1 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=soc2_cc1_id,
                control_id="CC1.1",
                name="Demonstrates Commitment to Integrity",
                description="COSO Principle 1 implementation",
            )
            db.add(soc2_cc1_1)
            db.commit()
            soc2_framework_id = soc2_id
            print("✓ Created SOC 2 Type II framework with sections and controls")

            # Create PCI DSS V4.0.1 framework
            pci_id = uuid.uuid4()
            pci = Framework(
                id=pci_id,
                tenant_id=tenant_id,
                name="PCI DSS V4.0.1",
                description="Payment Card Industry Data Security Standard",
                version="4.0.1",
            )
            db.add(pci)
            db.flush()

            # Requirement 2: Apply Secure Configurations to All System Components
            pci_req2_id = uuid.uuid4()
            pci_req2 = FrameworkSection(
                id=pci_req2_id,
                framework_id=pci_id,
                parent_section_id=None,
                name="Requirement 2: Apply Secure Configurations to All System Components",
                description="Malicious individuals, both external and internal to an entity, often use default passwords and other vendor default settings to compromise systems. These passwords and settings are well known and are easily determined via public information.",
                order=1,
            )
            db.add(pci_req2)
            db.flush()

            # Sub-section 2.2: System Components Are Configured and Managed Securely
            pci_req2_2_id = uuid.uuid4()
            pci_req2_2 = FrameworkSection(
                id=pci_req2_2_id,
                framework_id=pci_id,
                parent_section_id=pci_req2_id,
                name="2.2 System Components Are Configured and Managed Securely",
                description="System configuration standards are developed, implemented, and managed to cover all system components.",
                order=1,
            )
            db.add(pci_req2_2)
            db.flush()

            # Assessment checklist for 2.2.2 (predefined observations for auditor selection)
            assessment_checklist_222 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed there are default accounts in active status which do not require for any operation.",
                        "recommendation": "It is recommended to evaluate whether these default accounts are required or not. If these default accounts are not required, it is recommended to remove or disable.",
                    },
                    {
                        "id": "obs_2",
                        "label": "It was observed there are active default accounts and in use\n- without having business/technical need.\n- without having a password complying with organization's password length requirement",
                        "recommendation": "If these default accounts are required, it is recommended to\n- have a business/technical justification with a management approval\n- implement the password length in accordance with the organization's password length requirement",
                    },
                    {
                        "id": "obs_3",
                        "label": "No default accounts were identified on the system.",
                        "recommendation": "No vendor default accounts were identified on this system component. This control requirement is satisfied. No further action is required.",
                    },
                    {
                        "id": "obs_4",
                        "label": "Vendor default accounts exist but are not in use and have been properly disabled or removed.",
                        "recommendation": "Vendor default accounts are not in use and have been disabled or removed from the system. This control is satisfied. Continue monitoring to ensure accounts remain disabled.",
                    },
                ],
            }

            # Workflow definition for 2.2.2 (kept for reference/future use with guided assessment)
            workflow_222 = {
                "version": "1.0",
                "root_node_id": "q1",
                "nodes": {
                    "q1": {
                        "type": "question",
                        "prompt": "Do vendor default accounts exist on the system component?",
                        "input_type": "select",
                        "options": [
                            {"value": "yes", "label": "Yes", "next_node_id": "q2"},
                            {"value": "no", "label": "No", "next_node_id": "t_pass_no_defaults"},
                        ],
                    },
                    "t_pass_no_defaults": {
                        "type": "terminal",
                        "finding_type": "pass",
                        "title": "No Vendor Default Accounts Present",
                        "recommendation": "No vendor default accounts were identified on the system component. This control is satisfied — no further action is required.",
                    },
                    "q2": {
                        "type": "question",
                        "prompt": "Are the vendor default accounts currently in use?",
                        "input_type": "select",
                        "options": [
                            {"value": "in_use", "label": "Yes, in use", "next_node_id": "q3_password"},
                            {"value": "not_in_use", "label": "No, not in use", "next_node_id": "q_disabled"},
                        ],
                    },
                    "q_disabled": {
                        "type": "question",
                        "prompt": "Have the unused vendor default accounts been disabled or removed?",
                        "input_type": "select",
                        "options": [
                            {"value": "yes", "label": "Yes, disabled/removed", "next_node_id": "t_pass_disabled"},
                            {"value": "no", "label": "No, still active", "next_node_id": "t_fail_not_disabled"},
                        ],
                    },
                    "t_pass_disabled": {
                        "type": "terminal",
                        "finding_type": "pass",
                        "title": "Unused Default Accounts Properly Disabled",
                        "recommendation": "Vendor default accounts are not in use and have been disabled or removed. This control is satisfied.",
                    },
                    "t_fail_not_disabled": {
                        "type": "terminal",
                        "finding_type": "fail",
                        "title": "Unused Default Accounts Not Disabled",
                        "recommendation": "Vendor default accounts exist and are not in use, but have NOT been disabled or removed. Per PCI DSS 2.2.2, unused vendor default accounts must be removed or disabled. Immediate remediation is required.",
                    },
                    "q3_password": {
                        "type": "question",
                        "prompt": "Has the default password been changed from the vendor-supplied default?",
                        "input_type": "select",
                        "options": [
                            {"value": "yes", "label": "Yes, password changed", "next_node_id": "q4_password_detail"},
                            {"value": "no", "label": "No, still default", "next_node_id": "t_fail_default_password"},
                        ],
                    },
                    "t_fail_default_password": {
                        "type": "terminal",
                        "finding_type": "fail",
                        "title": "Default Password Not Changed",
                        "recommendation": "A vendor default account is actively in use with the vendor-supplied default password still in place. This is a critical finding. Per PCI DSS 2.2.2, all vendor-supplied default passwords must be changed before a system is installed on the network. Change the password immediately to meet complexity requirements.",
                    },
                    "q4_password_detail": {
                        "type": "question",
                        "prompt": "Provide details about the password configuration:",
                        "input_type": "group",
                        "fields": [
                            {
                                "name": "password_policy",
                                "label": "Password Policy Compliance",
                                "input_type": "select",
                                "options": [
                                    {"value": "compliant", "label": "Meets complexity requirements"},
                                    {"value": "non_compliant", "label": "Does not meet complexity requirements"},
                                ],
                            },
                            {
                                "name": "last_change_date",
                                "label": "Last Password Change Date",
                                "input_type": "date",
                            },
                            {
                                "name": "notes",
                                "label": "Observations",
                                "input_type": "textarea",
                            },
                        ],
                        "next_node_rules": [
                            {
                                "condition": {"field": "password_policy", "op": "eq", "value": "compliant"},
                                "next_node_id": "t_observation_in_use",
                            },
                            {
                                "condition": {"field": "password_policy", "op": "eq", "value": "non_compliant"},
                                "next_node_id": "t_fail_weak_password",
                            },
                        ],
                        "default_next_node_id": "t_observation_in_use",
                    },
                    "t_observation_in_use": {
                        "type": "terminal",
                        "finding_type": "observation",
                        "title": "Default Account In Use With Changed Password",
                        "recommendation": "A vendor default account is in use but the password has been changed and meets complexity requirements. While the control requirement is technically met, best practice recommends creating unique named accounts instead of relying on vendor defaults. Consider replacing this account with a unique named account for improved audit trail and accountability.",
                    },
                    "t_fail_weak_password": {
                        "type": "terminal",
                        "finding_type": "fail",
                        "title": "Password Does Not Meet Complexity Requirements",
                        "recommendation": "The vendor default account password has been changed but does not meet the organization's password complexity requirements. Per PCI DSS 2.2.2, passwords for vendor default accounts must be changed per Requirement 8.3.6. Update the password to meet complexity requirements immediately.",
                    },
                },
            }

            # Control 2.2.2: Vendor default accounts managed
            pci_ctrl_222 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req2_2_id,
                control_id="2.2.2",
                name="Vendor default accounts are managed",
                description="If the vendor default account(s) will be used, the default password is changed per Requirement 8.3.6. If the vendor default account(s) will not be used, the account is removed or disabled.",
                requirements_text=(
                    "If the vendor default account(s) will be used, the default password is changed "
                    "per Requirement 8.3.6.\n\n"
                    "If the vendor default account(s) will not be used, the account is removed or disabled."
                ),
                testing_procedures_text=(
                    "2.2.2.a: Examine system configuration standards to verify they include managing "
                    "vendor default accounts in accordance with all elements specified in this requirement.\n\n"
                    "2.2.2.b: Examine vendor documentation and observe a system administrator logging on "
                    "using vendor default accounts to verify accounts are implemented in accordance with "
                    "all elements specified in this requirement.\n\n"
                    "2.2.2.c: Interview personnel and examine system configurations to verify that all "
                    "vendor defaults have been changed in accordance with all elements specified in this requirement."
                ),
                check_points_text=(
                    "• Ask whether default accounts exist or check the user list to see whether there are "
                    "default accounts and their status\n\n"
                    "• Ask whether the default accounts are in use or required to be used\n\n"
                    "If default accounts are not in use, check whether accounts have been disabled?\n\n"
                    "Or\n\n"
                    "If in use or required to be used, check whether the default password has been changed?\n\n"
                    "• Check the assigned password policy and last password change date"
                ),
                implementation_guidance=(
                    "Changing vendor defaults — including default passwords and removing/disabling "
                    "unnecessary default accounts — is one of the most important steps in securing "
                    "an environment."
                ),
                assessment_checklist=assessment_checklist_222,
            )

            # A few more controls in 2.2 without workflows for variety
            pci_ctrl_221 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req2_2_id,
                control_id="2.2.1",
                name="System configuration standards are developed and maintained",
                description="Configuration standards are developed, implemented, and maintained to cover all system components, address all known security vulnerabilities, and be consistent with industry-accepted system hardening standards.",
            )
            pci_ctrl_223 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req2_2_id,
                control_id="2.2.3",
                name="Primary functions requiring different security levels are managed",
                description="Primary functions requiring different security levels are managed by ensuring only one primary function exists on a system component, or that primary functions with differing security levels that exist on the same system component are isolated.",
            )

            db.add_all([pci_ctrl_221, pci_ctrl_222, pci_ctrl_223])
            db.commit()
            pci_framework_id = pci_id
            print("✓ Created PCI DSS V4.0.1 framework with Requirement 2.2 and workflow for 2.2.2")
        else:
            iso_framework = db.query(Framework).filter(
                Framework.tenant_id == tenant_id,
                Framework.name == "ISO 27001:2022"
            ).first()
            soc2_framework = db.query(Framework).filter(
                Framework.tenant_id == tenant_id,
                Framework.name == "SOC 2 Type II"
            ).first()
            pci_framework = db.query(Framework).filter(
                Framework.tenant_id == tenant_id,
                Framework.name == "PCI DSS V4.0.1"
            ).first()
            iso_framework_id = iso_framework.id if iso_framework else None
            soc2_framework_id = soc2_framework.id if soc2_framework else None
            pci_framework_id = pci_framework.id if pci_framework else None
            print("✓ Frameworks already exist")

        # Check if projects exist
        existing_projects = db.query(Project).filter(
            Project.tenant_id == tenant_id
        ).count()

        if existing_projects == 0 and acme_id and iso_framework_id:
            # Create projects (admin user is owner)
            project1 = Project(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                client_id=acme_id,
                framework_id=iso_framework_id,
                owner_id=admin_user.id,
                name="Acme ISO 27001 Assessment",
                description="ISO 27001 compliance assessment for Acme Corp",
                status=ProjectStatus.IN_PROGRESS,
            )

            if beta_id and soc2_framework_id:
                project2 = Project(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    client_id=beta_id,
                    framework_id=soc2_framework_id,
                    owner_id=admin_user.id,
                    name="Beta SOC 2 Readiness",
                    description="SOC 2 Type II readiness assessment for Beta Ltd",
                    status=ProjectStatus.DRAFT,
                )
                db.add_all([project1, project2])
            else:
                db.add(project1)

            db.commit()
            print("✓ Created projects")
        else:
            # Back-fill owner_id on existing projects that lack it
            projects_without_owner = db.query(Project).filter(
                Project.tenant_id == tenant_id,
                Project.owner_id.is_(None),
            ).all()
            if projects_without_owner:
                for p in projects_without_owner:
                    p.owner_id = admin_user.id
                db.commit()
                print(f"✓ Back-filled owner_id on {len(projects_without_owner)} existing project(s)")
            else:
                print("✓ Projects already exist")

        print("\n✅ Database seeded successfully!")

    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
