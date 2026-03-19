This document explains the architecture, workflow, and data model of Themis for executing PCI DSS health check audits.

---

1. OVERVIEW

---

Themis is designed as a structured audit execution platform where a PCI DSS health check is performed through a hierarchical workflow.

The system separates:

* Control definition (global and reusable)
* Audit structure (project and review scope organization)
* Control execution (session-specific evaluation)

This separation ensures scalability, audit integrity, and flexibility.

---

2. HIERARCHICAL STRUCTURE (TREE MODEL)

---

The audit is organized as a three-level hierarchy:

1. Root Node (Project Level)
2. Parent Nodes (Review Scope Level)
3. Child Nodes (Session Level)

---

## 2.1 Root Node (Project)

The root node represents a single audit engagement.

It contains:

* Client Name
* Assessment Type (e.g., PCI DSS Health Check)
* PCI DSS Cycle
* Assessment Period

Example:
"ABC Client – PCI DSS Health Check – 2025 Cycle"

This node acts as the container for the entire audit.

---

## 2.2 Parent Nodes (Review Scope Level)

Parent nodes represent assessment review scopes.

Examples include:

* Application
* Database
* Servers
* Network Devices
* Operational Security
* HR / Call Center

Key characteristics:

* A parent node defines the *context* of assessment
* It determines which controls are relevant
* It does NOT represent a specific asset

Each review scope type is associated with a predefined set of controls through a mapping mechanism.

---

## 2.3 Child Nodes (Session Level)

Child nodes represent actual audit sessions for specific assets.

Examples:

* Under "Application":

  * ABC Application
  * XYZ Application

* Under "Servers":

  * ABC Server (10.0.0.1)
  * 123 Server (10.0.0.2)

Each child node:

* Represents a real asset
* Is the point where control evaluation occurs
* Stores assessment results and evidence

---

3. CONTROL ARCHITECTURE (GLOBAL LAYER)

---

Controls are maintained in a centralized control library.

Each control includes:

* Control ID (e.g., PCI DSS Req 1.1.1)
* Title / Description
* Framework (PCI DSS)
* Version (optional for future use)

Controls are NOT directly attached to projects or assets.

---

## 3.1 Control-to-Review-Scope Mapping

A mapping table defines which controls apply to which review scopes.

Example:

## Control ID      Review Scope

Req 6.x         Application
Req 2.x         Server
Req 1.x         Network
Req 12.x        Operational Security

This mapping is used to dynamically determine which controls are relevant when a parent node is selected.

---

4. SESSION INITIALIZATION (SNAPSHOT LOGIC)

---

When a child node (session) is created:

Step 1:
The system identifies the parent node type (e.g., Application).

Step 2:
It retrieves all controls mapped to that review scope.

Step 3:
Instead of referencing controls dynamically, the system creates a snapshot of these controls in a session-specific table.

This table is:

session_control_instances

---

## 4.1 session_control_instances Structure

Each record represents a control instance for a specific session.

Fields include:

* session_id
* control_id
* control_text_snapshot (optional but recommended)
* status (NOT_STARTED, IN_PROGRESS, PASS, FAIL, NA)
* evidence_reference (file path or object reference)
* notes
* assessed_by
* reviewed_by
* timestamps (created_at, updated_at)

---

5. EXECUTION FLOW

---

The workflow is as follows:

1. User creates a Project (Root Node)
2. User adds a Parent Node (selects review scope type)
3. User creates Child Nodes (sessions for specific assets)
4. System loads controls based on parent node type
5. System creates session_control_instances (snapshot)
6. Assessor evaluates each control within the session
7. Evidence and results are recorded per control

---

6. KEY DESIGN PRINCIPLES

---

1. Separation of Concerns

   * Controls are globally managed
   * Structure defines context
   * Execution is session-specific

2. Many-to-Many Relationship

   * A control can apply to multiple review scopes
   * A review scope can have multiple controls
   * A session contains multiple control instances

3. Snapshot-Based Execution

   * Controls are copied into sessions at creation time
   * Prevents future changes from affecting past audits

4. Context-Aware Evaluation

   * Controls are filtered based on review scope
   * Ensures relevance and reduces noise

5. Audit Integrity

   * Historical data remains unchanged
   * Supports compliance and reporting requirements

---

7. BENEFITS OF THIS DESIGN

---

* Scalable across multiple clients and frameworks
* Easy to extend (e.g., ISO 27001, SOC 2)
* Strong audit traceability
* Clean separation between definition and execution
* Flexible UI/UX implementation (tree-based navigation)

---

8. FUTURE EXTENSIONS (OPTIONAL)

---

* Control versioning (PCI DSS v4.0, v4.1)
* Multi-framework support
* Role-based access (Assessor, Reviewer, Manager)
* Automated evidence collection integrations
* Reporting engine (per control, per review scope, per project)

---

## END OF DOCUMENT
