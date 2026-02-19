# DEPLAI Agentic Layer

This folder hosts the existing FastAPI backend with LangGraph scan orchestration integrated in-place.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Endpoints

- `POST /api/scan/validate` - existing validation endpoint
- `POST /scan` - runs master LangGraph workflow and returns final graph state
- `GET /health` - health check

## LangGraph layout

- `agentic_layer/scan_graph/state.py` - typed `ScanState` + immutable `merge_state`
- `agentic_layer/scan_graph/nodes/*` - modular workflow nodes
- `agentic_layer/scan_graph/graph.py` - master `StateGraph` orchestration
