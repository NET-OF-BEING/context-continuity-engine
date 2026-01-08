# Context Continuity Engine

Privacy-aware activity tracking system that maintains awareness across applications and time, automatically surfacing relevant context when needed.

## Features

- **Activity Monitoring**: Tracks window focus, file access, and application usage
- **Semantic Search**: ChromaDB + SentenceTransformers for finding related contexts
- **Temporal Graph**: NetworkX-based knowledge graph with relationship decay
- **Context Prediction**: ML-based engine for predictive context delivery
- **Privacy Controls**: Blacklist apps, URLs, and directories
- **Cross-Device Sync**: API server for multi-device context sharing (optional)

## Architecture

```
context_engine/
├── storage/           # SQLite database for activities
├── vector_db/         # ChromaDB embeddings for semantic search
├── graph/             # Temporal knowledge graph
├── prediction/        # Context prediction engine
├── privacy/           # Privacy filtering
└── monitors/          # Activity monitoring (X11, filesystem)
```

## Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Start the Daemon

```bash
./context_daemon.py
```

### CLI Interface

```bash
# Show recent activities
./context_cli.py recent --hours 24

# Search for similar contexts
./context_cli.py search "working on Python project"

# Show statistics
./context_cli.py stats

# List contexts
./context_cli.py contexts

# Clean up old data
./context_cli.py cleanup --days 90
```

### Configuration

Edit `config/default_config.yaml` to customize:

- Privacy settings (blacklists)
- Monitoring behavior
- Vector database settings
- Graph parameters
- Prediction thresholds

## Privacy

The engine is **privacy-first**:

- All data stored locally (no cloud)
- Configurable blacklists for apps, URLs, directories
- Sensitive data filtering (passwords, tokens, etc.)
- File type exclusions (`.key`, `.pem`, etc.)
- Can be disabled entirely per component

Default blacklists:
- Password managers (KeePassXC, Bitwarden)
- Login/password pages
- Private directories (`~/.ssh`, `~/.gnupg`)

## Components

### ActivityDatabase
SQLite storage for all tracked activities, contexts, files, and applications.

### EmbeddingStore
ChromaDB vector database for semantic similarity search using SentenceTransformers.

### TemporalGraph
NetworkX graph tracking temporal relationships between activities with decay over time.

### ContextPredictor
Predicts relevant context using:
- Semantic similarity
- Temporal patterns
- Graph-based predictions
- Recent context continuation

### PrivacyFilter
Filters and sanitizes activity data based on privacy rules.

### ActivityMonitor
Monitors system activity:
- X11 window focus tracking
- Filesystem events (watchdog)
- Browser URL extraction (limited)

## Requirements

- Python 3.8+
- OpenSUSE Linux (or any Linux with X11)
- ~500MB disk space for embeddings model
- ~100MB for local data storage

## Development

Project tracked with [Outcome Backcasting MCP](../OutcomeBackcasting/).

View progress:
```bash
cd ~/Documents/PythonScripts/OutcomeBackcasting
./run_backcast.sh
# Load: context_continuity_engine.json
```

## License

MIT License - See LICENSE file

## Author

Derek M D Chan
