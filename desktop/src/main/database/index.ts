// Database index — Phase 8-M1-B
export { createSQLiteDatabase, type SQLiteDatabase, type SqlParam, type SqlParams, type PreparedStatement } from './sqlite-database'
export { createMigrationManager, type MigrationManager, type MigrationRecord, listMigrations, simpleChecksum } from './migration-manager'
export { resolveDatabaseConfig, type DatabaseConfig } from './database-config'