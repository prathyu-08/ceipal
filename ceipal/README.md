# CEIPAL Analytics Dashboard

A full-stack analytics dashboard that integrates with the **CEIPAL ATS APIs** to provide real-time
recruitment intelligence. Built with **React + Vite** (frontend) and **FastAPI** (backend).

```
Frontend (React + Vite :5173)
          ↓  /api proxy
FastAPI Backend (:8000)
          ↓  Bearer token auth
CEIPAL ATS APIs
```

---

## Project Structure

```
ceipal-dashboard/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, CORS, router registration
│   │   ├── config/
│   │   │   └── settings.py          # Pydantic settings from .env
│   │   ├── routes/
│   │   │   └── dashboard.py         # GET /dashboard/high-priority, /dashboard/stats
│   │   ├── services/
│   │   │   └── ceipal_service.py    # Auth + all CEIPAL API calls
│   │   └── utils/                   # (reserved for shared helpers)
│   ├── .env                         # Secrets — never commit this
│   └── requirements.txt
│
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── main.jsx
    │   ├── index.css                 # Tailwind + custom glassmorphism styles
    │   ├── components/
    │   │   ├── Navbar.jsx            # Top bar with live clock
    │   │   ├── DashboardCards.jsx    # 4 KPI stat cards
    │   │   └── HighPriorityTable.jsx # Sortable, searchable, paginated table
    │   ├── pages/
    │   │   └── Dashboard.jsx         # Page orchestrator + auto-refresh
    │   └── services/
    │       └── dashboardApi.js       # fetch() wrappers for the backend
    ├── index.html
    ├── package.json
    ├── vite.config.js                # Vite proxy: /api → :8000
    ├── tailwind.config.js
    └── postcss.config.js
```

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Node.js | 18+ |
| npm | 9+ |

---

## 1. Backend Setup

### 1a. Navigate & create virtual environment

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 1b. Install dependencies

```bash
pip install -r requirements.txt
```

### 1c. Configure .env

Open `backend/.env` and fill in your real CEIPAL credentials:

```env
CEIPAL_BASE_URL=https://api.ceipal.com
CEIPAL_USERNAME=your_actual_username
CEIPAL_PASSWORD=your_actual_password
CEIPAL_API_KEY=your_actual_api_key
```

> **Security**: Never commit `.env` to version control. It is already in `.gitignore`.

### 1d. Run the backend

```bash
# From the /backend directory
uvicorn app.main:app --reload --reload-dir app --port 8000
```

Backend will be live at: **http://localhost:8000**

- Swagger docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

---

## 2. Frontend Setup

### 2a. Navigate & install

```bash
cd frontend
npm install
```

### 2b. Run the dev server

```bash
npm run dev
```

Frontend will be live at: **http://localhost:5173**

The Vite dev server proxies `/api/*` → `http://localhost:8000` automatically (configured in `vite.config.js`), so no CORS issues in development.

---

## 3. CEIPAL Authentication Flow

```
React UI
  │
  │  GET /api/dashboard/stats
  │
  ▼
FastAPI Backend
  │
  ├─ POST https://api.ceipal.com/v1/createAuthToken
  │      body: { username, password, api_key }
  │      ← { token: "eyJ..." }
  │
  ├─ GET https://api.ceipal.com/v1/getJobPostingsList
  │      headers: Authorization: Bearer eyJ...
  │
  ├─ GET https://api.ceipal.com/v1/getUsersList
  │
  ├─ GET https://api.ceipal.com/v1/getApplicantsList
  │
  ├─ Map recruiter IDs → names
  ├─ Count submissions per job
  │
  └─ Return enriched JSON to React
```

---

## 4. API Endpoints

### `GET /dashboard/stats`
Returns KPI summary counts.

```json
{
  "active_jobs": 42,
  "total_recruiters": 15,
  "total_applicants": 310,
  "total_submissions": 310
}
```

### `GET /dashboard/high-priority`
Returns active job requirements with recruiter names and submission counts.

```json
[
  {
    "requirement": "Python Developer",
    "recruiter": "Akhil Kumar",
    "status": "Active",
    "submissions": 7,
    "job_code": "JOB001"
  }
]
```

---

## 5. CEIPAL API Fields Used

| API | Fields |
|-----|--------|
| `getJobPostingsList` | `position_title`, `job_status`, `primary_recruiter`, `assigned_recruiter`, `job_code` |
| `getUsersList` | `id`, `display_name`, `role` |
| `getApplicantsList` | `consultant_name`, `applicant_status`, `job_title`, `job_code` |

---

## 6. Dashboard Features

| Feature | Description |
|---------|-------------|
| KPI Cards | Active Jobs, Recruiters, Applicants, Submissions — live counts |
| High Priority Table | Sortable by any column, searchable, paginated (10/page) |
| Status Badges | Color-coded Active / Closed / On Hold |
| Recruiter Avatars | Auto-generated initials avatar |
| Auto-refresh | Data refreshes every 5 minutes |
| Loading skeletons | Shimmer placeholders during fetch |
| Error states | Inline error messages with context |
| Responsive | Works on mobile, tablet, and desktop |

---

## 7. Production Build

```bash
# Build frontend
cd frontend
npm run build
# Output → frontend/dist/

# Run backend in production mode
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

For production, update `CORS allow_origins` in `backend/app/main.py` to your specific frontend domain.

---

## 8. Troubleshooting

| Problem | Fix |
|---------|-----|
| `502 Bad Gateway` from backend | Check CEIPAL credentials in `.env` |
| CORS error in browser | Ensure backend is running on `:8000` |
| `Token not found` error | Verify CEIPAL auth endpoint URL in `ceipal_service.py` |
| Empty table | Check if `job_status` values match Active/Open filter in `dashboard.py` |
| Recruiter shows "Unassigned" | Verify field names `primary_recruiter` / `assigned_recruiter` match your CEIPAL version |
