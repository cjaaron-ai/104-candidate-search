"""
JD 優化服務 — 混合模式（規則比對 + LLM 生成）

根據目標履歷分析 JD 差異，產生改寫建議。
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.models.job import JobDescription
from app.models.jd_analysis import JDAnalysis
from app.services.jd_parser import parse_jd_from_url
from crawler.crawler_104 import Crawler104, CandidateData

logger = logging.getLogger(__name__)


async def optimize_jd_for_target(
    job_id: int,
    resume_url: str,
    db: Session,
) -> JDAnalysis:
    """主流程：爬取目標履歷 → 規則比對 → LLM 生成建議"""
    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        raise ValueError(f"Job ID {job_id} not found")

    analysis = JDAnalysis(
        job_id=job.id,
        analysis_type="resume_optimization",
        target_url=resume_url,
        status="processing",
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    try:
        # 爬取目標履歷
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

        # 階段一：規則比對
        rule_analysis = _rule_based_analysis(job, resume_data)

        # 階段二：LLM 生成
        llm_result = await _llm_generate_suggestions(job, resume_data, rule_analysis)

        analysis.summary = {
            "rule_analysis": rule_analysis,
            "resume_profile": {
                "name": resume_data.name,
                "title": resume_data.title,
                "experience_years": resume_data.experience_years,
                "skills": resume_data.skills,
                "education_level": resume_data.education_level,
                "industry": resume_data.industry,
            },
        }
        analysis.recommendations = llm_result.get("recommendations", [])
        analysis.report_markdown = llm_result.get("report_markdown", "")
        analysis.status = "completed"
        analysis.completed_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        analysis.status = "failed"
        analysis.summary = {"error": str(e)}
        db.commit()
        logger.error(f"JD 優化分析失敗: {e}")
        raise

    return analysis


def _rule_based_analysis(job: JobDescription, resume: CandidateData) -> dict:
    """規則比對：找出 JD 與目標履歷間的結構化差異"""
    diffs = []

    # 技能差異
    jd_skills = set(s.lower() for s in (job.required_skills or []))
    resume_skills = set(s.lower() for s in (resume.skills or []))

    missing_in_jd = resume_skills - jd_skills
    if missing_in_jd:
        diffs.append({
            "field": "skills",
            "type": "missing_in_jd",
            "current_jd": list(jd_skills),
            "resume_has": list(missing_in_jd),
            "suggestion": f"履歷具備但 JD 未列出的技能：{', '.join(missing_in_jd)}",
        })

    jd_only = jd_skills - resume_skills
    if jd_only:
        diffs.append({
            "field": "skills",
            "type": "jd_only",
            "current_jd": list(jd_only),
            "suggestion": f"JD 要求但目標人選不具備的技能：{', '.join(jd_only)}（考慮移至加分項）",
        })

    # 經驗差異
    if resume.experience_years and job.min_experience_years:
        if resume.experience_years < job.min_experience_years:
            diffs.append({
                "field": "experience",
                "type": "range_mismatch",
                "current_jd": f"{job.min_experience_years}-{job.max_experience_years}",
                "resume_value": resume.experience_years,
                "suggestion": f"目標人選經驗 {resume.experience_years} 年低於 JD 最低要求 {job.min_experience_years} 年，建議降低門檻",
            })

    # 學歷差異
    edu_rank = {"高中": 1, "專科": 2, "學士": 3, "碩士": 4, "博士": 5}
    jd_rank = edu_rank.get(job.education_level, 0)
    resume_rank = edu_rank.get(resume.education_level, 0)
    if jd_rank and resume_rank and resume_rank < jd_rank:
        diffs.append({
            "field": "education",
            "type": "level_mismatch",
            "current_jd": job.education_level,
            "resume_value": resume.education_level,
            "suggestion": f"JD 要求 {job.education_level} 但目標人選為 {resume.education_level}，建議放寬學歷要求",
        })

    # 薪資差異
    if resume.expected_salary_min and job.salary_max:
        if resume.expected_salary_min > job.salary_max:
            over_pct = round((resume.expected_salary_min - job.salary_max) / job.salary_max * 100)
            diffs.append({
                "field": "salary",
                "type": "budget_gap",
                "current_jd": f"{job.salary_min}-{job.salary_max}",
                "resume_value": resume.expected_salary_min,
                "suggestion": f"目標人選期望薪資超出預算 {over_pct}%，建議調整薪資範圍",
            })

    # 產業差異
    if resume.industry and job.industry:
        if job.industry.lower() not in resume.industry.lower():
            diffs.append({
                "field": "industry",
                "type": "mismatch",
                "current_jd": job.industry,
                "resume_value": resume.industry,
                "suggestion": f"目標人選來自「{resume.industry}」，JD 設定為「{job.industry}」，可考慮擴大產業範圍",
            })

    return {"differences": diffs, "diff_count": len(diffs)}


async def _llm_generate_suggestions(
    job: JobDescription,
    resume: CandidateData,
    rule_analysis: dict,
) -> dict:
    """呼叫 Claude API 生成自然語言的 JD 改寫建議"""
    if not settings.anthropic_api_key:
        # 無 API key 時回退到純規則模式
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
- 加分技能：{', '.join(job.preferred_skills or [])}
- 經驗要求：{job.min_experience_years}-{job.max_experience_years or '不限'} 年
- 學歷要求：{job.education_level or '不限'}
- 產業：{job.industry or '不限'}
- 薪資：{job.salary_min or '?'}-{job.salary_max or '?'}
- 描述：{(job.description or '')[:500]}

## 目標候選人
- 職稱：{resume.title}
- 技能：{', '.join(resume.skills or [])}
- 經驗：{resume.experience_years} 年
- 學歷：{resume.education_level}
- 產業：{resume.industry}

## 規則分析發現的差異
{_format_diffs(rule_analysis)}

請用繁體中文回答，以 JSON 格式回傳：
{{"recommendations": [{{"field": "...", "current": "...", "suggested": "...", "reason": "..."}}], "revised_jd_text": "完整修改版 JD"}}
"""

        message = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        import json
        response_text = message.content[0].text
        # 嘗試從回應中提取 JSON
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = {"recommendations": [], "revised_jd_text": response_text}

        # 生成 Markdown 報告
        result["report_markdown"] = _generate_optimization_report(job, resume, rule_analysis, result)
        return result

    except Exception as e:
        logger.warning(f"LLM 生成失敗，回退到規則模式: {e}")
        return _fallback_format(job, rule_analysis)


def _fallback_format(job: JobDescription, rule_analysis: dict) -> dict:
    """無 LLM 時的純規則建議格式"""
    recs = []
    for diff in rule_analysis.get("differences", []):
        recs.append({
            "field": diff["field"],
            "current": diff.get("current_jd", ""),
            "suggested": diff.get("resume_value", ""),
            "reason": diff["suggestion"],
        })

    report = _generate_optimization_report(job, None, rule_analysis, {"recommendations": recs})
    return {"recommendations": recs, "report_markdown": report}


def _format_diffs(rule_analysis: dict) -> str:
    lines = []
    for diff in rule_analysis.get("differences", []):
        lines.append(f"- [{diff['field']}] {diff['suggestion']}")
    return "\n".join(lines) or "無明顯差異"


def _generate_optimization_report(
    job: JobDescription,
    resume: CandidateData | None,
    rule_analysis: dict,
    llm_result: dict,
) -> str:
    """產生 JD 優化 Markdown 報告"""
    lines = [
        f"# JD 優化建議報告",
        f"",
        f"## 分析對象",
        f"- **職缺**: {job.title}",
    ]
    if resume:
        lines.extend([
            f"- **目標人選**: {resume.name or '未知'}（{resume.title}）",
            f"- **經驗**: {resume.experience_years} 年",
            f"- **技能**: {', '.join(resume.skills or [])}",
        ])
    lines.extend([f"", f"## 差異分析（共 {rule_analysis['diff_count']} 項）"])

    for diff in rule_analysis.get("differences", []):
        lines.append(f"- **{diff['field']}**: {diff['suggestion']}")

    lines.extend([f"", f"## 改寫建議"])
    for i, rec in enumerate(llm_result.get("recommendations", []), 1):
        lines.extend([
            f"### {i}. {rec.get('field', '')}",
            f"- **現況**: {rec.get('current', '')}",
            f"- **建議**: {rec.get('suggested', '')}",
            f"- **原因**: {rec.get('reason', '')}",
            f"",
        ])

    revised = llm_result.get("revised_jd_text", "")
    if revised:
        lines.extend([f"## 修改版 JD", f"", revised])

    return "\n".join(lines)
