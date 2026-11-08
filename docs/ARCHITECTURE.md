# Architecture - Intraday Trading Platform

## Overview

This document describes the architecture and design patterns used in the intraday trading platform.

## Technology Stack

### Backend
- **Framework:** FastAPI (Python 3.12)
- **Database:** PostgreSQL 17 (with SQLAlchemy ORM)
- **Cache:** Redis (session storage)
- **Testing:** pytest, Playwright (E2E)

### Frontend
- **Framework:** React 19 + Vite
- **Styling:** TailwindCSS + custom CSS
- **Charting:** Native canvas (no external charting library)
- **Testing:** Playwright

### Infrastructure
- **Containerization:** Docker
- **Orchestration:** Docker Compose
- **Reverse Proxy:** Nginx (static file serving + API proxy)

## Architecture Layers

### 1. Presentation Layer (Frontend)
- React components in `apps/web/src/`
- No external charting dependencies - native canvas rendering
- SPA architecture with client-side routing
- Accessible UI (WCAG 2.1 AA compliance)

### 2. API Layer (Backend)
- FastAPI routes in `apps/api/app/*/routes.py`
- Authenticated endpoints via `require_user` dependency
- Rate limiting and request validation
- CORS configured for local development only

### 3. Domain Layer
- Business logic in `apps/api/app/*/` modules
- Instrument contracts and market data
- Backtesting engine
- Paper trading logic

### 4. Persistence Layer
- PostgreSQL database via SQLAlchemy
- Alembic migrations
- Redis for sessions and caching

## Component Architecture

### Historical Market-Data Module
```
apps/api/app/historical/
├── routes.py          # API endpoints
│   - GET /api/v1/historical/imports
│   - GET /api/v1/historical/partitions
│   - GET /api/v1/historical/partitions/{id}/candles
│   - GET /api/v1/historical/imports/{job_id}/gaps
├── importer.py        # Data import logic
├── reader.py          # Candle reading logic
├── dhan.py            # Dhan API integration
└── credentials.py     # Credential management

apps/web/src/HistoricalView.tsx  # Canvas-based chart
apps/web/src/HistoricalView.css  # Component styles
```

### Research Module
```
apps/api/app/research/
├── routes.py          # Rankings and evaluations
└── models.py          # Report models

apps/web/src/ResearchView.tsx  # Rankings display
```

### Paper Trading Module
```
apps/api/app/paper_trading/
├── routes.py          # Order simulation
├── models.py          # Paper account models
└── risk.py            # Risk controls

apps/web/src/PaperTradingView.tsx  # Paper UI
```

## Data Flow

### Historical Data Import
1. Operator triggers `dhan-exact-import` CLI
2. Dhan API retrieves verified instrument data
3. Data written to Parquet files
4. Import job creates `HistoricalImportJob` record
5. Partitions created with checksums
6. Instrument metadata denormalized into `HistoricalPartition`

### Candle API Flow
1. User authenticates via session cookie
2. GET `/api/v1/historical/partitions/{id}/candles`
3. Backend reads Parquet file
4. Returns pagination-aware response with instrument metadata
5. Frontend renders OHLCV chart + table

### Backtest Flow
1. Operator triggers `backtest` CLI
2. Engine reads historical partitions
3. Strategy applied via `app.backtesting.engine.run()`
4. Reports persisted to database
5. Rankings computed from reports
6. UI displays ranked strategies

## Security Model

### Authentication
- Session-based auth via `auth.py`
- Production auth MUST remain fail-closed
- Dev mode: `AUTH_DISABLED=true` bypasses auth
- Credential key file validated at startup

### Authorization
- All research endpoints require auth
- Market data endpoints require auth
- Paper trading requires auth

### Data Protection
- Broker credentials encrypted
- No secrets in code or logs
- `.gitignore` excludes sensitive files
- Backup encryption recommended

## Performance Considerations

### Caching
- Redis for session storage
- Parquet files for fast read access
- Partition-level indexing

### Database
- SQLAlchemy relationship loading
- Denormalized fields for frequent access
- Migration-friendly schema evolution

### Frontend
- Lazy loading for large datasets
- Pagination for table views
- Canvas rendering for performance

## Scalability

### Horizontal Scaling
- Stateless API tier
- Shared Redis for sessions
- External storage for historical data

### Data Volume
- Parquet format for columnar storage
- Partition-based organization
- Checksums for integrity

## Testing Strategy

### Unit Tests
- pytest for backend
- Vitest for frontend
- Isolated component testing

### Integration Tests
- Database fixtures
- API endpoint testing
- Cross-module testing

### E2E Tests
- Playwright for browser automation
- HistoricalView coverage
- Navigation and flow testing

### Regression Tests
- Historical API tests
- Backtesting validation
- Ranking reproducibility

## Deployment

### Development
```bash
cd deployment/compose
docker compose up -d
```

### Production
- Separate Nginx reverse proxy
- HTTPS termination
- Production auth enabled
- No AUTH_DISABLED

### Rollback
- PostgreSQL dump in `backups/`
- Credential key backup
- Docker Compose version tags

## Observability

### Health Checks
- `/api/v1/monitoring/health`
- `/api/v1/monitoring/metrics`
- Credential presence validation

### Logging
- Application logs to stdout
- Error tracking
- No secrets in logs

### Metrics
- Prometheus-format endpoints
- Request counts
- Response times

## File Ownership

| Component | Owner |
|-----------|-------|
| API routes | BACKEND AGENT |
| Database models | BACKEND AGENT |
| Frontend UI | FRONTEND AGENT |
| Market data logic | MARKET/QUANT AGENT |
| Tests | QA AGENT |
| Security review | REVIEWER AGENT |
| Integration | ORCHESTRATOR |

## Shared Contracts

### Database Schema
- `apps/api/alembic/versions/` - Migrations
- `apps/api/app/models.py` - ORM models
- NO agent modifies schema without Orchestrator approval

### API Contracts
- `apps/api/app/*/routes.py` - Routes
- `apps/web/src/api.ts` - Frontend API client
- Changes coordinated by Orchestrator

### Frontend Components
- `apps/web/src/` - React components
- Shared styles via `style.css`
- Component contracts documented in code

---

**Last updated:** 2026-11-08  
**Phase:** 1 Complete - Historical market-data experience
