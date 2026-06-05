import structlog
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from supabase import create_client, Client
from backend.config import settings

log = structlog.get_logger()

class DBClient:
    _supabase_a: Client = None
    _supabase_b: Client = None
    _pg_pool_a: ThreadedConnectionPool = None

    @classmethod
    def connect(cls):
        """Initialize Supabase clients and PostgreSQL connection pool"""
        # Project A: Operational DB
        cls._supabase_a = create_client(
            settings.supabase_url_a, 
            settings.supabase_service_role_key_a
        )
        
        # Project B: Training Data DB
        cls._supabase_b = create_client(
            settings.supabase_url_b, 
            settings.supabase_service_role_key_b
        )
        
        # Setup psycopg2 connection pool for high-throughput Project A writes
        try:
            cls._pg_pool_a = ThreadedConnectionPool(
                minconn=1,
                maxconn=20,
                dsn=settings.supabase_db_url_a
            )
            log.info("db.connected", project_a=settings.supabase_url_a, project_b=settings.supabase_url_b)
        except Exception as e:
            log.error("db.connection_failed", error=str(e))
            raise

    @classmethod
    def disconnect(cls):
        if cls._pg_pool_a:
            cls._pg_pool_a.closeall()
            log.info("db.disconnected")

    @classmethod
    def get_supabase_a(cls) -> Client:
        if not cls._supabase_a:
            raise RuntimeError("DBClient not connected")
        return cls._supabase_a
        
    @classmethod
    def get_supabase_b(cls) -> Client:
        if not cls._supabase_b:
            raise RuntimeError("DBClient not connected")
        return cls._supabase_b

    @classmethod
    def get_pg_connection(cls):
        """Yields a psycopg2 connection from the pool to be used in context manager"""
        if not cls._pg_pool_a:
            raise RuntimeError("DBClient not connected")
        return cls._pg_pool_a.getconn()
        
    @classmethod
    def put_pg_connection(cls, conn):
        """Returns connection to pool"""
        if cls._pg_pool_a and conn:
            cls._pg_pool_a.putconn(conn)

    @classmethod
    def verify(cls):
        """Health check for startup"""
        try:
            cls.get_supabase_a().table('districts').select('id').limit(1).execute()
            log.info("db.health_check.success")
        except Exception as e:
            log.error("db.health_check.failed", error=str(e))
            raise

def get_db() -> DBClient:
    return DBClient
