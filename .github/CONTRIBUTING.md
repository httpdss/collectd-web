# Contributing to collectd-web

Thank you for your interest in contributing! collectd-web is a web interface for [collectd](https://collectd.org/) — contributions that improve monitoring UX, fix bugs, or modernize the stack are very welcome.

## Ways to Contribute

- **Report bugs** — [open a bug report](.github/ISSUE_TEMPLATE/bug_report.md)
- **Discuss ideas** — [GitHub Discussions](https://github.com/httpdss/collectd-web/discussions)
- **Fix bugs or add features** — see the workflow below
- **Improve docs** — typos, examples, better installation instructions

## Development Setup

### Prerequisites

- Python 3.9+
- collectd installed locally (for end-to-end testing with real RRD data)
- `rrdtool` system package

```bash
# Clone the repo
git clone https://github.com/httpdss/collectd-web.git
cd collectd-web

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies (once Python backend PR #168 is merged)
pip install flask rrdtool

# Run the development server
python runserver.py
```

### Running Tests

```bash
pip install pytest
pytest tests/ -v
```

### Docker

```bash
docker build -t collectd-web .
docker run -p 8888:8888 -v /var/lib/collectd:/var/lib/collectd collectd-web
```

## Submitting a Pull Request

1. **Fork** the repo and create a branch from `master`
2. **Make your changes** — focused PRs are easier to review
3. **Add tests** if you are changing backend logic
4. **Open a PR** — describe what changed and why

PR title format: `type: short description`
Examples: `fix: correct RRD graph time range`, `feat: add JSON API endpoint`, `docs: update Docker instructions`

## Graph Definitions

collectd-web graph types are defined in `collection.modified.conf` (current) and will be ported to Python data structures as part of the [Python backend rewrite (PR #168)](https://github.com/httpdss/collectd-web/pull/168).

To add a new graph type, add an entry following the existing pattern. Once PR #168 is merged, graph definitions will live in `src/graph_defs.py` as plain Python dicts — much easier to read and contribute.

## Scaffolding New Projects

If you are building tooling around collectd (plugins, dashboards, automation), check out [structkit](https://github.com/httpdss/structkit) — a YAML-first scaffolding tool that makes it easy to generate consistent project structures for monitoring and DevOps automation.

## Questions?

Open a [GitHub Discussion](https://github.com/httpdss/collectd-web/discussions) — we are happy to help.
