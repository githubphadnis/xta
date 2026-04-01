from sqlalchemy import Boolean, Column, Integer, String, Text

from app.db.session import Base


class SavedQuery(Base):
    __tablename__ = "saved_queries"

    id = Column(Integer, primary_key=True, index=True)
    owner_email = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    question = Column(Text, nullable=False)
    sql_query = Column(Text, nullable=False)
    chart_type = Column(String, nullable=False, default="bar")
    is_pinned = Column(Boolean, nullable=False, default=False)
