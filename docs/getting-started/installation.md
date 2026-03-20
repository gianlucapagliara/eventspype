# Installation

## Requirements

- Python 3.13 or higher

## Install from PyPI

```bash
# Using pip
pip install eventspype

# Using uv
uv add eventspype

# Using poetry
poetry add eventspype
```

## Optional Extras

### Redis Broker

To use `RedisBroker` for cross-process event dispatch, install the `redis` package:

```bash
pip install redis
# or
uv add redis
```

### Visualization

The `EventVisualizer` depends on both the `graphviz` Python package (included as a
dependency) and the Graphviz system binaries. Install the system binaries with:

```bash
# macOS
brew install graphviz

# Ubuntu / Debian
sudo apt-get install graphviz

# Fedora / RHEL
sudo dnf install graphviz
```

## Dependencies

EventsPype has minimal core dependencies:

| Package | Version | Purpose |
|---------|---------|---------|
| [async-timeout](https://github.com/aio-libs/async-timeout) | >= 4.0.3 | Async timeout support for `TrackingEventSubscriber.wait_for()` |
| [graphviz](https://graphviz.readthedocs.io/) | >= 0.20.1 | Architecture diagram generation in `EventVisualizer` |

## Verify Installation

```python
import eventspype
from eventspype import EventPublisher, EventPublication, EventSubscriber

print("eventspype installed successfully")
```
