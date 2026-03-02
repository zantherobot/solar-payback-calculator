# CLAUDE.md — Developer Guide for Claude Code

This file tells Claude how to work on this repository. For what the product does, see SPEC.md.

## Project Structure

```
app.py            # Flask routes and form handling
calculator.py     # Core calculation engine (solar production, financials, 20-year projection)
data.py           # Hardcoded lookup tables (zip → utility, zip → sun hours, TOU rates)
templates/        # Jinja2 HTML templates
static/css/       # Stylesheet
static/js/        # Client-side JS (chart rendering, UI toggles, completion notification)
tests/            # pytest test suite
SPEC.md           # Product specification
```

## Running the App Locally

```bash
pip install -r requirements.txt
python app.py
# Visit http://localhost:5000
```

## Running Tests

```bash
python -m pytest tests/ -v
```

All tests must pass before committing. If you add or change any calculation logic, add corresponding tests in `tests/test_calculator.py`.

## Development Standards

These apply to every change.

### Testing
- Every change must include or update tests covering the modified behaviour.
- All existing and new tests must pass before committing or deploying.
- Calculation logic (solar production, NEM 3.0 credits, financial math) must have unit tests with known-good expected outputs.
- Edge cases — zero bill, maximum system size, boundary zip codes, missing inputs — must be tested.

### Linting & Code Style
- Python code must pass `flake8` (or `ruff`) with no errors before committing.
- Follow PEP 8 conventions. Line length limit: 100 characters.
- JS/CSS changes should be consistent with existing formatting in the file.

### Spec Stays Current
- If a change modifies user-facing behaviour, inputs, outputs, or calculation logic, update SPEC.md in the same commit.
- Do not let the spec drift from the implementation.

### Input Validation
- All user inputs must be validated server-side, regardless of any client-side checks.
- Invalid inputs return clear, user-friendly error messages — never raw stack traces.

### No Secrets in Code
- API keys, credentials, and environment-specific config go in environment variables, never hardcoded in source files.

### Small, Focused Commits
- Each commit should do one thing. Avoid mixing unrelated changes.
- Commit messages should describe *why*, not just *what*.

### Graceful Error Handling
- Calculation failures (e.g. unknown zip code, out-of-range inputs) must display a helpful message to the user and log the error server-side.
- The app should never show a 500 error page to end users.

## Deployment

Pushes to `main` auto-deploy to Railway. No manual steps needed.
