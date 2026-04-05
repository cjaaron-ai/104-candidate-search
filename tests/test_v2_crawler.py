from crawler.crawler_104 import Crawler104, JobPostingData, CandidateData


# === JobPostingData ===

def test_job_posting_data_defaults():
    data = JobPostingData()
    assert data.source == "104"
    assert data.required_skills == []
    assert data.benefits == []
    assert data.salary_type == ""


# === CandidateData V2 fields ===

def test_candidate_data_v2_fields():
    data = CandidateData()
    assert data.certifications == []
    assert data.languages == []
    assert data.work_history == []
    assert data.autobiography == ""


# === _parse_salary_text ===

def test_parse_salary_text_range():
    min_s, max_s, stype = Crawler104._parse_salary_text("月薪 40000~60000")
    assert min_s == 40000
    assert max_s == 60000
    assert stype == "monthly"


def test_parse_salary_text_annual():
    min_s, max_s, stype = Crawler104._parse_salary_text("年薪 800000~1200000")
    assert min_s == 800000
    assert max_s == 1200000
    assert stype == "annual"


def test_parse_salary_text_negotiable():
    min_s, max_s, stype = Crawler104._parse_salary_text("待遇面議")
    assert min_s == 0
    assert max_s == 0
    assert stype == "negotiable"


def test_parse_salary_text_empty():
    min_s, max_s, stype = Crawler104._parse_salary_text("")
    assert stype == "negotiable"


def test_parse_salary_text_single_number():
    min_s, max_s, stype = Crawler104._parse_salary_text("月薪 50000 以上")
    assert min_s == 50000
    assert max_s == 50000


# === _parse_job_ajax ===

def test_parse_job_ajax_basic():
    data = {
        "header": {"jobName": "Backend Engineer", "custName": "Test Co", "salary": "月薪 50000~80000", "areaDesc": "台北市"},
        "condition": {"skill": [{"description": "Python"}], "specialty": [], "workExp": "3年以上", "edu": ["學士"], "industry": "軟體"},
        "welfare": {"welfare": "彈性上班、員工旅遊"},
        "jobDetail": {"jobDescription": "We need a backend engineer"},
    }
    result = Crawler104._parse_job_ajax(data, "https://www.104.com.tw/job/abc", "abc")
    assert result.title == "Backend Engineer"
    assert result.company == "Test Co"
    assert "Python" in result.required_skills
    assert result.salary_min == 50000
    assert result.salary_max == 80000
    assert "彈性上班" in result.benefits


# === BASE_URL ===

def test_base_url():
    assert Crawler104.BASE_URL == "https://vip.104.com.tw"
    assert Crawler104.PUBLIC_URL == "https://www.104.com.tw"
