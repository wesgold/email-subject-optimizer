# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI Email Subject Line Optimizer that generates optimized email subject line variations with A/B testing and analytics capabilities. The project is in initial setup phase with empty src/ and tests/ directories.

## Development Commands

### Environment Setup
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_<module>.py
```

### Running the Application
```bash
# Start FastAPI server
uvicorn src.main:app --reload --port 8000
```

## Architecture

### Tech Stack
- **Framework**: FastAPI for API endpoints
- **AI Integration**: OpenAI/Anthropic APIs for subject generation
- **Caching**: Redis or DiskCache for response caching
- **Database**: SQLAlchemy with SQLite/PostgreSQL for analytics
- **Testing**: pytest with async support

### Key Implementation Areas

1. **Subject Line Generation** (src/generators/)
   - Implement prompt engineering for generating 5 variations
   - Use email body hash for caching key
   - Include rate limiting for API calls

2. **Caching Layer** (src/cache/)
   - Hash email content for cache keys
   - Implement both Redis and file-based caching options
   - Cache TTL configuration

3. **A/B Testing** (src/analytics/)
   - Track subject line performance
   - Store click-through rates
   - Generate performance reports

4. **API Endpoints** (src/api/)
   - POST /generate - Generate subject lines
   - GET /analytics - View performance data
   - POST /track - Track email opens/clicks

## Development Workflow

### Using Claude Commands
The `.claude/` folder contains specialized command files:
- Use `/generic_implementation_plan` before implementing new features
- Use `/web-search-researcher` to research best practices
- Use `/linear-ticket-guide` for ticket management
- Use `/research-codebase-generic` to understand existing patterns

### Implementation Guidelines
- Start by reading the current ticket in `docs/tickets/`
- Generate an implementation plan before coding
- Follow the caching pattern: hash → check cache → generate if miss → store
- Implement rate limiting on all external API calls
- Write tests alongside implementation

## Current Status
- Initial setup phase - no implementation yet
- First ticket: `docs/tickets/ticket_001_initial_setup.md`
- Empty src/ and tests/ directories ready for implementation