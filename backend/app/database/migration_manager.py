import logging
from pathlib import Path
from typing import Optional
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect

logger = logging.getLogger(__name__)

class MigrationManager:
    """
    Manages database migrations using Alembic.
    """
    
    def __init__(self, db_url: str, alembic_cfg_path: Optional[str] = None):
        self.db_url = db_url
        self.engine = create_engine(db_url)
        
        # Setup Alembic config
        if alembic_cfg_path is None:
            # Default path relative to this file
            base_dir = Path(__file__).resolve().parent.parent.parent  
            alembic_cfg_path = str(base_dir / "alembic.ini")
        
        self.alembic_cfg = Config(alembic_cfg_path)
        self.alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    
    def is_database_up_to_date(self) -> bool:

        try:
            script_dir = ScriptDirectory.from_config(self.alembic_cfg)
            
            with self.engine.connect() as connection:
                context = MigrationContext.configure(connection)
                current_rev = context.get_current_revision()
                head_rev = script_dir.get_current_head()
                
                return current_rev == head_rev
        except Exception as e:
            logger.warning(f"Could not check migration status: {e}")
            # If we can't check, assume it's up to date to avoid blocking startup
            return True
    
    def get_current_revision(self) -> Optional[str]:
        try:
            with self.engine.connect() as connection:
                context = MigrationContext.configure(connection)
                return context.get_current_revision()
        except Exception as e:
            logger.error(f"Error getting current revision: {e}")
            return None
    
    def get_head_revision(self) -> Optional[str]:
        """Get head revision from migration scripts."""
        try:
            script_dir = ScriptDirectory.from_config(self.alembic_cfg)
            return script_dir.get_current_head()
        except Exception as e:
            logger.error(f"Error getting head revision: {e}")
            return None
    
    def upgrade_database(self, revision: str = "head") -> bool:
        try:
            command.upgrade(self.alembic_cfg, revision)
            logger.info(f"Database upgraded to revision: {revision}")
            return True
        except Exception as e:
            logger.error(f"Error upgrading database: {e}")
            return False
    
    def downgrade_database(self, revision: str) -> bool:
        try:
            command.downgrade(self.alembic_cfg, revision)
            logger.info(f"Database downgraded to revision: {revision}")
            return True
        except Exception as e:
            logger.error(f"Error downgrading database: {e}")
            return False
    
    def create_migration(self, message: str, autogenerate: bool = True) -> bool:
        """
        Create a new migration script.
        """
        try:
            command.revision(
                self.alembic_cfg, 
                message=message, 
                autogenerate=autogenerate
            )
            logger.info(f"Created migration: {message}")
            return True
        except Exception as e:
            logger.error(f"Error creating migration: {e}")
            return False
    
    def get_migration_history(self) -> list:
        try:
            script_dir = ScriptDirectory.from_config(self.alembic_cfg)
            
            with self.engine.connect() as connection:
                context = MigrationContext.configure(connection)
                current_rev = context.get_current_revision()
                
                history = []
                for revision in script_dir.walk_revisions():
                    is_current = revision.revision == current_rev
                    history.append({
                        'revision': revision.revision,
                        'message': revision.doc,
                        'is_current': is_current,
                        'down_revision': revision.down_revision
                    })
                
                return history
        except Exception as e:
            logger.error(f"Error getting migration history: {e}")
            return []
    
    def has_pending_migrations(self) -> bool:
        """
        Check if there are pending migrations.
        """
        return not self.is_database_up_to_date()

# Create global migration manager instance
# This will be initialized when the database manager starts
migration_manager: Optional[MigrationManager] = None

def initialize_migration_manager(db_url: str) -> None:
    global migration_manager
    try:
        migration_manager = MigrationManager(db_url)
        logger.info("Migration manager initialized successfully")
    except Exception as e:
        logger.warning(f"Could not initialize migration manager: {e}")
        migration_manager = None

def get_migration_manager() -> Optional[MigrationManager]:
    """
    Get global migration manager instance.
    """
    return migration_manager