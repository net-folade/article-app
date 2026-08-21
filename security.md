# Security

This document summarizes the security controls for the AWS deployment. The
Terraform configuration is the source of truth for their implementation.

The production deployment runs in AWS account `accountID` in `us-east-1`.
Development uses the same controls with separate, environment-specific
resources.

## Access control

The deployment follows least privilege and uses two service roles. Neither
role permits interactive sign-in or access by people.

- The Lambda execution role can read and replace only the `state.db` object in
  its environment's state bucket. It cannot list the bucket, delete objects, or
  access other buckets or keys.
- The Lambda execution role can create log streams and write events only in
  the function's own CloudWatch log group. Terraform creates the log group, so
  the role does not have permission to create log groups.
- The Scheduler role can invoke only the picker Lambda. Its trust policy limits
  use to EventBridge Scheduler, the deployment's AWS account, and the specific
  daily schedule.
- No AWS-managed policies are attached to either role.

RSS feeds, article pages, and ntfy are accessed over the public internet and
do not require IAM permissions.

## Data protection

The state bucket has the following protections:

- All public access is blocked.
- ACLs are disabled with bucket-owner-enforced ownership.
- Objects are encrypted at rest with Amazon S3-managed keys (SSE-S3).
- Requests made without TLS are denied.
- Versioning is enabled so `state.db` can be recovered.
- Noncurrent versions expire after seven days to limit storage growth.

A missing `state.db` on the first run creates an empty database. Other S3
errors stop the run rather than risk overwriting or losing saved history.

## Secrets and Terraform state

The ntfy topic is stored in the Lambda environment and appears in plaintext in
Terraform state. Read access to Terraform state must therefore be treated as
access to the ntfy topic.

The separately managed Terraform state bucket has versioning, SSE-S3
encryption, and public access blocking enabled. Local `terraform.tfvars` files
are excluded from Git; only the example file without a real topic is tracked.

## Deliberate trade-offs

- A customer-managed KMS key is not used because SSE-S3 provides encryption at
  rest without adding key-management cost and permissions.
- The ntfy topic is not stored in Parameter Store. The current design relies on
  restricted access to Lambda configuration and Terraform state; use a secret
  store if stronger protection becomes necessary.
- The Lambda is not placed in a VPC because it must fetch public feeds and
  articles. VPC placement would require additional networking, such as a NAT
  gateway, without protecting any private network resource.

## Reporting a vulnerability

Do not publish sensitive vulnerability details in a public issue. Report them privately to the repository owner and include the affected component, impact,
and steps needed to reproduce the issue.
