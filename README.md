# backend

fastapi + prisma (postgres). auth, uploads, gemini for extraction.

```bash
python3 -m venv venv
source venv/bin/activate   # windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**.env** — need `DATABASE_URL`, `JWT_SECRET`, `GEMINI_API_KEY`.

```bash
npx prisma generate
npx prisma migrate dev
```
