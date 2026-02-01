# Import the Base class
from app.db.models import Base

# Import all models here so Alembic can "see" them
from app.db.models import User, Expense