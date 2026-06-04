"""
routes/dashboard.py

Tuned performance + correctness for the dashboard endpoints.

Endpoints
- GET /dashboard/high-priority?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD

Notes
- Uses list APIs for jobs/users/submissions.
- Priority is read through the job-detail TTL cache; cache misses are fetched once.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import RLock
from typing import Optional
import logging
import re
import time

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.response_cache import cached_response
from app.config.settings import get_settings
from app.services.ceipal_service import (
    get_jobs,
    get_users,
    get_all_submissions,
    get_applicants_total_count,
    get_submissions_total_count,
    get_job_details,
    get_priority_cached,
    flush_job_detail_cache,
    build_user_map,
    get_jobposts_screen_rows,
)



router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
logger = logging.getLogger(__name__)
settings = get_settings()

_HIGH_PRIORITY_TTL = settings.high_priority_cache_ttl_seconds
_USE_JOBPOSTS_SCREEN_SOURCE = True
_high_priority_cache: dict[str, dict] = {}
_high_priority_lock = RLock()


class RequirementItem(BaseModel):
    bdm: str
    lead: str
    recruiter: str
    priority: str
    submissions: int
    submission_status: str
    requirement: str
    time_to_submit: str = "--"


class DashboardStats(BaseModel):
    active_jobs: int
    total_recruiters: int
    total_applicants: int
    total_submissions: int


class BdmKpiItem(BaseModel):
    bdm_name: str
    requirements_received: int
    profiles_submitted: int
    feedback_pending: int
    interviews: int
    closures: int


class TodaySubmissionItem(BaseModel):
    submission_id: str
    submitted_on: str
    recruiter: str
    job_title: str
    job_id: str
    candidate_id: str
    status: str
    source: str
    employment_type: str
    pay_rate: str
    tax_term: str


def _clean_title(t: str | None) -> str:
    if not t:
        return "Untitled"
    if " - " in t:
        after = t.split(" - ", 1)[1]
        pos = after.find("_")
        if pos != -1:
            r = after[pos + 1 :].strip()
            if r:
                return r
    return t


def _split_ids(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value).replace(";", ",").replace("|", ",").split(",")
    return [str(item).strip() for item in raw if str(item).strip()]


def _resolve_people(value: object, user_map: dict[str, str], fallback: str) -> str:
    if str(value or "").strip() in {"", "0", "N/A", "None", "none", "null"}:
        return fallback

    ids = _split_ids(value)
    if not ids:
        text = str(value or "").strip()
        return text or fallback

    names = [user_map.get(person_id, person_id) for person_id in ids]
    names = [name for name in names if name and name.lower() not in {"none", "null"}]
    if not names:
        text = str(value or "").strip()
        return text or fallback
    return ", ".join(dict.fromkeys(names))


def _looks_like_unresolved_id(value: object) -> bool:
    text = str(value or "").strip()
    if not text or " " in text or "@" in text:
        return False
    if text.isdigit():
        return True
    if len(text) < 16:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_+=/-]+", text))


def _has_unresolved_id(value: str, fallback: str) -> bool:
    if not value or value == fallback:
        return False
    return any(_looks_like_unresolved_id(part) for part in _split_ids(value))


def _resolve_people_candidates(
    candidates: tuple[object, ...],
    user_map: dict[str, str],
    fallback: str,
) -> str:
    unresolved = ""
    for candidate in candidates:
        resolved = _resolve_people(candidate, user_map, fallback)
        if resolved == fallback:
            continue
        if _has_unresolved_id(resolved, fallback):
            unresolved = unresolved or resolved
            continue
        return resolved
    return unresolved or fallback


def _field_variants(key: str) -> set[str]:
    text = key.strip().lower()
    compact = "".join(ch for ch in text if ch.isalnum())
    snake = "_".join(part for part in text.replace("/", " ").split() if part)
    return {text, compact, snake}


def _first_present(source: dict, keys: tuple[str, ...]) -> object:
    normalized: dict[str, object] = {}
    for raw_key, value in source.items():
        for variant in _field_variants(str(raw_key)):
            normalized.setdefault(variant, value)

    for key in keys:
        for variant in _field_variants(key):
            value = normalized.get(variant)
            if value not in (None, ""):
                return value
        value = source.get(key)
        if value not in (None, ""):
            return value
    return None


def _resolve_bdm(job: dict, user_map: dict[str, str]) -> str:
    return _resolve_people_candidates(
        (
            _first_present(
                job,
                (
                    "sales_manager",
                    "sales manager",
                    "bdm_name",
                    "bdm",
                    "hiring_manager",
                    "hiring manager",
                ),
            ),
            _first_present(
                job,
                (
                    "recruitment_manager",
                    "recruitment_manager_id",
                    "recruitment manager",
                    "Recruitment Manager",
                    "bdm_id",
                    "hiring_manager_id",
                    "sales_manager_id",
                    "posted_by",
                    "created_by",
                ),
            ),
        ),
        user_map,
        "Unassigned BDM",
    )


def _clean_person_name(value: object) -> str:
    return " ".join(str(value or "").split())


def _user_display_name(user: dict) -> str:
    name = (
        user.get("display_name")
        or user.get("name")
        or user.get("consultant_name")
        or user.get("full_name")
        or ""
    )
    if not name:
        name = f"{user.get('first_name', '')} {user.get('last_name', '')}"
    if not name:
        name = user.get("email_id") or user.get("email") or "Unknown"
    return _clean_person_name(name)


def _is_active_technical_recruiter(user: dict) -> bool:
    return (
        str(user.get("status") or "").strip().lower() == "active"
        and str(user.get("role") or "").strip().lower() == "technical recruiter"
    )


def _parse_date_yyyy_mm_dd(value: str | None) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_record_date(record: dict, keys: tuple[str, ...]) -> Optional[datetime.date]:
    for key in keys:
        value = _first_present(record, (key,))
        if not value:
            continue
        text = str(value).strip()[:10]
        for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
    return None


def _parse_record_datetime(record: dict, keys: tuple[str, ...]) -> Optional[datetime]:
    for key in keys:
        value = _first_present(record, (key,))
        if not value:
            continue
        text = str(value).strip()
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%y %H:%M:%S",
            "%m/%d/%Y",
            "%m/%d/%y",
        ):
            try:
                return datetime.strptime(text[: len(datetime.now().strftime(fmt))], fmt)
            except ValueError:
                continue
    return None


def _format_time_to_submit(start: Optional[datetime], submissions: list[dict]) -> str:
    if not start or not submissions:
        return "--"

    submitted_values = [
        _parse_record_datetime(
            sub,
            ("submitted_on", "submitted on", "submitted_date", "created", "created_on"),
        )
        for sub in submissions
    ]
    submitted_values = [value for value in submitted_values if value and value >= start]
    if not submitted_values:
        return "--"

    delta = min(submitted_values) - start
    total_minutes = max(0, int(delta.total_seconds() // 60))
    days, remainder = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(remainder, 60)

    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _parse_screen_date(value: object) -> Optional[datetime.date]:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%m/%d/%y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _screen_text(value: object, fallback: str) -> str:
    text = " ".join(str(value or "").split())
    if text and text not in {"0", "N/A", "None", "null"}:
        return text
    return fallback


def _clean_job_code(value: object) -> str:
    return " ".join(str(value or "").upper().replace(" -", " ").replace("-", " ").split())


def _job_id(record: dict) -> str:
    return str(
        _first_present(record, ("job_id", "job id", "requirement_id", "id")) or ""
    ).strip()


def _sub_status(subs: list[dict]) -> str:
    if not subs:
        return "Pending"

    s = sorted(subs, key=lambda x: x.get("submitted_on", ""), reverse=True)
    latest = s[0]
    st = str(
        _first_present(
            latest,
            (
                "status",
                "submission_status",
                "submission status",
                "application_status",
                "application status",
                "candidate_status",
            ),
        )
        or ""
    ).strip()
    return st or "In Progress"


def _resolve_submission_person(subs: list[dict], user_map: dict[str, str]) -> str:
    candidates: list[object] = []
    for sub in subs:
        candidates.append(
            _first_present(
                sub,
                (
                    "recruiter",
                    "recruiter_id",
                    "recruiter_name",
                    "submitted_by",
                    "submitted by",
                    "submitted_by_id",
                    "created_by",
                    "created_by_id",
                    "owner",
                    "owner_id",
                    "assigned_to",
                    "assigned_to_id",
                    "submission_owner",
                    "submission_owner_id",
                ),
            )
        )
    return _resolve_people_candidates(tuple(candidates), user_map, "Unassigned")


def _dedupe_jobs(jobs: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for job in jobs:
        key = str(job.get("id") or job.get("job_code") or "").strip()
        if not key:
            key = str(
                job.get("public_job_title") or job.get("position_title") or job
            ).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique


def _get_high_priority_cache(cache_key: str) -> Optional[list[RequirementItem]]:
    now = time.time()
    cached = _high_priority_cache.get(cache_key)
    if cached and now < cached["expires_at"]:
        logger.debug(
            "/dashboard/high-priority cache HIT key=%s results=%s",
            cache_key,
            len(cached["data"]),
        )
        return cached["data"]
    return None


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    async def build():
        return await asyncio.to_thread(_build_dashboard_stats)

    return await cached_response("dashboard:stats", 60, build)


def _build_dashboard_stats() -> DashboardStats:
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            jobs_future = executor.submit(get_jobs, max_pages=10)
            users_future = executor.submit(get_users)
            applicants_future = executor.submit(get_applicants_total_count)
            submissions_future = executor.submit(get_submissions_total_count)

            jobs, _jobs_total = jobs_future.result()
            users = users_future.result()
            total_applicants = applicants_future.result()
            total_submissions = submissions_future.result()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return DashboardStats(
        active_jobs=len(_dedupe_jobs(list(jobs))),
        total_recruiters=len(users),
        total_applicants=total_applicants,
        total_submissions=total_submissions,
    )


@router.get("/status")
async def get_recruiting_status():
    today = datetime.now().date()

    async def build():
        return await asyncio.to_thread(_build_recruiting_status, today)

    return await cached_response(
        f"dashboard:status:{today.isoformat()}",
        settings.status_cache_ttl_seconds,
        build,
    )


def _build_recruiting_status(today: datetime.date) -> dict:
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            jobs_future = executor.submit(get_jobposts_screen_rows, 0)
            users_future = executor.submit(get_users)
            subs_future = executor.submit(get_all_submissions, max_pages=0)

            screen_rows, _jobs_total = jobs_future.result()
            users = users_future.result()
            subs, _subs_total = subs_future.result()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    active_jobs = [
        row
        for row in screen_rows
        if _screen_text(row.get("job_status_text") or row.get("job_status"), "").lower()
        == "active"
    ]
    technical_recruiters = [user for user in users if _is_active_technical_recruiter(user)]
    technical_recruiter_names = {
        _user_display_name(user)
        for user in technical_recruiters
        if _user_display_name(user)
    }

    today_active_jobs = [
        job
        for job in active_jobs
        if _parse_screen_date(job.get("created_text")) == today
    ]

    working_names: set[str] = set()
    for job in today_active_jobs:
        for name in _split_ids(job.get("assigned_recruiter")):
            clean_value = _clean_person_name(name)
            if clean_value in technical_recruiter_names:
                working_names.add(clean_value)

    recruiters_working = sorted(working_names)
    idle_recruiters = sorted(technical_recruiter_names - working_names)

    active_today = len(today_active_jobs)
    carried_forward = sum(
        1
        for job in active_jobs
        if (created := _parse_screen_date(job.get("created_text"))) is not None
        and created < today
    )

    submissions_today = sum(
        1
        for sub in subs
        if _parse_record_date(
            sub,
            ("submitted_on", "submitted on", "created", "created_on"),
        )
        == today
    )

    return {
        "loadedAt": datetime.now().isoformat(),
        "technicalRecruitersCount": len(technical_recruiter_names),
        "activeRequirementsAsOfToday": active_today,
        "activeRequirementsCarriedForwardUpToYesterday": carried_forward,
        "recruitersWorkingOnRequirementsCount": len(recruiters_working),
        "idleRecruitersCount": len(idle_recruiters),
        "totalSubmissionsToday": submissions_today,
        "recruitersWorkingOnRequirements": recruiters_working,
        "idleRecruiters": idle_recruiters,
    }


@router.get("/today-submissions", response_model=list[TodaySubmissionItem])
async def get_today_submissions():
    today = datetime.now().date()

    async def build():
        return await asyncio.to_thread(_build_today_submissions, today)

    return await cached_response(
        f"dashboard:today-submissions:{today.isoformat()}",
        settings.today_submissions_cache_ttl_seconds,
        build,
    )


def _build_today_submissions(today: datetime.date) -> list[TodaySubmissionItem]:
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            subs_future = executor.submit(get_all_submissions, max_pages=0)
            users_future = executor.submit(get_users)

            subs, _subs_total = subs_future.result()
            users = users_future.result()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    user_map = build_user_map(users)
    today_subs = [
        sub
        for sub in subs
        if _parse_record_date(
            sub,
            ("submitted_on", "submitted on", "submitted_date", "submission_date", "created", "created_on"),
        )
        == today
    ]

    job_title_cache: dict[str, str] = {}

    def resolve_job_title(job_id: str) -> str:
        if not job_id:
            return "Unassigned Requirement"
        if job_id not in job_title_cache:
            details = get_job_details(job_id)
            title = _first_present(
                details,
                (
                    "job_title",
                    "job title",
                    "position_title",
                    "position title",
                    "requirement",
                    "title",
                    "posting_title",
                ),
            )
            job_title_cache[job_id] = _clean_title(str(title or "")) if title else "Unassigned Requirement"
        return job_title_cache[job_id]

    results: list[TodaySubmissionItem] = []
    for sub in sorted(today_subs, key=lambda item: str(item.get("submitted_on") or ""), reverse=True):
        job_id = _job_id(sub)
        recruiter = _resolve_people_candidates(
            (
                _first_present(
                    sub,
                    (
                        "submitted_by",
                        "submitted by",
                        "submitted_by_id",
                        "recruiter",
                        "recruiter_id",
                        "created_by",
                    ),
                ),
            ),
            user_map,
            "Unassigned",
        )
        results.append(
            TodaySubmissionItem(
                submission_id=str(_first_present(sub, ("submission_id", "id")) or ""),
                submitted_on=str(_first_present(sub, ("submitted_on", "submitted on")) or ""),
                recruiter=recruiter,
                job_title=resolve_job_title(job_id),
                job_id=job_id,
                candidate_id=str(_first_present(sub, ("job_seeker_id", "candidate_id", "applicant_id")) or ""),
                status=str(_first_present(sub, ("submission_status", "status", "application_status")) or "In Progress"),
                source=str(_first_present(sub, ("source",)) or "--"),
                employment_type=str(_first_present(sub, ("employment_type", "employment type")) or "--"),
                pay_rate=str(_first_present(sub, ("pay_rate", "pay rate")) or "--"),
                tax_term=str(_first_present(sub, ("tax_term", "tax term")) or "--"),
            )
        )

    return results


@router.get("/bdm-performance", response_model=list[BdmKpiItem])
async def get_bdm_performance(period: str = Query("today", pattern="^(today|yesterday)$")):
    cache_key = f"dashboard:bdm-performance:{period}:{datetime.now().date().isoformat()}"

    async def build():
        return await asyncio.to_thread(_build_bdm_performance, period)

    return await cached_response(
        cache_key,
        settings.bdm_performance_cache_ttl_seconds,
        build,
    )


def _build_bdm_performance(period: str) -> list[BdmKpiItem]:
    target_date = datetime.now().date()
    if period == "yesterday":
        target_date = target_date - timedelta(days=1)

    try:
        screen_rows, _screen_total = get_jobposts_screen_rows(max_pages=0)
    except RuntimeError as exc:
        logger.warning("CEIPAL JobPosts screen fetch failed; falling back to v2 API: %s", exc)
    except Exception as exc:
        logger.warning("CEIPAL JobPosts screen fetch failed; falling back to v2 API: %s", exc)
    else:
        groups: dict[str, BdmKpiItem] = {}
        for row in screen_rows:
            status = _screen_text(row.get("job_status_text") or row.get("job_status"), "").lower()
            if status != "active":
                continue
            if _parse_screen_date(row.get("created_text")) != target_date:
                continue

            bdm_name = _resolve_people_candidates(
                (
                    row.get("sales_manager"),
                    row.get("hiring_manager"),
                    row.get("recruitment_manager"),
                ),
                {},
                "Unassigned BDM",
            )
            groups.setdefault(
                bdm_name,
                BdmKpiItem(
                    bdm_name=bdm_name,
                    requirements_received=0,
                    profiles_submitted=0,
                    feedback_pending=0,
                    interviews=0,
                    closures=0,
                ),
            )
            row_group = groups[bdm_name]
            submissions_count = int(row.get("submissions_count") or 0)
            row_group.requirements_received += 1
            row_group.profiles_submitted += submissions_count
            row_group.feedback_pending += submissions_count

        return sorted(
            groups.values(),
            key=lambda row: (
                -row.requirements_received,
                -row.profiles_submitted,
                row.bdm_name,
            ),
        )

    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            jobs_future = executor.submit(
                get_jobs,
                max_pages=0,
                stop_before_date=target_date.isoformat(),
            )
            users_future = executor.submit(get_users)
            subs_future = executor.submit(get_all_submissions, max_pages=0)

            jobs, _jobs_total = jobs_future.result()
            users = users_future.result()
            subs, _subs_total = subs_future.result()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    user_map = build_user_map(users)
    all_jobs = _dedupe_jobs(list(jobs))
    jobs = [
        job
        for job in all_jobs
        if _parse_record_date(job, ("created", "created_on", "modified"))
        == target_date
    ]

    bdm_by_job = {
        str(job.get("id") or "").strip(): _resolve_bdm(job, user_map)
        for job in all_jobs
        if str(job.get("id") or "").strip()
    }

    submission_job_ids = {
        _job_id(sub)
        for sub in subs
        if _parse_record_date(
            sub,
            ("submitted_on", "submitted on", "created", "created_on"),
        )
        == target_date
    }
    for job_id in sorted(submission_job_ids - set(bdm_by_job)):
        if not job_id:
            continue
        details = get_job_details(job_id)
        if details:
            bdm_by_job[job_id] = _resolve_bdm(details, user_map)

    groups: dict[str, BdmKpiItem] = {}

    for job in jobs:
        bdm_name = bdm_by_job.get(str(job.get("id") or "").strip(), "Unassigned BDM")
        groups.setdefault(
            bdm_name,
            BdmKpiItem(
                bdm_name=bdm_name,
                requirements_received=0,
                profiles_submitted=0,
                feedback_pending=0,
                interviews=0,
                closures=0,
            ),
        )
        groups[bdm_name].requirements_received += 1

    for sub in subs:
        submitted = _parse_record_date(
            sub,
            ("submitted_on", "submitted on", "created", "created_on"),
        )
        if submitted != target_date:
            continue

        bdm_name = bdm_by_job.get(_job_id(sub), "Unassigned BDM")
        groups.setdefault(
            bdm_name,
            BdmKpiItem(
                bdm_name=bdm_name,
                requirements_received=0,
                profiles_submitted=0,
                feedback_pending=0,
                interviews=0,
                closures=0,
            ),
        )
        row = groups[bdm_name]
        row.profiles_submitted += 1

        status = _sub_status([sub]).lower()
        if "pending" in status or "waiting" in status:
            row.feedback_pending += 1
        if "interview" in status:
            row.interviews += 1
        if any(word in status for word in ("closure", "placed", "hired", "joined")):
            row.closures += 1

    return sorted(
        groups.values(),
        key=lambda row: (
            -row.requirements_received,
            -row.profiles_submitted,
            row.bdm_name,
        ),
    )


@router.get("/high-priority", response_model=list[RequirementItem])
async def get_high_priority_requirements(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    p_from = _parse_date_yyyy_mm_dd(date_from)
    p_to = _parse_date_yyyy_mm_dd(date_to)

    if not p_from and not p_to:
        p_from = datetime.now().date() - timedelta(days=1)
        p_to = p_from

    cache_key = f"dashboard:high-priority:{p_from.isoformat() if p_from else ''}:{p_to.isoformat() if p_to else ''}"

    async def build():
        return await asyncio.to_thread(
            _build_high_priority_requirements,
            date_from,
            date_to,
        )

    return await cached_response(cache_key, _HIGH_PRIORITY_TTL, build)


def _build_high_priority_requirements(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list[RequirementItem]:
    p_from = _parse_date_yyyy_mm_dd(date_from)
    p_to = _parse_date_yyyy_mm_dd(date_to)

    if not p_from and not p_to:
        p_from = datetime.now().date() - timedelta(days=1)
        p_to = p_from

    cache_key = f"posted-jobs:{p_from.isoformat() if p_from else ''}:{p_to.isoformat() if p_to else ''}"
    with _high_priority_lock:
        cached_result = _get_high_priority_cache(cache_key)
        if cached_result is not None:
            return cached_result

    has_filter = bool(p_from or p_to)

    try:
        if not _USE_JOBPOSTS_SCREEN_SOURCE:
            raise RuntimeError("Using v2 API source for time-to-submit support")
        screen_rows, screen_total = get_jobposts_screen_rows(max_pages=0)
    except RuntimeError as exc:
        logger.info("CEIPAL JobPosts screen source skipped; falling back to v2 API: %s", exc)
    except Exception as exc:
        logger.warning("CEIPAL JobPosts screen fetch failed; falling back to v2 API: %s", exc)
    else:
        try:
            with ThreadPoolExecutor(max_workers=3) as executor:
                jobs_future = executor.submit(
                    get_jobs,
                    max_pages=0,
                    stop_before_date=p_from.isoformat() if p_from else None,
                )
                users_future = executor.submit(get_users)
                subs_future = executor.submit(get_all_submissions, max_pages=0)

                v2_jobs, _jobs_total = jobs_future.result()
                users = users_future.result()
                subs_list, _subs_total = subs_future.result()
        except RuntimeError:
            v2_jobs = []
            users = []
            subs_list = []

        user_map = build_user_map(users)
        jobs_by_code = {
            _clean_job_code(job.get("job_code")): job
            for job in v2_jobs
            if _clean_job_code(job.get("job_code"))
        }

        subs_by_job: dict[str, list[dict]] = {}
        for sub in subs_list:
            jid = _job_id(sub)
            if jid:
                subs_by_job.setdefault(jid, []).append(sub)

        results: list[RequirementItem] = []
        for row in screen_rows:
            status = _screen_text(
                row.get("job_status_text") or row.get("job_status"),
                "",
            ).lower()
            if status != "active":
                continue

            priority = _screen_text(row.get("priority_id"), "Not Set")

            if has_filter:
                created = _parse_screen_date(row.get("created_text"))
                in_range = False
                if created is not None:
                    in_range = True
                    if p_from and created < p_from:
                        in_range = False
                    if p_to and created > p_to:
                        in_range = False
            if not in_range:
                continue

            matching_job = jobs_by_code.get(_clean_job_code(row.get("job_code_text")))
            job_id = _job_id(matching_job or row)
            job_subs = subs_by_job.get(job_id, [])
            submission_person = _resolve_submission_person(job_subs, user_map)
            created_at = _parse_record_datetime(
                matching_job or row,
                ("created", "created_on", "created_text"),
            )
            lead = _resolve_people_candidates(
                (
                    row.get("primary_recruiter"),
                    _first_present(
                        matching_job or {},
                        (
                            "primary_recruiter",
                            "primary_recruiter_id",
                            "primary recruiter",
                            "lead_recruiter",
                            "lead recruiter",
                            "lead",
                        ),
                    ),
                    submission_person,
                    row.get("assigned_recruiter"),
                ),
                user_map,
                "Unassigned",
            )
            recruiter = _resolve_people_candidates(
                (
                    row.get("assigned_recruiter"),
                    _first_present(
                        matching_job or {},
                        (
                            "assigned_recruiter",
                            "assigned recruiter",
                            "assigned_recruiter_id",
                            "assigned_to",
                            "assigned_to_id",
                            "recruiter",
                            "recruiter_id",
                            "recruiter_name",
                        ),
                    ),
                    submission_person,
                    row.get("primary_recruiter"),
                ),
                user_map,
                "Unassigned",
            )

            results.append(
                RequirementItem(
                    bdm=_resolve_people_candidates(
                        (
                            row.get("sales_manager"),
                            row.get("hiring_manager"),
                            _first_present(
                                matching_job or {},
                                (
                                    "sales_manager",
                                    "sales manager",
                                    "hiring_manager",
                                    "hiring manager",
                                    "recruitment_manager",
                                    "recruitment_manager_id",
                                ),
                            ),
                        ),
                        user_map,
                        "Unassigned BDM",
                    ),
                    lead=lead,
                    recruiter=recruiter,
                    priority=priority,
                    submissions=int(row.get("submissions_count") or 0),
                    submission_status=_sub_status(job_subs),
                    requirement=_screen_text(row.get("requirement_text"), "Untitled"),
                    time_to_submit=_format_time_to_submit(created_at, job_subs),
                )
            )

        priority_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Not Set": 4}
        results.sort(key=lambda item: (priority_order.get(item.priority, 9), -item.submissions))
        logger.debug(
            "/dashboard/high-priority source=JobPosts screen_rows=%s/%s results=%s",
            len(screen_rows),
            screen_total,
            len(results),
        )
        with _high_priority_lock:
            _high_priority_cache[cache_key] = {
                "data": results,
                "expires_at": time.time() + _HIGH_PRIORITY_TTL,
            }
        return results

    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            if has_filter:
                jobs_future = executor.submit(
                    get_jobs, max_pages=10, stop_before_date=date_from
                )
            else:
                jobs_future = executor.submit(get_jobs, max_pages=2)
            users_future = executor.submit(get_users)
            subs_future = executor.submit(get_all_submissions, max_pages=5)

            jobs_list, jobs_total = jobs_future.result()
            users = users_future.result()
            subs_list, _subs_total = subs_future.result()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    user_map = build_user_map(users)

    subs_by_job: dict[str, list[dict]] = {}
    for sub in subs_list:
        jid = str(sub.get("job_id", "")).strip()
        if jid:
            subs_by_job.setdefault(jid, []).append(sub)

    jobs = _dedupe_jobs(list(jobs_list))

    # Debug: log first job structure to see what fields CEIPAL provides
    if jobs:
        logger.debug(
            "DEBUG: Sample job from CEIPAL has fields: %s",
            list(jobs[0].keys()) if isinstance(jobs[0], dict) else "not a dict",
        )

    # Date filter: match CEIPAL JobPosts "Job Created" / posted date.
    if has_filter:
        filtered: list[dict] = []
        for j in jobs:
            cr = str(j.get("created", ""))[:10]

            cd = None
            if cr:
                try:
                    cd = datetime.strptime(cr, "%Y-%m-%d").date()
                except ValueError:
                    cd = None

            in_range = cd is not None
            if cd is not None:
                if p_from and cd < p_from:
                    in_range = False
                if p_to and cd > p_to:
                    in_range = False

            if in_range:
                filtered.append(j)

        jobs = filtered

    jobs = [
        job
        for job in jobs
        if _screen_text(
            _first_present(job, ("job_status", "job status", "status")),
            "Active",
        ).lower()
        == "active"
    ]

    def process_job(job: dict) -> RequirementItem:
        job_id = str(job.get("id", "")).strip()
        recruiter_ids = _first_present(
            job,
            (
                # Assigned variants
                "assigned_to",
                "assigned_to_id",
                "assigned to",
                "Assigned To",
                "assigned_recruiter",
                "assigned_recruiter_id",
                "assigned recruiter",
                "Assigned Recruiter",
                # Generic recruiter variants  
                "recruiter",
                "recruiter_id",
                "recruiter_name",
                "Recruiter",
                "Recruiter ID",
                # Owner/manager variants
                "owner",
                "owner_id",
                "Owner",
                "Owner ID",
                "consultant",
                "consultant_id",
                "Consultant",
                "Consultant ID",
                "account_manager",
                "account_manager_id",
                "Account Manager",
                "Account Manager ID",
                # CEIPAL specific
                "contact_person",
                "contact_person_id",
                "point_of_contact",
                "poc",
                "coordinator",
                "coordinator_id",
                "job_coordinator",
                "job_coordinator_id",
            ),
        )
        job_subs = subs_by_job.get(job_id, [])
        submission_person = _resolve_submission_person(job_subs, user_map)
        recruiter = _resolve_people_candidates(
            (
                recruiter_ids,
                submission_person,
                _first_present(
                    job,
                    (
                        "primary_recruiter",
                        "primary_recruiter_id",
                        "primary recruiter",
                        "Primary Recruiter",
                    ),
                ),
                _first_present(
                    job,
                    (
                        "recruitment_manager",
                        "recruitment_manager_id",
                        "recruitment manager",
                    ),
                ),
            ),
            user_map,
            "Unassigned",
        )
        bdm = _resolve_bdm(job, user_map)
        lead = _resolve_people_candidates(
            (
                _first_present(
                    job,
                    (
                        "primary_recruiter",
                        "primary_recruiter_id",
                        "primary recruiter",
                        "Primary Recruiter",
                        "lead_recruiter",
                        "lead recruiter",
                        "lead",
                    ),
                ),
                submission_person,
                recruiter_ids,
            ),
            user_map,
            "Unassigned",
        )

        title = _clean_title(job.get("public_job_title") or job.get("position_title") or "Untitled")

        # IMPORTANT: use cache-only priority to avoid per-job network calls during rendering.
        priority = get_priority_cached(job_id)

        created_at = _parse_record_datetime(job, ("created", "created_on", "job_created"))


        return RequirementItem(
            bdm=bdm,
            lead=lead,
            recruiter=recruiter,
            priority=priority,
            submissions=len(job_subs),
            submission_status=_sub_status(job_subs),
            requirement=title,
            time_to_submit=_format_time_to_submit(created_at, job_subs),
        )

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(process_job, jobs))
    flush_job_detail_cache()

    # Sort: Critical first; then by submissions.
    priority_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Not Set": 4}
    results.sort(key=lambda x: (priority_order.get(x.priority, 9), -x.submissions))

    logger.debug(
        "/dashboard/high-priority jobs=%s/%s subs=%s/%s filtered=%s results=%s",
        len(jobs_list),
        jobs_total,
        len(subs_list),
        _subs_total,
        has_filter,
        len(results),
    )

    with _high_priority_lock:
        _high_priority_cache[cache_key] = {
            "data": results,
            "expires_at": time.time() + _HIGH_PRIORITY_TTL,
        }
    return results


# NOTE:
# /dashboard/bdm-wise has been intentionally removed.
# Frontend currently loads /dashboard/high-priority for both dashboard and priority screen.
# Keeping an extra route duplicates logic and can confuse API consumers.



async def warm_dashboard_caches() -> None:
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    warmers = [
        get_recruiting_status(),
        get_bdm_performance("today"),
        get_bdm_performance("yesterday"),
        get_high_priority_requirements(
            date_from=today.isoformat(),
            date_to=today.isoformat(),
        ),
        get_high_priority_requirements(
            date_from=yesterday.isoformat(),
            date_to=yesterday.isoformat(),
        ),
    ]
    results = await asyncio.gather(*warmers, return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Dashboard cache warm failed: %s", result)


@router.get("/raw-data")
async def get_raw_data():
    if settings.app_env.lower() != "development":
        raise HTTPException(status_code=404, detail="Not found")

    return await asyncio.to_thread(_build_raw_data)


def _build_raw_data() -> dict:
    try:
        jobs, jt = get_jobs()
        users = get_users()
        subs, st = get_all_submissions()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {
        "jobs_fetched": len(jobs),
        "jobs_total": jt,
        "subs_fetched": len(subs),
        "subs_total": st,
        "users": len(users),
        "sample_job": {
            k: v
            for k, v in jobs[0].items()
            if k not in ("public_job_desc", "requisition_description")
        }
        if jobs
        else {},
    }
