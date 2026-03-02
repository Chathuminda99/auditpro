# Themis-Revamp Naming Conventions

This document outlines the consistent naming conventions used throughout the Themis-Revamp codebase to ensure code quality, readability, and maintainability.

---

## 1. Database Tables & Models

**Convention:** `snake_case` for table names, `PascalCase` for model classes

| Model Class | Database Table Name |
|---|---|
| User | users |
| Tenant | tenants |
| Client | clients |
| Project | projects |
| Framework | frameworks |
| Section | framework_sections |
| Control | framework_controls |
| ProjectResponse | project_responses |
| AuditDomain | audit_domains |
| AuditDomainType | audit_domain_types |
| AuditSession | audit_sessions |
| SessionControlInstance | session_control_instances |
| PciDssControl | pci_dss_controls |
| ControlToDomainMapping | control_to_domain_mappings |
| ControlInstanceEvidenceFile | control_instance_evidence_files |

---

## 2. Route Endpoints

**Convention:** RESTful paths using `lowercase`, `hyphens` for compound words

### RESTful Pattern

```
GET     /{resource}              → List
GET     /{resource}/new          → Show form
POST    /{resource}              → Create
GET     /{resource}/{id}         → Show detail
GET     /{resource}/{id}/edit    → Show edit form
POST    /{resource}/{id}         → Update
DELETE  /{resource}/{id}         → Delete
```

### Examples

```
GET     /projects                           → list_projects()
GET     /projects/new                       → new_project_form()
POST    /projects                           → create_project()
GET     /projects/{project_id}              → detail_project()
GET     /projects/{project_id}/domains/add  → add_domain_modal()
POST    /projects/{project_id}/domains      → add_domain()
DELETE  /projects/{project_id}/domains/{id} → remove_domain()
```

### Route Function Naming

- `list_{entity}`, `new_{entity}_form`, `create_{entity}`
- `detail_{entity}`, `update_{entity}`, `delete_{entity}`
- `add_{entity}_modal`, `remove_{entity}`
- `get_{entity}`, `download_{entity}`

---

## 3. Template Files

**Convention:**
- Full pages: `singular.html`
- Partial components: `_partial_name.html` (underscore prefix)
- Grouped by feature in subdirectories

### Directory Structure

```
templates/
├── base.html                    (Main layout)
├── components/
│   ├── breadcrumb.html
│   ├── sidebar.html
│   ├── topnav.html
│   └── _icon.html
├── auth/
│   ├── login.html
│   └── register.html
├── projects/
│   ├── list.html
│   ├── detail.html
│   ├── _form.html
│   ├── _row.html
│   └── health_check/
│       ├── overview.html
│       ├── domain_detail.html
│       ├── session_detail.html
│       ├── _domains_grid.html
│       ├── _sessions_list.html
│       ├── _add_session_modal.html
│       └── _control_panel.html
```

---

## 4. Enum Naming

**Convention:** `PascalCase` for enum class, `UPPER_CASE` for enum values

| Enum Class | Enum Values |
|---|---|
| ProjectStatus | DRAFT, IN_PROGRESS, COMPLETED, ARCHIVED |
| ProjectType | STANDARD_AUDIT, PCI_DSS_HEALTH_CHECK |
| ResponseStatus | NOT_STARTED, IN_PROGRESS, SUBMITTED, REVIEWED |
| UserRole | ADMIN, AUDITOR |
| WorkflowExecutionStatus | PENDING, IN_PROGRESS, COMPLETED, FAILED |
| ControlInstanceStatus | NOT_STARTED, IN_PROGRESS, PASS, FAIL, NA |

---

## 5. Repository Naming

**Convention:** `{ModelName}Repository`, method names use verb-noun pattern

### Repository Classes

```python
UserRepository
ProjectRepository
FrameworkRepository
ProjectResponseRepository
HealthCheckRepository
WorkflowExecutionRepository
ClientRepository
```

### Method Naming Patterns

```python
# CRUD Operations
get_by_id()
get_by_id_with_details()
get_all()
create()
update()
delete()

# Query Operations
filter_{entities}()
search_{entities}()
get_{entities}_for_{context}()

# Computation
compute_{noun}()
calculate_{noun}()
```

### Examples

```python
user_repo.get_by_id(user_id)
project_repo.get_by_id_with_details(tenant_id, project_id)
project_repo.filter_projects(tenant_id, status=None, user=user)
hc_repo.get_domains_for_project(project_id)
hc_repo.compute_domain_rollup(stats)
```

---

## 6. Variable Naming

**Convention:** `snake_case` for variables, descriptive names

### Categories

| Category | Pattern | Examples |
|---|---|---|
| Database IDs | `{entity}_id` | user_id, project_id, domain_id |
| Relationships | `{entity}_s` (plural) | domains, sessions, controls |
| Counts | `{action}_count`, `total_{entity}` | total_instances, control_count |
| Percentages | `{action}_pct` | progress_pct, assessed_pct |
| Collections | `{entity}_dict`, `{entity}_list` | domain_stats, projects_list |
| Status | `{action}_{state}` | is_active, has_error |

### Examples

```python
project_id, domain_id, session_id
domains, sessions, control_instances
total_instances, responded_count, control_count
progress_pct, assessed_pct, domains_pass
domain_stats (dict), projects (list), responses_dict
form_data, breadcrumbs, active_filters
```

---

## 7. Function/Method Naming

**Convention:** `snake_case`, verb-noun pattern

### Patterns

```python
# CRUD
create_{entity}()
get_{entity}()
update_{entity}()
delete_{entity}()

# Queries
get_{entity}_by_{criteria}()
get_{entities}_for_{context}()
filter_{entities}()
search_{entities}()

# Computations
compute_{noun}()
calculate_{noun}()
validate_{noun}()

# Checks/Predicates
can_{action}()
is_{state}()
has_{property}()
```

### Examples

```python
create_project(tenant_id, client_id, ...)
get_by_id(user_id)
get_by_id_with_details(tenant_id, project_id)
get_domains_for_project(project_id)
filter_projects(tenant_id, status=None, ...)
compute_domain_rollup(stats)
can_access_project(user, project)
```

---

## 8. Class/Model Naming

**Convention:** `PascalCase`, descriptive compound names

### Naming Patterns

- **Entities:** `{Noun}` → User, Project, Framework
- **Relationships:** `{Entity1}To{Entity2}` → ProjectResponse, ControlToDomainMapping
- **Types/Enums:** `{Entity}{Type}` → ProjectStatus, UserRole
- **Snapshots:** Fields like `control_title_snapshot` in SessionControlInstance

### Examples

```python
class User
class Project
class AuditDomain
class SessionControlInstance  # Snapshot model
class ControlToDomainMapping  # Relationship model
```

---

## 9. ID Field Naming

**Convention:** `{entity}_id` for ForeignKeys, `id` for primary keys

### Categories

| Category | Format | Examples |
|---|---|---|
| Primary Keys | `id` (UUID) | user.id, project.id |
| Foreign Keys | `{entity}_id` | project_id, domain_id |
| Tenant Scoping | `tenant_id` | For multi-tenancy |
| Ownership/Tracking | `{role}_id` | owner_id, assessed_by_id |

### Examples

```python
id: UUID  # Primary key
project_id: UUID  # Foreign key
tenant_id: UUID  # Tenant scoping
owner_id: UUID  # Owner tracking
assessed_by_id: UUID  # Assessor tracking
```

---

## 10. CSS Class Naming

**Convention:** Tailwind CSS utility classes, BEM for custom components

### Tailwind Pattern

```html
<!-- Spacing -->
<div class="p-6 m-4 gap-2">

<!-- Colors -->
<div class="bg-slate-900 text-white border-slate-200">

<!-- Layout -->
<div class="flex items-center grid grid-cols-3">

<!-- States -->
<button class="hover:bg-slate-100 dark:hover:bg-slate-700 focus:ring-2">

<!-- Responsive -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3">

<!-- Dark mode -->
<div class="bg-white dark:bg-slate-900 text-slate-900 dark:text-white">
```

### BEM Pattern (when custom CSS needed)

```html
<!-- Block -->
<div class="card">
  <!-- Element -->
  <div class="card__header">
    <!-- Modifier -->
    <span class="card__status card__status--active">
```

---

## 11. File/Directory Naming

**Convention:** `lowercase`, `hyphens` for compound words

### Categories

| Type | Pattern | Examples |
|---|---|---|
| Python files | `snake_case.py` | models.py, health_check.py |
| Directories | `snake_case/` | app/, templates/ |
| Template files | `snake_case.html`, `_partial.html` | overview.html, _domains_grid.html |
| Static assets | `lowercase-with-hyphens` | output.css, icon-set.js |

### Examples

```
app/models/project.py
app/repositories/health_check.py
app/routes/projects.py
static/css/output.css
templates/projects/health_check/domain_detail.html
templates/projects/health_check/_domains_grid.html
```

---

## 12. Timestamp Naming

**Convention:** Always include timestamps on models using `TimestampMixin`

### Standard Fields

```python
created_at: datetime  # When created (auto-set)
updated_at: datetime  # When last modified (auto-set)
```

### Examples

```python
user.created_at
project.updated_at
session.created_at
domain.updated_at
```

---

## 13. Utility/Helper Naming

**Convention:** Descriptive, action-based names in `utils/` subdirectories

### Files

| File | Purpose |
|---|---|
| access.py | Permission/access control |
| htmx.py | HTMX response utilities |
| email.py | Email sending utilities |
| validation.py | Form/data validation |

### Function Examples

```python
can_access_project(user, project)
can_modify_project(user, project)
htmx_toast(message, level="info")
send_email(to, subject, body)
validate_email(email)
```

---

## 14. Template Context Variables

**Convention:** `snake_case` for variables, descriptive names

### Standard Variables

| Variable | Type | Purpose |
|---|---|---|
| request | Request | HTTP request object |
| user | User | Authenticated user |
| project | Project | Single project |
| projects | List[Project] | Multiple projects |
| domains | List[AuditDomain] | Audit domains |
| domain_stats | Dict | Domain statistics |
| breadcrumbs | List | Navigation trail |
| active_filters | Dict | Applied filters |

### Examples

```python
{
    "request": request,
    "user": user,
    "project": project,
    "domains": domains,
    "domain_stats": domain_stats,
    "domain_rollup": domain_rollup,
    "breadcrumbs": breadcrumbs,
}
```

---

## 15. URL Parameter Naming

**Convention:** `snake_case` in path parameters, use descriptive names

### Examples

```
/projects/{project_id}
/domains/{domain_id}
/sessions/{session_id}
/controls/{instance_id}
/evidence/{evidence_id}
```

**Never use abbreviations** — Use `project_id` not `proj_id`, `domain_id` not `dom_id`

---

## 16. Form Field Naming

**Convention:** `snake_case`, matches database field names

### Examples

```html
<input name="name" />
<input name="client_id" />
<input name="framework_id" />
<textarea name="description" />
<input name="asset_identifier" />
```

---

## Summary

| Element | Convention | Example |
|---|---|---|
| Database tables | `snake_case` | `audit_domains` |
| Model classes | `PascalCase` | `AuditDomain` |
| Functions/methods | `snake_case` | `get_domain_by_id()` |
| Variables | `snake_case` | `project_id`, `domain_stats` |
| Enums (class) | `PascalCase` | `ControlInstanceStatus` |
| Enums (values) | `UPPER_CASE` | `NOT_STARTED`, `PASS` |
| Routes | RESTful + `lowercase` | `/projects/{project_id}` |
| Templates | `lowercase.html` | `overview.html` |
| Partials | `_lowercase.html` | `_domains_grid.html` |
| Files | `snake_case.py` | `health_check.py` |
| IDs | `{entity}_id` | `project_id`, `domain_id` |
| Timestamps | `created_at`, `updated_at` | `user.created_at` |
| Repository | `{Model}Repository` | `ProjectRepository` |

---

## Violations to Avoid

❌ **Don't do:**
- Mix camelCase and snake_case in same context
- Use abbreviations (proj_id, dom_id, ctrl_id)
- Use magic strings for statuses (use enums)
- Create files without meaningful names
- Use single-letter variable names (except loop counters `i`, `j`)
- Create unnamed or cryptic functions

✅ **Do:**
- Use consistent casing throughout file
- Use full descriptive names
- Use enums for all status fields
- Use meaningful file/function names
- Use descriptive variable names
- Document complex logic with comments

---

**Last Updated:** 2026-03-02
**Version:** 1.0
