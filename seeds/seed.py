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
    ProjectType,
)
from app.models.user import UserRole
from app.models.health_check import ReviewScopeType, ControlToReviewScopeMapping
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

            # Create PCI DSS V4.0.1 framework (sections/controls seeded separately below)
            pci_id = uuid.uuid4()
            pci = Framework(
                id=pci_id,
                tenant_id=tenant_id,
                name="PCI DSS V4.0.1",
                description="Payment Card Industry Data Security Standard",
                version="4.0.1",
            )
            db.add(pci)
            db.commit()
            pci_framework_id = pci_id
            print("✓ Created PCI DSS V4.0.1 framework")
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

        # ── Seed PCI DSS Requirement 2 sections/controls (idempotent) ──
        pci_has_sections = db.query(FrameworkSection).filter(
            FrameworkSection.framework_id == pci_framework_id
        ).count() > 0 if pci_framework_id else True

        if pci_framework_id and not pci_has_sections:
            pci_id = pci_framework_id

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

            # ── Sub-section 2.3: Wireless Environments ──
            pci_req2_3_id = uuid.uuid4()
            pci_req2_3 = FrameworkSection(
                id=pci_req2_3_id,
                framework_id=pci_id,
                parent_section_id=pci_req2_id,
                name="2.3 Wireless Environments Are Configured and Managed Securely",
                description="Wireless environments connected to the CDE or transmitting account data are configured and managed securely.",
                order=2,
            )
            db.add(pci_req2_3)
            db.flush()

            # ── Assessment checklists (observations + recommendations from R2 sheet) ──

            checklist_221 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was informed that, this server/application/database has not been hardened.",
                        "recommendation": "It is recommended to develop a configuration standard (hardening guideline) based on organizational criteria or industry standard such as CIS benchmark, SDIG, etc and harden accordingly.",
                    },
                    {
                        "id": "obs_2",
                        "label": "It was observed that this server/application/database has not been hardened although there is a configuration standard available.",
                        "recommendation": "It is recommended to harden this server/application/database based on standard configuration.",
                    },
                    {
                        "id": "obs_3",
                        "label": "It was observed that there is no configuration standard to follow for this system component.",
                        "recommendation": "It is recommended to develop a configuration standard (hardening guideline) based on organizational criteria or industry standard such as CIS benchmark, SDIG, etc.",
                    },
                    {
                        "id": "obs_4",
                        "label": "It was observed that the level of hardening is not adequate. There are only a few hardening configurations.",
                        "recommendation": "It is recommended to increase the level of hardening based on a standard configuration/hardening guideline.",
                    },
                ],
            }

            checklist_222 = {
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
                ],
            }

            checklist_223 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that this server/database is running multiple functions with different criticality levels; however, the hardening applied is not adequate for the function with the highest criticality.",
                        "recommendation": (
                            "It is recommended to review the functions hosted on the server/database and identify the function with the highest security or criticality requirement. "
                            "The system should either be segregated to isolate functions with differing security levels or be hardened in accordance with the requirements applicable to the function with the highest criticality "
                            "(e.g., PCI DSS in-scope requirements). Hardening standards, configuration baselines, and security controls should be updated accordingly and periodically reviewed to ensure ongoing compliance."
                        ),
                    },
                ],
            }

            checklist_224 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed there are unnecessary services, protocols, and daemons available in active status.",
                        "recommendation": "It is recommended to remove or disable unnecessary services, protocols, and daemons available in active status.",
                    },
                    {
                        "id": "obs_2",
                        "label": "It was observed that services, protocols, and daemons which are in use or required do not have documented or any documented approvals.",
                        "recommendation": "It is recommended to document or obtain documented approvals for the services, protocols, and daemons being used.",
                    },
                ],
            }

            checklist_225 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed there are insecure services, protocols, and daemons in use without having business justifications.",
                        "recommendation": "If any insecure services, protocols, and daemons are in use, it is recommended to document the business justification.",
                    },
                    {
                        "id": "obs_2",
                        "label": "It was observed there are insecure services, protocols, and daemons being used without having additional security features that reduce the risk of using insecure services, protocols, or daemons.",
                        "recommendation": "It is recommended to implement additional security features that reduce the risk of using insecure services, protocols, or daemons.",
                    },
                ],
            }

            checklist_227 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that the administrators access this system component without having encrypted means. They use insecure means such as http, telnet or RDP.",
                        "recommendation": "It is recommended to secure all non-console access to this system component by using strong cryptography. E.g. https. At least, can use a self-signed certificate for internal communications.",
                    },
                ],
            }

            checklist_231 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that following vendor defaults exist.\n\u2022 Default encryption keys\n\u2022 Default passwords\n\u2022 SNMP defaults",
                        "recommendation": "It is recommended to change following vendor defaults.\n\u2022 Default encryption keys\n\u2022 Default passwords\n\u2022 SNMP defaults",
                    },
                ],
            }

            checklist_232 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that keys have not been changed when personnel with knowledge of the key leave the company.",
                        "recommendation": "It is recommended to change keys whenever personnel with knowledge of the key leave the company.",
                    },
                    {
                        "id": "obs_2",
                        "label": "It was observed that keys have not been changed as per the policy directions, though it requires to change the keys once every x years as per the ABC policy.",
                        "recommendation": "It is recommended to change keys as per frequency defined in the ABC policy.",
                    },
                    {
                        "id": "obs_3",
                        "label": "It was observed that there is no policy level direction to change the keys in a frequent manner.",
                        "recommendation": "It is recommended to have a policy direction and change keys in a defined frequency.",
                    },
                ],
            }

            # ── Control 2.2.1 ──
            pci_ctrl_221 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req2_2_id,
                control_id="2.2.1",
                name="Configuration standards are developed, implemented, and maintained",
                description=(
                    "Configuration standards are developed, implemented, and maintained to:\n"
                    "\u2022 Cover all system components.\n"
                    "\u2022 Address all known security vulnerabilities.\n"
                    "\u2022 Be consistent with industry-accepted system hardening standards or vendor hardening recommendations.\n"
                    "\u2022 Be updated as new vulnerability issues are identified, as defined in Requirement 6.3.1.\n"
                    "\u2022 Be applied when new systems are configured and verified as in place before or immediately after a system component is connected to a production environment."
                ),
                requirements_text=(
                    "Configuration standards are developed, implemented, and maintained to:\n"
                    "\u2022 Cover all system components.\n"
                    "\u2022 Address all known security vulnerabilities.\n"
                    "\u2022 Be consistent with industry-accepted system hardening standards or vendor hardening recommendations.\n"
                    "\u2022 Be updated as new vulnerability issues are identified, as defined in Requirement 6.3.1.\n"
                    "\u2022 Be applied when new systems are configured and verified as in place before or immediately after a system component is connected to a production environment."
                ),
                testing_procedures_text=(
                    "2.2.1.a Examine system configuration standards to verify they define processes that include all elements specified in this requirement.\n\n"
                    "2.2.1.b Examine policies and procedures and interview personnel to verify that system configuration standards are updated as new vulnerability issues are identified, as defined in Requirement 6.3.1.\n\n"
                    "2.2.1.c Examine configuration settings and interview personnel to verify that system configuration standards are applied when new systems are configured and verified as being in place before or immediately after a system component is connected to a production environment."
                ),
                check_points_text=(
                    "Ask whether there is a configuration standard for the hardening? "
                    "(If this is an application, check whether there is a vendor provided hardening guide. "
                    "E.g. if it is a PCI S3 Application, whether there is a guide for implementation. "
                    "If not you can skip this check for applications)\n\n"
                    "Verify that system configuration standards have been applied? "
                    "(When new system components are onboarded)"
                ),
                implementation_guidance=(
                    "There are known weaknesses with many operating systems, databases, network devices, software, applications, "
                    "container images, and other devices used by an entity or within an entity's environment. There are also known "
                    "ways to configure these system components to fix security vulnerabilities. Fixing security vulnerabilities "
                    "reduces the opportunities available to an attacker.\n\n"
                    "Sources for guidance on configuration standards include but are not limited to: Center for Internet Security (CIS), "
                    "International Organization for Standardization (ISO), National Institute of Standards and Technology (NIST), "
                    "Cloud Security Alliance, and product vendors."
                ),
                assessment_checklist=checklist_221,
            )

            # ── Control 2.2.2 ──
            pci_ctrl_222 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req2_2_id,
                control_id="2.2.2",
                name="Vendor default accounts are managed",
                description=(
                    "Vendor default accounts are managed as follows:\n"
                    "\u2022 If the vendor default account(s) will be used, the default password is changed per Requirement 8.3.6.\n"
                    "\u2022 If the vendor default account(s) will not be used, the account is removed or disabled."
                ),
                requirements_text=(
                    "Vendor default accounts are managed as follows:\n"
                    "\u2022 If the vendor default account(s) will be used, the default password is changed per Requirement 8.3.6.\n"
                    "\u2022 If the vendor default account(s) will not be used, the account is removed or disabled."
                ),
                testing_procedures_text=(
                    "2.2.2.a Examine system configuration standards to verify they include managing vendor default accounts in accordance with all elements specified in this requirement.\n\n"
                    "2.2.2.b Examine vendor documentation and observe a system administrator logging on using vendor default accounts to verify accounts are implemented in accordance with all elements specified in this requirement.\n\n"
                    "2.2.2.c Examine configuration files and interview personnel to verify that all vendor default accounts that will not be used are removed or disabled."
                ),
                check_points_text=(
                    "\u2022 Ask whether default accounts exist or check the user list to see whether there are default accounts and their status\n\n"
                    "\u2022 Ask whether the default accounts are in use or required to be used\n\n"
                    "If default accounts are not in use, check whether accounts have been disabled?\n\n"
                    "Or\n\n"
                    "If in use or required to be used, check whether the default password has been changed? "
                    "Check the assigned password policy and last password change date"
                ),
                implementation_guidance=(
                    "Malicious individuals often use vendor default account names and passwords to compromise operating systems, "
                    "applications, and the systems on which they are installed. Because these default settings are often published "
                    "and are well known, changing these settings will make systems less vulnerable to attack.\n\n"
                    "All vendor default accounts should be identified, and their purpose and use understood."
                ),
                assessment_checklist=checklist_222,
            )

            # ── Control 2.2.3 ──
            pci_ctrl_223 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req2_2_id,
                control_id="2.2.3",
                name="Primary functions requiring different security levels are managed",
                description=(
                    "Primary functions requiring different security levels are managed as follows:\n"
                    "\u2022 Only one primary function exists on a system component,\nOR\n"
                    "\u2022 Primary functions with differing security levels that exist on the same system component are isolated from each other,\nOR\n"
                    "\u2022 Primary functions with differing security levels on the same system component are all secured to the level required by the function with the highest security need."
                ),
                requirements_text=(
                    "Primary functions requiring different security levels are managed as follows:\n"
                    "\u2022 Only one primary function exists on a system component,\nOR\n"
                    "\u2022 Primary functions with differing security levels that exist on the same system component are isolated from each other,\nOR\n"
                    "\u2022 Primary functions with differing security levels on the same system component are all secured to the level required by the function with the highest security need."
                ),
                testing_procedures_text=(
                    "2.2.3.a Examine system configuration standards to verify they include managing primary functions requiring different security levels as specified in this requirement.\n\n"
                    "2.2.3.b Examine system configurations to verify that primary functions requiring different security levels are managed per one of the ways specified in this requirement.\n\n"
                    "2.2.3.c Where virtualization technologies are used, examine the system configurations to verify that system functions requiring different security levels are managed in one of the following ways:\n"
                    "\u2022 Functions with differing security needs do not co-exist on the same system component.\n"
                    "\u2022 Functions with differing security needs that exist on the same system component are isolated from each other.\n"
                    "\u2022 Functions with differing security needs on the same system component are all secured to the level required by the function with the highest security need."
                ),
                check_points_text=(
                    "Check whether the server, VM, database or any system component is running more than one primary function. "
                    "If multiple functions are hosted on the same server, assess whether they have differing security requirements. "
                    "Where different security levels apply, identify the function with the highest security requirement based on its criticality.\n\n"
                    "For example, if one of the applications running on the server is classified as CAT 01 (PCI DSS in-scope), "
                    "the entire server should be treated as critical and must be hardened in accordance with PCI DSS requirements applicable to in-scope systems."
                ),
                assessment_checklist=checklist_223,
            )

            # ── Control 2.2.4 ──
            pci_ctrl_224 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req2_2_id,
                control_id="2.2.4",
                name="Only necessary services, protocols, daemons, and functions are enabled",
                description="Only necessary services, protocols, daemons, and functions are enabled, and all unnecessary functionality is removed or disabled.",
                requirements_text="Only necessary services, protocols, daemons, and functions are enabled, and all unnecessary functionality is removed or disabled.",
                testing_procedures_text=(
                    "2.2.4.a Examine system configuration standards to verify necessary system services, protocols, and daemons are identified and documented.\n\n"
                    "2.2.4.b Examine system configurations to verify the following:\n"
                    "\u2022 All unnecessary functionality is removed or disabled.\n"
                    "\u2022 Only required functionality, as documented in the configuration standards, is enabled."
                ),
                check_points_text=(
                    "List enabled services, protocols, and daemons, then check whether there are unnecessary services, protocols, and daemons.\n\n"
                    "Check whether necessary services have been documented with the technical reasons or have any business justifications with approvals (may be emails)."
                ),
                implementation_guidance=(
                    "Unnecessary services and functions can provide additional opportunities for malicious individuals to gain access to a system. "
                    "By removing or disabling all unnecessary services, protocols, daemons, and functions, organizations can focus on securing the functions "
                    "that are required and reduce the risk that unknown or unnecessary functions will be exploited.\n\n"
                    "Examples of unnecessary functionality may include scripts, drivers, features, subsystems, file systems, interfaces (USB and Bluetooth), and unnecessary web servers."
                ),
                assessment_checklist=checklist_224,
            )

            # ── Control 2.2.5 ──
            pci_ctrl_225 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req2_2_id,
                control_id="2.2.5",
                name="Insecure services, protocols, or daemons are secured",
                description=(
                    "If any insecure services, protocols, or daemons are present:\n"
                    "\u2022 Business justification is documented.\n"
                    "\u2022 Additional security features are documented and implemented that reduce the risk of using insecure services, protocols, or daemons."
                ),
                requirements_text=(
                    "If any insecure services, protocols, or daemons are present:\n"
                    "\u2022 Business justification is documented.\n"
                    "\u2022 Additional security features are documented and implemented that reduce the risk of using insecure services, protocols, or daemons."
                ),
                testing_procedures_text=(
                    "2.2.5.a If any insecure services, protocols, or daemons are present, examine system configuration standards and interview personnel "
                    "to verify they are managed and implemented in accordance with all elements specified in this requirement.\n\n"
                    "2.2.5.b If any insecure services, protocols, or daemons are present, examine configuration settings to verify that additional security features "
                    "are implemented to reduce the risk of using insecure services, daemons, and protocols."
                ),
                check_points_text=(
                    "Check whether the existing services, protocols, and daemons are insecure?\n\n"
                    "If any insecure services, protocols, or daemons are present, examine configuration settings to verify that "
                    "additional security features have been implemented to reduce the risk of using insecure services, daemons, and protocols."
                ),
                implementation_guidance=(
                    "Ensuring that all insecure services, protocols, and daemons are adequately secured with appropriate security features "
                    "makes it more difficult for malicious individuals to exploit common points of compromise within a network.\n\n"
                    "For guidance on services, protocols, or daemons considered to be insecure, refer to industry standards and guidance "
                    "(for example, as published by NIST, ENISA, and OWASP)."
                ),
                assessment_checklist=checklist_225,
            )

            # ── Control 2.2.6 ──
            pci_ctrl_226 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req2_2_id,
                control_id="2.2.6",
                name="System security parameters are configured to prevent misuse",
                description="System security parameters are configured to prevent misuse.",
                requirements_text="System security parameters are configured to prevent misuse.",
                testing_procedures_text=(
                    "2.2.6.a Examine system configuration standards to verify they include configuring system security parameters to prevent misuse.\n\n"
                    "2.2.6.b Interview system administrators and/or security managers to verify they have knowledge of common security parameter settings for system components.\n\n"
                    "2.2.6.c Examine system configurations to verify that common security parameters are set appropriately and in accordance with the system configuration standards."
                ),
                implementation_guidance=(
                    "Correctly configuring security parameters provided in system components takes advantage of the capabilities of the system component "
                    "to defeat malicious attacks. For systems to be configured securely, personnel responsible for configuration and/or administering systems "
                    "should be knowledgeable in the specific security parameters and settings that apply to the system."
                ),
            )

            # ── Control 2.2.7 ──
            pci_ctrl_227 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req2_2_id,
                control_id="2.2.7",
                name="All non-console administrative access is encrypted using strong cryptography",
                description="All non-console administrative access is encrypted using strong cryptography.",
                requirements_text="All non-console administrative access is encrypted using strong cryptography.",
                testing_procedures_text=(
                    "2.2.7.a Examine system configuration standards to verify they include encrypting all non-console administrative access using strong cryptography.\n\n"
                    "2.2.7.b Observe an administrator log on to system components and examine system configurations to verify that non-console administrative access is managed in accordance with this requirement.\n\n"
                    "2.2.7.c Examine settings for system components and authentication services to verify that insecure remote login services are not available for non-console administrative access.\n\n"
                    "2.2.7.d Examine vendor documentation and interview personnel to verify that strong cryptography for the technology in use is implemented according to industry best practices and/or vendor recommendations."
                ),
                check_points_text=(
                    "Check the access is encrypted? Whether the system component is accessed using https? "
                    "Check whether insecure methods such as http, telnet, etc. are in use?"
                ),
                implementation_guidance=(
                    "If non-console (including remote) administration does not use encrypted communications, administrative authorization factors "
                    "(such as IDs and passwords) can be revealed to an eavesdropper. A malicious individual could use this information to access the "
                    "network, become administrator, and steal data.\n\n"
                    "Cleartext protocols (such as HTTP, telnet, etc.) do not encrypt traffic or logon details, making it easy for an eavesdropper to intercept this information."
                ),
                assessment_checklist=checklist_227,
            )

            # ── Control 2.3.1 ──
            pci_ctrl_231 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req2_3_id,
                control_id="2.3.1",
                name="Wireless vendor defaults are changed at installation or confirmed secure",
                description=(
                    "For wireless environments connected to the CDE or transmitting account data, all wireless vendor defaults are changed at installation or are confirmed to be secure, including but not limited to:\n"
                    "\u2022 Default wireless encryption keys.\n"
                    "\u2022 Passwords on wireless access points.\n"
                    "\u2022 SNMP defaults.\n"
                    "\u2022 Any other security-related wireless vendor defaults."
                ),
                requirements_text=(
                    "For wireless environments connected to the CDE or transmitting account data, all wireless vendor defaults are changed at installation or are confirmed to be secure, including but not limited to:\n"
                    "\u2022 Default wireless encryption keys.\n"
                    "\u2022 Passwords on wireless access points.\n"
                    "\u2022 SNMP defaults.\n"
                    "\u2022 Any other security-related wireless vendor defaults."
                ),
                testing_procedures_text=(
                    "2.3.1.a Examine policies and procedures and interview responsible personnel to verify that processes are defined for wireless vendor defaults to either change them upon installation or to confirm them to be secure in accordance with all elements of this requirement.\n\n"
                    "2.3.1.b Examine vendor documentation and observe a system administrator logging into wireless devices to verify:\n"
                    "\u2022 SNMP defaults are not used.\n"
                    "\u2022 Default passwords/passphrases on wireless access points are not used.\n\n"
                    "2.3.1.c Examine vendor documentation and wireless configuration settings to verify other security-related wireless vendor defaults were changed, if applicable."
                ),
                check_points_text=(
                    "This is applicable only for wireless network devices. This is not applicable to other network devices.\n\n"
                    "Check whether:\n"
                    "\u2022 Default encryption keys have been changed?\n"
                    "\u2022 Default passwords have been changed?\n"
                    "\u2022 SNMP defaults exist?\n"
                    "\u2022 Any other security-related wireless vendor defaults?"
                ),
                implementation_guidance=(
                    "If wireless networks are not implemented with sufficient security configurations (including changing default settings), "
                    "wireless sniffers can eavesdrop on the traffic, easily capture data and passwords, and easily enter and attack the network.\n\n"
                    "Wireless passwords should be constructed so that they are resistant to offline brute force attacks."
                ),
                assessment_checklist=checklist_231,
            )

            # ── Control 2.3.2 ──
            pci_ctrl_232 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req2_3_id,
                control_id="2.3.2",
                name="Wireless encryption keys are changed appropriately",
                description=(
                    "For wireless environments connected to the CDE or transmitting account data, wireless encryption keys are changed as follows:\n"
                    "\u2022 Whenever personnel with knowledge of the key leave the company or the role for which the knowledge was necessary.\n"
                    "\u2022 Whenever a key is suspected of or known to be compromised."
                ),
                requirements_text=(
                    "For wireless environments connected to the CDE or transmitting account data, wireless encryption keys are changed as follows:\n"
                    "\u2022 Whenever personnel with knowledge of the key leave the company or the role for which the knowledge was necessary.\n"
                    "\u2022 Whenever a key is suspected of or known to be compromised."
                ),
                testing_procedures_text=(
                    "2.3.2 Interview responsible personnel and examine key-management documentation to verify that wireless encryption keys "
                    "are changed in accordance with all elements specified in this requirement."
                ),
                check_points_text=(
                    "This is applicable only for wireless network devices. This is not applicable to other network devices.\n\n"
                    "Check the date on which the keys were last changed.\n\n"
                    "Obtain confirmation from the administrator or designated key custodian regarding the date on which they were assigned key custodian responsibilities.\n\n"
                    "Based on these dates, verify whether the keys were changed after the individual was assigned key custodian responsibilities.\n\n"
                    "Check whether there is a policy requirement to change the encryption keys in a defined frequency and whether they have been changed accordingly."
                ),
                implementation_guidance=(
                    "Changing wireless encryption keys whenever someone with knowledge of the key leaves the organization or moves to a role "
                    "that no longer requires knowledge of the key, helps keep knowledge of keys limited to only those with a business need to know.\n\n"
                    "Also, changing wireless encryption keys whenever a key is suspected or known to be compromised makes a wireless network more resistant to compromise."
                ),
                assessment_checklist=checklist_232,
            )

            db.add_all([
                pci_ctrl_221, pci_ctrl_222, pci_ctrl_223,
                pci_ctrl_224, pci_ctrl_225, pci_ctrl_226, pci_ctrl_227,
                pci_ctrl_231, pci_ctrl_232,
            ])
            db.commit()
            print("✓ Seeded PCI DSS V4.0.1 Requirement 2 (2.2.1-2.2.7, 2.3.1-2.3.2)")
        else:
            if pci_framework_id:
                print("✓ PCI DSS V4.0.1 Requirement 2 sections already exist")

        # ── Seed PCI DSS Requirement 5 sections/controls (idempotent) ──
        pci_has_req5 = db.query(FrameworkSection).filter(
            FrameworkSection.framework_id == pci_framework_id,
            FrameworkSection.name.like("Requirement 5%"),
        ).count() > 0 if pci_framework_id else True

        if pci_framework_id and not pci_has_req5:
            pci_id = pci_framework_id

            # Requirement 5: Protect All Systems and Networks from Malicious Software
            pci_req5_id = uuid.uuid4()
            pci_req5 = FrameworkSection(
                id=pci_req5_id,
                framework_id=pci_id,
                parent_section_id=None,
                name="Requirement 5: Protect All Systems and Networks from Malicious Software",
                description="Malicious software (malware) is a type of software or firmware that is designed to infiltrate or damage a computer system without the owner's informed consent.",
                order=2,
            )
            db.add(pci_req5)
            db.flush()

            # Sub-section 5.2: Malicious Software Is Prevented, or Detected and Addressed
            pci_req5_2_id = uuid.uuid4()
            pci_req5_2 = FrameworkSection(
                id=pci_req5_2_id,
                framework_id=pci_id,
                parent_section_id=pci_req5_id,
                name="5.2 Malicious Software (Malware) Is Prevented, or Detected and Addressed",
                description="An anti-malware solution(s) is deployed on all system components, except for those system components identified in periodic evaluations that concludes the system components are not at risk from malware.",
                order=1,
            )
            db.add(pci_req5_2)
            db.flush()

            # Sub-section 5.3: Anti-malware Mechanisms and Processes Are Active, Maintained, and Monitored
            pci_req5_3_id = uuid.uuid4()
            pci_req5_3 = FrameworkSection(
                id=pci_req5_3_id,
                framework_id=pci_id,
                parent_section_id=pci_req5_id,
                name="5.3 Anti-malware Mechanisms and Processes Are Active, Maintained, and Monitored",
                description="Anti-malware mechanisms and processes are active, maintained, and monitored to ensure ongoing protection against malware.",
                order=2,
            )
            db.add(pci_req5_3)
            db.flush()

            # Sub-section 5.4: Anti-phishing Mechanisms Protect Users Against Phishing Attacks
            pci_req5_4_id = uuid.uuid4()
            pci_req5_4 = FrameworkSection(
                id=pci_req5_4_id,
                framework_id=pci_id,
                parent_section_id=pci_req5_id,
                name="5.4 Anti-phishing Mechanisms Protect Users Against Phishing Attacks",
                description="Processes and automated mechanisms are in place to detect and protect personnel against phishing attacks.",
                order=3,
            )
            db.add(pci_req5_4)
            db.flush()

            # ── Assessment checklists (observations + recommendations from R5 sheet) ──

            checklist_521 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that there is no anti-malware solution deployed on this system component.",
                        "recommendation": (
                            "It is recommended to deploy an anti-malware solution for this system component and ensure it:\n"
                            "\u2022 Detects all known types of malware.\n"
                            "\u2022 Removes, blocks, or contains all known types of malware."
                        ),
                    },
                    {
                        "id": "obs_2",
                        "label": "Although this server is considered as a system component which is not at malware risk, there is no documented evidence such as an approved list of systems or any other specific approval to consider it as a system component which is not at malware risk.",
                        "recommendation": "It is recommended to have a list of systems with management approval which are considered as system components which are not at malware risk.",
                    },
                    {
                        "id": "obs_3",
                        "label": "It was observed that there is no TRA for this server which is considered as a system component which is not at malware risk.",
                        "recommendation": "It is recommended to have a TRA for this server to evaluate the malware risk at a defined frequency.",
                    },
                    {
                        "id": "obs_4",
                        "label": "It was observed that the defined frequency for malware risk evaluation in the TRA is more than six months.",
                        "recommendation": "It is recommended to have a frequency for evaluation of malware risk for this server of less than six months.",
                    },
                    {
                        "id": "obs_5",
                        "label": "It was informed that evaluation of malware risk for this server has not been performed as per the defined frequency.",
                        "recommendation": "It is recommended to evaluate malware risk for this server as per the defined frequency with sufficient evidence.",
                    },
                ],
            }

            checklist_522 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that only the following malware types have been configured:\nA\u2026\nB\u2026",
                        "recommendation": "It is recommended to configure the solution to detect more types of malware based on threats such as ransomware, spyware, etc.",
                    },
                    {
                        "id": "obs_2",
                        "label": "It was observed that actions have not been configured for the following malware types:\nA\u2026\nB\u2026\nC\u2026\nD\u2026",
                        "recommendation": "It is recommended to define necessary actions for each malware type upon detection.",
                    },
                ],
            }

            checklist_531 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that the anti-malware solution was not current since definitions have not been updated.",
                        "recommendation": "It is recommended to keep the anti-malware solution current with the latest definitions.",
                    },
                    {
                        "id": "obs_2",
                        "label": "It was observed that the anti-malware solution has not been configured to perform automatic updates. Currently updates are performed manually.",
                        "recommendation": "It is recommended to configure the anti-malware solution to perform automatic updates in order to keep the solution current with the latest definitions.",
                    },
                ],
            }

            checklist_532 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that scans have not been performed since (Date) as per the schedule although the agent is active.",
                        "recommendation": "It is recommended to identify the root cause and rectify the scanning as required.",
                    },
                    {
                        "id": "obs_2",
                        "label": "It was observed that the anti-malware solution is not active since (Date).",
                        "recommendation": "It is recommended to identify the root cause and activate the agent immediately. Further ensure scans are performed as per the schedule or in the expected manner.",
                    },
                ],
            }

            checklist_5321 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that there is no TRA for the defined frequency of periodic scanning.",
                        "recommendation": "It is recommended to have a TRA for the defined frequency of periodic scanning.",
                    },
                    {
                        "id": "obs_2",
                        "label": "It was observed that the defined frequency for periodic scanning in the TRA is more than one day.",
                        "recommendation": "It is recommended to have a frequency for periodic scanning of less than one day.",
                    },
                ],
            }

            checklist_533 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that the anti-malware solution has not been configured to scan removable media (USB).",
                        "recommendation": "It is recommended to configure the anti-malware solution to scan removable media (USB) as and when removable media are inserted.",
                    },
                ],
            }

            checklist_534 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that the anti-malware solution has not been configured to trigger events/results after detecting from scans.",
                        "recommendation": "It is recommended to configure the malware solution to trigger events/results after detecting from scans.",
                    },
                    {
                        "id": "obs_2",
                        "label": "It was observed that admin logs of the malware solution are not enabled.",
                        "recommendation": "It is recommended to enable admin logs of the malware solution.",
                    },
                    {
                        "id": "obs_3",
                        "label": "It was observed that events and admin logs are retained only for XX months either in the solution itself or SIEM.",
                        "recommendation": "It is recommended to retain events and admin logs for at least 12 months.",
                    },
                    {
                        "id": "obs_4",
                        "label": "It was observed that events and admin logs are retained only for XX months for immediate access.",
                        "recommendation": "It is recommended to retain events and admin logs of the most recent 3 months for immediate access.",
                    },
                ],
            }

            checklist_535 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that the end user or the server admin is able to disable the anti-malware service from the host level.",
                        "recommendation": "It is recommended to configure the anti-malware solution in a manner that the end user or the server admin cannot disable it.",
                    },
                ],
            }

            checklist_541 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that phishing controls/detection configurations have not been enabled.",
                        "recommendation": "It is recommended to enable phishing controls/detection configurations.",
                    },
                ],
            }

            # ── Control 5.2.1 ──
            pci_ctrl_521 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req5_2_id,
                control_id="5.2.1",
                name="Anti-malware solution deployed on all system components",
                description=(
                    "An anti-malware solution(s) is deployed on all system components, except for those system components "
                    "identified in periodic evaluations per Requirement 5.2.3 that concludes the system components are not at risk from malware."
                ),
                requirements_text=(
                    "An anti-malware solution(s) is deployed on all system components, except for those system components "
                    "identified in periodic evaluations per Requirement 5.2.3 that concludes the system components are not at risk from malware."
                ),
                testing_procedures_text=(
                    "5.2.1.a Examine system components to verify that an anti-malware solution(s) is deployed on all system components, "
                    "except for those determined to not be at risk from malware based on periodic evaluations per Requirement 5.2.3.\n\n"
                    "5.2.1.b For any system components without an anti-malware solution, examine the periodic evaluations to verify the "
                    "component was evaluated and the evaluation concludes that the component is not at risk from malware."
                ),
                check_points_text=(
                    "Ask whether the system component requires anti-malware protection. If yes, check whether an anti-malware solution is deployed.\n\n"
                    "If the system component is not at risk from malware, check whether there is documented evidence such as an approved list "
                    "of systems that do not require an anti-malware solution or any other approval.\n\n"
                    "If the system component is not at risk from malware, check whether there is a proper TRA available.\n\n"
                    "If there is a TRA with a defined frequency, check whether the defined frequency is higher than the allowed frequency.\n\n"
                    "If there is a TRA with a defined frequency, check evidence to verify that evaluations are performed at the frequency defined."
                ),
                implementation_guidance=(
                    "It is beneficial for entities to be aware of \u201czero-day\u201d attacks (those that exploit a previously unknown vulnerability) "
                    "and consider solutions that focus on behavioral characteristics and will alert and react to unexpected behavior."
                ),
                assessment_checklist=checklist_521,
            )

            # ── Control 5.2.2 ──
            pci_ctrl_522 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req5_2_id,
                control_id="5.2.2",
                name="Anti-malware detects, removes, blocks, or contains all known malware types",
                description=(
                    "The deployed anti-malware solution(s):\n"
                    "\u2022 Detects all known types of malware.\n"
                    "\u2022 Removes, blocks, or contains all known types of malware."
                ),
                requirements_text=(
                    "The deployed anti-malware solution(s):\n"
                    "\u2022 Detects all known types of malware.\n"
                    "\u2022 Removes, blocks, or contains all known types of malware."
                ),
                testing_procedures_text=(
                    "5.2.2 Examine vendor documentation and configurations of the anti-malware solution(s) to verify that the solution:\n"
                    "\u2022 Detects all known types of malware.\n"
                    "\u2022 Removes, blocks, or contains all known types of malware."
                ),
                check_points_text=(
                    "Check all the anti-malware policies/rules applicable for the system components and what types of malware have been configured. "
                    "E.g. Ransomware, Trojans, Spyware, etc. and actions upon detection."
                ),
                implementation_guidance=(
                    "Anti-malware solutions may include a combination of network-based controls, host-based controls, and endpoint security solutions. "
                    "In addition to signature-based tools, capabilities used by modern anti-malware solutions include sandboxing, privilege escalation controls, "
                    "and machine learning.\n\n"
                    "Solution techniques include preventing malware from getting into the network and removing or containing malware that does get into the network.\n\n"
                    "Examples of malware types include, but are not limited to, viruses, Trojans, worms, spyware, ransomware, keyloggers, rootkits, "
                    "malicious code, scripts, and links."
                ),
                assessment_checklist=checklist_522,
            )

            # ── Control 5.3.1 ──
            pci_ctrl_531 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req5_3_id,
                control_id="5.3.1",
                name="Anti-malware solution is kept current via automatic updates",
                description="The anti-malware solution(s) is kept current via automatic updates.",
                requirements_text="The anti-malware solution(s) is kept current via automatic updates.",
                testing_procedures_text=(
                    "5.3.1.a Examine anti-malware solution(s) configurations, including any master installation of the software, "
                    "to verify the solution is configured to perform automatic updates.\n\n"
                    "5.3.1.b Examine system components and logs, to verify that the anti-malware solution(s) and definitions are current "
                    "and have been promptly deployed."
                ),
                check_points_text=(
                    "Check anti-malware solution notifications or update notes or logs to verify that the anti-malware solution(s) "
                    "and definitions are current.\n\n"
                    "Check configurations (update schedule) of the anti-malware solution to perform automatic updates."
                ),
                implementation_guidance=(
                    "Anti-malware mechanisms should be updated via a trusted source as soon as possible after an update is available. "
                    "Using a trusted common source to distribute updates to end-user systems helps ensure the integrity and consistency "
                    "of the solution architecture.\n\n"
                    "Updates may be automatically downloaded to a central location\u2014for example, to allow for testing\u2014prior to being "
                    "deployed to individual system components."
                ),
                assessment_checklist=checklist_531,
            )

            # ── Control 5.3.2 ──
            pci_ctrl_532 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req5_3_id,
                control_id="5.3.2",
                name="Periodic scans, real-time scans, or continuous behavioral analysis performed",
                description=(
                    "The anti-malware solution(s):\n"
                    "\u2022 Performs periodic scans and active or real-time scans.\nOR\n"
                    "\u2022 Performs continuous behavioral analysis of systems or processes."
                ),
                requirements_text=(
                    "The anti-malware solution(s):\n"
                    "\u2022 Performs periodic scans and active or real-time scans.\nOR\n"
                    "\u2022 Performs continuous behavioral analysis of systems or processes."
                ),
                testing_procedures_text=(
                    "5.3.2.a Examine anti-malware solution(s) configurations, including any master installation of the software, to verify "
                    "the solution(s) is configured to perform at least one of the elements specified in this requirement.\n\n"
                    "5.3.2.b Examine system components, including all operating system types identified as at risk for malware, to verify "
                    "the solution(s) is enabled in accordance with at least one of the elements specified in this requirement.\n\n"
                    "5.3.2.c Examine logs and scan results to verify that the solution(s) is enabled in accordance with at least one of "
                    "the elements specified in this requirement."
                ),
                check_points_text=(
                    "Ask whether and how malware scans are performed: periodically (schedule), real-time, and behavioral analysis.\n\n"
                    "Check dashboard/alerts to verify the scans are performed as configured (periodically, real-time, and behavioral analysis) "
                    "and see whether there are lapses or indications that scans are not performed as expected."
                ),
                implementation_guidance=(
                    "Using a combination of periodic scans (scheduled and on-demand) and active, real-time (on-access) scanning helps ensure "
                    "that malware residing in both static and dynamic elements of the CDE is addressed. Users should also be able to run "
                    "on-demand scans on their systems if suspicious activity is detected.\n\n"
                    "Scans should include the entire file system, including all disks, memory, and start-up files and boot records (at system restart) "
                    "to detect all malware upon file execution, including any software that may be resident on a system but not currently active. "
                    "Scan scope should include all systems and software in the CDE, including those that are often overlooked such as email servers, "
                    "web browsers, and instant messaging software."
                ),
                assessment_checklist=checklist_532,
            )

            # ── Control 5.3.2.1 ──
            pci_ctrl_5321 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req5_3_id,
                control_id="5.3.2.1",
                name="Periodic malware scan frequency defined in targeted risk analysis",
                description=(
                    "If periodic malware scans are performed to meet Requirement 5.3.2, the frequency of scans is defined in the entity\u2019s "
                    "targeted risk analysis, which is performed according to all elements specified in Requirement 12.3.1."
                ),
                requirements_text=(
                    "If periodic malware scans are performed to meet Requirement 5.3.2, the frequency of scans is defined in the entity\u2019s "
                    "targeted risk analysis, which is performed according to all elements specified in Requirement 12.3.1."
                ),
                testing_procedures_text="",
                check_points_text=(
                    "If periodic scans are performed, check whether there is a proper TRA available.\n\n"
                    "If there is a TRA with a defined frequency for scanning, check whether the defined frequency is higher than the allowed frequency."
                ),
                assessment_checklist=checklist_5321,
            )

            # ── Control 5.3.3 ──
            pci_ctrl_533 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req5_3_id,
                control_id="5.3.3",
                name="Anti-malware scans removable electronic media",
                description=(
                    "For removable electronic media, the anti-malware solution(s):\n"
                    "\u2022 Performs automatic scans of when the media is inserted, connected, or logically mounted,\nOR\n"
                    "\u2022 Performs continuous behavioral analysis of systems or processes when the media is inserted, connected, or logically mounted."
                ),
                requirements_text=(
                    "For removable electronic media, the anti-malware solution(s):\n"
                    "\u2022 Performs automatic scans of when the media is inserted, connected, or logically mounted,\nOR\n"
                    "\u2022 Performs continuous behavioral analysis of systems or processes when the media is inserted, connected, or logically mounted."
                ),
                testing_procedures_text="",
                check_points_text="Check whether the anti-malware solution has been configured to scan removable media (USB).",
                assessment_checklist=checklist_533,
            )

            # ── Control 5.3.4 ──
            pci_ctrl_534 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req5_3_id,
                control_id="5.3.4",
                name="Audit logs for anti-malware solution are enabled and retained",
                description="Audit logs for the anti-malware solution(s) are enabled and retained in accordance with Requirement 10.5.1.",
                requirements_text="Audit logs for the anti-malware solution(s) are enabled and retained in accordance with Requirement 10.5.1.",
                testing_procedures_text="",
                check_points_text=(
                    "Check whether the anti-malware solution has been configured to trigger events/results (check the dashboard).\n\n"
                    "Check whether the admin logs of the malware solution are enabled.\n\n"
                    "Check whether events and admin logs are retained for 12 months either in the solution itself or SIEM.\n\n"
                    "Check whether events and admin logs of the most recent 3 months are retained for immediate access."
                ),
                assessment_checklist=checklist_534,
            )

            # ── Control 5.3.5 ──
            pci_ctrl_535 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req5_3_id,
                control_id="5.3.5",
                name="Anti-malware mechanisms cannot be disabled or altered by users",
                description=(
                    "Anti-malware mechanisms cannot be disabled or altered by users, unless specifically documented, "
                    "and authorized by management on a case-by-case basis for a limited time period."
                ),
                requirements_text=(
                    "Anti-malware mechanisms cannot be disabled or altered by users, unless specifically documented, "
                    "and authorized by management on a case-by-case basis for a limited time period."
                ),
                testing_procedures_text="",
                check_points_text=(
                    "Check whether the anti-malware solution cannot be disabled by the server admin or the end user.\n\n"
                    "Note: If the end user or server admin can disable, this finding should go under Malware Solution Review report."
                ),
                implementation_guidance=(
                    "Where there is a legitimate need to temporarily disable a system\u2019s anti-malware protection\u2014for example, "
                    "to support a specific maintenance activity or investigation of a technical problem\u2014the reason for taking such action "
                    "should be understood and approved by an appropriate management representative. Any disabling or altering of anti-malware "
                    "mechanisms, including on administrators\u2019 own devices, should be performed by authorized personnel.\n\n"
                    "Additional security measures that may need to be implemented for the period during which anti-malware protection is not active "
                    "include disconnecting the unprotected system from the Internet while the anti-malware protection is disabled and running a full "
                    "scan once it is re-enabled."
                ),
                assessment_checklist=checklist_535,
            )

            # ── Control 5.4.1 ──
            pci_ctrl_541 = FrameworkControl(
                id=uuid.uuid4(),
                framework_section_id=pci_req5_4_id,
                control_id="5.4.1",
                name="Processes and automated mechanisms detect and protect against phishing",
                description="Processes and automated mechanisms are in place to detect and protect personnel against phishing attacks.",
                requirements_text="Processes and automated mechanisms are in place to detect and protect personnel against phishing attacks.",
                testing_procedures_text="",
                check_points_text="Check the configuration for detecting phishing attacks.",
                implementation_guidance=(
                    "When developing anti-phishing controls, entities are encouraged to consider a combination of approaches. "
                    "For example, using anti-spoofing controls such as Domain-based Message Authentication, Reporting & Conformance (DMARC), "
                    "Sender Policy Framework (SPF), and Domain Keys Identified Mail (DKIM) will help stop phishers from spoofing the entity\u2019s "
                    "review_scope and impersonating personnel.\n\n"
                    "The deployment of technologies for blocking phishing emails and malware before they reach personnel, such as link scrubbers "
                    "and server-side anti-malware, can reduce incidents and decrease the time required by personnel to check and report phishing attacks. "
                    "Additionally, training personnel to recognize and report phishing emails can allow similar emails to be identified and permit them "
                    "to be removed before being opened.\n\n"
                    "It is recommended (but not required) that anti-phishing controls are applied across an entity\u2019s entire organization."
                ),
                assessment_checklist=checklist_541,
            )

            db.add_all([
                pci_ctrl_521, pci_ctrl_522,
                pci_ctrl_531, pci_ctrl_532, pci_ctrl_5321, pci_ctrl_533, pci_ctrl_534, pci_ctrl_535,
                pci_ctrl_541,
            ])
            db.commit()
            print("✓ Seeded PCI DSS V4.0.1 Requirement 5 (5.2.1-5.2.2, 5.3.1-5.3.5, 5.4.1)")

            # ── Map R5 controls to existing review_scope types ──
            pci_domain_types = {}
            for dt in db.query(ReviewScopeType).filter(
                ReviewScopeType.framework_id == pci_id
            ).all():
                pci_domain_types[dt.name] = dt

            dt_servers = pci_domain_types.get("Servers")
            dt_end_user = pci_domain_types.get("End User Devices")
            dt_other = pci_domain_types.get("Other Systems")

            r5_mappings = []
            if dt_servers and dt_end_user and dt_other:
                # 5.2.1: Servers, End User, Other
                for dt in [dt_servers, dt_end_user, dt_other]:
                    r5_mappings.append(ControlToReviewScopeMapping(id=uuid.uuid4(),
                        review_scope_type_id=dt.id, framework_control_id=pci_ctrl_521.id))
                # 5.2.2: Other (Anti-Malware Solution)
                r5_mappings.append(ControlToReviewScopeMapping(id=uuid.uuid4(),
                    review_scope_type_id=dt_other.id, framework_control_id=pci_ctrl_522.id))
                # 5.3.1: Other (Anti-Malware Solution)
                r5_mappings.append(ControlToReviewScopeMapping(id=uuid.uuid4(),
                    review_scope_type_id=dt_other.id, framework_control_id=pci_ctrl_531.id))
                # 5.3.2: Servers, End User, Other
                for dt in [dt_servers, dt_end_user, dt_other]:
                    r5_mappings.append(ControlToReviewScopeMapping(id=uuid.uuid4(),
                        review_scope_type_id=dt.id, framework_control_id=pci_ctrl_532.id))
                # 5.3.2.1: Servers, End User, Other
                for dt in [dt_servers, dt_end_user, dt_other]:
                    r5_mappings.append(ControlToReviewScopeMapping(id=uuid.uuid4(),
                        review_scope_type_id=dt.id, framework_control_id=pci_ctrl_5321.id))
                # 5.3.3: Servers, End User, Other
                for dt in [dt_servers, dt_end_user, dt_other]:
                    r5_mappings.append(ControlToReviewScopeMapping(id=uuid.uuid4(),
                        review_scope_type_id=dt.id, framework_control_id=pci_ctrl_533.id))
                # 5.3.4: Other (Anti-Malware Solution)
                r5_mappings.append(ControlToReviewScopeMapping(id=uuid.uuid4(),
                    review_scope_type_id=dt_other.id, framework_control_id=pci_ctrl_534.id))
                # 5.3.5: Servers, End User, Other
                for dt in [dt_servers, dt_end_user, dt_other]:
                    r5_mappings.append(ControlToReviewScopeMapping(id=uuid.uuid4(),
                        review_scope_type_id=dt.id, framework_control_id=pci_ctrl_535.id))
                # 5.4.1: Other (Email Gateway/Firewall)
                r5_mappings.append(ControlToReviewScopeMapping(id=uuid.uuid4(),
                    review_scope_type_id=dt_other.id, framework_control_id=pci_ctrl_541.id))

                db.add_all(r5_mappings)
                db.commit()
                print(f"✓ Mapped {len(r5_mappings)} R5 control-to-review_scope mappings")
            else:
                print("⚠ Could not map R5 controls to review_scopes (review_scope types not found)")
        else:
            if pci_framework_id:
                print("✓ PCI DSS V4.0.1 Requirement 5 sections already exist")

        # ── Seed PCI DSS Requirement 7 sections/controls (idempotent) ──
        pci_has_req7 = db.query(FrameworkSection).filter(
            FrameworkSection.framework_id == pci_framework_id,
            FrameworkSection.name.like("Requirement 7%"),
        ).count() > 0 if pci_framework_id else True

        if pci_framework_id and not pci_has_req7:
            pci_id = pci_framework_id

            # Requirement 7: Restrict Access to System Components and Cardholder Data by Business Need to Know
            pci_req7_id = uuid.uuid4()
            pci_req7 = FrameworkSection(
                id=pci_req7_id, framework_id=pci_id, parent_section_id=None,
                name="Requirement 7: Restrict Access to System Components and Cardholder Data by Business Need to Know",
                description="Access to system components and cardholder data is limited to only those individuals whose jobs require such access.",
                order=3,
            )
            db.add(pci_req7)
            db.flush()

            pci_req7_2_id = uuid.uuid4()
            pci_req7_2 = FrameworkSection(
                id=pci_req7_2_id, framework_id=pci_id, parent_section_id=pci_req7_id,
                name="7.2 Access to System Components and Data Is Appropriately Defined and Assigned",
                description="Access to system components and data is appropriately defined and assigned.",
                order=1,
            )
            pci_req7_3_id = uuid.uuid4()
            pci_req7_3 = FrameworkSection(
                id=pci_req7_3_id, framework_id=pci_id, parent_section_id=pci_req7_id,
                name="7.3 Access to System Components and Data Is Managed via an Access Control System(s)",
                description="Access to system components and data is managed via an access control system(s).",
                order=2,
            )
            db.add_all([pci_req7_2, pci_req7_3])
            db.flush()

            # ── R7 Checklists ──
            checklist_721 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "Currently, privileges are granted individually to each user rather than assigning predefined roles.",
                        "recommendation": "It is recommended to implement role-based access granting by directly assigning the specific role based on the job function to each individual user account.",
                    },
                ],
            }

            checklist_723 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that formal user access requests have not been available for the following user accounts.",
                        "recommendation": "It is recommended to have a formal user access request for user account creations and modifications in accordance with the applicable policy/procedure.",
                    },
                    {
                        "id": "obs_2",
                        "label": "It was observed that the user access request has not been approved by authorized personnel as per the applicable policy/procedure.",
                        "recommendation": "It is recommended to obtain approval for user access requests from authorized personnel in accordance with the applicable policy/procedure.",
                    },
                ],
            }

            checklist_724 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that user accounts and related privileges are not reviewed.",
                        "recommendation": "It is recommended to review all user accounts and related access privileges at least once every six months.",
                    },
                    {
                        "id": "obs_2",
                        "label": "It was informed that user accounts and related privileges are reviewed annually but not every six months.",
                        "recommendation": "It is recommended to increase the review frequency to at least once every six months.",
                    },
                    {
                        "id": "obs_3",
                        "label": "It was observed that user accounts and related privilege reviews have not been conducted since (Date/Year).",
                        "recommendation": "It is recommended to conduct user accounts and related privilege reviews immediately and ensure they are performed at least once every six months.",
                    },
                    {
                        "id": "obs_4",
                        "label": "It was observed that though the user account reviews are conducted, privileges are not reviewed.",
                        "recommendation": "It is recommended to include a review of assigned privileges as part of the user account review process.",
                    },
                    {
                        "id": "obs_5",
                        "label": "Although reviews are conducted, it was observed that documented records are not maintained with review results and management approvals.",
                        "recommendation": "It is recommended to maintain documented records of review results with management acknowledgment.",
                    },
                    {
                        "id": "obs_6",
                        "label": "It was observed that necessary actions have not been taken to address inappropriate access identified in the review report.",
                        "recommendation": "It is recommended to address all inappropriate access identified during reviews in a timely manner.",
                    },
                    {
                        "id": "obs_7",
                        "label": "It was observed that remaining access which has been considered as appropriate in the report has not been acknowledged by management.",
                        "recommendation": "It is recommended to obtain management acknowledgment that remaining access is appropriate.",
                    },
                ],
            }

            # ── R7 Controls ──
            pci_ctrl_721 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req7_2_id,
                control_id="7.2.1",
                name="Access control model is defined and includes appropriate access",
                description=(
                    "An access control model is defined and includes granting access as follows:\n"
                    "\u2022 Appropriate access depending on the entity\u2019s business and access needs.\n"
                    "\u2022 Access to system components and data resources that is based on users\u2019 job classification and functions.\n"
                    "\u2022 The least privileges required (for example, user, administrator) to perform a job function."
                ),
                requirements_text=(
                    "An access control model is defined and includes granting access as follows:\n"
                    "\u2022 Appropriate access depending on the entity\u2019s business and access needs.\n"
                    "\u2022 Access to system components and data resources that is based on users\u2019 job classification and functions.\n"
                    "\u2022 The least privileges required (for example, user, administrator) to perform a job function."
                ),
                testing_procedures_text=(
                    "7.2.1.a Examine documented policies and procedures and interview personnel to verify the access control model is defined "
                    "in accordance with all elements specified in this requirement.\n\n"
                    "7.2.1.b Examine access control model settings and verify that access needs are appropriately defined in accordance with "
                    "all elements specified in this requirement."
                ),
                check_points_text=(
                    "Ask what is the model being followed when granting user access? E.g. Role-based.\n\n"
                    "If there is a model, check how that has been implemented."
                ),
                assessment_checklist=checklist_721,
            )

            pci_ctrl_722 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req7_2_id,
                control_id="7.2.2",
                name="Access is assigned to users based on job classification and least privileges",
                description=(
                    "Access is assigned to users, including privileged users, based on:\n"
                    "\u2022 Job classification and function.\n"
                    "\u2022 Least privileges necessary to perform job responsibilities."
                ),
                requirements_text=(
                    "Access is assigned to users, including privileged users, based on:\n"
                    "\u2022 Job classification and function.\n"
                    "\u2022 Least privileges necessary to perform job responsibilities."
                ),
                testing_procedures_text=(
                    "7.2.2.a Examine policies and procedures to verify they cover assigning access to users in accordance with all elements "
                    "specified in this requirement.\n\n"
                    "7.2.2.b Examine user access settings, including for privileged users, and interview responsible management personnel "
                    "to verify that privileges assigned are in accordance with all elements specified in this requirement.\n\n"
                    "7.2.2.c Interview personnel responsible for assigning access to verify that privileged user access is assigned in "
                    "accordance with all elements specified in this requirement."
                ),
                check_points_text=(
                    "Check whether there are access control request forms for user creations and modifications for a selected sample of user accounts.\n\n"
                    "Check whether the requested privileges have been assigned to the users as mentioned in the user access request form."
                ),
            )

            pci_ctrl_723 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req7_2_id,
                control_id="7.2.3",
                name="Required privileges are approved by authorized personnel",
                description="Required privileges are approved by authorized personnel.",
                requirements_text="Required privileges are approved by authorized personnel.",
                testing_procedures_text=(
                    "7.2.3.a Examine policies and procedures to verify they define processes for approval of all privileges by authorized personnel.\n\n"
                    "7.2.3.b Examine user IDs and assigned privileges, and compare with documented approvals to verify that:\n"
                    "\u2022 Documented approval exists for the assigned privileges.\n"
                    "\u2022 The approval was by authorized personnel.\n"
                    "\u2022 Specified privileges match the roles assigned to the individual."
                ),
                check_points_text=(
                    "Check whether user access requests have approvals for a selected sample.\n\n"
                    "Check whether the user access requests have been approved by the authorized personnel (check the Access Control policy or procedure)."
                ),
                assessment_checklist=checklist_723,
            )

            pci_ctrl_724 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req7_2_id,
                control_id="7.2.4",
                name="All user accounts and related access privileges are reviewed at least every six months",
                description=(
                    "All user accounts and related access privileges, including third-party/vendor accounts, are reviewed as follows:\n"
                    "\u2022 At least once every six months.\n"
                    "\u2022 To ensure user accounts and access remain appropriate based on job function.\n"
                    "\u2022 Any inappropriate access is addressed.\n"
                    "\u2022 Management acknowledges that access remains appropriate."
                ),
                requirements_text=(
                    "All user accounts and related access privileges, including third-party/vendor accounts, are reviewed as follows:\n"
                    "\u2022 At least once every six months.\n"
                    "\u2022 To ensure user accounts and access remain appropriate based on job function.\n"
                    "\u2022 Any inappropriate access is addressed.\n"
                    "\u2022 Management acknowledges that access remains appropriate."
                ),
                testing_procedures_text=(
                    "7.2.4.a Examine policies and procedures to verify they define processes to review all user accounts and related access privileges, "
                    "including third-party/vendor accounts, in accordance with all elements specified in this requirement.\n\n"
                    "7.2.4.b Interview responsible personnel and examine documented results of periodic reviews of user accounts to verify that all the "
                    "results are in accordance with all elements specified in this requirement."
                ),
                check_points_text=(
                    "Check whether user accounts and privilege reviews are being conducted every six months.\n\n"
                    "If the reviews are conducted, check evidence and documented results of conducted reviews.\n\n"
                    "Check the review results and whether necessary actions have been taken to address any inappropriate access.\n\n"
                    "Check whether management has acknowledged the remaining access."
                ),
                assessment_checklist=checklist_724,
            )

            pci_ctrl_725 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req7_2_id,
                control_id="7.2.5",
                name="All application and system accounts and related access privileges are managed",
                description=(
                    "All application and system accounts and related access privileges are assigned and managed as follows:\n"
                    "\u2022 Based on the least privileges necessary for the operability of the system or application.\n"
                    "\u2022 Access is limited to the systems, applications, or processes that specifically require their use."
                ),
                requirements_text=(
                    "All application and system accounts and related access privileges are assigned and managed as follows:\n"
                    "\u2022 Based on the least privileges necessary for the operability of the system or application.\n"
                    "\u2022 Access is limited to the systems, applications, or processes that specifically require their use."
                ),
                testing_procedures_text=(
                    "7.2.5.a Examine policies and procedures to verify they define processes to manage and assign application and system accounts "
                    "and related access privileges in accordance with all elements specified in this requirement.\n\n"
                    "7.2.5.b Examine privileges associated with system and application accounts and interview responsible personnel to verify that "
                    "application and system accounts and related access privileges are assigned and managed in accordance with all elements specified."
                ),
            )

            pci_ctrl_7251 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req7_2_id,
                control_id="7.2.5.1",
                name="All access by application and system accounts is reviewed periodically",
                description=(
                    "All access by application and system accounts and related access privileges are reviewed as follows:\n"
                    "\u2022 Periodically (at the frequency defined in the entity\u2019s targeted risk analysis).\n"
                    "\u2022 The application/system access remains appropriate for the function being performed.\n"
                    "\u2022 Any inappropriate access is addressed.\n"
                    "\u2022 Management acknowledges that access remains appropriate."
                ),
                requirements_text=(
                    "All access by application and system accounts and related access privileges are reviewed as follows:\n"
                    "\u2022 Periodically (at the frequency defined in the entity\u2019s targeted risk analysis).\n"
                    "\u2022 The application/system access remains appropriate for the function being performed.\n"
                    "\u2022 Any inappropriate access is addressed.\n"
                    "\u2022 Management acknowledges that access remains appropriate."
                ),
                testing_procedures_text=(
                    "7.2.5.1.a Examine policies and procedures to verify they define processes to review all application and system accounts "
                    "and related access privileges in accordance with all elements specified in this requirement.\n\n"
                    "7.2.5.1.b Examine the entity\u2019s targeted risk analysis for the frequency of periodic reviews of application and system accounts "
                    "and related access privileges to verify the risk analysis was performed in accordance with all elements specified in Requirement 12.3.1.\n\n"
                    "7.2.5.1.c Interview responsible personnel and examine documented results of periodic reviews of system and application accounts "
                    "and related privileges to verify that the reviews occur in accordance with all elements specified in this requirement."
                ),
            )

            pci_ctrl_726 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req7_2_id,
                control_id="7.2.6",
                name="All user access to query repositories of stored cardholder data is restricted",
                description=(
                    "All user access to query repositories of stored cardholder data is restricted as follows:\n"
                    "\u2022 Via applications or other programmatic methods, with access and allowed actions based on user roles and least privileges.\n"
                    "\u2022 Only the responsible administrator(s) can directly access or query repositories of stored CHD."
                ),
                requirements_text=(
                    "All user access to query repositories of stored cardholder data is restricted as follows:\n"
                    "\u2022 Via applications or other programmatic methods, with access and allowed actions based on user roles and least privileges.\n"
                    "\u2022 Only the responsible administrator(s) can directly access or query repositories of stored CHD."
                ),
                testing_procedures_text=(
                    "7.2.6.a Examine policies and procedures and interview personnel to verify processes are defined for granting user access to "
                    "query repositories of stored cardholder data, in accordance with all elements specified in this requirement.\n\n"
                    "7.2.6.b Examine configuration settings for querying repositories of stored cardholder data to verify they are in accordance "
                    "with all elements specified in this requirement."
                ),
            )

            pci_ctrl_731 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req7_3_id,
                control_id="7.3.1",
                name="An access control system restricts access based on a user\u2019s need to know",
                description="An access control system(s) is in place that restricts access based on a user\u2019s need to know and covers all system components.",
                requirements_text="An access control system(s) is in place that restricts access based on a user\u2019s need to know and covers all system components.",
                testing_procedures_text=(
                    "7.3.1 Examine vendor documentation and system settings to verify that access is managed for each system component via an access "
                    "control system(s) that restricts access based on a user\u2019s need to know and covers all system components."
                ),
            )

            pci_ctrl_732 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req7_3_id,
                control_id="7.3.2",
                name="Access control system enforces permissions based on job classification and function",
                description="The access control system(s) is configured to enforce permissions assigned to individuals, applications, and systems based on job classification and function.",
                requirements_text="The access control system(s) is configured to enforce permissions assigned to individuals, applications, and systems based on job classification and function.",
                testing_procedures_text=(
                    "7.3.2 Examine vendor documentation and system settings to verify that the access control system(s) is configured to enforce "
                    "permissions assigned to individuals, applications, and systems based on job classification and function."
                ),
            )

            pci_ctrl_733 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req7_3_id,
                control_id="7.3.3",
                name="Access control system is set to deny all by default",
                description="The access control system(s) is set to \u201cdeny all\u201d by default.",
                requirements_text="The access control system(s) is set to \u201cdeny all\u201d by default.",
                testing_procedures_text="7.3.3 Examine vendor documentation and system settings to verify that the access control system(s) is set to \u201cdeny all\u201d by default.",
            )

            r7_controls = [
                pci_ctrl_721, pci_ctrl_722, pci_ctrl_723, pci_ctrl_724,
                pci_ctrl_725, pci_ctrl_7251, pci_ctrl_726,
                pci_ctrl_731, pci_ctrl_732, pci_ctrl_733,
            ]
            db.add_all(r7_controls)
            db.commit()
            print("✓ Seeded PCI DSS V4.0.1 Requirement 7 (7.2.1-7.2.6, 7.2.5.1, 7.3.1-7.3.3)")

            # ── Map R7 controls to existing review_scope types ──
            pci_domain_types = {}
            for dt in db.query(ReviewScopeType).filter(ReviewScopeType.framework_id == pci_id).all():
                pci_domain_types[dt.name] = dt

            dt_srv = pci_domain_types.get("Servers")
            dt_app = pci_domain_types.get("Applications")
            dt_db = pci_domain_types.get("Databases")
            dt_net = pci_domain_types.get("Network")
            dt_sec = pci_domain_types.get("Security Tools")
            dt_eu = pci_domain_types.get("End User Devices")
            dt_oth = pci_domain_types.get("Other Systems")
            dt_gen = pci_domain_types.get("General")

            r7_mappings = []
            all_sys = [dt_srv, dt_app, dt_db, dt_net, dt_sec, dt_oth]
            # 7.2.1: Servers, Apps, DBs, Network, Security, Other
            for dt in all_sys:
                if dt:
                    r7_mappings.append(ControlToReviewScopeMapping(id=uuid.uuid4(),
                        review_scope_type_id=dt.id, framework_control_id=pci_ctrl_721.id))
            # 7.2.3: Servers, Apps, DBs, Network, Security
            for dt in [dt_srv, dt_app, dt_db, dt_net, dt_sec]:
                if dt:
                    r7_mappings.append(ControlToReviewScopeMapping(id=uuid.uuid4(),
                        review_scope_type_id=dt.id, framework_control_id=pci_ctrl_723.id))
            if r7_mappings:
                db.add_all(r7_mappings)
                db.commit()
                print(f"✓ Mapped {len(r7_mappings)} R7 control-to-review_scope mappings")
        else:
            if pci_framework_id:
                print("✓ PCI DSS V4.0.1 Requirement 7 sections already exist")

        # ── Seed PCI DSS Requirement 8 sections/controls (idempotent) ──
        pci_has_req8 = db.query(FrameworkSection).filter(
            FrameworkSection.framework_id == pci_framework_id,
            FrameworkSection.name.like("Requirement 8%"),
        ).count() > 0 if pci_framework_id else True

        if pci_framework_id and not pci_has_req8:
            pci_id = pci_framework_id

            # Requirement 8
            pci_req8_id = uuid.uuid4()
            pci_req8 = FrameworkSection(
                id=pci_req8_id, framework_id=pci_id, parent_section_id=None,
                name="Requirement 8: Identify Users and Authenticate Access to System Components",
                description="Two fundamental principles of identifying and authenticating users are to 1) establish the identity of an individual or process on a computer system, and 2) prove or verify the user associated with the identity is who the user claims to be.",
                order=4,
            )
            db.add(pci_req8)
            db.flush()

            pci_req8_2_id = uuid.uuid4()
            pci_req8_2 = FrameworkSection(
                id=pci_req8_2_id, framework_id=pci_id, parent_section_id=pci_req8_id,
                name="8.2 User Identification and Related Accounts Are Strictly Managed",
                description="User identification and related accounts for users and administrators are strictly managed throughout an account\u2019s lifecycle.",
                order=1,
            )
            pci_req8_3_id = uuid.uuid4()
            pci_req8_3 = FrameworkSection(
                id=pci_req8_3_id, framework_id=pci_id, parent_section_id=pci_req8_id,
                name="8.3 Strong Authentication for Users and Administrators Is Established and Managed",
                description="Strong authentication for users and administrators is established and managed.",
                order=2,
            )
            pci_req8_4_id = uuid.uuid4()
            pci_req8_4 = FrameworkSection(
                id=pci_req8_4_id, framework_id=pci_id, parent_section_id=pci_req8_id,
                name="8.4 Multi-Factor Authentication (MFA) Is Implemented to Secure Access into the CDE",
                description="Multi-factor authentication (MFA) is implemented to secure access into the CDE.",
                order=3,
            )
            pci_req8_5_id = uuid.uuid4()
            pci_req8_5 = FrameworkSection(
                id=pci_req8_5_id, framework_id=pci_id, parent_section_id=pci_req8_id,
                name="8.5 Multi-Factor Authentication (MFA) Systems Are Configured to Prevent Misuse",
                description="Multi-factor authentication (MFA) systems are configured to prevent misuse.",
                order=4,
            )
            pci_req8_6_id = uuid.uuid4()
            pci_req8_6 = FrameworkSection(
                id=pci_req8_6_id, framework_id=pci_id, parent_section_id=pci_req8_id,
                name="8.6 Use of Application and System Accounts Is Strictly Managed",
                description="Use of application and system accounts and associated authentication factors is strictly managed.",
                order=5,
            )
            db.add_all([pci_req8_2, pci_req8_3, pci_req8_4, pci_req8_5, pci_req8_6])
            db.flush()

            # ── R8 Checklists ──
            checklist_821 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "The user IDs seem not unique and unable to uniquely identify the assigned user.",
                        "recommendation": "It is recommended to use unique user IDs when granting access to system components. These user accounts should be regranted or reissued with unique user IDs.",
                    },
                ],
            }

            checklist_822 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that group, shared, or generic accounts are being used.",
                        "recommendation": "It is recommended to use unique user IDs for all users instead of using group, shared, or generic accounts.",
                    },
                    {
                        "id": "obs_2",
                        "label": "Although it is necessary to use group, shared, or generic accounts, these accounts have been granted without approved business justification and not on an exceptional basis, and without establishing accountability for the users to whom they are assigned.",
                        "recommendation": "If the use of group, shared, or generic accounts is required, it is recommended that such accounts be used only with approved business justification, on an exceptional basis (enabled only when required and disabled when not required), and with established accountability for every action performed by the users to whom they are assigned.",
                    },
                ],
            }

            checklist_825 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that there are terminated/resigned users in active status.",
                        "recommendation": "It is recommended to remove or disable terminated/resigned user accounts immediately after the termination/resignation.",
                    },
                ],
            }

            checklist_826 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that there are inactive/dormant user accounts more than 90 days.",
                        "recommendation": "It is recommended to remove or disable inactive user accounts after 90 days.",
                    },
                ],
            }

            checklist_828 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that the idle timeout has not been set.",
                        "recommendation": "It is recommended to set idle timeout to 15 minutes.",
                    },
                    {
                        "id": "obs_2",
                        "label": "The existing idle timeout is XX minutes.",
                        "recommendation": "It is recommended to set idle timeout to 15 minutes.",
                    },
                ],
            }

            checklist_831 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "The user access authentication is not required. The users can just login without an authentication factor.",
                        "recommendation": "It is recommended to configure this system component to validate the authentication factor.",
                    },
                    {
                        "id": "obs_2",
                        "label": "The authentication factor (password) is not authenticated.",
                        "recommendation": "It is recommended to fix the system, or ensure the authentication factor is validated.",
                    },
                ],
            }

            checklist_832 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that the password (authentication factor) is stored in plaintext.",
                        "recommendation": "It is recommended to render the password (authentication factor) unreadable by using strong cryptography such as encryption or hashing.",
                    },
                ],
            }

            checklist_833 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that password changes have been carried out without formal request from the user and proper validation of the user.",
                        "recommendation": "It is recommended to obtain a formal password change request and validate the user who made the request prior to making any changes.",
                    },
                    {
                        "id": "obs_2",
                        "label": "It was observed that password change requests have been performed without formal user validation.",
                        "recommendation": "It is recommended to perform a formal user validation prior to carrying out any password changes.",
                    },
                    {
                        "id": "obs_3",
                        "label": "It was observed that user validations are not conducted before carrying out password changes.",
                        "recommendation": "It is recommended to perform a formal user validation prior to carrying out any password changes.",
                    },
                ],
            }

            checklist_834 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that the account lockout setting has not been set.",
                        "recommendation": "It is recommended to set account lockout to 10 attempts.",
                    },
                    {
                        "id": "obs_2",
                        "label": "The existing account lockout is XX attempts.",
                        "recommendation": "It is recommended to set account lockout to 10 attempts.",
                    },
                    {
                        "id": "obs_3",
                        "label": "It was observed that account lockout duration has not been set.",
                        "recommendation": "It is recommended to set account lockout duration to 30 minutes.",
                    },
                    {
                        "id": "obs_4",
                        "label": "It was observed that account lockout duration is XX minutes.",
                        "recommendation": "It is recommended to set account lockout duration to 30 minutes.",
                    },
                ],
            }

            checklist_835 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that the system component has not been configured to change the password after its first use.",
                        "recommendation": "It is recommended to configure the system component to change the password after its first use or a reset by the administration.",
                    },
                ],
            }

            checklist_836 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that the password length has not been set.",
                        "recommendation": "It is recommended to set password length to 12 characters.",
                    },
                    {
                        "id": "obs_2",
                        "label": "The existing password length is XX characters.",
                        "recommendation": "It is recommended to set password length to 12 characters.",
                    },
                    {
                        "id": "obs_3",
                        "label": "It was observed that password complexity has not been set.",
                        "recommendation": "It is recommended to set password complexity with both numeric, alphabetic, and special characters.",
                    },
                    {
                        "id": "obs_4",
                        "label": "It was observed that password complexity does not require numeric, alphabetic, and special characters.",
                        "recommendation": "It is recommended to set password complexity with both numeric, alphabetic, and special characters.",
                    },
                ],
            }

            checklist_837 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that the password history has not been set.",
                        "recommendation": "It is recommended to set password history to 4.",
                    },
                    {
                        "id": "obs_2",
                        "label": "The existing password history is XX previous passwords.",
                        "recommendation": "It is recommended to set password history to 4.",
                    },
                ],
            }

            checklist_839 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that the password expiry has not been set. Therefore passwords are not expired.",
                        "recommendation": "It is recommended to set password expiry to 90 days.",
                    },
                    {
                        "id": "obs_2",
                        "label": "The existing password expiry period is XX days.",
                        "recommendation": "It is recommended to set password expiry to 90 days.",
                    },
                ],
            }

            checklist_8311 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was informed that there are security tokens, smart cards, or certificates shared among multiple users.",
                        "recommendation": "It is recommended to have unique security tokens, smart cards, or certificates for each user instead of sharing among multiple users.",
                    },
                ],
            }

            checklist_842 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was informed that MFA has not been implemented for this system component.",
                        "recommendation": "It is necessary to implement MFA for all access to in-scope system components.",
                    },
                ],
            }

            checklist_843 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that MFA is not available for remote access originating from outside the entity\u2019s network.",
                        "recommendation": "It is necessary to implement MFA for all (including administrators, users, and vendors) remote network access originating from outside the entity\u2019s network.",
                    },
                    {
                        "id": "obs_2",
                        "label": "It was observed that MFA is not available for remote access originating from outside the entity\u2019s network for administrators.",
                        "recommendation": "It is necessary to implement MFA for all (including administrators, users, and vendors) remote network access originating from outside the entity\u2019s network.",
                    },
                    {
                        "id": "obs_3",
                        "label": "It was observed that MFA is not available for remote access originating from outside the entity\u2019s network for users.",
                        "recommendation": "It is necessary to implement MFA for all (including administrators, users, and vendors) remote network access originating from outside the entity\u2019s network.",
                    },
                    {
                        "id": "obs_4",
                        "label": "It was observed that MFA is not available for remote access originating from outside the entity\u2019s network for vendors/third-party service providers.",
                        "recommendation": "It is necessary to implement MFA for all (including administrators, users, and vendors) remote network access originating from outside the entity\u2019s network.",
                    },
                ],
            }

            checklist_851 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that administrators/users can bypass the MFA when accessing following system components.",
                        "recommendation": "It is recommended to configure the MFA system in a manner that users/administrators are not possible to bypass.",
                    },
                    {
                        "id": "obs_2",
                        "label": "It was informed that there are business requirements that users/administrators are required to bypass the MFA in some situations. However, there was no documented business justification with management approval.",
                        "recommendation": "If there is/are business requirement(s) to bypass MFA, the requirement should be documented and management approval should be obtained.",
                    },
                    {
                        "id": "obs_3",
                        "label": "It was observed that MFA is also the same type as the original authentication factor.",
                        "recommendation": "It is recommended to use a different type of authentication factor from the second authentication factor.",
                    },
                    {
                        "id": "obs_4",
                        "label": "Although MFA is enabled, it is not functioning as expected. It is possible to access following systems without MFA or before MFA authentication is completed.",
                        "recommendation": "It is recommended to identify the root cause and immediately fix the issue and ensure access is granted once all the factors are authenticated.",
                    },
                    {
                        "id": "obs_5",
                        "label": "It was observed that following lapses in the configurations of the MFA solution make it susceptible to replay attacks.",
                        "recommendation": "It is recommended to address the configuration lapses to ensure the MFA system is not susceptible to replay attacks.",
                    },
                ],
            }

            checklist_861 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that there are system/application accounts which are being used for interactive logins. However, these accounts do not have documented business justification with management approval.",
                        "recommendation": "If system/application accounts are used for interactive logins, it is recommended to have business justifications with management approval, use on an exceptional basis, and implement administrative controls to establish accountability for every action performed.",
                    },
                    {
                        "id": "obs_2",
                        "label": "It was observed and informed that these accounts are used as part of routine business operations rather than being restricted to exceptional circumstances with appropriate business justification and prior approval.",
                        "recommendation": "It is recommended to limit use of system/application accounts only for exceptional circumstances with appropriate business justification and prior approval.",
                    },
                    {
                        "id": "obs_3",
                        "label": "It was informed that there are no administrative processes to confirm user identity and to establish accountability.",
                        "recommendation": "If system/application accounts are used for interactive logins, it is recommended to implement appropriate administrative controls to confirm user identity and establish accountability for every action performed by the users to whom they are assigned.",
                    },
                ],
            }

            checklist_862 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was observed that following passwords of system/application accounts have been hardcoded.",
                        "recommendation": "It is recommended to avoid hardcoding passwords in any script, configuration/property file, or bespoke and custom source code. Instead, store them using strong cryptography. For example, consider password vaults or other system-managed controls.",
                    },
                ],
            }

            checklist_863 = {
                "type": "observations",
                "observations": [
                    {
                        "id": "obs_1",
                        "label": "It was informed that the system/application account passwords are not changed. It was observed that the password expiry has not been set.",
                        "recommendation": "It is recommended to change the passwords periodically (at the frequency defined in the entity\u2019s targeted risk analysis).",
                    },
                    {
                        "id": "obs_2",
                        "label": "Although the passwords of system/application accounts are changed, there is no TRA to justify the current frequency of changing passwords.",
                        "recommendation": "It is recommended to have a TRA for the frequency of changing system/application account passwords.",
                    },
                    {
                        "id": "obs_3",
                        "label": "The existing password expiry period is XX days. It is not complied with minimum requirements for the frequency of changing passwords.",
                        "recommendation": "It is recommended to change system/application account passwords in a defined frequency which is less than the minimum requirement.",
                    },
                    {
                        "id": "obs_4",
                        "label": "It was observed that password complexity has not been set for system/application accounts.",
                        "recommendation": "It is recommended to set password complexity with both numeric, alphabetic, and special characters.",
                    },
                ],
            }

            # ── R8 Controls: Section 8.2 ──
            pci_ctrl_821 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_2_id,
                control_id="8.2.1",
                name="All users are assigned a unique ID",
                description="All users are assigned a unique ID before access to system components or cardholder data is allowed.",
                requirements_text="All users are assigned a unique ID before access to system components or cardholder data is allowed.",
                testing_procedures_text=(
                    "8.2.1.a Interview responsible personnel to verify that all users are assigned a unique ID for access to system components and cardholder data.\n\n"
                    "8.2.1.b Examine audit logs and other evidence to verify that access to system components and cardholder data can be uniquely identified and associated with individuals."
                ),
                check_points_text="Obtain user list of the system component.\nCheck whether unique user IDs have been assigned.",
                assessment_checklist=checklist_821,
            )

            pci_ctrl_822 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_2_id,
                control_id="8.2.2",
                name="Group, shared, or generic accounts are only used when necessary",
                description=(
                    "Group, shared, or generic accounts, or other shared authentication credentials are only used when necessary on an exception basis, and are managed as follows:\n"
                    "\u2022 Account use is prevented unless needed for an exceptional circumstance.\n"
                    "\u2022 Use is limited to the time needed for the exceptional circumstance.\n"
                    "\u2022 Business justification for use is documented.\n"
                    "\u2022 Use is explicitly approved by management.\n"
                    "\u2022 Individual user identity is confirmed before access to an account is granted.\n"
                    "\u2022 Every action taken is attributable to an individual user."
                ),
                requirements_text=(
                    "Group, shared, or generic accounts, or other shared authentication credentials are only used when necessary on an exception basis."
                ),
                testing_procedures_text=(
                    "8.2.2.a Examine user account lists on system components and applicable documentation to verify that shared authentication credentials "
                    "are only used when necessary, on an exception basis, and are managed in accordance with all elements specified in this requirement.\n\n"
                    "8.2.2.b Examine authentication policies and procedures to verify processes are defined for shared authentication credentials.\n\n"
                    "8.2.2.c Interview system administrators to verify that shared authentication credentials are only used when necessary, on an exception basis."
                ),
                check_points_text=(
                    "Obtain user list of the system component.\n"
                    "Check whether there are group, shared, or generic accounts, or other shared authentication credentials.\n"
                    "If there are group, shared, or generic accounts, check how often these accounts are used (only in exceptional circumstances).\n"
                    "If there are group, shared, or generic accounts, check whether there is a business justification.\n"
                    "Check whether there are administrative controls implemented to make an individual user accountable for such accounts before access is granted."
                ),
                assessment_checklist=checklist_822,
            )

            pci_ctrl_823 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_2_id,
                control_id="8.2.3",
                name="Service providers use unique authentication factors for each customer premises",
                description="Additional requirement for service providers only: Service providers with remote access to customer premises use unique authentication factors for each customer premises.",
                requirements_text="Service providers with remote access to customer premises use unique authentication factors for each customer premises.",
                testing_procedures_text=(
                    "8.2.3 Additional testing procedure for service provider assessments only: Examine authentication policies and procedures and interview "
                    "personnel to verify that service providers with remote access to customer premises use unique authentication factors for remote access to each customer premises."
                ),
            )

            pci_ctrl_824 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_2_id,
                control_id="8.2.4",
                name="Addition, deletion, and modification of user IDs are managed",
                description=(
                    "Addition, deletion, and modification of user IDs, authentication factors, and other identifier objects are managed as follows:\n"
                    "\u2022 Authorized with the appropriate approval.\n"
                    "\u2022 Implemented with only the privileges specified on the documented approval."
                ),
                requirements_text=(
                    "Addition, deletion, and modification of user IDs, authentication factors, and other identifier objects are managed as follows:\n"
                    "\u2022 Authorized with the appropriate approval.\n"
                    "\u2022 Implemented with only the privileges specified on the documented approval."
                ),
                testing_procedures_text=(
                    "8.2.4 Examine documented authorizations across various phases of the account lifecycle (additions, modifications, and deletions) "
                    "and examine system settings to verify the activity has been managed in accordance with all elements specified in this requirement."
                ),
            )

            pci_ctrl_825 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_2_id,
                control_id="8.2.5",
                name="Access for terminated users is immediately revoked",
                description="Access for terminated users is immediately revoked.",
                requirements_text="Access for terminated users is immediately revoked.",
                testing_procedures_text=(
                    "8.2.5.a Examine information sources for terminated users and review current user access lists\u2014for both local and remote access\u2014"
                    "to verify that terminated user IDs have been deactivated or removed from the access lists.\n\n"
                    "8.2.5.b Interview responsible personnel to verify that all physical authentication factors\u2014such as smart cards, tokens, etc.\u2014"
                    "have been returned or deactivated for terminated users."
                ),
                check_points_text=(
                    "Obtain user list in the system component and compare with HR list.\n"
                    "Check whether there are terminated/resigned users in active status."
                ),
                assessment_checklist=checklist_825,
            )

            pci_ctrl_826 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_2_id,
                control_id="8.2.6",
                name="Inactive user accounts are removed or disabled within 90 days",
                description="Inactive user accounts are removed or disabled within 90 days of inactivity.",
                requirements_text="Inactive user accounts are removed or disabled within 90 days of inactivity.",
                testing_procedures_text=(
                    "8.2.6 Examine user accounts and last logon information, and interview personnel to verify that any inactive user accounts "
                    "are removed or disabled within 90 days of inactivity."
                ),
                check_points_text=(
                    "Obtain user list in the system component and check last login details.\n"
                    "Check whether there are inactive users more than 90 days."
                ),
                assessment_checklist=checklist_826,
            )

            pci_ctrl_827 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_2_id,
                control_id="8.2.7",
                name="Third-party remote access accounts are managed",
                description=(
                    "Accounts used by third parties to access, support, or maintain system components via remote access are managed as follows:\n"
                    "\u2022 Enabled only during the time period needed and disabled when not in use.\n"
                    "\u2022 Use is monitored for unexpected activity."
                ),
                requirements_text=(
                    "Accounts used by third parties to access, support, or maintain system components via remote access are managed as follows:\n"
                    "\u2022 Enabled only during the time period needed and disabled when not in use.\n"
                    "\u2022 Use is monitored for unexpected activity."
                ),
                testing_procedures_text=(
                    "8.2.7 Interview personnel, examine documentation for managing accounts, and examine evidence to verify that accounts used by "
                    "third parties for remote access are managed according to all elements specified in this requirement."
                ),
                check_points_text=(
                    "Obtain user list in the system component and check last login details.\n"
                    "Ask whether there are user accounts used by third parties.\n"
                    "Check how vendor access is granted. Check whether the user account is activated and enabled only during the time period needed and disabled when not in use.\n"
                    "Check whether vendor access is monitored. Ask how they monitor vendor access (e.g., through PAM)."
                ),
            )

            pci_ctrl_828 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_2_id,
                control_id="8.2.8",
                name="Session idle timeout is set to 15 minutes or less",
                description="If a user session has been idle for more than 15 minutes, the user is required to re-authenticate to re-activate the terminal or session.",
                requirements_text="If a user session has been idle for more than 15 minutes, the user is required to re-authenticate to re-activate the terminal or session.",
                testing_procedures_text=(
                    "8.2.8 Examine system configuration settings to verify that system/session idle timeout features for user sessions have been set to 15 minutes or less."
                ),
                check_points_text="Check idle timeout settings.",
                assessment_checklist=checklist_828,
            )

            # ── R8 Controls: Section 8.3 ──
            pci_ctrl_831 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_3_id,
                control_id="8.3.1",
                name="All user access is authenticated via at least one authentication factor",
                description=(
                    "All user access to system components for users and administrators is authenticated via at least one of the following authentication factors:\n"
                    "\u2022 Something you know, such as a password or passphrase.\n"
                    "\u2022 Something you have, such as a token device or smart card.\n"
                    "\u2022 Something you are, such as a biometric element."
                ),
                requirements_text=(
                    "All user access to system components is authenticated via at least one authentication factor."
                ),
                testing_procedures_text=(
                    "8.3.1.a Examine documentation describing the authentication factor(s) used to verify that user access to system components "
                    "is authenticated via at least one authentication factor specified in this requirement.\n\n"
                    "8.3.1.b For each type of authentication factor used with each type of system component, observe an authentication to verify "
                    "that authentication is functioning consistently with documented authentication factor(s)."
                ),
                check_points_text=(
                    "Check whether authentication is required. Check whether the user can just login by entering the user name without a password.\n"
                    "Check whether the user access is authenticated via any means (e.g., Password, Smartcard, Biometric).\n"
                    "Check whether the authentication is working."
                ),
                assessment_checklist=checklist_831,
            )

            pci_ctrl_832 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_3_id,
                control_id="8.3.2",
                name="Strong cryptography renders all authentication factors unreadable",
                description="Strong cryptography is used to render all authentication factors unreadable during transmission and storage on all system components.",
                requirements_text="Strong cryptography is used to render all authentication factors unreadable during transmission and storage on all system components.",
                testing_procedures_text=(
                    "8.3.2.a Examine vendor documentation and system configuration settings to verify that authentication factors are rendered unreadable "
                    "with strong cryptography during transmission and storage.\n\n"
                    "8.3.2.b Examine repositories of authentication factors to verify that they are unreadable during storage.\n\n"
                    "8.3.2.c Examine data transmissions to verify that authentication factors are unreadable during transmission."
                ),
                check_points_text=(
                    "Check how authentication factors are stored: whether encrypted/hashed or plaintext.\n"
                    "Check whether authentication factors are unreadable during transmission."
                ),
                assessment_checklist=checklist_832,
            )

            pci_ctrl_833 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_3_id,
                control_id="8.3.3",
                name="User identity is verified before modifying any authentication factor",
                description="User identity is verified before modifying any authentication factor.",
                requirements_text="User identity is verified before modifying any authentication factor.",
                testing_procedures_text=(
                    "8.3.3 Examine procedures for modifying authentication factors and observe security personnel to verify that when a user requests "
                    "a modification of an authentication factor, the user\u2019s identity is verified before the authentication factor is modified."
                ),
                check_points_text=(
                    "Check how password changes take place. Whether it is self-service. What is the process.\n"
                    "Check formal requests and user verification processes followed prior to carrying out any changes.\n"
                    "Check a sample of password changes."
                ),
                assessment_checklist=checklist_833,
            )

            pci_ctrl_834 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_3_id,
                control_id="8.3.4",
                name="Invalid authentication attempts are limited",
                description=(
                    "Invalid authentication attempts are limited by:\n"
                    "\u2022 Locking out the user ID after not more than 10 attempts.\n"
                    "\u2022 Setting the lockout duration to a minimum of 30 minutes or until the user\u2019s identity is confirmed."
                ),
                requirements_text=(
                    "Invalid authentication attempts are limited by:\n"
                    "\u2022 Locking out the user ID after not more than 10 attempts.\n"
                    "\u2022 Setting the lockout duration to a minimum of 30 minutes or until the user\u2019s identity is confirmed."
                ),
                testing_procedures_text=(
                    "8.3.4.a Examine system configuration settings to verify that authentication parameters are set to require that user accounts "
                    "be locked out after not more than 10 invalid logon attempts.\n\n"
                    "8.3.4.b Examine system configuration settings to verify that password parameters are set to require that once a user account is "
                    "locked out, it remains locked for a minimum of 30 minutes or until the user\u2019s identity is confirmed."
                ),
                check_points_text="Check account lockout settings.\nCheck account lockout duration.",
                assessment_checklist=checklist_834,
            )

            pci_ctrl_835 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_3_id,
                control_id="8.3.5",
                name="Passwords are set to unique value for first-time use and forced to change",
                description=(
                    "If passwords/passphrases are used as authentication factors to meet Requirement 8.3.1, they are set and reset for each user as follows:\n"
                    "\u2022 Set to a unique value for first-time use and upon reset.\n"
                    "\u2022 Forced to be changed immediately after the first use."
                ),
                requirements_text=(
                    "Passwords/passphrases are set and reset for each user as follows:\n"
                    "\u2022 Set to a unique value for first-time use and upon reset.\n"
                    "\u2022 Forced to be changed immediately after the first use."
                ),
                testing_procedures_text=(
                    "8.3.5 Examine procedures for setting and resetting passwords/passphrases and observe security personnel to verify that "
                    "passwords/passphrases are set and reset in accordance with all elements specified in this requirement."
                ),
                check_points_text="Check whether the system component has been configured to reset password immediately after first use.",
                assessment_checklist=checklist_835,
            )

            pci_ctrl_836 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_3_id,
                control_id="8.3.6",
                name="Passwords meet minimum complexity requirements",
                description=(
                    "If passwords/passphrases are used as authentication factors, they meet the following minimum level of complexity:\n"
                    "\u2022 A minimum length of 12 characters (or if the system does not support 12 characters, a minimum length of eight characters).\n"
                    "\u2022 Contain both numeric and alphabetic characters."
                ),
                requirements_text=(
                    "Passwords/passphrases meet the following minimum level of complexity:\n"
                    "\u2022 A minimum length of 12 characters.\n"
                    "\u2022 Contain both numeric and alphabetic characters."
                ),
                testing_procedures_text=(
                    "8.3.6 Examine system configuration settings to verify that user password/passphrase complexity parameters are set in "
                    "accordance with all elements specified in this requirement."
                ),
                check_points_text="Check the password length and the complexity.",
                assessment_checklist=checklist_836,
            )

            pci_ctrl_837 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_3_id,
                control_id="8.3.7",
                name="New passwords cannot be the same as last four passwords",
                description="Individuals are not allowed to submit a new password/passphrase that is the same as any of the last four passwords/passphrases used.",
                requirements_text="Individuals are not allowed to submit a new password/passphrase that is the same as any of the last four passwords/passphrases used.",
                testing_procedures_text=(
                    "8.3.7 Examine system configuration settings to verify that password parameters are set to require that new passwords/passphrases "
                    "cannot be the same as the four previously used passwords/passphrases."
                ),
                check_points_text="Check the password history.",
                assessment_checklist=checklist_837,
            )

            pci_ctrl_838 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_3_id,
                control_id="8.3.8",
                name="Authentication policies and procedures are documented and communicated",
                description=(
                    "Authentication policies and procedures are documented and communicated to all users including:\n"
                    "\u2022 Guidance on selecting strong authentication factors.\n"
                    "\u2022 Guidance for how users should protect their authentication factors.\n"
                    "\u2022 Instructions not to reuse previously used passwords/passphrases.\n"
                    "\u2022 Instructions to change passwords/passphrases if there is any suspicion or knowledge that they have been compromised."
                ),
                requirements_text="Authentication policies and procedures are documented and communicated to all users.",
                testing_procedures_text=(
                    "8.3.8.a Examine procedures and interview personnel to verify that authentication policies and procedures are distributed to all users.\n\n"
                    "8.3.8.b Review authentication policies and procedures that are distributed to users and verify they include the elements specified.\n\n"
                    "8.3.8.c Interview users to verify that they are familiar with authentication policies and procedures."
                ),
            )

            pci_ctrl_839 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_3_id,
                control_id="8.3.9",
                name="Passwords are changed at least once every 90 days or dynamic analysis is used",
                description=(
                    "If passwords/passphrases are used as the only authentication factor for user access then either:\n"
                    "\u2022 Passwords/passphrases are changed at least once every 90 days,\nOR\n"
                    "\u2022 The security posture of accounts is dynamically analyzed, and real-time access to resources is automatically determined accordingly."
                ),
                requirements_text=(
                    "Passwords/passphrases are changed at least once every 90 days, or the security posture of accounts is dynamically analyzed."
                ),
                testing_procedures_text=(
                    "8.3.9 If passwords/passphrases are used as the only authentication factor for user access, inspect system configuration settings "
                    "to verify that passwords/passphrases are managed in accordance with ONE of the elements specified in this requirement."
                ),
                check_points_text="Check the password expiry period.",
                assessment_checklist=checklist_839,
            )

            pci_ctrl_8310 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_3_id,
                control_id="8.3.10",
                name="Service providers provide guidance to customer users on password changes",
                description=(
                    "Additional requirement for service providers only: If passwords/passphrases are used as the only authentication factor for "
                    "customer user access, then guidance is provided to customer users."
                ),
                requirements_text="Service provider guidance to customer users on password management.",
                testing_procedures_text=(
                    "8.3.10 Additional testing procedure for service provider assessments only: If passwords/passphrases are used as the only "
                    "authentication factor for customer user access to cardholder data, examine guidance provided to customer users."
                ),
            )

            pci_ctrl_83101 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_3_id,
                control_id="8.3.10.1",
                name="Service providers enforce customer password expiry or dynamic analysis",
                description=(
                    "Additional requirement for service providers only: If passwords/passphrases are used as the only authentication factor for "
                    "customer user access then either passwords are changed every 90 days or dynamic analysis is used."
                ),
                requirements_text="Service provider enforcement of customer password management.",
                testing_procedures_text=(
                    "8.3.10.1 Additional testing procedure for service provider assessments only."
                ),
            )

            pci_ctrl_8311 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_3_id,
                control_id="8.3.11",
                name="Authentication factors are assigned to individual users and not shared",
                description=(
                    "Where authentication factors such as physical or logical security tokens, smart cards, or certificates are used:\n"
                    "\u2022 Factors are assigned to an individual user and not shared among multiple users.\n"
                    "\u2022 Physical and/or logical controls ensure only the intended user can use that factor to gain access."
                ),
                requirements_text=(
                    "Authentication factors such as tokens, smart cards, or certificates are assigned to individual users and not shared."
                ),
                testing_procedures_text=(
                    "8.3.11.a Examine authentication policies and procedures to verify that procedures for using authentication factors are defined.\n\n"
                    "8.3.11.b Interview security personnel to verify authentication factors are assigned to an individual user and not shared.\n\n"
                    "8.3.11.c Examine system configuration settings and/or observe physical controls to verify that only the intended user can use that factor."
                ),
                check_points_text=(
                    "Ask whether any other authentication factors such as physical or logical security tokens, smart cards, or certificates are used. If not, this will not be applicable.\n"
                    "If used, check whether such authentication factors are shared among multiple users."
                ),
                assessment_checklist=checklist_8311,
            )

            # ── R8 Controls: Section 8.4 ──
            pci_ctrl_841 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_4_id,
                control_id="8.4.1",
                name="MFA is implemented for all non-console access into the CDE for admin users",
                description="MFA is implemented for all non-console access into the CDE for personnel with administrative access.",
                requirements_text="MFA is implemented for all non-console access into the CDE for personnel with administrative access.",
                testing_procedures_text=(
                    "8.4.1.a Examine network and/or system configurations to verify MFA is required for all non-console access into the CDE for personnel with administrative access.\n\n"
                    "8.4.1.b Observe administrator personnel logging into the CDE and verify that MFA is required."
                ),
            )

            pci_ctrl_842 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_4_id,
                control_id="8.4.2",
                name="MFA is implemented for all access into the CDE",
                description="MFA is implemented for all access into the CDE.",
                requirements_text="MFA is implemented for all access into the CDE.",
                testing_procedures_text=(
                    "8.4.2.a Examine network and/or system configurations to verify MFA is implemented for all access into the CDE.\n\n"
                    "8.4.2.b Observe personnel logging in to the CDE and examine evidence to verify that MFA is required."
                ),
                check_points_text="If this is a PCI DSS in-scope system component, check whether MFA has been implemented.",
                assessment_checklist=checklist_842,
            )

            pci_ctrl_843 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_4_id,
                control_id="8.4.3",
                name="MFA is implemented for all remote network access from outside the entity\u2019s network",
                description=(
                    "MFA is implemented for all remote network access originating from outside the entity\u2019s network that could access or impact the CDE as follows:\n"
                    "\u2022 All remote access by all personnel, both users and administrators, originating from outside the entity\u2019s network.\n"
                    "\u2022 All remote access by third parties and vendors."
                ),
                requirements_text="MFA is implemented for all remote network access originating from outside the entity\u2019s network.",
                testing_procedures_text=(
                    "8.4.3.a Examine network and/or system configurations for remote access servers and systems to verify MFA is required "
                    "in accordance with all elements specified in this requirement.\n\n"
                    "8.4.3.b Observe personnel connecting remotely from outside the entity\u2019s network and verify that multi-factor authentication is required."
                ),
                check_points_text=(
                    "Check whether multifactor authentication is implemented for all types (e.g., VPN) of remote access.\n"
                    "Check whether administrators are required.\n"
                    "Check whether normal users are required.\n"
                    "Check whether vendors/third parties are required."
                ),
                assessment_checklist=checklist_843,
            )

            # ── R8 Controls: Section 8.5 ──
            pci_ctrl_851 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_5_id,
                control_id="8.5.1",
                name="MFA systems are implemented to prevent misuse",
                description=(
                    "MFA systems are implemented as follows:\n"
                    "\u2022 The MFA system is not susceptible to replay attacks.\n"
                    "\u2022 MFA systems cannot be bypassed by any users, including administrative users unless specifically documented and authorized.\n"
                    "\u2022 At least two different types of authentication factors are used.\n"
                    "\u2022 Success of all authentication factors is required before access is granted."
                ),
                requirements_text="MFA systems are implemented to prevent misuse and are not susceptible to replay attacks.",
                testing_procedures_text=(
                    "8.5.1.a Examine vendor system documentation to verify that the MFA system is not susceptible to replay attacks.\n\n"
                    "8.5.1.b Examine system configurations for the MFA implementation to verify it is configured in accordance with all elements.\n\n"
                    "8.5.1.c Interview responsible personnel and observe processes to verify that any requests to bypass MFA are specifically documented and authorized.\n\n"
                    "8.5.1.d Observe personnel logging into system components in the CDE to verify that access is granted only after all authentication factors are successful.\n\n"
                    "8.5.1.e Observe personnel connecting remotely to verify that access is granted only after all authentication factors are successful."
                ),
                check_points_text=(
                    "Check whether MFA system cannot be bypassed by any users, including administrative users.\n"
                    "If it is possible to bypass, check whether there is any business justification with management approval.\n"
                    "Check whether the type of MFA is different from the original authentication factor (e.g., Original: Password, MFA: OTP).\n"
                    "Check whether the access is allowed after all authentication factors are successful.\n"
                    "Check whether the MFA system is not susceptible to replay attacks."
                ),
                assessment_checklist=checklist_851,
            )

            # ── R8 Controls: Section 8.6 ──
            pci_ctrl_861 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_6_id,
                control_id="8.6.1",
                name="Interactive use of system/application accounts is managed",
                description=(
                    "If accounts used by systems or applications can be used for interactive login, they are managed as follows:\n"
                    "\u2022 Interactive use is prevented unless needed for an exceptional circumstance.\n"
                    "\u2022 Interactive use is limited to the time needed for the exceptional circumstance.\n"
                    "\u2022 Business justification for interactive use is documented.\n"
                    "\u2022 Interactive use is explicitly approved by management.\n"
                    "\u2022 Individual user identity is confirmed before access to account is granted.\n"
                    "\u2022 Every action taken is attributable to an individual user."
                ),
                requirements_text="Interactive use of system/application accounts is strictly managed.",
                testing_procedures_text=(
                    "8.6.1 Examine application and system accounts that can be used interactively and interview administrative personnel to verify "
                    "that application and system accounts are managed in accordance with all elements specified in this requirement."
                ),
                check_points_text=(
                    "Check whether there are interactive user accounts. Ask whether there are user accounts used for interactive logins.\n"
                    "If there are interactive user accounts, check whether business justifications with management approvals are available.\n"
                    "Check whether these accounts are used on an exceptional basis.\n"
                    "Check how user identity is confirmed and accountability is managed."
                ),
                assessment_checklist=checklist_861,
            )

            pci_ctrl_862 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_6_id,
                control_id="8.6.2",
                name="Passwords for system/application accounts are not hardcoded",
                description=(
                    "Passwords/passphrases for any application and system accounts that can be used for interactive login are not hard coded "
                    "in scripts, configuration/property files, or bespoke and custom source code."
                ),
                requirements_text="Passwords for system/application accounts are not hardcoded in scripts or configuration files.",
                testing_procedures_text=(
                    "8.6.2.a Interview personnel and examine system development procedures to verify that processes are defined specifying that "
                    "passwords/passphrases are not hard coded.\n\n"
                    "8.6.2.b Examine scripts, configuration/property files, and bespoke and custom source code to verify passwords/passphrases are not present."
                ),
                check_points_text=(
                    "Check how passwords of system/application accounts are handled/stored.\n"
                    "Check whether such passwords are hardcoded in scripts, configuration/property files, or bespoke and custom source code.\n"
                    "Check whether such passwords are stored using strong cryptography."
                ),
                assessment_checklist=checklist_862,
            )

            pci_ctrl_863 = FrameworkControl(
                id=uuid.uuid4(), framework_section_id=pci_req8_6_id,
                control_id="8.6.3",
                name="Passwords for system/application accounts are protected against misuse",
                description=(
                    "Passwords/passphrases for any application and system accounts are protected against misuse as follows:\n"
                    "\u2022 Passwords/passphrases are changed periodically (at the frequency defined in the entity\u2019s targeted risk analysis).\n"
                    "\u2022 Passwords/passphrases are constructed with sufficient complexity appropriate for how frequently the entity changes them."
                ),
                requirements_text="Passwords for system/application accounts are changed periodically and constructed with sufficient complexity.",
                testing_procedures_text=(
                    "8.6.3.a Examine policies and procedures to verify that procedures are defined to protect passwords/passphrases for application "
                    "or system accounts against misuse.\n\n"
                    "8.6.3.b Examine the entity\u2019s targeted risk analysis for the change frequency and complexity for passwords/passphrases used "
                    "for interactive login to application and system accounts.\n\n"
                    "8.6.3.c Interview responsible personnel and examine system configuration settings to verify that passwords/passphrases are "
                    "protected against misuse in accordance with all elements specified."
                ),
                check_points_text=(
                    "Check how frequently the system/application account passwords are changed.\n"
                    "Check whether there is a TRA for changing passwords of system/application accounts.\n"
                    "Check the system/application account password complexities."
                ),
                assessment_checklist=checklist_863,
            )

            r8_controls = [
                pci_ctrl_821, pci_ctrl_822, pci_ctrl_823, pci_ctrl_824, pci_ctrl_825, pci_ctrl_826, pci_ctrl_827, pci_ctrl_828,
                pci_ctrl_831, pci_ctrl_832, pci_ctrl_833, pci_ctrl_834, pci_ctrl_835, pci_ctrl_836, pci_ctrl_837, pci_ctrl_838,
                pci_ctrl_839, pci_ctrl_8310, pci_ctrl_83101, pci_ctrl_8311,
                pci_ctrl_841, pci_ctrl_842, pci_ctrl_843,
                pci_ctrl_851,
                pci_ctrl_861, pci_ctrl_862, pci_ctrl_863,
            ]
            db.add_all(r8_controls)
            db.commit()
            print("✓ Seeded PCI DSS V4.0.1 Requirement 8 (8.2.1-8.2.8, 8.3.1-8.3.11, 8.4.1-8.4.3, 8.5.1, 8.6.1-8.6.3)")

            # ── Map R8 controls to existing review_scope types ──
            pci_domain_types = {}
            for dt in db.query(ReviewScopeType).filter(ReviewScopeType.framework_id == pci_id).all():
                pci_domain_types[dt.name] = dt

            dt_srv = pci_domain_types.get("Servers")
            dt_app = pci_domain_types.get("Applications")
            dt_db = pci_domain_types.get("Databases")
            dt_net = pci_domain_types.get("Network")
            dt_sec = pci_domain_types.get("Security Tools")
            dt_eu = pci_domain_types.get("End User Devices")
            dt_oth = pci_domain_types.get("Other Systems")

            r8_mappings = []
            all_7 = [dt_srv, dt_app, dt_db, dt_net, dt_sec, dt_eu, dt_oth]
            no_eu = [dt_srv, dt_app, dt_db, dt_net, dt_sec, dt_oth]

            # Controls mapped to all 7 review_scopes: 8.2.1, 8.2.2, 8.2.5, 8.2.6, 8.2.8, 8.3.1-8.3.7, 8.3.9, 8.3.11
            ctrls_all7 = [
                pci_ctrl_821, pci_ctrl_822, pci_ctrl_825, pci_ctrl_826, pci_ctrl_828,
                pci_ctrl_831, pci_ctrl_832, pci_ctrl_833, pci_ctrl_834, pci_ctrl_835,
                pci_ctrl_836, pci_ctrl_837, pci_ctrl_839, pci_ctrl_8311,
            ]
            for ctrl in ctrls_all7:
                for dt in all_7:
                    if dt:
                        r8_mappings.append(ControlToReviewScopeMapping(id=uuid.uuid4(),
                            review_scope_type_id=dt.id, framework_control_id=ctrl.id))

            # Controls mapped to 6 review_scopes (no End User): 8.4.2, 8.4.3, 8.5.1, 8.6.1, 8.6.3
            ctrls_no_eu = [pci_ctrl_842, pci_ctrl_843, pci_ctrl_851, pci_ctrl_861, pci_ctrl_863]
            for ctrl in ctrls_no_eu:
                for dt in no_eu:
                    if dt:
                        r8_mappings.append(ControlToReviewScopeMapping(id=uuid.uuid4(),
                            review_scope_type_id=dt.id, framework_control_id=ctrl.id))

            # 8.6.2: Apps, DBs, Security, Other
            for dt in [dt_app, dt_db, dt_sec, dt_oth]:
                if dt:
                    r8_mappings.append(ControlToReviewScopeMapping(id=uuid.uuid4(),
                        review_scope_type_id=dt.id, framework_control_id=pci_ctrl_862.id))

            if r8_mappings:
                db.add_all(r8_mappings)
                db.commit()
                print(f"✓ Mapped {len(r8_mappings)} R8 control-to-review_scope mappings")
        else:
            if pci_framework_id:
                print("✓ PCI DSS V4.0.1 Requirement 8 sections already exist")

        # ── Seed ReviewScopeType + ControlToReviewScopeMapping for PCI DSS ──
        pci_has_domain_types = db.query(ReviewScopeType).filter(
            ReviewScopeType.framework_id == pci_framework_id
        ).count() > 0 if pci_framework_id else True

        if pci_framework_id and not pci_has_domain_types:
            # Get control records from DB (handles both fresh-seed and re-seed)
            pci_controls = {}
            for ctrl in db.query(FrameworkControl).join(FrameworkSection).filter(
                FrameworkSection.framework_id == pci_framework_id
            ).all():
                pci_controls[ctrl.control_id] = ctrl

            dt_servers = ReviewScopeType(id=uuid.uuid4(), framework_id=pci_framework_id,
                name="Servers", description="Physical and virtual servers", sort_order=1)
            dt_apps = ReviewScopeType(id=uuid.uuid4(), framework_id=pci_framework_id,
                name="Applications", description="Software applications and web services", sort_order=2)
            dt_dbs = ReviewScopeType(id=uuid.uuid4(), framework_id=pci_framework_id,
                name="Databases", description="Database systems and data stores", sort_order=3)
            dt_network = ReviewScopeType(id=uuid.uuid4(), framework_id=pci_framework_id,
                name="Network", description="Network devices and infrastructure", sort_order=4)
            dt_security = ReviewScopeType(id=uuid.uuid4(), framework_id=pci_framework_id,
                name="Security Tools", description="Firewalls, IDS/IPS, WAF and security appliances", sort_order=5)
            dt_end_user = ReviewScopeType(id=uuid.uuid4(), framework_id=pci_framework_id,
                name="End User Devices", description="Workstations, laptops, and user endpoints", sort_order=6)
            dt_other = ReviewScopeType(id=uuid.uuid4(), framework_id=pci_framework_id,
                name="Other Systems", description="Miscellaneous systems and components", sort_order=7)
            dt_general = ReviewScopeType(id=uuid.uuid4(), framework_id=pci_framework_id,
                name="General", description="General organizational controls", sort_order=8)

            db.add_all([dt_servers, dt_apps, dt_dbs, dt_network, dt_security, dt_end_user, dt_other, dt_general])
            db.flush()

            mappings = []
            hardening_ids = ["2.2.1", "2.2.2", "2.2.3", "2.2.4", "2.2.5", "2.2.6", "2.2.7"]
            wireless_ids = ["2.3.1", "2.3.2"]
            hardening_domains = [dt_servers, dt_apps, dt_dbs, dt_network, dt_security, dt_end_user, dt_general]

            for cid in hardening_ids:
                ctrl = pci_controls.get(cid)
                if ctrl:
                    for dt in hardening_domains:
                        mappings.append(ControlToReviewScopeMapping(id=uuid.uuid4(),
                            review_scope_type_id=dt.id, framework_control_id=ctrl.id))

            for cid in wireless_ids:
                ctrl = pci_controls.get(cid)
                if ctrl:
                    mappings.append(ControlToReviewScopeMapping(id=uuid.uuid4(),
                        review_scope_type_id=dt_network.id, framework_control_id=ctrl.id))

            # "Other" gets all controls
            for ctrl in pci_controls.values():
                mappings.append(ControlToReviewScopeMapping(id=uuid.uuid4(),
                    review_scope_type_id=dt_other.id, framework_control_id=ctrl.id))

            db.add_all(mappings)
            db.commit()
            print(f"✓ Seeded 8 category types + {len(mappings)} control mappings for PCI DSS V4.0.1")
        else:
            if pci_framework_id:
                print("✓ PCI DSS category types already exist")

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
                project_type=ProjectType.STANDARD_AUDIT,
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
                    project_type=ProjectType.STANDARD_AUDIT,
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

            # Back-fill project_type on existing projects that lack it
            projects_without_type = db.query(Project).filter(
                Project.tenant_id == tenant_id,
                Project.project_type.is_(None),
            ).all()
            if projects_without_type:
                for p in projects_without_type:
                    p.project_type = ProjectType.STANDARD_AUDIT
                db.commit()
                print(f"✓ Back-filled project_type on {len(projects_without_type)} existing project(s)")
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
