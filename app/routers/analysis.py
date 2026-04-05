from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.jd_analysis import JDAnalysis
from app.schemas.analysis import (
    CompetitiveAnalysisRequest,
    JDOptimizeRequest,
    AnalysisResponse,
)
from app.services.competitive_analysis import analyze_competitive_landscape
from app.services.jd_optimizer import optimize_jd_for_target

router = APIRouter(prefix="/api/analysis", tags=["Analysis"])


@router.post("/competitive/{job_id}", response_model=AnalysisResponse)
async def trigger_competitive_analysis(
    job_id: int,
    req: CompetitiveAnalysisRequest | None = None,
    db: Session = Depends(get_db),
):
    """觸發競爭 JD 分析"""
    max_comp = req.max_competitors if req else 10
    try:
        analysis = await analyze_competitive_landscape(job_id, db, max_comp)
        return analysis
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/optimize/{job_id}", response_model=AnalysisResponse)
async def trigger_jd_optimization(
    job_id: int,
    req: JDOptimizeRequest,
    db: Session = Depends(get_db),
):
    """觸發 JD 優化分析"""
    try:
        analysis = await optimize_jd_for_target(job_id, req.target_resume_url, db)
        return analysis
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    """查詢分析結果"""
    analysis = db.query(JDAnalysis).filter(JDAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@router.get("/{analysis_id}/report")
def get_analysis_report(analysis_id: int, db: Session = Depends(get_db)):
    """取得 Markdown 格式報告"""
    analysis = db.query(JDAnalysis).filter(JDAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"report_markdown": analysis.report_markdown or "報告尚未生成"}
