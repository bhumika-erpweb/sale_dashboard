from sqlalchemy import create_engine

engine = create_engine(
    "postgresql+psycopg2://readonly_user:admin@localhost:5432/aus_live"
)

