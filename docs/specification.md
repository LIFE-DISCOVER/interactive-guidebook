# Interactive Guidebook — Specification

## What This Application Does

The Interactive Guidebook is a web application for **energy agency managers**. These managers support **initiators** — people or organisations starting energy projects — by guiding them through hurdles at each stage of their project lifecycle.

The application serves three purposes:

1. **Service catalog** — A searchable collection of support services. Each service helps overcome specific hurdles and is attributed to one or more lifecycle phases. Managers browse and search this catalog to find the right service for a given situation.

2. **Client & project tracking** — Managers maintain records of their initiators (clients) and the energy projects those initiators are pursuing. Each project moves through the lifecycle phases.

3. **Service outcome recording** — When a manager applies a service to a project, they record the result. This creates a history of what support was provided and what came of it.

## Energy Project Lifecycle

Every energy project passes through three phases in order:

1. **Planning** — feasibility, permits, financing, design
2. **Realisation** — construction, procurement, installation
3. **Operation** — commissioning, monitoring, maintenance, optimisation

Each phase has its own set of **hurdles** — recurring challenges that projects typically face. Services in the catalog are mapped to the phases (and optionally specific hurdles) they address.

## Domain Model

```
Phase (3 fixed records: Planning, Realisation, Operation)
  └── Hurdle (many per phase)

Service (the catalog)
  ├── phases  → M2M → Phase  (through ServicePhase)
  └── hurdles → M2M → Hurdle (through ServiceHurdle)

Initiator (a client of the energy agency)
  └── Project (an energy project)
       ├── current_phase → FK → Phase
       ├── ProjectPhaseEntry (audit log of phase transitions)
       └── ServiceApplication (a service was applied; stores outcome data)
```

### Phase

| Field | Type | Notes |
|---|---|---|
| name | CharField(50) | "Planning", "Realisation", "Operation" |
| slug | SlugField | `planning`, `realisation`, `operation` |
| order | PositiveSmallIntegerField | 1, 2, 3 |
| description | TextField(blank) | |

Fixed domain data. Seed via data migration. Never expose create/delete in UI.

### Hurdle

| Field | Type | Notes |
|---|---|---|
| phase | FK → Phase | on_delete=PROTECT |
| name | CharField(200) | |
| description | TextField(blank) | |
| order | PositiveSmallIntegerField | display order within phase |
| created_at / updated_at | auto timestamps | |

### Service

| Field | Type | Notes |
|---|---|---|
| name | CharField(200) | |
| slug | SlugField(unique) | |
| summary | CharField(500) | short description for list views |
| description | TextField | full detail |
| phases | M2M → Phase (through ServicePhase) | |
| hurdles | M2M → Hurdle (through ServiceHurdle) | |
| is_active | BooleanField(default=True) | soft-disable without deleting |
| created_at / updated_at | auto timestamps | |

### ServicePhase / ServiceHurdle (explicit through tables)

Each has: `service` FK, `phase`/`hurdle` FK, `notes` TextField(blank). Unique together on the FK pair. Explicit through tables allow adding metadata later without migration pain.

### Initiator

| Field | Type | Notes |
|---|---|---|
| first_name | CharField(100) | |
| last_name | CharField(100) | |
| email | EmailField(unique) | |
| phone | CharField(30, blank) | |
| organization | CharField(200, blank) | company or municipality |
| notes | TextField(blank) | internal manager notes |
| created_at / updated_at | auto timestamps | |

### Project

| Field | Type | Notes |
|---|---|---|
| initiator | FK → Initiator | on_delete=PROTECT |
| name | CharField(200) | |
| description | TextField(blank) | |
| current_phase | FK → Phase | on_delete=PROTECT |
| status | CharField choices | `active`, `on_hold`, `completed`, `cancelled` |
| started_on | DateField(null, blank) | |
| created_at / updated_at | auto timestamps | |

### ProjectPhaseEntry

| Field | Type | Notes |
|---|---|---|
| project | FK → Project | on_delete=CASCADE |
| phase | FK → Phase | on_delete=PROTECT |
| entered_on | DateTimeField(auto_now_add) | |
| notes | TextField(blank) | |

Created automatically via `post_save` signal when `Project.current_phase` changes.

### ServiceApplication

| Field | Type | Notes |
|---|---|---|
| project | FK → Project | on_delete=CASCADE |
| service | FK → Service | on_delete=PROTECT |
| applied_by | FK → User | on_delete=SET_NULL, null |
| applied_on | DateField | defaults to today |
| outcome_notes | TextField(blank) | what happened / results |
| created_at / updated_at | auto timestamps | |

Unique together: `(project, service)`.

## App Structure

### `accounts`

- Owns: `CustomUser` (extends `AbstractUser`)
- Declare `AUTH_USER_MODEL = 'accounts.CustomUser'` before the first migration

### `catalog`

- Owns: `Phase`, `Hurdle`, `Service`, `ServicePhase`, `ServiceHurdle`
- Read-heavy reference data. No knowledge of `initiators`.

### `initiators`

- Owns: `Initiator`, `Project`, `ProjectPhaseEntry`, `ServiceApplication`
- Depends on `catalog` (FKs to Phase, Service). Dependency is one-way only.

## Features

### Authentication
- Login/logout with Django auth. No self-registration — admins create manager accounts.
- `LoginRequiredMixin` on every view. Only the login page is public.

### Service Catalog
- List all active services with phase filter tabs and keyword search (`?phase=<slug>&q=<term>`)
- Service detail page showing description, phases, hurdles addressed

### Initiator Management
- CRUD for initiator records (list, create, edit, detail)
- Initiator detail shows contact info, notes, and all their projects

### Project Management
- Create projects under an initiator
- Project detail shows current phase, status, phase history, and applied services
- Dedicated phase-change action (not inline edit) to enforce `ProjectPhaseEntry` creation
- Status management: active, on_hold, completed, cancelled

### Service Application
- Record that a service was applied to a project
- Add outcome notes documenting results
- View all applied services on project detail page
- Remove a service application if added in error

### Admin
- Django admin for managing the service catalog (services, hurdles)
- Phase admin is read-only for name/slug/order; description is editable
- Admin can create manager accounts

## URL Structure

```
/                                        → redirect to /catalog/
/accounts/login/                         → login
/accounts/logout/                        → logout (POST)
/catalog/                                → service list
/catalog/<slug>/                         → service detail
/initiators/                             → initiator list
/initiators/new/                         → create initiator
/initiators/<id>/                        → initiator detail
/initiators/<id>/edit/                   → edit initiator
/initiators/<id>/projects/new/           → create project
/projects/                               → all projects
/projects/<id>/                          → project detail
/projects/<id>/edit/                     → edit project
/projects/<id>/phase/                    → change phase
/projects/<id>/services/add/             → apply a service
/projects/<id>/services/<sa_id>/delete/  → remove service application
/admin/                                  → Django admin
```

## Design Decisions

- **Server-rendered HTML** — Django templates, no SPA. HTMX can be added incrementally.
- **Custom User model from day one** — must be set before first migration.
- **Phases are fixtures** — 3 fixed domain constants seeded via data migration, not user-editable.
- **Explicit M2M through tables** — `ServicePhase`, `ServiceHurdle` allow future metadata fields.
- **Phase history via signal** — `post_save` on Project creates `ProjectPhaseEntry` entries.
- **One-way dependency** — `initiators` imports from `catalog`, never the reverse.
- **Hard deletes with PROTECT** — no soft-delete complexity; PROTECT prevents accidental cascading.

## Implementation Order

1. `accounts` — CustomUser, migrations, login/logout, `base.html` template
2. `catalog` models — Phase, Hurdle, Service, through tables, data migration for phases, admin
3. `catalog` views — service list (filter + search), service detail
4. `initiators` models — Initiator, Project, ProjectPhaseEntry, admin
5. `initiators` views — CRUD for initiators and projects, phase-change view
6. `ServiceApplication` — model, add/delete views, wire into project detail
7. Polish — validation messages, empty states, pagination, nav highlighting

## Testing

Each app has `tests/` with `test_models.py`, `test_views.py`, `test_forms.py`. Use `TestCase` for DB tests, `SimpleTestCase` otherwise. Phase fixture loaded via `cls.fixtures`.
