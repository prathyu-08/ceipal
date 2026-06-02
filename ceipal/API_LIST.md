# API List

## Dashboard Backend APIs

Base URL in development:

```text
http://localhost:8000
```

When called from the Vite frontend, `/api` is proxied to the backend:

```text
http://localhost:5173/api
```

### GET /dashboard/stats

Returns dashboard summary counts.

Frontend call:

```text
/api/dashboard/stats
```

Backend route:

```text
GET http://localhost:8000/dashboard/stats
```

### GET /dashboard/status

Returns recruiting status screen data.

Frontend call:

```text
/api/dashboard/status
```

Backend route:

```text
GET http://localhost:8000/dashboard/status
```

### GET /dashboard/bdm-performance

Returns BDM KPI cards.

Query params:

```text
period=today
period=yesterday
```

Frontend call:

```text
/api/dashboard/bdm-performance?period=today
/api/dashboard/bdm-performance?period=yesterday
```

Backend route:

```text
GET http://localhost:8000/dashboard/bdm-performance?period=today
```

### GET /dashboard/high-priority

Returns requirements table data for the dashboard and priority screen.

Query params:

```text
date_from=YYYY-MM-DD
date_to=YYYY-MM-DD
```

Frontend call:

```text
/api/dashboard/high-priority?date_from=2026-05-28&date_to=2026-05-28
```

Backend route:

```text
GET http://localhost:8000/dashboard/high-priority?date_from=2026-05-28&date_to=2026-05-28
```

### GET /dashboard/raw-data

Debug endpoint for raw fetched counts and a sample job.

Frontend call:

```text
/api/dashboard/raw-data
```

Backend route:

```text
GET http://localhost:8000/dashboard/raw-data
```

## CEIPAL External APIs Used By Backend

Base URL:

```text
https://api.ceipal.com
```

### POST /v2/createAuthtoken/

Used to create the CEIPAL access token.

```text
POST https://api.ceipal.com/v2/createAuthtoken/
```

### GET /v2/getJobPostingsList

Used to fetch job posting records.

```text
GET https://api.ceipal.com/v2/getJobPostingsList
```

### GET /v2/getJobPostingDetails/{job_id}

Used to fetch job details, including priority fields.

```text
GET https://api.ceipal.com/v2/getJobPostingDetails/{job_id}
```

### GET /v2/getUsersList

Used to fetch CEIPAL users and map user IDs to names.

```text
GET https://api.ceipal.com/v2/getUsersList
```

### GET /v2/getSubmissionsList

Used to fetch submissions and submission status.

```text
GET https://api.ceipal.com/v2/getSubmissionsList
```

### GET /v2/getApplicantsList

Used to fetch total applicant count.

```text
GET https://api.ceipal.com/v2/getApplicantsList
```

## CEIPAL Web Screen APIs Used By Backend

Base URL:

```text
https://talenthirecls2.ceipal.com
```

### GET /pages/signin

Used before web login.

```text
GET https://talenthirecls2.ceipal.com/pages/signin
```

### POST /users/login

Used to log in to the CEIPAL web app session.

```text
POST https://talenthirecls2.ceipal.com/users/login
```

### POST /JobPosts/getJobsList

Used to fetch the same rows shown on the CEIPAL JobPosts screen.

```text
POST https://talenthirecls2.ceipal.com/JobPosts/getJobsList
```

## Source Files

Backend app routes:

```text
ceipal/backend/app/routes/dashboard.py
```

CEIPAL API service:

```text
ceipal/backend/app/services/ceipal_service.py
```

Frontend API wrapper:

```text
ceipal/frontend/src/services/dashboardApi.js
```
