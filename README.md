# backend

this is the api layer for synapse.

it handles auth, email verification + forgot password (resend), memories, uploads, extraction (gemini + ocr), and semantic search data.

## quick start (linux/mac)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npx prisma generate
npx prisma migrate dev
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## quick start (windows powershell)

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
npx prisma generate
npx prisma migrate dev
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## env vars

required: `DATABASE_URL`, `JWT_SECRET`, `GEMINI_API_KEY`

for email verification + reset links: `FRONTEND_BASE_URL`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`

optional (windows ocr): `TESSERACT_CMD`

```env
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

## heads up

if you want ocr, install tesseract on your system too (pip install alone is not enough).

recommended startup order: backend first, then frontend/extension.

after pulling auth changes, run prisma migrate + generate before starting api.
