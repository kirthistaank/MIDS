# Contributing to ConfidenceOS

## Project Status

ConfidenceOS is primarily a **personal portfolio project** built to demonstrate end-to-end agentic AI system design. It is open source and free to use, but is not actively maintained as a community project.

**What this means:**
- ✅ Fork it freely and adapt it for your own use — that's encouraged
- ✅ Open an issue if you find a bug or have a suggestion
- ✅ Share it, reference it, learn from it
- ⚠️ Direct pull requests are not actively reviewed
- ⚠️ Issues may not receive a timely response

If you build something cool on top of it, feel free to share — always happy to see what the community creates!

---

## Forking & Running Locally

```bash
# 1. Fork the repo on GitHub (click Fork top right)
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/confidenceos.git
cd confidenceos

# 3. Set up backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # fill in your own keys

# 4. Set up frontend
cd ../frontend
npm install
npm run dev

# 5. Pull Ollama models
ollama pull llama3.2
ollama pull nomic-embed-text
ollama serve
```

---

## Customising for Your Own Use

The project is designed to be easy to adapt:

- **Change the coaching persona** — edit `PERSONA` in `backend/prompts.py`
- **Add new modes** — add a key to `PROMPTS` and an entry to `get_available_modes()`
- **Add your own books** — index chunks into Pinecone, add nodes to AuraDB
- **Swap the LLM** — change `OLLAMA_MODEL` in `.env`
- **Change the theme** — all colours are in `frontend/src/App.jsx`

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your own keys.
Never commit your `.env` file — it is in `.gitignore`.

---

## License

MIT — see [LICENSE](./LICENSE). You are free to use, modify, and distribute this project.
# Contributing to ConfidenceOS

Thank you for your interest in contributing! This is a community project and all contributions are welcome.

---

## Ways to Contribute

- **Bug reports** — found something broken? Open an issue with steps to reproduce
- **Feature requests** — have an idea? Open an issue and describe the use case
- **Pull requests** — want to fix or build something? See the workflow below
- **Knowledge base** — share book recommendations or indexing scripts
- **Prompts** — improve the coaching prompts in `backend/prompts.py`
- **Documentation** — help improve the README or add examples

---

## Development Setup

```bash
# 1. Fork the repo on GitHub
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/confidenceos.git
cd confidenceos

# 3. Set up backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # fill in your keys

# 4. Set up frontend
cd ../frontend
npm install
npm run dev

# 5. Pull Ollama models
ollama pull llama3.2
ollama pull nomic-embed-text
ollama serve
```

---

## Pull Request Workflow

1. Create a branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes — keep commits focused and descriptive
3. Test locally — make sure the backend starts and the UI loads
4. Open a PR against `main` with:
   - A clear title
   - What you changed and why
   - Screenshots if it's a UI change

---

## Code Style

- **Python** — follow PEP 8, use type hints where possible
- **JavaScript/JSX** — keep components focused, one responsibility per file
- **Prompts** — all prompts go in `backend/prompts.py`, never hardcoded in logic files
- **Logging** — use `from log_config import get_logger` in every new module

---

## What NOT to commit

- `.env` files with real API keys
- `node_modules/` or `venv/` directories
- `/tmp/confidenceos/` log files
- Any personal data or conversation history

---

## Questions?

Open a GitHub Discussion or file an issue — happy to help!