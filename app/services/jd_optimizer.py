"""
JD 優化服務 — 混合模式（規則比對 + LLM 生成）

根據目標履歷分析 JD 差異，產生改寫建議。
"""

import logging
from datetime import datetime

from google.cloud import firestore

from app.config import settings
from app.models.job import JobDescription
from app.repositories.jobs import JobRepository
from app.repositories.analyses import AnalysisRepository
from crawler.crawler_104 import Crawler104, CandidateData

logger = logging.getLogger(__name__)


async def optimize_jd_for_target(
    job_id: int,
    resume_url: str,
    db: firestore.Client,
):
    """主流程：爬取目標履歷 → 規則比對 → LLM 生成建議"""
    job_repo = JobRepository(db)
    analysis_repo = AnalysisRepository(db)

    job = job_repo.get_job(job_id)
    if not job:
        raise ValueError(f"Job ID {job_id} not found")

    analysis = analysis_repo.create_analysis({
        "job_id": job.id,
        "analysis_type": "resume_optimization",
        "target_url": resume_url,
        "status": "processing",
    })

    try:
        crawler = Crawler104(
            settings.account_104_username,
            settings.account_104_password,
            cookie_storage_path=settings.cookie_storage_path,
        )
        try:
            await crawler.start()
            logged_in = await crawler.login()
            if not logged_in:
                raise RuntimeError("104 登入失敗")
            resume_data = await crawler.scrape_candidate_profile(resume_url)
        finally:
            await crawler.close()

        rule_analysis = _rule_based_analysis(job, resume_data)
        llm_result = await _llm_generate_suggestions(job, resume_data, rule_analysis)

        analysis = analysis_repo.update_analysis(analysis.id, {
            "summary": {
                "rule_analysis": rule_analysis,
                "resume_profile": {
                    "name": resume_data.name,
                    "title": resume_data.title,
                    "experience_years": resume_data.experience_years,
                    "skills": resume_data.skills,
                    "education_level": resume_data.education_level,
                    "industry": resume_data.industry,
                },
            },
            "recommendations": llm_result.get("recommendations", []),
            "report_markdown": llm_result.get("report_markdown", ""),
            "status": "completed",
            "completed_at": datetime.utcnow(),
        })

    except Exception as e:
        analysis_repo.update_analysis(analysis.id, {
            "status": "failed",
            "summary": {"error": str(e)},
        })
        logger.error(f"JD 優化分析失敗: {e}")
        raise

    return analysis


def _rule_based_analysis(job: JobDescription, resume: CandidateData) -> dict:
    """規則比對：找出 JD 與目標履歷間的結構化差異"""
    diffs = []

    jd_skills = set(s.lower() for s in (job.required_skills or []))
    resume_skills = set(s.lower() for s in (resume.skills or []))

    missing_in_jd = resume_skills - jd_skills
    if missing_in_jd:
        diffs.append({
            "field": "skills", "type": "missing_in_jd",
            "current_jd": list(jd_skills), "resume_has": list(missing_in_jd),
            "suggestion": f"履歷具備但 JD 未列出的技能：{', '.join(missing_in_jd)}",
        })

    jd_only = jd_skills - resume_skills
    if jd_only:
        diffs.append({
            "field": "skills", "type": "jd_only",
            "current_jd": list(jd_only),
            "suggestion": f"JD 要求但目標人選不具備的技能：{', '.join(jd_only)}（考慮移至加分項）",
        })

    if resume.experience_years and job.min_experience_years:
        if resume.experience_years < job.min_experience_years:
            diffs.append({
                "field": "experience", "type": "range_mismatch",
                "current_jd": f"{job.min_experience_years}-{job.max_experience_years}",
                "resume_value": resume.experience_years,
                "suggestion": f"目標人選經驗 {resume.experience_years} 年低於 JD 最低要求 {job.min_experience_years} 年，建議降低門檻",
            })

    edu_rank = {"高中": 1, "專科": 2, "學士": 3, "碩士": 4, "博士": 5}
    jd_rank = edu_rank.get(job.education_level, 0)
    resume_rank = edu_rank.get(resume.education_level, 0)
    if jd_rank and resume_rank and resume_rank < jd_rank:
        diffs.append({
            "field": "education", "type": "level_mismatch",
            "current_jd": job.education_level, "resume_value": resume.education_level,
            "suggestion": f"JD 要求 {job.education_level} 但目標人選為 {resume.education_level}，建議放寬學歷要求",
        })

    if resume.expected_salary_min and job.salary_max:
        if resume.expected_salary_min > job.salary_max:
            over_pct = round((resume.expected_salary_min - job.salary_max) / job.salary_max * 100)
            diffs.append({
                "field": "salary", "type": "budget_gap",
                "current_jd": f"{job.salary_min}-{job.salary_max}",
                "resume_value": resume.expected_salary_min,
                "suggestion": f"目標人選期望薪資超出預算 {over_pct}%，建議調整薪資範圍",
            })

    if resume.industry and job.industry:
        if job.industry.lower() not in resume.industry.lower():
            diffs.append({
                "field": "industry", "type": "mismatch",
                "current_jd": job.industry, "resume_value": resume.industry,
                "suggestion": f"目標人選來自「{resume.industry}」，JD 設定為「{job.industry}」，可考慮擴大產業範圍",
            })

    return {"differences": diffs, "diff_count": len(diffs)}


async def _llm_generate_suggestions(job, resume, rule_analysis) -> dict:
    """呼叫 Claude API 生成自然語言的 JD 改寫建議"""
    if not settings.anthropic_api_key:
        return _fallback_format(job, rule_analysis)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        prompt = f"""你是一位資深招募顧問。根據以下目標候選人履歷與現有 JD 的差異分析，請提供：
1. 具體的 JD 改寫建議（每項含 field、current、suggested、reason）
2. 一份完整的修改版 JD 文案

## 現有 JD
- 職稱：{job.title}
- 必要技能：{', '.join(job.required_skills or [])}
- 經驗要求：{job.min_experience_years}-{job.max_experience_years or '不限'} 年
- 學歷要求：{job.education_level or '不限'}
- 薪資：{job.salary_min or '?'}-{job.salary_max or '?'}

## 目標候選人
- 職稱：{resume.title}
- 技能：{', '.join(resume.skills or [])}
- 經驗：{resume.experience_years} 年
- 學歷：{resume.education_level}

## 差異
{_format_diffs(rule_analysis)}

請用繁體中文回答，以 JSON 格式回傳：
{{"recommendations": [{{"field": "...", "current": "...", "suggested": "...", "reason": "..."}}], "revised_jd_text": "完整修改版 JD"}}
"""

        message = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        import json, re
        response_text = message.content[0].text
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            json_match = re.search(r"\{[\s\S]*\}", response_text)
            result = json.loads(json_match.group()) if json_match else {"recommendations": [], "revised_jd_text": response_text}

        result["report_markdown"] = _generate_report(job, resume, rule_analysis, result)
        return result

    except Exception as e:
        logger.warning(f"LLM 生成失敗，回退到規則模式: {e}")
        return _fallback_format(job, rule_analysis)


def _fallback_format(job, rule_analysis):
    recs = [{"field": d["field"], "current": d.get("current_jd", ""), "suggested": d.get("resume_value", ""), "reason": d["suggestion"]} for d in rule_analysis.get("differences", [])]
    return {"recommendations": recs, "report_markdown": _generate_report(job, None, rule_analysis, {"recommendations": recs})}


def _format_diffs(rule_analysis):
    return "\n".join(f"- [{d['field']}] {d['suggestion']}" for d in rule_analysis.get("differences", [])) or "無明顯差異"


def _generate_report(job, resume, rule_analysis, llm_result):
    lines = [f"# JD 優化建議報告", f"", f"## 分析對象", f"- **職缺**: {job.title}"]
    if resume:
        lines.extend([f"- **目標人選**: {resume.name or '未知'}（{resume.title}）", f"- **經驗**: {resume.experience_years} 年"])
    lines.extend([f"", f"## 差異分析（共 {rule_analysis['diff_count']} 項）"])
    for d in rule_analysis.get("differences", []):
        lines.append(f"- **{d['field']}**: {d['suggestion']}")
    lines.extend([f"", f"## 改寫建議"])
    for i, r in enumerate(llm_result.get("recommendations", []), 1):
        lines.extend([f"### {i}. {r.get('field', '')}", f"- **現況**: {r.get('current', '')}", f"- **建議**: {r.get('suggested', '')}", f"- **原因**: {r.get('reason', '')}", ""])
    revised = llm_result.get("revised_jd_text", "")
    if revised:
        lines.extend([f"## 修改版 JD", "", revised])
    return "\n".join(lines)
