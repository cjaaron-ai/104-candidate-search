from crawler.crawler_104 import Crawler104, CandidateData


# === _parse_experience ===

def test_parse_experience_normal():
    result = Crawler104._parse_experience("5年工作經驗")
    assert result == 5


def test_parse_experience_no_number():
    result = Crawler104._parse_experience("新鮮人")
    assert result == 0


def test_parse_experience_multiple_numbers():
    result = Crawler104._parse_experience("3-5年經驗")
    assert result == 3


# === _parse_education_level ===

def test_parse_education_masters():
    result = Crawler104._parse_education_level("國立台灣大學 碩士")
    assert result == "碩士"


def test_parse_education_bachelor():
    result = Crawler104._parse_education_level("學士畢業")
    assert result == "學士"


def test_parse_education_phd():
    result = Crawler104._parse_education_level("博士班")
    assert result == "博士"


def test_parse_education_unknown():
    result = Crawler104._parse_education_level("其他")
    assert result == ""


# === CandidateData ===

def test_candidate_data_defaults():
    data = CandidateData()
    assert data.source == "104"
    assert data.skills == []
    assert data.experience_years == 0
