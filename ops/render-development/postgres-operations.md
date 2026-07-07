# PostgreSQL Operations on Render

**Load this reference when:** creating, managing, migrating, or querying PostgreSQL databases on Render.

## Creating a PostgreSQL Instance

```python
# List existing instances first
mcp__render__list_postgres_instances()

# Create new instance
mcp__render__create_postgres(
    name="your-db",
    plan="starter",  # starter, standard, pro
    region="frankfurt"  # Match your service region
)

# Get connection details
mcp__render__get_postgres(postgres_id="dpg-xxxxx")
```

## Connection String Formats

### Internal (same region - for production app)
```
postgresql+asyncpg://user:pass@dpg-xxxxx-a.frankfurt-postgres.render.com/dbname
```
Use this format in `DATABASE_URL` environment variable for the deployed service.

### External (migrations, local dev, queries from outside Render)
```
postgresql+psycopg2://user:pass@dpg-xxxxx-a.frankfurt-postgres.render.com/dbname?sslmode=require
```
**IMPORTANT:** External connections REQUIRE `?sslmode=require` suffix.

## Running Migrations

```bash
# From your project directory (adjust to your migration tool)
DATABASE_URL="postgresql+psycopg2://user:pass@host/db?sslmode=require" <migration-tool> upgrade head

# Check current migration status
DATABASE_URL="postgresql+psycopg2://user:pass@host/db?sslmode=require" <migration-tool> current

# Create new migration
<migration-tool> revision --autogenerate -m "Add new table"
```

## Querying Database via MCP

```python
# Direct query via MCP (useful for debugging)
mcp__render__query_render_postgres(
    postgres_id="dpg-xxxxx",
    query="SELECT COUNT(*) FROM users"
)

# Check table structure
mcp__render__query_render_postgres(
    postgres_id="dpg-xxxxx",
    query="SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'users'"
)

# Check recent records
mcp__render__query_render_postgres(
    postgres_id="dpg-xxxxx",
    query="SELECT * FROM your_table ORDER BY created_at DESC LIMIT 5"
)
```

## Common Database Operations

### Check Database Status
```python
mcp__render__get_postgres(postgres_id="dpg-xxxxx")
# Returns: status, connection info, plan details
```

### List All Tables
```python
mcp__render__query_render_postgres(
    postgres_id="dpg-xxxxx",
    query="SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
)
```

### Check Migration History
```python
mcp__render__query_render_postgres(
    postgres_id="dpg-xxxxx",
    query="SELECT * FROM alembic_version"  -- table name depends on your migration tool
)
```

## Backup Considerations

- Render provides automatic daily backups on paid plans
- For free tier: manually export critical data periodically
- Use `query_render_postgres` for ad-hoc data exports:

```python
# Export users to review
mcp__render__query_render_postgres(
    postgres_id="dpg-xxxxx",
    query="SELECT id, email, created_at FROM users"
)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Connection refused | Check postgres_id is correct, verify instance is running |
| SSL required error | Add `?sslmode=require` to external connection strings |
| Migration fails | Use psycopg2 (or equivalent sync driver) for migrations, not asyncpg |
| Permission denied | Verify you're using the correct credentials from `get_postgres` |
| Database does not exist | Check database name matches exactly |
