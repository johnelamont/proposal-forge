"""FastAPI dependencies shared by feature routers."""

from typing import Annotated

from fastapi import Depends

from app.core.auth import CurrentUser, current_user
from app.core.config import Settings, get_settings
from app.services.db import UserDb


def get_db(
    user: Annotated[CurrentUser, Depends(current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserDb:
    """A database handle that acts as the calling user (RLS applies)."""
    return UserDb(settings, user.token)


Db = Annotated[UserDb, Depends(get_db)]
