import pytest

from core.matcher import load_jobs

GOOD = """Ravi Kumar
ravi.kumar@example.com | +91 98765 43210 | github.com/ravik | linkedin.com/in/ravik

Summary
Computer science student focused on computer vision and Python.

Skills
Languages: Python, C++, SQL
Tools: OpenCV, PyTorch, Docker, Git, Pytest

Projects
- Built a defect detection system using YOLO and OpenCV, reaching 94% accuracy on 5000 images
- Developed a FastAPI service serving 3 models, cutting latency by 40%
- Automated dataset labelling with Python scripts, saving 12 hours per week

Education
B.Tech Computer Science, R.K. College of Engineering, 2022 - 2026
""" + ("Additional detail line for length and realism in the sample resume text. " * 6)

BAD = """I am responsible for many things. My work was worked on by others.
Skills
Word
"""


@pytest.fixture(scope="session")
def jobs():
    return load_jobs()


@pytest.fixture
def good_text():
    return GOOD


@pytest.fixture
def bad_text():
    return BAD
