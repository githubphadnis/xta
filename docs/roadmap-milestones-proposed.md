# Proposed Roadmap & Milestone Mapping (Ground-Truth Reset)

This document is the canonical proposal to cleanly realign GitHub roadmap/milestones with the current shipped reality.

## Current Ground Reality (from code + issues)

### Shipped / Completed
- Native camera upload flow
- CSV/XLS/XLSX statement ingestion
- Entity normalization
- Cloudflare ownership tagging/auth scoping
- Multi-currency conversion to base currency
- AI analyst ask/save/pin/delete + date filters
- Itemization per receipt
- Dashboard KPI enrichments + trend
- Ingest confidence banner/meta
- Backup/restore scripts and runbook

### Open Gaps
- Pagination / infinite scroll (Issue #3)
- PDF handling in active upload pipeline
- Bulk upload queue (pending/processing/retry)
- Export (filtered CSV + receipt bundle)
- Security hardening pipeline (SBOM/scan/secret scan)
- Geospatial visualization
- Income tracker
- Credit card parsing
- Voice command exploration

## Proposed Milestone Structure

### Milestone: V3.0 Stabilization (re-baseline)
Goal: close remaining near-term UX/accuracy gaps before net-new verticals.

Include:
1. **Date parsing correctness hardening** (all ingestion paths + filters) *(new issue recommended)*
2. **Dashboard card explainability (`i` tooltips)** *(new issue recommended)*
3. **Dashboard totals/currency correctness validation** *(new issue recommended)*
4. **Infinite scroll / pagination** (existing #3)

Exit criteria:
- Date parsing tests cover ambiguous/common formats
- Dashboard cards include explainability tooltips
- Currency totals use base-currency normalized amounts consistently
- Expenses list supports scalable pagination

### Milestone: V3.5 Ops & Compliance
Goal: production operations and audit readiness.

Include:
1. PDF handling
2. Bulk upload queue
3. Data export / tax readiness
4. Security hardening pipeline (SBOM + vuln + secret scans)

### Milestone: V4.0 Product Expansion
Goal: new financial domains and interaction surfaces.

Include:
1. Income tracker (existing #13)
2. Credit card parsing (existing #14)
3. Geospatial visualization
4. Voice commands (+ research issues #15/#16/#17 as scoped spikes)

## Proposed GitHub Issue Actions

1. Keep issue **#3** in V3.0.
2. Keep **#13** and **#14** in v4.0.
3. Convert #15/#16/#17 into either:
   - research-only milestone ("Exploration"), or
   - explicit scoped feature issues with acceptance criteria.
4. Create new issues for:
   - Date correctness hardening
   - Dashboard card explainability
   - Dashboard totals/currency correctness
   - PDF handling
   - Bulk queue
   - Export/tax readiness
   - Security scan/SBOM
   - Geospatial visualization

## Documentation Governance

To avoid docs drift:
- Keep this file + `docs/index.md` as source of truth.
- Update milestone/issue links when issues are created.
- Add a "Release Notes by Milestone" section before each production release.
