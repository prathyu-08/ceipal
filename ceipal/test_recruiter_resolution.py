#!/usr/bin/env python3
"""Test recruiter resolution logic."""

# Sample CEIPAL job data
sample_job = {
    "id": "cjJmWnhZajEyamxzOW8xd25rMk01Zz09",
    "position_title": "QA Automation Tester",
    "assigned_recruiter": "",
    "sales_manager": "",
    "primary_recruiter": "",
    "recruitment_manager": "eG9mWXk1Uk1ZTTVBQU13eDhLTWJkZD09",
}

# Sample user map
user_map = {
    "eG9mWXk1Uk1ZTTVBQU13eDhLTWJkZD09": "Bhavya Surabhi",
    "user123": "Rishi Balgotra",
}

# Replicate the _first_present and _resolve functions
def _field_variants(key: str):
    text = key.strip().lower()
    compact = "".join(ch for ch in text if ch.isalnum())
    snake = "_".join(part for part in text.replace("/", " ").split() if part)
    return {text, compact, snake}

def _first_present(source, keys):
    normalized = {}
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

def _split_ids(value):
    if value is None:
        return []
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value).replace(";", ",").replace("|", ",").split(",")
    return [str(item).strip() for item in raw if str(item).strip()]

def _resolve_people(value, user_map, fallback):
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

def _resolve_recruiters(value, user_map):
    if not value:
        return "Unassigned"
    return _resolve_people(value, user_map, "Unassigned")

# Test the new field list
recruiter_ids = _first_present(
    sample_job,
    (
        "primary_recruiter",
        "primary_recruiter_id",
        "primary recruiter",
        "Primary Recruiter",
        "assigned_recruiter",
        "assigned_recruiter_id",
        "recruiter",
        "recruiter_id",
        "recruiter_name",
        "assigned_to",
        "assigned_to_id",
        "owner",
        "owner_id",
        "consultant",
        "consultant_id",
        "account_manager",
        "account_manager_id",
    ),
)

print(f"Found recruiter_ids: {recruiter_ids}")

recruiter = _resolve_recruiters(recruiter_ids, user_map)
print(f"Resolved recruiter: {recruiter}")

# The issue: all recruiter fields are empty, so it returns None
# which becomes "Unassigned"
# 
# Potential solution: also check recruitment_manager as fallback

print("\n--- Testing with recruitment_manager as fallback ---")

recruiter_ids_with_fallback = _first_present(
    sample_job,
    (
        "primary_recruiter",
        "primary_recruiter_id",
        "primary recruiter",
        "Primary Recruiter",
        "assigned_recruiter",
        "assigned_recruiter_id",
        "recruiter",
        "recruiter_id",
        "recruiter_name",
        "assigned_to",
        "assigned_to_id",
        "owner",
        "owner_id",
        "consultant",
        "consultant_id",
        "account_manager",
        "account_manager_id",
        "recruitment_manager",
        "recruitment_manager_id",
    ),
)

print(f"Found recruiter_ids with fallback: {recruiter_ids_with_fallback}")

recruiter_with_fallback = _resolve_recruiters(recruiter_ids_with_fallback, user_map)
print(f"Resolved recruiter: {recruiter_with_fallback}")
