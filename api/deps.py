from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from crawler.services.database import get_db as get_crawler_db

DBDep = Annotated[Session, Depends(get_crawler_db)]
