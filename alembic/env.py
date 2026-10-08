import sys
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config
fileConfig(config.config_file_name)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.models.base import Base
import app.models.user
import app.models.profile
import app.models.notification_settings
import app.models.web_push_subscription
import app.models.diary_question
import app.models.monthly_report
import app.models.pearl
import app.models.letter_feedback
import app.models.letter
import app.models.fortune
import app.models.shop
import app.models.auth_token
from app.models.diary import DiaryEntry
from app.models.letter import OtterLetter

target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"}
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()