"""JimQ FastAPI entrypoint.

Stripped fork of boilerplate v0.15.0 ``main.py``: removed crudadmin mount and
admin lifespan; the app is a plain ``create_application`` wiring of the router
and settings.
"""

from .api import router
from .core.config import settings
from .core.setup import create_application

app = create_application(router=router, settings=settings)
