# boostgauge

> Lightweight system tachometer with peak-hold needles for monitoring AI agent resource pressure.

## Overview

BoostGauge is a real-time system monitor styled like a racing tachometer. It tracks ConPTY allocations, process counts, and system metrics with peak-hold (telltale) needles that persist at the highest value reached across multiple time windows — so you can see not just where you are, but where you've been.

Built for developers running multiple concurrent AI coding sessions (Claude Code, Cursor, Windsurf, Copilot) who need visibility into invisible resource pressure.

## Status

| Aspect | Status |
|--------|--------|
| Development | Planning |
| Documentation | In Progress |
| Tests | None |

## Quick Start

```bash
# Installation
pip install boostgauge

# Run
boostgauge
```

## Project Structure

```
boostgauge/
├── src/            # Application source code
├── tests/          # Test suites
├── docs/           # Documentation
└── tools/          # Development utilities
```

## Documentation

- [Architecture](docs/adrs/) - Architecture Decision Records
- [Standards](docs/standards/) - Coding and process standards
- [Runbooks](docs/runbooks/) - Operational procedures

## Development

This project follows [AssemblyZero](https://github.com/martymcenroe/AssemblyZero) conventions:
- Worktree isolation for all code changes
- Pre-merge gates (implementation + test reports)
- Session logging for agent continuity

## License

MIT License - See LICENSE file.

---

*Managed under [AssemblyZero](https://github.com/martymcenroe/AssemblyZero) governance.*
