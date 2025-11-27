# Unified Trust Console - POC

A Proof-of-Concept implementation of a runtime governance system combining **Policy + Attestation + Credentials (PAC)** with predictive queueing theory for intelligent policy escalation.

## Overview

This project implements a trust console that:
- Enforces simple policy rules (writes require approval, read-only for risky units)
- Generates cryptographically signed receipts for all decisions (tamper-proof audit trail)
- Uses queueing theory to predict system overload and automatically escalate protection
- Integrates external trust signals via Trust Data Exchange (TDX)
- Provides a web UI for policy management, runtime demos, and evidence inspection

## Architecture

The project follows **Clean Architecture** principles with clear separation of concerns:

```
utc/
├── config/          # Configuration management (Pydantic V2)
├── core/            # Constants, enums, shared utilities
├── database/        # Database session management (SQLAlchemy 2.0)
├── models/          # Domain entities (Rule, Receipt, Event, Feature)
├── services/        # Business logic layer
│   ├── queueing.py  # Queueing theory calculations (λ/μ/ρ)
│   ├── rules.py     # Policy evaluation engine
│   ├── signer.py    # JWT/HMAC signing service
│   └── receipts.py  # Decision recording service
├── api/             # FastAPI routes and endpoints
└── templates/       # Jinja2 HTML templates for UI
```

### Key Technologies

- **Python 3.11+**
- **FastAPI 0.115.0** - Modern async web framework
- **SQLAlchemy 2.0.36** - ORM with type safety
- **Pydantic 2.9.2** - Data validation and settings management
- **PyJWT 2.9.0** - Cryptographic signing for receipts
- **SQLite** - Embedded database with WAL mode

## Current Implementation Status

### ✅ Completed Components

**Infrastructure:**
- [x] Virtual environment setup
- [x] Dependency management (requirements.txt)
- [x] Configuration management with environment variables
- [x] Database session handling with context managers

**Models:**
- [x] Base model with timestamp and serialization mixins
- [x] Feature model (queueing metrics: λ, μ, ρ)
- [ ] Rule model (policy configuration)
- [ ] Receipt model (decision audit trail)
- [ ] Event model (external trust signals)

**Services:**
- [x] **Queueing Service** - EWMA smoothing, protection levels, auto-relaxation
- [ ] Signing Service - JWT/HMAC for tamper-proof receipts
- [ ] Rules Service - Policy evaluation and management
- [ ] Receipts Service - Decision recording
- [ ] TDX Service - External event processing

**API Layer:**
- [ ] Application entry point (FastAPI app)
- [ ] Decision Service endpoints
- [ ] Gateway Proxy endpoints
- [ ] UI routes

**UI Layer:**
- [ ] HTML templates
- [ ] Rules management tab
- [ ] Runtime demo tab
- [ ] Evidence inspection tab

## Setup Instructions

### Prerequisites

- Python 3.11 or higher
- pip (Python package installer)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd unified-trust-console-poc
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create environment configuration**
   ```bash
   cp .env.example .env  # If available, or create .env manually
   ```

   Edit `.env` and configure:
   ```bash
   APP_ENV=development
   APP_DEBUG=true
   HMAC_SECRET=your-secret-key-min-32-chars-required
   DATABASE_URL=sqlite:///./data/utc.db
   QUEUE_ALPHA=0.3
   QUEUE_THRESHOLD_LOW=0.6
   QUEUE_THRESHOLD_HIGH=0.9
   ```

5. **Initialize the database**
   ```bash
   python -c "from utc.database import create_all_tables; create_all_tables(); print('Database initialized')"
   ```

## Usage

### Testing the Queueing Service

Run the built-in test suite:

```bash
python -m utc.services.queueing
```

This demonstrates:
- Initial low load state (ρ=0.3, permissive)
- Load increase triggering require_approval (ρ=0.6+)
- Critical load triggering read_only (ρ=0.9+)
- Auto-relaxation when load decreases
- EWMA smoothing preventing overreaction to spikes

### Programmatic Usage

```python
from utc.database import get_db_context
from utc.services import get_queueing_service

# Calculate protection level for a unit
with get_db_context() as db:
    queueing = get_queueing_service(db)

    # Update metrics with observed values
    feature = queueing.update_feature(
        unit="payments-api",
        arrival_rate=70.0,  # λ: 70 requests/hour
        service_rate=100.0  # μ: 100 requests/hour capacity
    )

    # Get protection level
    protection = queueing.get_protection_level("payments-api")
    print(f"Protection level: {protection}")  # "require_approval"

    # Get detailed metrics
    summary = queueing.get_metrics_summary("payments-api")
    print(f"Utilization: {summary['rho']:.1%}")
    print(f"Recommendation: {summary['recommendation']}")
```

## Queueing Theory Explained

### Core Metrics

- **λ (lambda)**: Arrival rate - how many requests arrive per time unit
- **μ (mu)**: Service rate - system capacity per time unit
- **ρ (rho)**: Utilization ratio = λ/μ - percentage of capacity in use

### EWMA Smoothing

Uses Exponentially Weighted Moving Average to smooth observations:

```
new_λ = α * observed_λ + (1-α) * old_λ
```

Where α=0.3 means:
- 30% weight to new observation
- 70% weight to historical average
- Prevents overreaction to temporary spikes

### Protection Levels

| Utilization (ρ) | Protection Level | Behavior |
|-----------------|------------------|----------|
| ρ < 0.6 | Permissive | All operations allowed |
| 0.6 ≤ ρ < 0.9 | Require Approval | Writes need human approval |
| ρ ≥ 0.9 | Read-Only | Only reads allowed, prevent overload |

### Auto-Relaxation

When utilization drops below 0.5, the system automatically relaxes protection:
- Read-only → Require approval
- Require approval → Permissive

This prevents staying in elevated mode when load decreases.

## Project Structure

```
unified-trust-console-poc/
├── .env                    # Environment configuration (not in git)
├── .gitignore              # Git exclusions
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── Poc Sales Demo Master Plan.pdf  # Original specification
│
├── data/                   # Database files (gitignored)
│   └── utc.db
│
└── utc/                    # Main application package
    ├── __init__.py
    ├── config/             # Configuration layer
    │   ├── __init__.py
    │   └── settings.py     # Pydantic V2 settings
    │
    ├── database/           # Database layer
    │   ├── __init__.py
    │   └── session.py      # SQLAlchemy session management
    │
    ├── models/             # Domain models
    │   ├── __init__.py
    │   ├── base.py         # Base model with mixins
    │   └── feature.py      # Queueing metrics model
    │
    └── services/           # Business logic
        ├── __init__.py
        └── queueing.py     # Queueing theory service
```

## Configuration

All configuration is managed via environment variables (`.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| APP_ENV | development | Environment name |
| APP_DEBUG | true | Enable debug logging |
| HMAC_SECRET | (required) | Secret key for JWT signing (min 32 chars) |
| DATABASE_URL | sqlite:///./data/utc.db | Database connection string |
| QUEUE_ALPHA | 0.3 | EWMA smoothing factor (0-1) |
| QUEUE_THRESHOLD_LOW | 0.6 | Threshold for require_approval mode |
| QUEUE_THRESHOLD_HIGH | 0.9 | Threshold for read_only mode |
| HUMAN_APPROVAL_RATE_PER_HOUR | 0.4 | Human approval capacity rate |

## Design Principles

This project follows industry best practices:

### SOLID Principles
- **Single Responsibility**: Each service handles one domain
- **Open/Closed**: Extensible via inheritance and composition
- **Liskov Substitution**: Mixins can be composed freely
- **Interface Segregation**: Services expose minimal, focused interfaces
- **Dependency Inversion**: Services depend on abstractions (Session), not concrete classes

### DRY (Don't Repeat Yourself)
- Base model with reusable mixins (TimestampMixin, SerializationMixin)
- Centralized configuration management
- Shared utilities and constants

### Clean Architecture
- Clear separation: Models → Services → API → UI
- Business logic in services, not controllers
- Database-agnostic service layer

## Development Workflow

### Running Tests

```bash
# Test queueing service
python -m utc.services.queueing

# Test individual components (as they're implemented)
python -m utc.services.rules
python -m utc.services.signer
```

### Database Management

```bash
# Create all tables
python -c "from utc.database import create_all_tables; create_all_tables()"

# Drop all tables (caution!)
python -c "from utc.database import drop_all_tables; drop_all_tables()"

# Reset database
python -c "from utc.database import drop_all_tables, create_all_tables; drop_all_tables(); create_all_tables()"
```

### Code Style

- Type hints throughout (mypy compatible)
- Docstrings for all public methods
- Comprehensive inline comments explaining "why"
- PEP 8 formatting

## Roadmap

### Phase 1: Foundation ✅
- [x] Project setup and configuration
- [x] Database infrastructure
- [x] Base models and mixins
- [x] Queueing service

### Phase 2: Core Services 🚧
- [ ] Rule and Receipt models
- [ ] Event model for TDX
- [ ] Signing service (JWT/HMAC)
- [ ] Rules service (policy evaluation)
- [ ] Receipts service (decision recording)
- [ ] TDX service (external events)

### Phase 3: API Layer 📋
- [ ] FastAPI application setup
- [ ] Decision Service endpoints
- [ ] Gateway Proxy endpoints
- [ ] Error handling middleware

### Phase 4: UI Layer 📋
- [ ] HTML templates
- [ ] Rules management interface
- [ ] Runtime demo interface
- [ ] Evidence inspection interface

### Phase 5: Advanced Features 📋
- [ ] TDX background job (hourly event processing)
- [ ] Approval queue management
- [ ] Evidence bundle generator (ZIP exports)

### Phase 6: Deployment 📋
- [ ] Docker configuration
- [ ] Deployment documentation
- [ ] Demo script and video

## Key Concepts

### Policy + Attestation + Credentials (PAC)

**Policy**: Simple rules defining allowed/denied operations
- `writes_require_approval`: All write operations need human approval
- `read_only_for_risky`: Risky units are locked to read-only mode

**Attestation**: Cryptographically signed receipts for every decision
- Who requested the operation
- What the decision was (allow/deny/require_approval)
- Which policies were active
- Timestamp and signature (JWT/HMAC-SHA256)

**Credentials**: Trust signals from external sources
- Risk events from security tools
- Compliance violations
- Behavioral anomalies

### Runtime Governance

Policies are enforced at runtime, not build time:
- Every operation goes through the decision service
- Receipts provide non-repudiable audit trail
- Can replay historical decisions for debugging
- Can retroactively audit policy effectiveness

### Predictive Escalation

Instead of reacting to incidents, predict overload:
- Monitor arrival rate (λ) and service rate (μ)
- Calculate utilization (ρ = λ/μ)
- Automatically escalate protection when ρ increases
- Auto-relax when load decreases

## Contributing

This is a POC project for demonstration purposes. Key areas for enhancement:

1. **Persistence**: Add PostgreSQL support for production
2. **Caching**: Redis for receipt lookups and metrics
3. **Monitoring**: Prometheus metrics and Grafana dashboards
4. **Testing**: Unit tests with pytest, integration tests
5. **Security**: Rate limiting, API authentication
6. **Scalability**: Horizontal scaling, message queue integration

## License

See LICENSE file for details.

## References

- Original specification: `Poc Sales Demo Master Plan — Pac + Aagate Lessons + Alpha Flow Path.pdf`
- FastAPI documentation: https://fastapi.tiangolo.com/
- SQLAlchemy 2.0: https://docs.sqlalchemy.org/
- Pydantic V2: https://docs.pydantic.dev/
- Queueing Theory: https://en.wikipedia.org/wiki/Queueing_theory

## Contact

For questions or support, please open an issue in the repository.

---

**Built with ❤️ following industry best practices and clean architecture principles.**
