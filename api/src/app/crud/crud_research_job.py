"""FastCRUD instance for ``research_job`` (卡 #23 W4;沿用 backtest_run 風格)。"""

from fastcrud import FastCRUD

from ..models.research_job import ResearchJob
from ..schemas.research_job import (
    ResearchJobCreate,
    ResearchJobRead,
    ResearchJobUpdate,
)

CRUDResearchJob = FastCRUD[
    ResearchJob,
    ResearchJobCreate,
    ResearchJobUpdate,
    ResearchJobUpdate,
    ResearchJobRead,
    ResearchJobRead,
]
crud_research_jobs = CRUDResearchJob(ResearchJob)
