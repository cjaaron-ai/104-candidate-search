"""
JD Scorecard 評分引擎

依據 JD 定義的各項條件與權重，對候選人進行匹配度評分。
評分維度：技能、經驗、學歷、產業、地區、薪資。
"""

import logging

from app.models.job import JobDescription
from app.models.candidate import Candidate

logger = logging.getLogger(__name__)

EDUCATION_RANK = {"高中": 1, "專科": 2, "學士": 3, "碩士": 4, "博士": 5}


def score_candidate(job: JobDescription, candidate: Candidate) -> dict:
    """計算單一候選人對特定 JD 的匹配分數"""

    details = {}

    # 1. 技能匹配度 (0-100)
    score_skills, details["skills"] = _score_skills(job, candidate)

    # 2. 工作經驗相關性 (0-100)
    score_exp, details["experience"] = _score_experience(job, candidate)

    # 3. 學歷符合度 (0-100)
    score_edu, details["education"] = _score_education(job, candidate)

    # 4. 產業背景相關性 (0-100)
    score_ind, details["industry"] = _score_industry(job, candidate)

    # 5. 地區匹配度 (0-100)
    score_loc, details["location"] = _score_location(job, candidate)

    # 6. 薪資期望匹配度 (0-100)
    score_sal, details["salary"] = _score_salary(job, candidate)

    # 加權總分
    total_weight = (
        job.weight_skills + job.weight_experience + job.weight_education
        + job.weight_industry + job.weight_location + job.weight_salary
    )

    if total_weight == 0:
        total_weight = 100.0

    total_score = (
        score_skills * job.weight_skills
        + score_exp * job.weight_experience
        + score_edu * job.weight_education
        + score_ind * job.weight_industry
        + score_loc * job.weight_location
        + score_sal * job.weight_salary
    ) / total_weight

    return {
        "score_skills": round(score_skills, 1),
        "score_experience": round(score_exp, 1),
        "score_education": round(score_edu, 1),
        "score_industry": round(score_ind, 1),
        "score_location": round(score_loc, 1),
        "score_salary": round(score_sal, 1),
        "total_score": round(total_score, 1),
        "score_details": details,
    }


def _score_skills(job: JobDescription, candidate: Candidate) -> tuple[float, dict]:
    required = set(s.lower() for s in (job.required_skills or []))
    preferred = set(s.lower() for s in (job.preferred_skills or []))
    candidate_skills = set(s.lower() for s in (candidate.skills or []))

    if not required and not preferred:
        return 100.0, {"reason": "JD 未定義技能要求"}

    # 必要技能匹配（佔 70%）
    required_match = required & candidate_skills
    required_score = (len(required_match) / len(required) * 100) if required else 100

    # 加分技能匹配（佔 30%）
    preferred_match = preferred & candidate_skills
    preferred_score = (len(preferred_match) / len(preferred) * 100) if preferred else 0

    score = required_score * 0.7 + preferred_score * 0.3

    return score, {
        "required_matched": list(required_match),
        "required_missing": list(required - candidate_skills),
        "preferred_matched": list(preferred_match),
    }


def _score_experience(job: JobDescription, candidate: Candidate) -> tuple[float, dict]:
    cand_exp = candidate.experience_years or 0
    min_exp = job.min_experience_years or 0
    max_exp = job.max_experience_years

    if min_exp == 0 and max_exp is None:
        return 100.0, {"reason": "JD 未定義經驗要求"}

    if max_exp and min_exp <= cand_exp <= max_exp:
        score = 100.0
    elif cand_exp >= min_exp:
        # 超過最大值，稍微扣分
        over = cand_exp - (max_exp or min_exp + 5)
        score = max(60.0, 100.0 - over * 5)
    else:
        # 不足最低要求
        gap = min_exp - cand_exp
        score = max(0.0, 100.0 - gap * 20)

    return score, {
        "candidate_years": cand_exp,
        "required_range": f"{min_exp}-{max_exp or '不限'}",
    }


def _score_education(job: JobDescription, candidate: Candidate) -> tuple[float, dict]:
    required_level = job.education_level
    cand_level = candidate.education_level

    if not required_level:
        return 100.0, {"reason": "JD 未定義學歷要求"}

    req_rank = EDUCATION_RANK.get(required_level, 0)
    cand_rank = EDUCATION_RANK.get(cand_level, 0)

    if cand_rank >= req_rank:
        score = 100.0
    elif cand_rank == req_rank - 1:
        score = 70.0
    else:
        score = max(0.0, 100.0 - (req_rank - cand_rank) * 30)

    return score, {
        "required": required_level,
        "candidate": cand_level or "未知",
    }


def _score_industry(job: JobDescription, candidate: Candidate) -> tuple[float, dict]:
    if not job.industry:
        return 100.0, {"reason": "JD 未定義產業要求"}

    if not candidate.industry:
        return 50.0, {"reason": "候選人未填寫產業"}

    if job.industry.lower() in candidate.industry.lower():
        return 100.0, {"match": True}
    return 40.0, {"match": False, "jd": job.industry, "candidate": candidate.industry}


def _score_location(job: JobDescription, candidate: Candidate) -> tuple[float, dict]:
    if not job.location:
        return 100.0, {"reason": "JD 未定義地區要求"}

    if not candidate.location:
        return 50.0, {"reason": "候選人未填寫地區"}

    if job.location in candidate.location or candidate.location in job.location:
        return 100.0, {"match": True}
    return 30.0, {"match": False, "jd": job.location, "candidate": candidate.location}


def _score_salary(job: JobDescription, candidate: Candidate) -> tuple[float, dict]:
    if not job.salary_max:
        return 100.0, {"reason": "JD 未定義薪資"}

    if not candidate.expected_salary_min:
        return 70.0, {"reason": "候選人未填寫期望薪資"}

    cand_min = candidate.expected_salary_min
    job_max = job.salary_max
    job_min = job.salary_min or 0

    if cand_min <= job_max:
        return 100.0, {"within_budget": True}

    over_pct = (cand_min - job_max) / job_max * 100
    score = max(0.0, 100.0 - over_pct * 2)
    return score, {"over_budget_pct": round(over_pct, 1)}
