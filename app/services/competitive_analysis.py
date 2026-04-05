"""
競爭 JD 分析服務

搜尋相似職缺，比較薪資、技能、經驗、福利，產生結構化分析與 Markdown 報告。
"""

import logging
import statistics
from datetime import datetime

from google.cloud import firestore

from app.config import settings
from app.models.job import JobDescription
from app.models.jd_analysis import JDAnalysis
from app.models.competitor_jd import CompetitorJD
from app.repositories.jobs import JobRepository
from app.repositories.analyses import AnalysisRepository, CompetitorJDRepository
from crawler.crawler_104 import Crawler104, JobPostingData

logger = logging.getLogger(__name__)


async def analyze_competitive_landscape(
    job_id: int,
    db: firestore.Client,
    max_competitors: int = 10,
) -> JDAnalysis:
    """執行完整的競爭 JD 分析"""
    job_repo = JobRepository(db)
    analysis_repo = AnalysisRepository(db)
    comp_repo = CompetitorJDRepository(db)

    job = job_repo.get_job(job_id)
    if not job:
        raise ValueError(f"Job ID {job_id} not found")

    analysis = analysis_repo.create_analysis({
        "job_id": job.id,
        "analysis_type": "competitive",
        "target_url": job.source_url,
        "status": "processing",
    })

    try:
        keywords = []
        if job.title:
            keywords.append(job.title)
        keywords.extend((job.required_skills or [])[:3])

        crawler = Crawler104(
            settings.account_104_username,
            settings.account_104_password,
            cookie_storage_path=settings.cookie_storage_path,
        )
        try:
            postings = await crawler.search_jobs(
                keywords=keywords,
                industry=job.industry,
                location=job.location,
                max_pages=min(3, (max_competitors // 5) + 1),
            )
        finally:
            await crawler.close()

        competitors = []
        for p in postings[:max_competitors]:
            comp = comp_repo.create_competitor({
                "analysis_id": analysis.id,
                "source_url": p.source_url,
                "source_id": p.source_id,
                "title": p.title,
                "company": p.company,
                "industry": p.industry,
                "required_skills": p.required_skills,
                "preferred_skills": p.preferred_skills,
                "min_experience_years": p.min_experience_years,
                "max_experience_years": p.max_experience_years,
                "education_level": p.education_level,
                "location": p.location,
                "salary_min": p.salary_min,
                "salary_max": p.salary_max,
                "salary_type": p.salary_type,
                "benefits": p.benefits,
                "description": p.description,
            })
            competitors.append(comp)

        comparison = _generate_comparison(job, competitors)
        recommendations = _generate_recommendations(job, comparison)
        report = _generate_markdown_report(job, competitors, comparison, recommendations)

        analysis = analysis_repo.update_analysis(analysis.id, {
            "competitor_count": len(competitors),
            "summary": comparison,
            "recommendations": recommendations,
            "report_markdown": report,
            "status": "completed",
            "completed_at": datetime.utcnow(),
        })

    except Exception as e:
        analysis_repo.update_analysis(analysis.id, {
            "status": "failed",
            "summary": {"error": str(e)},
        })
        logger.error(f"競爭分析失敗: {e}")
        raise

    return analysis


def _generate_comparison(job: JobDescription, competitors: list[CompetitorJD]) -> dict:
    """產生結構化比較分析"""
    if not competitors:
        return {"message": "未找到競爭職缺", "competitor_count": 0}

    salary_maxes = [c.salary_max for c in competitors if c.salary_max]
    salary_mins = [c.salary_min for c in competitors if c.salary_min]

    salary_comparison = {
        "user_range": f"{job.salary_min or 0}-{job.salary_max or 0}",
        "market_min_median": int(statistics.median(salary_mins)) if salary_mins else None,
        "market_max_median": int(statistics.median(salary_maxes)) if salary_maxes else None,
        "competitor_count_with_salary": len(salary_maxes),
    }
    if salary_maxes and job.salary_max:
        salary_comparison["percentile_position"] = round(
            sum(1 for s in salary_maxes if s <= job.salary_max) / len(salary_maxes) * 100
        )

    skill_freq = {}
    for c in competitors:
        for skill in (c.required_skills or []):
            skill_lower = skill.lower()
            skill_freq[skill_lower] = skill_freq.get(skill_lower, 0) + 1
    sorted_skills = sorted(skill_freq.items(), key=lambda x: x[1], reverse=True)
    user_skills_lower = {s.lower() for s in (job.required_skills or [])}
    skills_you_lack = [s for s, _ in sorted_skills[:20] if s not in user_skills_lower]
    unique_skills = [s for s in user_skills_lower if s not in skill_freq]

    skills_comparison = {
        "top_market_skills": sorted_skills[:15],
        "skills_you_lack": skills_you_lack[:10],
        "unique_skills_you_have": list(unique_skills)[:10],
    }

    exp_mins = [c.min_experience_years for c in competitors if c.min_experience_years]
    experience_comparison = {
        "user_range": f"{job.min_experience_years or 0}-{job.max_experience_years or '不限'}",
        "market_median_min": int(statistics.median(exp_mins)) if exp_mins else None,
    }

    benefit_freq = {}
    for c in competitors:
        for b in (c.benefits or []):
            benefit_freq[b] = benefit_freq.get(b, 0) + 1
    user_benefits = set(job.benefits or [])
    common_benefits_you_lack = [
        b for b, cnt in sorted(benefit_freq.items(), key=lambda x: x[1], reverse=True)
        if b not in user_benefits and cnt >= len(competitors) * 0.3
    ]

    benefits_comparison = {
        "common_benefits_you_lack": common_benefits_you_lack[:10],
        "top_market_benefits": sorted(benefit_freq.items(), key=lambda x: x[1], reverse=True)[:10],
    }

    return {
        "competitor_count": len(competitors),
        "salary": salary_comparison,
        "skills": skills_comparison,
        "experience": experience_comparison,
        "benefits": benefits_comparison,
    }


def _generate_recommendations(job: JobDescription, comparison: dict) -> list[dict]:
    """將比較結果轉化為 actionable 建議"""
    recs = []

    salary = comparison.get("salary", {})
    if salary.get("market_max_median") and job.salary_max:
        market_median = salary["market_max_median"]
        if job.salary_max < market_median * 0.85:
            gap_pct = round((market_median - job.salary_max) / market_median * 100)
            recs.append({
                "dimension": "salary",
                "priority": "high",
                "current": f"{job.salary_min}-{job.salary_max}",
                "market_data": f"市場中位數上限 {market_median}",
                "suggestion": f"薪資上限低於市場中位 {gap_pct}%，建議調升至 {market_median} 以上",
            })

    skills = comparison.get("skills", {})
    lacking = skills.get("skills_you_lack", [])
    if lacking:
        recs.append({
            "dimension": "skills",
            "priority": "medium",
            "current": ", ".join(job.required_skills or []),
            "market_data": ", ".join(lacking[:5]),
            "suggestion": f"市場常見技能您的 JD 未列入：{', '.join(lacking[:5])}",
        })

    benefits = comparison.get("benefits", {})
    lacking_benefits = benefits.get("common_benefits_you_lack", [])
    if lacking_benefits:
        recs.append({
            "dimension": "benefits",
            "priority": "low",
            "current": ", ".join(job.benefits or []) or "未列出",
            "market_data": ", ".join(lacking_benefits[:5]),
            "suggestion": f"競爭者常見福利：{', '.join(lacking_benefits[:5])}",
        })

    return recs


def _generate_markdown_report(
    job: JobDescription,
    competitors: list[CompetitorJD],
    comparison: dict,
    recommendations: list[dict],
) -> str:
    """產生 Markdown 格式的分析報告"""
    lines = [
        f"# 競爭 JD 分析報告",
        f"",
        f"## 分析對象",
        f"- **職缺**: {job.title}",
        f"- **公司**: {job.company or '未填'}",
        f"- **地區**: {job.location or '未填'}",
        f"- **競爭職缺數**: {len(competitors)}",
        f"",
    ]

    salary = comparison.get("salary", {})
    lines.extend([
        f"## 薪資比較",
        f"| 項目 | 數值 |",
        f"|---|---|",
        f"| 您的薪資範圍 | {salary.get('user_range', 'N/A')} |",
        f"| 市場中位數（下限） | {salary.get('market_min_median', 'N/A')} |",
        f"| 市場中位數（上限） | {salary.get('market_max_median', 'N/A')} |",
        f"| 您的百分位排名 | {salary.get('percentile_position', 'N/A')}% |",
        f"",
    ])

    skills = comparison.get("skills", {})
    lines.extend([f"## 技能比較", f"### 您缺少的市場常見技能"])
    for s in skills.get("skills_you_lack", [])[:10]:
        lines.append(f"- {s}")
    lines.extend([f"", f"### 您的獨特技能"])
    for s in skills.get("unique_skills_you_have", [])[:10]:
        lines.append(f"- {s}")

    lines.extend([f"", f"## 改善建議"])
    for i, rec in enumerate(recommendations, 1):
        priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(rec["priority"], "⚪")
        lines.append(f"### {i}. {priority_icon} {rec['dimension'].title()}")
        lines.append(f"- **現況**: {rec['current']}")
        lines.append(f"- **市場資料**: {rec['market_data']}")
        lines.append(f"- **建議**: {rec['suggestion']}")
        lines.append("")

    lines.extend([f"## 競爭者列表", f"| 公司 | 職稱 | 薪資 | 地區 |", f"|---|---|---|---|"])
    for c in competitors:
        salary_str = f"{c.salary_min or '?'}-{c.salary_max or '?'}" if c.salary_min or c.salary_max else "面議"
        lines.append(f"| {c.company or '未知'} | {c.title or '未知'} | {salary_str} | {c.location or '未知'} |")

    return "\n".join(lines)
