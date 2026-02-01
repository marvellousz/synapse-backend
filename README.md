# Synapse Backend

FastAPI backend with Prisma (PostgreSQL), auth, file uploads, and AI extraction (Gemini).

## Virtual environment

```bash
# Create venv (first time only)
python3 -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

On Windows: `venv\Scripts\activate` (or `.venv\Scripts\activate`) then `uvicorn app.main:app --reload --port 8000`.

## Environment

Copy `.env` from your setup or create one with at least:

- `DATABASE_URL` – PostgreSQL connection string
- `JWT_SECRET` – secret for JWT signing
- `GEMINI_API_KEY` – (optional) for AI summary, tags, and transcription

## Prisma

```bash
# Generate client (after schema changes)
npx prisma generate

# Run migrations
npx prisma migrate dev
```
