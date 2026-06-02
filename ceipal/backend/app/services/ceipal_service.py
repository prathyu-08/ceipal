"""services/ceipal_service.py

All CEIPAL API interactions live here.
Uses CEIPAL ATS v2 endpoints.

FIXES applied (per Ceipal Customer Success ticket, 05/22/2026):
  1. [getSubmissionsList] Expired token → proactive token refresh 60 s before expiry.
  2. [getJobPostingDetails] 40,000 calls → per-job TTL cache (10 min).
  3. [getJobPostingsList] 16,000 calls → pagination capped (max_pages=1 default).

PERFORMANCE (observed in logs 2026-05-23):
  4. Users re-fetched every request → cached 10 min (they never change mid-session).
  5. Submissions re-fetched every request→ cached 2 min.
  6. Same date job query hitting API twice→ jobs-by-date cached 2 min per date key.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
import base64
import re
import json
from pathlib import Path
from threading import RLock
import time
from datetime import datetime, date, timedelta
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


_HTTP_RETRY = Retry(
    total=3,
    connect=3,
    read=3,
    backoff_factor=0.5,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset(["GET", "POST"]),
)
_http = requests.Session()
_http.mount("https://", HTTPAdapter(max_retries=_HTTP_RETRY, pool_connections=20, pool_maxsize=20))
_http.mount("http://", HTTPAdapter(max_retries=_HTTP_RETRY, pool_connections=20, pool_maxsize=20))

# ---------------------------------------------------------------------------
# Token cache — FIX 1: refresh 60 s before expiry so tokens never arrive stale
# ---------------------------------------------------------------------------

_TOKEN_LIFETIME_SECONDS = 25 * 60
_TOKEN_REFRESH_BUFFER = 60

_token_cache: dict[str, Any] = {"token": None, "expires_at": 0.0}
_token_lock = RLock()


def _token_is_valid() -> bool:
    return (
        bool(_token_cache["token"])
        and time.time() < (_token_cache["expires_at"] - _TOKEN_REFRESH_BUFFER)
    )


def get_access_token() -> str:
    if _token_is_valid():
        return _token_cache["token"]

    with _token_lock:
        if _token_is_valid():
            return _token_cache["token"]

        url = f"{settings.ceipal_base_url}/v2/createAuthtoken/"
        payload = {
            "email": settings.ceipal_username,
            "password": settings.ceipal_password,
            "apiKey": settings.ceipal_api_key,
        }
        try:
            response = _http.post(
                url, headers={"Content-Type": "application/json"}, json=payload, timeout=20
            )
            response.raise_for_status()
            data = response.json()
            token = data.get("access_token")
            if not token:
                raise RuntimeError("Access token not found in CEIPAL response")
            _token_cache["token"] = token
            _token_cache["expires_at"] = time.time() + _TOKEN_LIFETIME_SECONDS
            logger.info("CEIPAL token refreshed; valid for %d s", _TOKEN_LIFETIME_SECONDS)
            return token
        except requests.RequestException as exc:
            logger.error("Authentication failed: %s", exc)
            raise RuntimeError(f"CEIPAL authentication failed: {exc}") from exc


def get_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ---------------------------------------------------------------------------
# Job-detail cache — FIX 2: per-job TTL cache (10 min)
# ---------------------------------------------------------------------------

_JOB_DETAIL_TTL = 6 * 60 * 60
_JOB_DETAIL_CACHE_FILE = Path(__file__).resolve().parents[2] / ".cache" / "job_details.json"
_job_detail_cache: dict[str, dict] = {}
_job_detail_lock = RLock()
_last_job_detail_persist = 0.0


def _load_job_detail_cache() -> None:
    try:
        if not _JOB_DETAIL_CACHE_FILE.exists():
            return
        data = json.loads(_JOB_DETAIL_CACHE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return
        now = time.time()
        with _job_detail_lock:
            for job_id, cached in data.items():
                if not isinstance(cached, dict):
                    continue
                expires_at = float(cached.get("expires_at") or 0)
                details = cached.get("data")
                if expires_at > now and isinstance(details, dict):
                    _job_detail_cache[str(job_id)] = {
                        "data": details,
                        "expires_at": expires_at,
                    }
        logger.info("Loaded %d persisted job-detail cache entries", len(_job_detail_cache))
    except Exception as exc:
        logger.warning("Could not load persisted job-detail cache: %s", exc)


def _persist_job_detail_cache(force: bool = False) -> None:
    global _last_job_detail_persist

    try:
        now = time.time()
        with _job_detail_lock:
            if not force and now - _last_job_detail_persist < 5:
                return
            _last_job_detail_persist = now
            payload = dict(_job_detail_cache)
            _JOB_DETAIL_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = _JOB_DETAIL_CACHE_FILE.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(payload), encoding="utf-8")
            tmp_path.replace(_JOB_DETAIL_CACHE_FILE)
    except Exception as exc:
        logger.warning("Could not persist job-detail cache: %s", exc)


def _normalize_priority(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    lookup = {
        "critical": "Critical",
        "high": "High",
        "medium": "Medium",
        "normal": "Medium",
        "low": "Low",
    }
    return lookup.get(text.lower(), text)


def _find_priority_value(data: Any) -> str:
    """Find priority in CEIPAL job details, including custom job fields."""

    priority_keys = {
        "priority",
        "job_priority",
        "requirement_priority",
        "req_priority",
        "custom_priority",
    }

    if isinstance(data, dict):
        for key, value in data.items():
            key_text = str(key).strip().lower()
            if key_text in priority_keys or "priority" in key_text:
                normalized = _normalize_priority(value)
                if normalized:
                    return normalized

            if isinstance(value, dict):
                label = str(
                    value.get("label")
                    or value.get("field_label")
                    or value.get("name")
                    or value.get("field_name")
                    or ""
                ).lower()
                if "priority" in label:
                    normalized = _normalize_priority(
                        value.get("value")
                        or value.get("field_value")
                        or value.get("display_value")
                        or value.get("selected_value")
                    )
                    if normalized:
                        return normalized

        for value in data.values():
            found = _find_priority_value(value)
            if found:
                return found

    if isinstance(data, list):
        for item in data:
            found = _find_priority_value(item)
            if found:
                return found

    return ""


def get_job_details(job_id: str) -> dict:
    now = time.time()
    with _job_detail_lock:
        cached = _job_detail_cache.get(job_id)
        if cached and now < cached["expires_at"]:
            return cached["data"]

    url = f"{settings.ceipal_base_url}/v2/getJobPostingDetails/{job_id}"
    try:
        resp = _http.get(url, headers=get_headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.warning("Could not fetch job details for %s: %s", job_id, exc)
        return {}
    except Exception:
        logger.warning("Invalid JSON for job details %s", job_id)
        return {}

    with _job_detail_lock:
        _job_detail_cache[job_id] = {"data": data, "expires_at": now + _JOB_DETAIL_TTL}
    _persist_job_detail_cache()
    return data


def get_priority(job_id: str) -> str:
    details = get_job_details(job_id)
    return _find_priority_value(details) or "Not Set"


def get_priority_cached(job_id: str) -> str:
    """Cache-only priority getter.

    Returns "Not Set" if job details are not already cached (or expired).

    This is what the /dashboard/high-priority route should use to avoid
    per-job network calls during rendering.
    """

    now = time.time()
    with _job_detail_lock:
        cached = _job_detail_cache.get(job_id)
        if cached and now < cached.get("expires_at"):
            details = cached.get("data") or {}
            return _find_priority_value(details) or "Not Set"
    return "Not Set"


def is_priority_cache_ready() -> bool:
    return bool(_job_detail_cache)


def invalidate_job_detail_cache(job_id: Optional[str] = None) -> None:
    if job_id:
        with _job_detail_lock:
            _job_detail_cache.pop(job_id, None)
    else:
        with _job_detail_lock:
            _job_detail_cache.clear()
    _persist_job_detail_cache(force=True)


def flush_job_detail_cache() -> None:
    _persist_job_detail_cache(force=True)


def start_priority_cache_loader() -> None:
    """Warm job-detail cache in background on server startup."""
    import threading

    def _load():
        try:
            logger.info("Priority cache loader: fetching jobs list...")
            recent_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            jobs, _ = get_jobs(max_pages=10, stop_before_date=recent_from)
            logger.info(
                "Priority cache loader: warming details for %d jobs...", len(jobs)
            )
            job_ids = []
            for job in jobs:
                job_id = str(job.get("id", "")).strip()
                if job_id:
                    job_ids.append(job_id)
            with ThreadPoolExecutor(max_workers=12) as executor:
                list(executor.map(get_job_details, job_ids))
            _persist_job_detail_cache(force=True)
            logger.info(
                "Priority cache loader: done — %d entries cached.", len(_job_detail_cache)
            )
        except Exception as exc:
            logger.warning("Priority cache loader failed (non-fatal): %s", exc)

    threading.Thread(
        target=_load, daemon=True, name="priority-cache-loader"
    ).start()


# ---------------------------------------------------------------------------
# Response-level caches — PERF 4/5/6: avoid re-hitting API on every request
# ---------------------------------------------------------------------------

_load_job_detail_cache()


_USERS_TTL = 10 * 60  # users change rarely
_SUBS_TTL = settings.submissions_cache_ttl_seconds
_JOBS_DATE_TTL = settings.jobs_date_cache_ttl_seconds
_JOBPOSTS_SCREEN_TTL = settings.jobposts_screen_cache_ttl_seconds

_users_cache: dict[str, Any] = {"data": None, "expires_at": 0.0}
_subs_cache: dict[str, Any] = {}
# key = "YYYY-MM-DD:YYYY-MM-DD" (from_date:to_date) or "default"
_jobs_date_cache: dict[str, dict] = {}
_jobposts_screen_cache: dict[str, Any] = {"data": None, "total": 0, "expires_at": 0.0}


# ---------------------------------------------------------------------------
# Datetime helper
# ---------------------------------------------------------------------------


def _parse_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    value = str(value).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# Paginated GET — FIX 3: max_pages=1 default
# ---------------------------------------------------------------------------


def _paginated_get(
    endpoint: str,
    headers: dict,
    params: dict | None = None,
    max_pages: int = 1,
    stop_before_date: Optional[str] = None,
) -> tuple[list[dict], int]:
    url = f"{settings.ceipal_base_url}{endpoint}"
    all_records: list[dict] = []
    page = 1
    limit = 50
    pages_fetched = 0
    total_count = 0

    stop_date: Optional[date] = None
    if stop_before_date:
        try:
            stop_date = datetime.strptime(stop_before_date, "%Y-%m-%d").date()
        except ValueError:
            pass

    default_target_date = (datetime.now() - timedelta(days=1)).date()

    while True:
        query = {"page": page, "limit": limit, **(params or {})}
        try:
            response = _http.get(url, headers=headers, params=query, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Error fetching %s page %d: %s", endpoint, page, exc)
            raise RuntimeError(f"CEIPAL API error on {endpoint}: {exc}") from exc

        try:
            body = response.json()
        except Exception:
            raise RuntimeError(f"Invalid JSON response from {endpoint}")

        records: list[dict] = []
        if isinstance(body, list):
            records = body
        elif isinstance(body, dict):
            records = body.get("results") or body.get("data") or []
            total_count = body.get("count") or total_count

        if not records:
            break

        stop_fetching = False
        for record in records:
            if endpoint == "/v2/getJobPostingsList":
                created_dt = _parse_datetime(str(record.get("created", "")).strip())
                if not created_dt:
                    continue
                record_date = created_dt.date()
                if stop_date and record_date < stop_date:
                    logger.debug("Stopping — reached stop_before_date %s", stop_date)
                    stop_fetching = True
                    break
                if not stop_date:
                    if record_date < default_target_date:
                        logger.debug("Stopping — older than yesterday")
                        stop_fetching = True
                        break
                    if record_date != default_target_date:
                        continue
                all_records.append(record)
            else:
                all_records.append(record)

        pages_fetched += 1
        logger.debug(
            "%s page %d: +%d scanned | %d matched",
            endpoint,
            page,
            len(records),
            len(all_records),
        )

        if stop_fetching:
            break
        if max_pages > 0 and pages_fetched >= max_pages:
            break
        if isinstance(body, dict) and body.get("next") is None:
            break
        if len(records) < limit:
            break
        if total_count and len(all_records) >= total_count:
            break

        page += 1

    logger.debug("Fetched %d matching records from %s", len(all_records), endpoint)
    return all_records, total_count


# ---------------------------------------------------------------------------
# Public API functions — with response-level caching
# ---------------------------------------------------------------------------


def get_jobs(
    max_pages: int = 1,
    stop_before_date: Optional[str] = None,
) -> tuple[list[dict], int]:
    """Cache results per date-range key for 2 minutes."""

    cache_key = f"{stop_before_date or 'default'}:p{max_pages}"
    now = time.time()
    cached = _jobs_date_cache.get(cache_key)
    if cached and now < cached["expires_at"]:
        logger.debug("get_jobs cache HIT for key=%s", cache_key)
        return cached["data"], cached["total"]

    result, total = _paginated_get(
        "/v2/getJobPostingsList",
        get_headers(),
        max_pages=max_pages,
        stop_before_date=stop_before_date,
    )
    _jobs_date_cache[cache_key] = {
        "data": result,
        "total": total,
        "expires_at": now + _JOBS_DATE_TTL,
    }
    return result, total


def _ceipal_web_login(session: requests.Session) -> None:
    """Login to the CEIPAL ATS web app used by /JobPosts?tab_id=all."""

    base_url = settings.ceipal_web_base_url.rstrip("/")
    timestamp_ms = int(time.time() * 1000)
    raw_password = f"{timestamp_ms}-/{settings.ceipal_password}-/{timestamp_ms}"
    encoded_password = base64.b64encode(raw_password.encode("utf-8")).decode("ascii")

    session.get(f"{base_url}/pages/signin", timeout=30)
    response = session.post(
        f"{base_url}/users/login",
        data={
            "username": settings.ceipal_username,
            "pass": encoded_password,
            "remember": "true",
            "browser_id": "",
            "firebase_token": "",
            "previousUrl": "/JobPosts?tab_id=all",
        },
        timeout=30,
    )
    response.raise_for_status()


def _strip_html(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"<[^>]+>", "", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
    )
    return " ".join(text.split())


def get_jobposts_screen_rows(max_pages: int = 0) -> tuple[list[dict], int]:
    """Fetch rows from the same CEIPAL web endpoint as JobPosts?tab_id=all.

    The v2 API leaves some screen columns blank or derived differently. This
    endpoint returns the exact screen metadata, including priority_id and the
    displayed recruiter/manager names.
    """

    now = time.time()
    if (
        _jobposts_screen_cache["data"] is not None
        and now < _jobposts_screen_cache["expires_at"]
    ):
        return _jobposts_screen_cache["data"], _jobposts_screen_cache["total"]

    base_url = settings.ceipal_web_base_url.rstrip("/")
    session = requests.Session()
    session.mount(
        "https://",
        HTTPAdapter(max_retries=_HTTP_RETRY, pool_connections=10, pool_maxsize=10),
    )
    _ceipal_web_login(session)

    selected_columns = (
        "1",
        "2",
        "1119",
        "8",
        "10",
        "6",
        "5",
        "7",
        "3",
        "4",
        "16",
        "17",
        "18",
        "795",
        "20",
        "21",
        "1357",
        "1358",
        "1359",
    )

    rows: list[dict] = []
    total = 0
    page_size = 25

    page_limit = max_pages if max_pages > 0 else 50

    for page in range(page_limit):
        payload: list[tuple[str, str]] = [
            ("sEcho", str(page + 1)),
            ("iDisplayStart", str(page * page_size)),
            ("iDisplayLength", str(page_size)),
        ]
        payload.extend(("columns_list[]", column) for column in selected_columns)
        payload.extend(
            [
                ("_method", "POST"),
                ("tab_index", "0"),
                ("rep_mod_id", "3"),
                ("placements_market_type", "1"),
                ("iTotalRecords", "0"),
                ("placement_report_on[]", "0"),
                ("currency_details", ""),
                ("interview_type", "0"),
                ("lead_type", "0"),
                ("report_id", "1"),
                ("saved_filter_id_type1", "0"),
                ("cat_wise_srch_value", ""),
                ("cat_wise_srch_col_id", "any"),
                ("cat_start_date", ""),
                ("cat_end_date", ""),
                ("onoffswitch", "1"),
                ("business_unit_ids", ""),
                ("business_unit_ids[]", "1"),
                ("saved_filter_id_type3", "0"),
                ("module_sec_edit", "3"),
                ("module_sec_add", "1"),
                ("has_clone_access", "1"),
                ("has_assigned_recuiter_edit", "0"),
                ("linkedin_plugin_config_details", ""),
            ]
        )

        response = session.post(
            f"{base_url}/JobPosts/getJobsList",
            data=payload,
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=45,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("success") != 1:
            raise RuntimeError(body.get("message") or "CEIPAL JobPosts screen fetch failed")

        total = int(body.get("iTotalRecords") or body.get("iTotalDisplayRecords") or total or 0)
        page_rows = body.get("aaData") or []
        if not page_rows:
            break

        for row in page_rows:
            if not isinstance(row, list) or not row or not isinstance(row[0], dict):
                continue
            meta = dict(row[0])
            meta["job_code_text"] = _strip_html(row[1] if len(row) > 1 else "")
            meta["requirement_text"] = _strip_html(row[2] if len(row) > 2 else "")
            meta["job_status_text"] = _strip_html(row[8] if len(row) > 8 else meta.get("job_status"))
            meta["created_text"] = _strip_html(row[15] if len(row) > 15 else "")
            meta["modified_text"] = _strip_html(row[16] if len(row) > 16 else "")
            rows.append(meta)

        if len(rows) >= total:
            break

    _jobposts_screen_cache["data"] = rows
    _jobposts_screen_cache["total"] = total
    _jobposts_screen_cache["expires_at"] = now + _JOBPOSTS_SCREEN_TTL
    return rows, total


def get_users() -> list[dict]:
    """Users (~48) are cached for 10 minutes."""

    now = time.time()
    if _users_cache["data"] is not None and now < _users_cache["expires_at"]:
        logger.debug("get_users cache HIT")
        return _users_cache["data"]

    records, _ = _paginated_get("/v2/getUsersList", get_headers(), max_pages=0)
    _users_cache["data"] = records
    _users_cache["expires_at"] = now + _USERS_TTL
    return records


def get_all_submissions(max_pages: int = 2) -> tuple[list[dict], int]:
    """Submissions cached briefly per pagination mode."""

    now = time.time()
    cache_key = f"p{max_pages}"
    cached = _subs_cache.get(cache_key)
    if cached and now < cached["expires_at"]:
        logger.debug("get_all_submissions cache HIT for key=%s", cache_key)
        return cached["data"], cached["total"]

    records, total = _paginated_get(
        "/v2/getSubmissionsList", get_headers(), max_pages=max_pages
    )
    _subs_cache[cache_key] = {
        "data": records,
        "total": total,
        "expires_at": now + _SUBS_TTL,
    }
    return records, total


def get_applicants_total_count() -> int:
    headers = get_headers()
    url = f"{settings.ceipal_base_url}/v2/getApplicantsList"
    try:
        resp = _http.get(url, headers=headers, params={"page": 1, "limit": 1}, timeout=30)
        resp.raise_for_status()
        return resp.json().get("count", 0)
    except Exception as exc:
        logger.error("Error getting applicant count: %s", exc)
        return 0


def get_submissions_total_count() -> int:
    headers = get_headers()
    url = f"{settings.ceipal_base_url}/v2/getSubmissionsList"
    try:
        resp = _http.get(url, headers=headers, params={"page": 1, "limit": 1}, timeout=30)
        resp.raise_for_status()
        return resp.json().get("count", 0)
    except Exception as exc:
        logger.error("Error getting submission count: %s", exc)
        return 0


# ---------------------------------------------------------------------------
# Recruiter Map
# ---------------------------------------------------------------------------


def _user_display_name(user: dict) -> str:
    name = (
        user.get("display_name")
        or user.get("name")
        or user.get("consultant_name")
        or user.get("full_name")
        or ""
    )
    if not name:
        first = user.get("first_name", "")
        last = user.get("last_name", "")
        name = f"{first} {last}".strip()
    if not name:
        name = user.get("email_id") or user.get("email") or "Unknown"
    return str(name).strip()


def build_user_map(users: list[dict]) -> dict[str, str]:
    user_map: dict[str, str] = {}
    for user in users:
        uid = str(user.get("id", "")).strip()
        if uid:
            user_map[uid] = _user_display_name(user)
    return user_map


def build_recruiter_map(users: list[dict]) -> dict[str, str]:
    return build_user_map(users)
