# AI Email Subject Line Optimizer

An intelligent system for generating and optimizing email subject lines using AI, with built-in A/B testing and analytics.

## Project Structure
email-subject-optimizer/
+-- .claude/           # Claude command files for planning & development
+-- docs/
¦   +-- tickets/       # Project tickets and requirements
¦   +-- plans/         # Implementation plans
¦   +-- research/      # Research documents
+-- src/               # Source code
+-- tests/             # Test files
+-- data/              # Data storage (cache, A/B results)
+-- config/            # Configuration files

## Core Features

- **Subject Line Generation**: Generate 5 optimized variations for any email
- **Intelligent Caching**: Cache results by email hash to reduce API calls
- **A/B Testing**: Track performance of different subject variations
- **Analytics**: Monitor click-through rates and engagement metrics
- **Rate Limiting**: Manage API usage efficiently

## Getting Started

1. Copy your 5 Claude command files to `.claude/` folder
2. Use the command files to plan your implementation
3. Check `docs/tickets/` for the initial requirements
4. Generate implementation plans before coding

## Claude Commands

The `.claude/` folder should contain:
- `web-search-researcher-generic.md` - Research web for best practices
- `linear-ticket-guide.md` - Manage project tickets
- `generic_implementation_plan.md` - Create detailed implementation plans
- `generic-commit-guide.md` - Structure your git commits
- `research-codebase-generic.md` - Research codebase patterns

These commands help you:
1. Research best practices before implementing
2. Create detailed technical plans
3. Track progress with tickets
4. Maintain clean git history

## Development Workflow

1. **Planning Phase** (use Claude commands):
   - Research best practices for prompt engineering
   - Create implementation plan
   - Set up tickets for tracking

2. **Implementation Phase**:
   - Follow the implementation plan
   - Write tests alongside code
   - Use caching patterns researched

3. **Optimization Phase**:
   - Implement A/B testing
   - Add analytics tracking
   - Optimize based on data

## Technical Stack

- **Language**: Python 3.8+
- **AI Integration**: OpenAI/Anthropic API
- **Caching**: Redis or file-based
- **Analytics**: Simple SQLite or PostgreSQL
- **Testing**: pytest
- **API**: FastAPI or Flask

## Next Steps

1. Read the initial ticket in `docs/tickets/ticket_001_initial_setup.md`
2. Use `/generic_implementation_plan docs/tickets/ticket_001_initial_setup.md` to create a plan
3. Use `/web-search-researcher` to research prompt engineering best practices
4. Begin implementation following the generated plan
