from sqlalchemy import inspect, text

from app.db import Base, engine
from app import models  # noqa: F401  register tables on Base.metadata


def _add_missing_columns(sync_conn) -> None:
    inspector = inspect(sync_conn)
    if inspector.has_table("devices"):
        columns = {column["name"] for column in inspector.get_columns("devices")}
        if "item_id" not in columns:
            sync_conn.execute(text("ALTER TABLE devices ADD COLUMN item_id VARCHAR(6) NULL"))
        if "service_mode" not in columns:
            sync_conn.execute(text("ALTER TABLE devices ADD COLUMN service_mode INTEGER NOT NULL DEFAULT 0"))
        if "monitor_type" not in columns:
            sync_conn.execute(text("ALTER TABLE devices ADD COLUMN monitor_type VARCHAR(16) NOT NULL DEFAULT 'ping'"))
        if "port" not in columns:
            sync_conn.execute(text("ALTER TABLE devices ADD COLUMN port INTEGER NULL"))
        if "monitor_spec" not in columns:
            sync_conn.execute(text("ALTER TABLE devices ADD COLUMN monitor_spec TEXT NULL"))
        if "monitor_key" not in columns:
            sync_conn.execute(text("ALTER TABLE devices ADD COLUMN monitor_key VARCHAR(190) NULL"))
        if "ssl_info" not in columns:
            sync_conn.execute(text("ALTER TABLE devices ADD COLUMN ssl_info TEXT NULL"))
        sync_conn.execute(
            text("UPDATE devices SET monitor_type = 'ping' WHERE monitor_type IS NULL OR monitor_type = ''")
        )
        sync_conn.execute(
            text(
                "UPDATE devices SET monitor_key = CONCAT('ping|', LOWER(host), '||') "
                "WHERE monitor_key IS NULL OR monitor_key = ''"
            )
        )
        # Same host can now have several monitor types; uniqueness moves to monitor_key.
        try:
            rows = sync_conn.execute(text("SHOW INDEX FROM devices")).mappings().all()
            unique_names = {
                row["Key_name"]
                for row in rows
                if row["Column_name"] == "host"
                and row["Non_unique"] == 0
                and row["Key_name"] != "PRIMARY"
            }
            for name in unique_names:
                cols = [row["Column_name"] for row in rows if row["Key_name"] == name]
                if cols == ["host"]:
                    sync_conn.execute(text("ALTER TABLE devices DROP INDEX `%s`" % name))
        except Exception:
            pass
        try:
            sync_conn.execute(text("CREATE UNIQUE INDEX uq_devices_monitor_key ON devices (monitor_key)"))
        except Exception:
            pass
        try:
            sync_conn.execute(text("CREATE INDEX ix_devices_host ON devices (host)"))
        except Exception:
            pass
        sync_conn.execute(
            text("UPDATE devices SET item_id = LPAD(id, 6, '0') WHERE item_id IS NULL OR item_id = ''")
        )
        try:
            sync_conn.execute(text("CREATE UNIQUE INDEX ix_devices_item_id ON devices (item_id)"))
        except Exception:
            pass
    if inspector.has_table("ping_results"):
        columns = {column["name"] for column in inspector.get_columns("ping_results")}
        if "error" not in columns:
            sync_conn.execute(text("ALTER TABLE ping_results ADD COLUMN error VARCHAR(255) NULL"))
    if inspector.has_table("users"):
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "timezone" not in columns:
            sync_conn.execute(text("ALTER TABLE users ADD COLUMN timezone VARCHAR(64) NULL"))
        if "updated_at" not in columns:
            sync_conn.execute(text("ALTER TABLE users ADD COLUMN updated_at DATETIME NULL"))
        if "password_updated_at" not in columns:
            sync_conn.execute(text("ALTER TABLE users ADD COLUMN password_updated_at DATETIME NULL"))
        if "approved_by_id" not in columns:
            sync_conn.execute(text("ALTER TABLE users ADD COLUMN approved_by_id INTEGER NULL"))
        sync_conn.execute(text("UPDATE users SET updated_at = created_at WHERE updated_at IS NULL"))
        sync_conn.execute(text("UPDATE users SET password_updated_at = created_at WHERE password_updated_at IS NULL"))
        if inspector.has_table("access_requests"):
            sync_conn.execute(
                text(
                    "UPDATE users u "
                    "JOIN access_requests ar ON ar.email = u.email AND ar.status = 'approved' "
                    "SET u.approved_by_id = ar.reviewed_by "
                    "WHERE u.approved_by_id IS NULL AND ar.reviewed_by IS NOT NULL"
                )
            )
    if inspector.has_table("incidents"):
        columns = {column["name"] for column in inspector.get_columns("incidents")}
        if "number" not in columns:
            sync_conn.execute(text("ALTER TABLE incidents ADD COLUMN number VARCHAR(32) NULL"))
        if "description" not in columns:
            sync_conn.execute(text("ALTER TABLE incidents ADD COLUMN description TEXT NULL"))
        sync_conn.execute(
            text(
                "UPDATE incidents SET number = CONCAT('INC', LPAD(id, 7, '0')) "
                "WHERE number IS NULL OR number = '' OR number LIKE 'INC-%'"
            )
        )
        sync_conn.execute(
            text(
                "UPDATE incidents SET description = CONCAT("
                "'Device is not responding to ICMP.', "
                "IF(last_error IS NULL OR last_error = '', '', CONCAT(' ', last_error))"
                ") WHERE description IS NULL OR description = ''"
            )
        )
        try:
            sync_conn.execute(text("CREATE UNIQUE INDEX ix_incidents_number ON incidents (number)"))
        except Exception:
            pass
        if "priority" not in columns:
            sync_conn.execute(text("ALTER TABLE incidents ADD COLUMN priority VARCHAR(4) NULL"))
        if "short_description" not in columns:
            sync_conn.execute(text("ALTER TABLE incidents ADD COLUMN short_description VARCHAR(190) NULL"))
        if inspector.has_table("devices"):
            sync_conn.execute(
                text(
                    "UPDATE incidents i "
                    "JOIN devices d ON d.id = i.device_id "
                    "SET i.short_description = LEFT(CONCAT("
                    "d.name, ' (', d.host, ') - ', "
                    "IF(i.last_error IS NULL OR i.last_error = '', 'Not responding to ICMP', i.last_error)"
                    "), 88) "
                    "WHERE i.short_description IS NULL OR i.short_description = ''"
                )
            )
        if "active_ci_key" not in columns:
            sync_conn.execute(text("ALTER TABLE incidents ADD COLUMN active_ci_key INTEGER NULL"))
        sync_conn.execute(text("UPDATE incidents SET active_ci_key = NULL"))
        sync_conn.execute(
            text(
                "UPDATE incidents i "
                "JOIN ("
                "  SELECT device_id, MIN(id) AS keep_id FROM incidents "
                "  WHERE status IN ('open', 'acknowledged') GROUP BY device_id"
                ") k ON i.id = k.keep_id "
                "SET i.active_ci_key = i.device_id"
            )
        )
        sync_conn.execute(
            text(
                "UPDATE incidents SET status = 'cancelled', recovered_at = UTC_TIMESTAMP() "
                "WHERE status IN ('open', 'acknowledged') AND active_ci_key IS NULL"
            )
        )
        try:
            sync_conn.execute(text("CREATE UNIQUE INDEX ix_incidents_active_ci ON incidents (active_ci_key)"))
        except Exception:
            pass
        try:
            sync_conn.execute(text("ALTER TABLE incidents MODIFY COLUMN status VARCHAR(32) NOT NULL DEFAULT 'open'"))
        except Exception:
            pass
        sync_conn.execute(text("UPDATE incidents SET status = 'work_in_progress' WHERE status = 'acknowledged'"))
        sync_conn.execute(text("UPDATE incidents SET status = 'closed_successful' WHERE status = 'resolved'"))


async def ensure_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
