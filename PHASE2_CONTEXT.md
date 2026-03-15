# Phase 2: Schema Explorer + ER Diagram + Multi-DB Query

## Overview

Phase 2 builds on the clean Connectors tab (Phase 1) to add:
1. **Schema Explorer** — rich table/column browser with search, replacing the basic DatabaseOverview
2. **ER Diagram** — interactive entity-relationship diagram using React Flow
3. **Multi-database query** — query across multiple databases of the same provider type

## Planned Components

### Schema Explorer (Databases tab replacement)
- Tree view: database > schema > table > columns
- Column details: type, nullable, default, constraints
- Search across tables/columns
- Quick copy of table/column names

### ER Diagram
- React Flow-based interactive diagram
- Auto-layout with dagre
- Tables as nodes, foreign keys as edges
- Click table to see details in side panel
- Export as PNG/SVG

### Multi-DB Query
- Backend: fan-out query to multiple databases of same type
- Merge results with source database column
- Frontend: show combined results with database indicator

## Dependencies
- `@xyflow/react` (React Flow v12) for ER diagram
- `dagre` for auto-layout
- Backend changes to support fan-out queries

## Files to Create/Modify
- `frontend/src/components/SchemaExplorer.jsx` — new tree-based schema browser
- `frontend/src/components/ERDiagram.jsx` — React Flow ER diagram
- `frontend/src/components/TableDetailPanel.jsx` — side panel for table details
- `app/api/v1/endpoints/query.py` — multi-database query fan-out
- `frontend/src/App.jsx` — replace DatabaseOverview with SchemaExplorer

## Notes
- The existing `SchemaViewer.jsx` and `DatabaseOverview.jsx` will be replaced
- React Flow requires careful memoization for performance
- dagre layout should be computed once and cached
