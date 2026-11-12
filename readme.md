# article-app

Article App sends one article to your phone each day. An AWS Lambda checks 33
RSS feeds, selects an article with an estimated reading time of 5–15 minutes,
and publishes it to an [ntfy](https://ntfy.sh) topic.

The picker does not learn user preferences. It selects a wildcard category 30%
of the time, avoids repeating categories, and limits each source to three
selections within 30 days.

The production flow is EventBridge Scheduler → Lambda → ntfy. A private S3
object named `state.db` stores the SQLite selection history.

## Requirements

- Python 3.13
- AWS CLI v2 configured for the target account
- Terraform 1.10 or later
- Make and Git
- An AWS account
- The ntfy app and separate development and production topics

## Setup and deployment

1. Create a Python virtual environment and install `requirements.txt` and
   `requirements-dev.txt`.
2. Run `make test` to verify the application locally. Use `make dry-run` to
   exercise the pipeline against live feeds without sending a notification.
3. Create a private, versioned S3 bucket for Terraform state. Configure its
   name in the S3 backend blocks for both environments. Terraform cannot use a
   variable for this value because backend configuration is loaded first.
4. Copy each environment's `terraform.tfvars.example` to `terraform.tfvars`,
   then set a unique `ntfy_topic` and `bucket_suffix`. These local files are
   excluded from Git.
5. Initialize and deploy development with `make init ENV=dev` and
   `make deploy ENV=dev`. Confirm it with `make invoke ENV=dev`.
6. Repeat the initialization, deployment, and invocation with `ENV=prod` after
   development works as expected.

`ENV` defaults to `dev`, so a command without an environment does not target
production.

## Common commands

| Command | Purpose |
|---|---|
| `make test` | Run the offline test suite |
| `make dry-run` | Run locally against live feeds without sending |
| `make validate-feeds` | Check that configured feeds resolve |
| `make inspect-feeds` | Measure usable articles from each feed |
| `make plan ENV=…` | Build the package and review infrastructure changes |
| `make deploy ENV=…` | Build and apply an environment |
| `make invoke ENV=…` | Invoke the deployed function once |
| `make logs ENV=…` | Follow the function's CloudWatch logs |
| `make stats ENV=…` | Report selection statistics from `state.db` |
| `make destroy ENV=…` | Delete an environment and its state bucket |

## Environments

Development and production use the same application code but separate AWS
resources, ntfy topics, Terraform state, and selection history.

| Setting | Development | Production |
|---|---|---|
| Schedule | Disabled; manual invocation only | Daily at 07:00 UTC |
| Log retention | 7 days | 14 days |
| Terraform state key | `envs/dev/terraform.tfstate` | `envs/prod/terraform.tfstate` |

The development deployment catches issues that offline tests cannot, including
package compatibility and AWS permission errors.

Production also has CloudWatch monitoring: a dashboard named
`article-app-prod`, and email alarms for a missed run (no invocation for 26
hours), any function error, and a run using more than 80% of its timeout. The
first apply sends an AWS subscription email that must be confirmed once.

## Deploy pipeline

GitHub Actions deploys through OIDC. Each job trades a GitHub-signed token for
a one-hour AWS role session, so no access keys are stored anywhere.

| Event | What runs |
|---|---|
| Pull request | Tests, then a read-only `terraform plan` for dev and prod |
| Merge to `main` | Tests, then plan and apply dev, then a smoke test that invokes dev once |
| Merge to `main`, prod changed | A read-only prod plan (`check-prod`), then an apply that waits for approval in the `prod` environment |

Plans and applies are skipped when there are no changes, so a merge that does
not touch the infrastructure does not ask for prod approval. The package build
is deterministic for the same reason: an unchanged function produces the same
zip and the same hash.

The CI can create and update resources but not delete them. `make destroy`
stays a local command.

### One-time setup

1. Apply the CI roles locally with admin credentials:
   `terraform -chdir=infra/terraform/bootstrap init` and then `apply`.
2. Add the repository secrets `AWS_PLAN_ROLE_ARN`, `TFVARS_DEV`, and
   `TFVARS_PROD`. The `TFVARS_*` values are the full contents of each
   environment's local `terraform.tfvars`.
3. Create the `dev` and `prod` environments, each limited to the `main`
   branch, with `AWS_DEPLOY_ROLE_ARN` set from the bootstrap outputs. Add a
   required reviewer to `prod`.

After editing a local `terraform.tfvars`, update the matching `TFVARS_*`
secret. Otherwise CI deploys the old values.

## Repository layout

- `src/` contains the application and Lambda handler.
- `tests/` contains the pytest suite.
- `scripts/` contains feed, packaging, dry-run, and statistics utilities.
- `infra/terraform/modules/` contains the reusable AWS modules.
- `infra/terraform/envs/` contains the development and production deployments.
- `infra/terraform/bootstrap/` contains the GitHub OIDC provider and CI roles,
  applied once by hand.

## Operations and security

The workload is small and is designed for very low AWS usage, but actual cost
depends on the account's current AWS pricing and free-tier eligibility.

### Annual cost estimate
Current architecture: approximately $0–$1.20 per year.
With 1,000 users on the same ntfy topic: approximately $0–$1.20 per year.
This assumes one shared daily notification, AWS free allowances, and free ntfy.sh.

See `security.md` for IAM, storage, encryption, secret-handling, and
vulnerability-reporting details.

Production `state.db` contains the complete send history. Destroying the
production environment deletes that history and resets category repetition and
per-source limits.
