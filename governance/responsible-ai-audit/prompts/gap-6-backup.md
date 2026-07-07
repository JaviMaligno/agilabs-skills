# Gap 6 (sub-backup) — Backup & restore runbook

[Preamble must be prepended at invocation.]

## Objective

Document the backup mechanism, restore procedure, RPO/RTO targets, and ownership for the service's persistence layer. Stack-agnostic — the deliverable is documentation, not code.

## "Done" criteria (stack-agnostic)

`docs/BACKUP_PROCEDURE.md` exists and contains:

1. **Scope** — which data stores hold business data, their TTLs, and the loss impact per store (what loss is acceptable, what is binding).
2. **Recovery objectives** — RPO and RTO with one-line rationale per number.
3. **Backup mechanism** — provider PITR window, frequency, retention, granularity, cost class. Source-of-truth setting (e.g. "continuous-7d, configured at account level").
4. **Restore runbook** — exact CLI commands the operator runs, parameterised by env. Include the "restore into new account/cluster, never overwrite source" pattern when supported.
5. **Verification** — sanity-count queries to confirm the restore worked.
6. **Cutover** — two paths: severe (rotate connection string + redeploy) and partial (dump → inspect → merge).
7. **Ownership table** — account-level access owner vs restore execution vs cutover decision.
8. **Periodic test** — quarterly drill schedule.
9. **Out of scope** — explicit list (secrets backup, container images, configmap, customer data outside the service).

Update `docs/RESPONSIBLE_AI_COMPLIANCE.md` item 6 backup sub-control to ✅.

## Discovery (stack-agnostic)

Find the persistence dependencies:

```bash
grep -rEn "MONGODB_URI|POSTGRES_URL|DATABASE_URL|REDIS_URL|connectionString|DB_HOST|DB_DATABASE" . --include='.env*' --include='*.yaml' --include='*.yml' --include='*.json' --include='*.toml' --include='*.php' --include='*.ts' --include='*.py' --include='*.go' 2>/dev/null | head -20
grep -rEn "expire|ttl|retention" {{SOURCE_DIR}} 2>/dev/null | head -10
```

Pick the runbook commands per provider:

| Backend | Restore command family |
|---|---|
| Azure Cosmos DB | `az cosmosdb restore` (account-level, restores into a new account) |
| Azure SQL / Postgres Flexible | `az sql db restore` / `az postgres flexible-server restore` (PITR) |
| MongoDB Atlas | Atlas backup snapshots via UI or `mongocli` |
| AWS RDS | `aws rds restore-db-instance-to-point-in-time` |
| AWS DynamoDB | `aws dynamodb restore-table-to-point-in-time` |
| GCP Cloud SQL | `gcloud sql backups restore` |
| Self-hosted Postgres | `pg_basebackup` / WAL-replay |
| MySQL / MariaDB | `mysqldump` + binary log replay |

If the service uses a shared/managed database owned by a separate platform or infra team, document that fact and link to the central infra runbook instead of duplicating it.

## Out of scope

- Implementing automated backup.
- Cross-region replication.
- Changing the existing backup configuration.
