# lunawave_framework.core.storage -- generic SQLite storage layer:
# connection lifecycle (DatabaseConnection), session-token persistence
# (SessionRepository), and single-row admin-account persistence
# (AdminAccountRepository). Moved from the app's persistence/ in Phase 4.
#
# Schema ownership: per ADR 0014, this layer does NOT own or ship a
# schema.sql of its own. DatabaseConnection.init() takes a schema_path
# argument and executes whatever schema file the caller provides --
# the app owns its full schema (including the `sessions` and
# `admin_account` tables these classes read/write) as a single file.
# This keeps the migration schema-agnostic and avoids a bigger, riskier
# schema-splitting change in the same phase as the code move.
