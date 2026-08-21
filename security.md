# security.md — AWS permissions

Every permission in this stack is listed below with the line of code that
needs it. If a permission has no caller, it should not be here.

Account `accountID`, region `us-east-1`. Names below are the **prod**
names; dev is identical with `dev` in place of `prod`.

| Resource | prod name |
|---|---|
| State bucket | `article-app-prod-state-099e02cf` |
| Function | `article-app-prod-picker` |
| Execution role | `article-app-prod-picker-role` |
| Log group | `/aws/lambda/article-app-prod-picker` |
| Schedule | `article-app-prod-daily` |
| Scheduler role | `article-app-prod-scheduler-role` |

---

## 1. Roles

There are two roles. People cannot use either role or sign in with them.

| Role | Can do | Cannot do |
|---|---|---|
| **Execution role** `article-app-prod-picker-role` | Read and write the single object `state.db` in its own bucket; create log streams and write log events in its own log group | List the bucket, delete any object, touch any other key or bucket, read or write any other log group, invoke anything, call any other AWS service |
| **Scheduler role** `article-app-prod-scheduler-role` | Invoke `article-app-prod-picker` and nothing else — and only when EventBridge Scheduler is acting for schedule `article-app-prod-daily` in this account | Invoke any other function, read S3, write logs, be assumed by any other service or by a schedule in another account |

RSS, article, and ntfy requests need no IAM permissions. The function has
normal internet access outside a VPC.

---

## 2. Execution role

### 2.1 Trust policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Principal": { "Service": "lambda.amazonaws.com" }
    }
  ]
}
```

Only Lambda can use this role.

### 2.2 Inline policy `article-app-prod-picker-logs`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "WriteOwnLogs",
      "Effect": "Allow",
      "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:us-east-1:accountID:log-group:/aws/lambda/article-app-prod-picker:*"
    }
  ]
}
```

| Permission | Used by code? | Where |
|---|---|---|
| `logs:CreateLogStream` | **Y** | Lambda opens a stream for logs from `src/handler.py` |
| `logs:PutLogEvents` | **Y** | Every `log.info` call in `src/handler.py` |
| `logs:CreateLogGroup` | **N — deliberately absent** | Terraform creates the group (`aws_cloudwatch_log_group.this`), so the function never needs to |

**Why not `AWSLambdaBasicExecutionRole`.** It allows access to every log group.
This policy allows access only to this function's log group.

### 2.3 Inline policy `article-app-prod-picker-state`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadWriteStateDb",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::article-app-prod-state-099e02cf/state.db"
    }
  ]
}
```

| Permission | Used by code? | Where |
|---|---|---|
| `s3:GetObject` | **Y** | `_download_state` in `src/db.py` — `client.download_file` |
| `s3:PutObject` | **Y** | `s3_backed_db` in `src/db.py` — `client.upload_file` on clean exit |
| `s3:DeleteObject` | **N** | The function never deletes state |
| `s3:ListBucket` | **N** | The function uses the fixed key `state.db` |
| `s3:GetObjectVersion` | **N** | Version rollback is a human operation done with the CLI, not something the function does |

The policy allows access only to `state.db`, not the whole bucket.

On the first run, a missing `state.db` starts an empty database. All other S3
errors stop the run to protect saved history.

---

## 3. Scheduler role

### 3.1 Trust policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Principal": { "Service": "scheduler.amazonaws.com" },
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "accountID"
        },
        "ArnEquals": {
          "aws:SourceArn": "arn:aws:scheduler:us-east-1:accountID:schedule/default/article-app-prod-daily"
        }
      }
    }
  ]
}
```

These conditions allow only this AWS account and this schedule to use the
role. Other accounts and schedules cannot invoke the function through it.

### 3.2 Inline policy `article-app-prod-daily-invoke`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvokePickerFunction",
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:us-east-1:accountID:function:article-app-prod-picker"
    }
  ]
}
```

| Permission | Used by code? | Where |
|---|---|---|
| `lambda:InvokeFunction` | **Y** | The schedule's target; this is the only thing the role exists for |

EventBridge Scheduler invokes Lambda through this role, so no separate
`aws_lambda_permission` resource is needed.

---

## 4. Bucket protection

| Control | Setting | Why |
|---|---|---|
| Public access block | all four flags `true` | Block all public access |
| Object ownership | `BucketOwnerEnforced` | Disable ACLs and use IAM policies |
| Encryption | `AES256` (SSE-S3) | Encrypt data at rest |
| Versioning | Enabled | Keep older copies of `state.db` for recovery |
| Lifecycle | noncurrent versions expire after 7 days | One version a day accumulates forever otherwise |
| Bucket policy | `Deny s3:*` when `aws:SecureTransport` is `false` | Block plain HTTP requests |

The bucket holds one object and has no public read path of any kind.

---

## 5. Verify the deployment

Run these after `make deploy ENV=prod`.

```bash
BUCKET=article-app-prod-state-099e02cf
ROLE=article-app-prod-picker-role
SCHED_ROLE=article-app-prod-scheduler-role
ACCOUNT=accountID
```

**No managed policies attached** — this is the `AWSLambdaBasicExecutionRole`
check. Expect an empty list:

```bash
aws iam list-attached-role-policies --role-name "$ROLE"
# => { "AttachedPolicies": [] }
```

**The two inline policies exist and nothing else does:**

```bash
aws iam list-role-policies --role-name "$ROLE"
# => article-app-prod-picker-logs, article-app-prod-picker-state
```

**Each inline policy's actual document:**

```bash
aws iam get-role-policy --role-name "$ROLE" \
  --policy-name article-app-prod-picker-state
# => Action GetObject/PutObject, Resource ending /state.db — no DeleteObject

aws iam get-role-policy --role-name "$ROLE" \
  --policy-name article-app-prod-picker-logs
# => Resource is the single log group ARN, never "*"
```

**Scheduler role trust conditions:**

```bash
aws iam get-role --role-name "$SCHED_ROLE" \
  --query 'Role.AssumeRolePolicyDocument'
# => Condition contains both aws:SourceAccount and aws:SourceArn
```

**Bucket is fully private:**

```bash
aws s3api get-public-access-block --bucket "$BUCKET"
# => all four flags true

aws s3api get-bucket-policy --bucket "$BUCKET" --output text
# => the DenyInsecureTransport statement

aws s3api get-bucket-versioning --bucket "$BUCKET"
# => Status: Enabled

aws s3api get-bucket-encryption --bucket "$BUCKET"
# => SSEAlgorithm: AES256

aws s3api get-bucket-ownership-controls --bucket "$BUCKET"
# => ObjectOwnership: BucketOwnerEnforced
```

**Check that people cannot use the function role.** This should fail with
`AccessDenied`:

```bash
aws sts assume-role --role-arn "arn:aws:iam::$ACCOUNT:role/$ROLE" \
  --role-session-name audit 2>&1 | head -3
# => AccessDenied: only lambda.amazonaws.com may assume it, not you
```

The failure confirms that only Lambda can use the role.

---

## 6. Security options not used

| Skipped | Reason |
|---|---|
| **KMS customer-managed key on the bucket** | SSE-S3 already encrypts the data. A custom key adds cost and more permissions without a useful benefit here |
| **VPC placement for the Lambda** | The function's entire job is outbound HTTP to 33 public feeds. In a VPC that needs private subnets plus a NAT gateway at ~$32/month — more than 30× the rest of the stack — to make public internet access work again |
| **GuardDuty / CloudTrail data events / Config** | These services cost more than this small personal app needs |
| **`NTFY_TOPIC` in SSM Parameter Store (SecureString)** | The topic is stored as plain text in Lambda settings and Terraform state. Anyone who reads it can read or publish notifications. The private state bucket limits access. Move it to SSM if stronger protection becomes necessary |
| **Reserved concurrency on the function** | One invocation a day from a single scheduler with `maximum_retry_attempts = 0`. There is no concurrency to reserve against |
| **Dead-letter queue on the schedule** | Add it with CloudWatch alarms as one failure-reporting change |
| **MFA-delete on the bucket** | Requires root credentials to enable and blocks the lifecycle rule from expiring noncurrent versions |
| **Object Lock** | Incompatible with overwriting the same key daily, which is the entire access pattern |

---

## 7. Protect Terraform state

`terraform-state-145b8d8b` holds `envs/dev/terraform.tfstate` and
`envs/prod/terraform.tfstate`. Because `ntfy_topic` is a Lambda environment
variable, **it appears in plaintext in those state files** — `sensitive = true`
on the variable hides it from CLI output but not from state.

That bucket was created by hand, outside this Terraform config, with
versioning, AES256, and all four public-access-block flags on. It is not
managed by this stack and does not appear in any plan. Treat read access to it
as equivalent to holding the ntfy topic.

`terraform.tfvars` is gitignored for the same reason; `terraform.tfvars.example`
carries the shape with the secret replaced.
