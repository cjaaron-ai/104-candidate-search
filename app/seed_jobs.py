"""
Seed 職缺資料 — 麻布數據科技在 104 上的 10 個職缺
自動建立 JD 到資料庫，供排程搜尋使用。
"""

from app.database import SessionLocal, Base, engine
from app.models.job import JobDescription


SEED_JOBS = [
    {
        "title": "Junior Business Development / 初階商務開發專員",
        "department": "商務開發",
        "description": "加入 InvosData 商務開發團隊，開發 FMCG、食品飲料、健康營養等產業品牌客戶",
        "required_skills": ["業務開發", "提案簡報", "B2B銷售", "客戶開發"],
        "preferred_skills": ["零售", "電商", "行銷企劃", "SaaS", "數據科技"],
        "min_experience_years": 1,
        "max_experience_years": 5,
        "education_level": "學士",
        "industry": "網際網路相關業",
        "location": "台北市信義區",
        "weight_skills": 30, "weight_experience": 25, "weight_education": 10,
        "weight_industry": 15, "weight_location": 10, "weight_salary": 10,
    },
    {
        "title": "Associate Account Manager 儲備客戶經理",
        "department": "客戶服務",
        "description": "數據行銷實戰，從執行到策略的成長路徑，服務品牌客戶",
        "required_skills": ["客戶服務", "行銷策略", "數據分析", "廣告業務", "專案執行"],
        "preferred_skills": ["FMCG", "數位行銷", "廣告投放"],
        "min_experience_years": 2,
        "max_experience_years": 7,
        "education_level": "學士",
        "industry": "網際網路相關業",
        "location": "台北市信義區",
        "weight_skills": 30, "weight_experience": 25, "weight_education": 10,
        "weight_industry": 15, "weight_location": 10, "weight_salary": 10,
    },
    {
        "title": "Senior Product Manager - Media 資深產品經理",
        "department": "產品",
        "description": "負責 InvosData 核心 Media 產品線，影響數百品牌行銷決策",
        "required_skills": ["產品管理", "產品策略", "專案管理", "競品分析", "消費者行為", "產品開發"],
        "preferred_skills": ["Google Analytics", "Scrum", "Python", "DSP", "SaaS", "AWS"],
        "min_experience_years": 5,
        "max_experience_years": 15,
        "education_level": "學士",
        "industry": "網際網路相關業",
        "location": "台北市信義區",
        "weight_skills": 35, "weight_experience": 30, "weight_education": 10,
        "weight_industry": 15, "weight_location": 5, "weight_salary": 5,
    },
    {
        "title": "Business Development Manager 業務開發經理",
        "department": "商務開發",
        "description": "開發外商品牌與本土品牌新客戶，顧問式銷售數據解決方案",
        "required_skills": ["業務開發", "提案簡報", "B2B銷售", "客戶經營", "顧問式銷售"],
        "preferred_skills": ["FMCG", "數位行銷", "MarTech", "廣告科技"],
        "min_experience_years": 3,
        "max_experience_years": 10,
        "education_level": "學士",
        "industry": "網際網路相關業",
        "location": "台北市信義區",
        "weight_skills": 30, "weight_experience": 30, "weight_education": 10,
        "weight_industry": 15, "weight_location": 10, "weight_salary": 5,
    },
    {
        "title": "Senior Marketing Specialist 資深行銷專員 (2B)",
        "department": "行銷",
        "description": "負責 invosData B2B 行銷策略，讓行銷真正影響商業成效",
        "required_skills": ["行銷策略", "廣告投放", "品牌推廣", "網站流量分析", "市場調查"],
        "preferred_skills": ["B2B行銷", "數據行銷", "內容行銷", "SEO", "Meta廣告"],
        "min_experience_years": 3,
        "max_experience_years": 10,
        "education_level": "專科",
        "industry": "網際網路相關業",
        "location": "台北市信義區",
        "weight_skills": 35, "weight_experience": 25, "weight_education": 10,
        "weight_industry": 15, "weight_location": 10, "weight_salary": 5,
    },
    {
        "title": "Product Designer 產品設計師",
        "department": "設計",
        "description": "負責發票存摺及引客數據 app 與 web 產品體驗策略與設計",
        "required_skills": ["UI設計", "UX設計", "產品設計", "視覺設計"],
        "preferred_skills": ["Figma", "HTML", "CSS", "Adobe Photoshop", "設計系統"],
        "min_experience_years": 3,
        "max_experience_years": 10,
        "education_level": "專科",
        "industry": "網際網路相關業",
        "location": "台北市信義區",
        "weight_skills": 40, "weight_experience": 25, "weight_education": 5,
        "weight_industry": 10, "weight_location": 10, "weight_salary": 10,
    },
    {
        "title": "客戶企劃 Account Planner",
        "department": "客戶服務",
        "description": "協助 AM 團隊服務大型集團客戶，專案追蹤、數據整理、簡報製作",
        "required_skills": ["文書處理", "報表整理", "簡報製作", "專案追蹤"],
        "preferred_skills": ["Excel", "PowerPoint", "Canva", "數據分析", "行銷企劃"],
        "min_experience_years": 0,
        "max_experience_years": 3,
        "education_level": "學士",
        "industry": "網際網路相關業",
        "location": "台北市信義區",
        "weight_skills": 25, "weight_experience": 15, "weight_education": 15,
        "weight_industry": 15, "weight_location": 15, "weight_salary": 15,
    },
    {
        "title": "AI Agent Engineer / AI 應用工程師",
        "department": "工程",
        "description": "組建小部隊，用 AI 放大戰力，開發 AI Agent 應用",
        "required_skills": ["Python", "AI", "LLM", "機器學習", "軟體開發"],
        "preferred_skills": ["LangChain", "OpenAI API", "RAG", "向量資料庫", "Docker", "FastAPI"],
        "min_experience_years": 0,
        "max_experience_years": 10,
        "education_level": "專科",
        "industry": "網際網路相關業",
        "location": "台北市信義區",
        "weight_skills": 40, "weight_experience": 20, "weight_education": 10,
        "weight_industry": 10, "weight_location": 10, "weight_salary": 10,
    },
    {
        "title": "Backend & DevOps Engineer 後端暨維運工程師",
        "department": "工程",
        "description": "負責後端系統開發與維運，支撐 900 萬用戶級產品",
        "required_skills": ["後端開發", "DevOps", "CI/CD", "雲端服務", "資料庫"],
        "preferred_skills": ["Python", "AWS", "Docker", "Kubernetes", "PostgreSQL", "Redis", "Terraform"],
        "min_experience_years": 0,
        "max_experience_years": 10,
        "education_level": "專科",
        "industry": "網際網路相關業",
        "location": "台北市信義區",
        "weight_skills": 40, "weight_experience": 25, "weight_education": 5,
        "weight_industry": 10, "weight_location": 10, "weight_salary": 10,
    },
    {
        "title": "Mobile Lead 行動應用開發主管",
        "department": "工程",
        "description": "帶領行動應用開發，管理發票存摺與麻布記帳 App",
        "required_skills": ["iOS開發", "Android開發", "行動應用架構", "團隊管理"],
        "preferred_skills": ["Swift", "Kotlin", "Flutter", "React Native", "CI/CD"],
        "min_experience_years": 0,
        "max_experience_years": 15,
        "education_level": "專科",
        "industry": "網際網路相關業",
        "location": "台北市信義區",
        "weight_skills": 40, "weight_experience": 25, "weight_education": 5,
        "weight_industry": 10, "weight_location": 10, "weight_salary": 10,
    },
]


def seed():
    """建立 seed 職缺（跳過已存在的）"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(JobDescription).count()
        if existing > 0:
            print(f"已有 {existing} 筆職缺，跳過 seed")
            return existing

        for job_data in SEED_JOBS:
            job = JobDescription(**job_data)
            db.add(job)

        db.commit()
        print(f"✅ 已建立 {len(SEED_JOBS)} 筆職缺")
        return len(SEED_JOBS)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
