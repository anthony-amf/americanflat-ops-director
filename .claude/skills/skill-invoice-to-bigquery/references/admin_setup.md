# Admin setup (one-time) — run by the dataset owner, NOT by the skill

The skill deliberately performs **no IAM or schema operations**. Everything
in this file is run once by the admin (the person who owns the BigQuery
dataset) so they stay the single gatekeeper for who can write invoices.
Operators never run these commands.

Replace `PROJECT` with your GCP project id throughout.

## 1. Create the writer service account

This one identity is what every operator, bot, or app writes *through*.

```bash
gcloud iam service-accounts create invoice-writer \
  --project=PROJECT \
  --display-name="Invoice -> BigQuery writer"
```

## 2. Create the dataset and table

```bash
# Dataset (skip if it already exists)
bq --location=US mk --dataset PROJECT:finance

# Table, from the schema shipped with the skill
bq mk --table \
  PROJECT:finance.freight_invoices \
  references/bq_schema.json

# Optional but recommended once you have volume:
#   partition by invoice_date, cluster by vendor_name + invoice_id
# bq mk --table \
#   --time_partitioning_field=invoice_date \
#   --clustering_fields=vendor_name,invoice_id \
#   PROJECT:finance.freight_invoices references/bq_schema.json
```

## 3. Let the service account write to ONLY this dataset

Least privilege — grant on the dataset, not the whole project.

```bash
bq show --format=prettyjson PROJECT:finance > /tmp/finance.json
# add this object to the "access" array in /tmp/finance.json:
#   {"role": "WRITER", "userByEmail": "invoice-writer@PROJECT.iam.gserviceaccount.com"}
bq update --source /tmp/finance.json PROJECT:finance
```

## 3b. Let the service account run BigQuery jobs

Dataset `WRITER` lets the SA write to tables, but *running* any job — both a
load and a query — additionally requires `bigquery.jobs.create` at the project
level. `roles/bigquery.jobUser` grants exactly that and nothing more: the SA
can run jobs, but data access is still governed by the dataset ACL from step 3
(so it can only touch `finance`).

```bash
gcloud projects add-iam-policy-binding PROJECT \
  --member="serviceAccount:invoice-writer@PROJECT.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"
```

## 4. Let a person impersonate the writer (repeat per operator)

This is the only command you run to add or remove an operator. No keys are
ever created or shared.

```bash
# GRANT access to a new operator
gcloud iam service-accounts add-iam-policy-binding \
  invoice-writer@PROJECT.iam.gserviceaccount.com \
  --member="user:newperson@americanflat.com" \
  --role="roles/iam.serviceAccountTokenCreator"

# REVOKE access (same command, --remove-iam-policy-binding)
gcloud iam service-accounts remove-iam-policy-binding \
  invoice-writer@PROJECT.iam.gserviceaccount.com \
  --member="user:formerperson@americanflat.com" \
  --role="roles/iam.serviceAccountTokenCreator"
```

The operator then runs `gcloud auth login` once on their machine. That is
their entire setup — no key file, no direct dataset grant.

## 5. Fill in config.json

Put the real values in the skill's `config.json` and commit them (they are
identifiers, not secrets):

```json
{
  "project_id": "PROJECT",
  "dataset": "finance",
  "table": "freight_invoices",
  "impersonate_service_account": "invoice-writer@PROJECT.iam.gserviceaccount.com",
  "location": "US"
}
```

## Querying line items later

`line_items` is a repeated record, so unnest it:

```sql
SELECT invoice_id, li.description, li.amount
FROM `PROJECT.finance.freight_invoices`, UNNEST(line_items) AS li
WHERE vendor_name = 'Your Carrier';
```

`raw_extraction` is stored as a JSON string — read it with `PARSE_JSON`:

```sql
SELECT invoice_id, PARSE_JSON(raw_extraction) AS raw
FROM `PROJECT.finance.freight_invoices`;
```
