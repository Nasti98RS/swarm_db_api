from sqlmodel import create_engine, Session, SQLModel
from dotenv import load_dotenv
import project.models
import os

load_dotenv()
postgres_url = os.getenv("SWARM_DB_CONNECTION")
connect_args = {"check_same_thread": False}
engine = create_engine(
    postgres_url, echo=False
)  # Para mostrar los logs de las SQLModel querys


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


if __name__ == "__main__":
    create_db_and_tables()
