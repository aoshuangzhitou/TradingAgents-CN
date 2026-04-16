# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TradingAgents-CN is a Chinese stock analysis platform using a multi-agent architecture built on LangGraph. It provides AI-powered stock research with support for A-shares, Hong Kong stocks, and US stocks.

**Key Technologies:**
- **Backend Core**: Python 3.10+, LangGraph, LangChain
- **Backend API**: FastAPI + Uvicorn (port 8000)
- **Frontend**: Vue 3 + Vite + Element Plus (port 3000)
- **Databases**: MongoDB (data), Redis (cache)
- **Data Sources**: AKShare, Tushare, Baostock, Yahoo Finance, Finnhub
- **LLM Providers**: DeepSeek, DashScope (Aliyun), Google Gemini, OpenAI, SiliconFlow

## Development Commands

### Setup Environment

```bash
# Install Python dependencies (recommended: use uv)
pip install -e .
# OR using uv
uv pip install -e .

# Install frontend dependencies
cd frontend && yarn install

# Copy environment file
cp .env.example .env
# Edit .env to configure API keys
```

### Run Development Servers

```bash
# Start MongoDB and Redis (Docker)
docker-compose up -d mongodb redis

# Run FastAPI backend
python -m app
# OR directly
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run Vue frontend (in another terminal)
cd frontend && yarn dev
```

### Run Tests

```bash
# Run all tests (excludes integration tests by default)
python -m pytest tests/

# Run specific test file
python tests/test_analysis.py

# Run with integration tests
python -m pytest tests/ -m integration

# Run single test
python -m pytest tests/test_analysis.py::test_function_name -v
```

### Docker Deployment

```bash
# Build and run full stack
docker-compose up -d

# With management UI (Mongo Express + Redis Commander)
docker-compose --profile management up -d

# Build multi-arch images
./scripts/build-multiarch.sh
```

### CLI Usage

```bash
# Run CLI interface
python -m cli

# Quick analysis
python main.py
```

## Architecture Overview

### Multi-Agent System (tradingagents/)

The core is a LangGraph workflow with specialized agents:

```
TradingAgentsGraph (tradingagents/graph/trading_graph.py)
├── Analysts (tradingagents/agents/analysts/)
│   ├── fundamentals_analyst.py    # PE, PB, financial metrics
│   ├── market_analyst.py          # Technical indicators
│   ├── news_analyst.py            # News sentiment
│   ├── social_media_analyst.py    # Reddit/social sentiment
│   └── china_market_analyst.py    # A-share specific analysis
├── Researchers (tradingagents/agents/researchers/)
│   ├── bull_researcher.py         # Bullish case analysis
│   └── bear_researcher.py         # Bearish case analysis
├── Managers (tradingagents/agents/managers/)
│   ├── research_manager.py        # Orchestrates research
│   └── risk_manager.py            # Risk assessment
├── Risk Management (tradingagents/agents/risk_mgmt/)
│   ├── aggressive_debator.py      # Risk-seeking perspective
│   ├── conservative_debator.py    # Risk-averse perspective
│   └── neutral_debator.py         # Balanced perspective
└── Trader (tradingagents/agents/trader/)
    └── trader.py                  # Final trading decision
```

### Data Layer (tradingagents/dataflows/)

Unified data access with automatic fallback:

```
dataflows/
├── interface.py                   # Main public API for data access
├── data_source_manager.py         # Multi-source orchestration
├── optimized_china_data.py        # A-share optimized fetcher
├── providers/
│   ├── china/
│   │   ├── akshare.py            # AKShare provider (free)
│   │   ├── tushare.py            # Tushare provider (professional)
│   │   └── baostock.py           # Baostock provider
│   ├── us/                        # US stock providers
│   └── hk/                        # HK stock providers
├── cache/                         # Caching layer
│   ├── file_cache.py
│   ├── db_cache.py
│   └── adaptive.py
└── news/                          # News sources
```

**Key Data Access Pattern:**
```python
# Preferred way to get stock data
from tradingagents.dataflows import interface

# A-share data (auto-fallback: Tushare -> AKShare -> Baostock)
data = interface.get_china_stock_data_unified("000001.SZ", "2024-01-01", "2024-12-31")

# US stock data
data = interface.get_YFin_data("AAPL", "2024-01-01", "2024-12-31")
```

### LLM Adapters (tradingagents/llm_adapters/)

Custom adapters for Chinese LLM providers:

```
llm_adapters/
├── dashscope_openai_adapter.py   # Aliyun DashScope
├── deepseek_adapter.py           # DeepSeek
├── google_openai_adapter.py      # Google Gemini (OpenAI-compatible)
└── openai_compatible_base.py     # Base for OpenAI-compatible APIs
```

### FastAPI Backend (app/)

```
app/
├── main.py                       # FastAPI app factory
├── __main__.py                   # Entry point (python -m app)
├── core/                         # Core config
│   ├── config.py                 # Settings management
│   ├── database.py               # MongoDB connection
│   └── redis.py                  # Redis connection
├── routers/                      # API routes
│   ├── analysis.py               # Stock analysis endpoints
│   ├── auth_db.py                # Authentication
│   ├── config.py                 # Configuration management
│   ├── financial_data.py         # Financial data APIs
│   ├── health.py                 # Health check
│   └── ...
├── services/                     # Business logic
├── worker/                       # Background task workers
└── models/                       # Pydantic models
```

### Frontend (frontend/)

```
frontend/
├── src/
│   ├── api/                      # API client
│   ├── components/               # Vue components
│   ├── stores/                   # Pinia stores
│   ├── router/                   # Vue Router
│   └── views/                    # Page views
├── vite.config.ts
└── package.json
```

## Configuration

### Environment Variables (Key)

Required for system startup:
```bash
# Database
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_USERNAME=admin
MONGODB_PASSWORD=tradingagents123
MONGODB_DATABASE=tradingagents

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=tradingagents123

# Security (change in production!)
JWT_SECRET=your-secret-key
CSRF_SECRET=your-csrf-secret

# LLM APIs (at least one)
DEEPSEEK_API_KEY=your-key
DASHSCOPE_API_KEY=your-key
GOOGLE_API_KEY=your-key

# Data sources
TUSHARE_TOKEN=your-token
FINNHUB_API_KEY=your-key
```

### Default Config (tradingagents/default_config.py)

Runtime configuration for the trading graph:
```python
DEFAULT_CONFIG = {
    "llm_provider": "openai",
    "deep_think_llm": "o4-mini",
    "quick_think_llm": "gpt-4o-mini",
    "max_debate_rounds": 1,
    "online_tools": False,
    "online_news": True,
    ...
}
```

## Key Patterns

### Adding a New Agent

1. Create agent file in appropriate subdirectory of `tradingagents/agents/`
2. Implement `create_<agent_name>()` function returning a LangChain Runnable
3. Import and export in `tradingagents/agents/__init__.py`
4. Add to graph in `tradingagents/graph/setup.py`

### Adding a New Data Provider

1. Create provider in `tradingagents/dataflows/providers/<market>/`
2. Inherit from base provider class
3. Add to `data_source_manager.py` fallback chain
4. Export via `interface.py`

### Running Single Test

```bash
# Run specific test file
python tests/test_chinese_output.py

# Run with pytest
python -m pytest tests/test_analysis.py -v

# Run specific test function
python -m pytest tests/test_analysis.py::test_analyst_selection -v
```

## License Notes

This project uses a dual-license:
- **Open Source (Apache 2.0)**: `tradingagents/`, `tests/`, `docs/`, `scripts/`, `cli/`, `examples/`
- **Proprietary**: `app/` (FastAPI backend), `frontend/` (Vue frontend)

The `app/` and `frontend/` directories require commercial authorization for business use.
