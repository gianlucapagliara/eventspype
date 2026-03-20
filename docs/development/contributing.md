# Contributing

## Development Setup

Clone the repository and install dependencies:

```bash
git clone https://github.com/gianlucapagliara/eventspype.git
cd eventspype
uv sync
```

## Running Tests

```bash
uv run pytest
```

With coverage:

```bash
uv run pytest --cov=eventspype --cov-report=term-missing
```

## Code Quality

### Linting and Formatting

```bash
# Check code style
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

### Type Checking

```bash
uv run mypy eventspype
```

The project uses MyPy in strict mode. All public functions must have type annotations.

### Pre-commit Hooks

Install hooks to run checks automatically before each commit:

```bash
uv run pre-commit install
```

Run all hooks manually:

```bash
uv run pre-commit run --all-files
```

## Project Structure

```
eventspype/
├── eventspype/
│   ├── __init__.py                # Public API exports
│   ├── event.py                   # Event base class and EventTag type alias
│   ├── pub/
│   │   ├── __init__.py
│   │   ├── publication.py         # EventPublication descriptor
│   │   ├── publisher.py           # EventPublisher (single publication)
│   │   └── multipublisher.py      # MultiPublisher (multiple publications)
│   ├── sub/
│   │   ├── __init__.py
│   │   ├── subscriber.py          # EventSubscriber and OwnedEventSubscriber
│   │   ├── functional.py          # FunctionalEventSubscriber
│   │   ├── multisubscriber.py     # MultiSubscriber base class
│   │   ├── subscription.py        # EventSubscription and PublicationSubscription
│   │   ├── tracker.py             # TrackingEventSubscriber
│   │   └── reporter.py            # ReportingEventSubscriber
│   ├── broker/
│   │   ├── __init__.py
│   │   ├── broker.py              # MessageBroker abstract base class
│   │   ├── local.py               # LocalBroker (in-process)
│   │   ├── redis.py               # RedisBroker (Redis Pub/Sub)
│   │   └── serializer.py          # EventSerializer and JsonEventSerializer
│   └── viz/
│       ├── __init__.py
│       └── visualizer.py          # EventVisualizer (graphviz)
├── tests/
├── examples/
├── docs/                          # Documentation (mkdocs)
├── scripts/
│   └── release.sh                 # Release automation
└── pyproject.toml
```

## Releasing

Releases are managed via the release script:

```bash
./scripts/release.sh patch  # or minor, or major
```

This script:

1. Validates you are on the `main` branch with a clean tree
2. Bumps the version in `pyproject.toml`
3. Runs all checks (ruff, mypy, pytest)
4. Commits, tags, and pushes
5. Creates a GitHub release (which triggers PyPI publishing via CI)

## CI/CD

- **CI** runs on every push and PR to `main`: linting, type checking, tests with coverage
- **Publish** runs on GitHub release creation: tests, build, publish to PyPI
- **Docs** deploys to GitHub Pages on every push to `main`
