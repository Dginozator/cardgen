# Cardgen

Cardgen is a Python toolkit for generating visual cards with AI.  
It combines a CLI workflow, a lightweight web interface, and a RouterAI layer to route requests across model providers.

## Why Cardgen

- Generate cards from prompts or prepared data.
- Run locally as a CLI tool or as a small web app.
- Keep model integration flexible through RouterAI.
- Stay close to production with simple FastAPI-based serving.

## Tech Stack

- Python 3.10+
- FastAPI + Uvicorn
- Jinja2 templates
- OpenAI-compatible SDK integration

## Quick Start

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

### 2) Configure environment

Copy `.env.example` to `.env` and set API keys / model settings.

### 3) Run web interface

```bash
cardgen-serve
```

### 4) Use CLI

```bash
cardgen --help
```

## Project Structure

- `cardgen/` - core package, routing, CLI, and web app code
- `data/` - local data files
- `samples/` - sample inputs and outputs
- `scripts/` - utility scripts

## Roadmap

The active backlog and implementation plans are maintained in `BACKLOG.md` and `PLAN.md`.

## License

If you plan to open-source this project, add a `LICENSE` file to define usage terms explicitly.
