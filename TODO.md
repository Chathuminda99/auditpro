# Themis Revamp — TODO

## UI / Styling

- [x] Fix the glitchiness of the Edit Project popup (animation / overlay jank)
- [x] Fix UI issues in the Edit Project and Add/Edit Client popups (layout, spacing)
- [x] Match dropdown colors with the main color theme (active item uses bg-primary)
- [x] Improve visual weight of input fields and dropdowns (borders, focus rings, styling)
- [x] Reduce dropdown list item size to match the rest of the app scale
- [x] Highlight the active/selected item in the sidebar nav
- [x] Fix font color mismatch in the Frameworks detail view
- [x] Fix client name font color mismatch in the Clients list view
- [x] Replace the Controls and Settings sidebar icons with better alternatives
- [x] Enhance the Icons of the client names and avatars across all views

## UI / Styling (Backlog)

- [x] Fix Frameworks list page — old gray-* classes, no dark mode, cards need redesign to match app style
- [x] Audit and fix Admin controls page styling (likely same gray-* mismatch)
- [x] Sidebar collapse chevron should flip direction when sidebar is open/closed
- [x] Fix "Finalize & Submit Audit" button in project detail — use bg-primary instead of bg-slate-900
- [x] Polish the login page to match the current design system
- [x] The profile hovering model window not align with the theme
- [x] Fix Frameworks detail page — redesign to match design system
- [x] Remove max-width constraints from clients and dashboard pages (too much whitespace)
- [x] Fix version badge visibility (text-[10px] not compiled, dark mode color too faint)
- [x] Fix dashboard project card progress bar — currently hardcoded to 0%
- [x] Add proper empty state to dashboard when no active projects exist
- [ ] When an user add same observation multiple times, give him/her a warning.
- [x] Shrink the Control metadata and Audit trail section and give more room for observations table.
- [ ] Add option to view commands/view path for some observations.

## Features & Functionality

- [x] Evidence panel per observation — add text notes and upload images/files
- [x] Audit timer in project controls sidebar — start, pause, stop with localStorage persistence
- [x] Access Controls (RBAC)
  - [x] Role-based access control: Admin (all projects, clients, controls, users) + Auditor (own/shared projects only)
  - [x] Project ownership tracking and transfer
  - [x] Project sharing with auditors
  - [x] User management interface (/admin/users)
  - [x] Route-level and repository-level access guards
  - [x] Control detail metadata shows project owner
- [ ] Create Project Hierachy
  - [ ] Defining how reporting happens
  - [ ] Obeservations and Controls structure
  - [ ] Audit session categories(Application, Server, DB etc)

## Antigravity UX/UI suggestions

- [x] **Sticky Action Buttons in Control Detail**: In `_control_detail.html`, move "Save & Continue" and "Cancel" buttons to a fixed bottom bar or sticky header so they remain accessible when long observations are added.
- [x] **Empty State Polish**: Elevate the "No observations added yet" empty state in `_control_detail.html` using a subtle icon illustration or dotted-border drop-zone style.
- [x] **Dropdown Positioning**: Custom Alpine.js dropdowns in filters (`list.html`) can be clipped by `overflow-hidden` containers. Fixed using `position: fixed` + `getBoundingClientRect()` — no Floating UI needed.
- [x] **Scrollable Content Friction**: Requirements and Testing Procedures in `_control_detail.html` use `max-h-64` with inner scrollbars. Consider an expandable "Read More / Show Less" toggle instead of forcing scroll within a small box.
- [x] **Dropdown Text Truncation**: Predefined observation dropdowns truncate text at ~60 characters, hiding crucial information. Switched to multi-line layout with full label text.
- [ ] **Mobile Filter UX**: The filter bar in `list.html` stacks large dropdowns vertically on mobile/tablet. Consider hiding filters behind a "Filters" button that opens a slide-out drawer or modal on smaller screens.

## Codex UX/UI suggestions

- [ ] Create a **global page header pattern** (title + short context + primary CTA + secondary actions) so every screen starts with consistent orientation and task focus.
- [ ] Add a **command palette / quick actions** launcher (e.g., `⌘K` / `Ctrl+K`) for frequent tasks such as creating project, jumping to clients/frameworks, and opening recent records.
- [ ] Improve **information hierarchy on dashboard**: promote highest-priority KPIs, reduce decorative weight, and add "what changed since last visit" indicators.
- [ ] Introduce **empty-state system** (illustration + guidance + one CTA) for all list/detail pages to reduce dead ends when data is missing.
- [ ] Add **table usability upgrades**: sticky headers, column density toggle (comfortable/compact), saved filters, and visible sort state indicators.
- [ ] Improve **form UX consistency**: inline helper text, validation timing rules (on blur + submit), field-level error summaries, and required/optional clarity.
- [ ] Implement a **unified feedback language** for toasts/modals (success, warning, destructive) with predictable placement, duration, and copy style.
- [ ] Standardize **loading states** across pages (skeletons for content + disabled actions with progress labels) to avoid layout shifts and uncertainty.
- [x] Add **unsaved changes protection** for long forms/workflows (dirty-state badge + confirmation on navigate/close).
- [ ] Improve **project detail workflow readability** by grouping control assessment actions into clearer phases with persistent progress context.
- [ ] Strengthen **navigation wayfinding**: highlight current location more clearly, add "recently viewed" section, and improve breadcrumb click targets.
- [ ] Add **responsive behavior polish** for medium screens (tablet/laptop widths), especially table overflow, sidebar collapse defaults, and action button wrapping.
- [ ] Improve **keyboard and accessibility support**: visible focus states everywhere, ARIA labels for icon-only controls, logical tab order, and color-contrast audit.
- [x] Refine **microcopy and labeling** (buttons, statuses, helper text) to use user outcomes instead of internal/system wording.
- [ ] Add **contextual onboarding hints** for first-time users (progressive tooltips/checklist) that can be dismissed and later reopened from Help.
