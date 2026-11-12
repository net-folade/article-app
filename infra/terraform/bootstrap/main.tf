# GitHub Actions -> AWS without stored access keys.
#
# GitHub signs a short-lived OIDC token for each job. AWS trusts GitHub's
# issuer (the provider below), and each role's trust policy decides which jobs
# may assume it by matching the token's `sub` claim:
#
#   plan         <prefix>:pull_request, <prefix>:ref:refs/heads/main   read-only
#   deploy-dev   <prefix>:environment:dev                             writes article-app-dev-*
#   deploy-prod  <prefix>:environment:prod                            writes article-app-prod-*
#
# CLI equivalent of one assumption: `aws sts assume-role-with-web-identity`.
#
# Nothing here grants delete on buckets, functions, roles, schedules or log
# groups. `make destroy` stays a local, deliberate act.

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = "us-east-1"
  # The repo uses GitHub's immutable subject format: owner and repo carry their
  # numeric IDs, so a rename cannot hand these roles to a different repo.
  # Source: gh api repos/net-folade/article-app/actions/oidc/customization/sub
  sub_prefix   = "repo:net-folade@148221490/article-app@1340726485"
  project      = "article-app"
  state_bucket = "terraform-state-145b8d8b"
  oidc_host    = "token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://${local.oidc_host}"
  client_id_list = ["sts.amazonaws.com"]
}

# ---------------------------------------------------------------------------
# plan — pull requests and check-prod, read-only, both environments
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "plan_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:sub"
      # Pull request plans, plus check-prod on main (no environment attached).
      values = [
        "${local.sub_prefix}:pull_request",
        "${local.sub_prefix}:ref:refs/heads/main",
      ]
    }
  }
}

resource "aws_iam_role" "plan" {
  name                 = "${local.project}-ci-plan"
  assume_role_policy   = data.aws_iam_policy_document.plan_trust.json
  max_session_duration = 3600
}

# `terraform plan -lock=false` only reads: the state object, then every
# resource it manages. state.db is explicitly denied below.
data "aws_iam_policy_document" "plan" {
  statement {
    sid       = "ReadTerraformState"
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${local.state_bucket}/envs/*/terraform.tfstate"]
  }

  statement {
    sid       = "ListTerraformState"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.state_bucket}"]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["envs/*"]
    }
  }

  statement {
    sid       = "ReadAppBuckets"
    actions   = ["s3:Get*", "s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.project}-*-state-*"]
  }

  # IAM wildcards cross "/", so the pattern above also matches .../state.db.
  statement {
    sid       = "NeverReadAppObjects"
    effect    = "Deny"
    actions   = ["s3:GetObject*"]
    resources = ["arn:aws:s3:::${local.project}-*-state-*/*"]
  }

  statement {
    sid       = "ReadFunctions"
    actions   = ["lambda:Get*", "lambda:List*"]
    resources = ["arn:aws:lambda:${local.region}:${local.account_id}:function:${local.project}-*"]
  }

  statement {
    sid = "ReadRoles"
    actions = [
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:ListRoleTags",
    ]
    resources = ["arn:aws:iam::${local.account_id}:role/${local.project}-*"]
  }

  statement {
    sid       = "ReadLogGroups"
    actions   = ["logs:ListTagsForResource"]
    resources = ["arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/lambda/${local.project}-*"]
  }

  # DescribeLogGroups takes no resource ARN; AWS requires "*" here.
  statement {
    sid       = "DescribeLogGroups"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["*"]
  }

  statement {
    sid     = "ReadSchedules"
    actions = ["scheduler:GetSchedule", "scheduler:GetScheduleGroup", "scheduler:ListTagsForResource"]
    resources = [
      "arn:aws:scheduler:${local.region}:${local.account_id}:schedule/${local.project}-*/*",
      "arn:aws:scheduler:${local.region}:${local.account_id}:schedule-group/${local.project}-*",
    ]
  }

  statement {
    sid       = "ReadAlarmTopics"
    actions   = ["sns:GetTopicAttributes", "sns:GetSubscriptionAttributes", "sns:ListTagsForResource"]
    resources = ["arn:aws:sns:${local.region}:${local.account_id}:${local.project}-*"]
  }

  statement {
    sid     = "ReadAlarmsAndDashboards"
    actions = ["cloudwatch:DescribeAlarms", "cloudwatch:ListTagsForResource", "cloudwatch:GetDashboard"]
    resources = [
      "arn:aws:cloudwatch:${local.region}:${local.account_id}:alarm:${local.project}-*",
      "arn:aws:cloudwatch::${local.account_id}:dashboard/${local.project}-*",
    ]
  }
}

resource "aws_iam_role_policy" "plan" {
  name   = "${local.project}-ci-plan"
  role   = aws_iam_role.plan.id
  policy = data.aws_iam_policy_document.plan.json
}

# ---------------------------------------------------------------------------
# deploy-<env> — main branch, GitHub environment gate, one environment each
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "deploy_trust" {
  for_each = toset(["dev", "prod"])

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:sub"
      values   = ["${local.sub_prefix}:environment:${each.key}"]
    }
  }
}

resource "aws_iam_role" "deploy" {
  for_each = toset(["dev", "prod"])

  name                 = "${local.project}-ci-deploy-${each.key}"
  assume_role_policy   = data.aws_iam_policy_document.deploy_trust[each.key].json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "deploy" {
  for_each = toset(["dev", "prod"])

  # State read/write plus the S3 lock file (`use_lockfile = true`).
  statement {
    sid     = "TerraformState"
    actions = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = [
      "arn:aws:s3:::${local.state_bucket}/envs/${each.key}/terraform.tfstate",
      "arn:aws:s3:::${local.state_bucket}/envs/${each.key}/terraform.tfstate.tflock",
    ]
  }

  statement {
    sid       = "ListTerraformState"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.state_bucket}"]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["envs/${each.key}/*"]
    }
  }

  # Bucket configuration only — no object access, no bucket deletion.
  statement {
    sid = "AppBucket"
    actions = [
      "s3:Get*",
      "s3:ListBucket",
      "s3:CreateBucket",
      "s3:PutBucketPolicy",
      "s3:PutBucketVersioning",
      "s3:PutBucketTagging",
      "s3:PutBucketOwnershipControls",
      "s3:PutBucketPublicAccessBlock",
      "s3:PutEncryptionConfiguration",
      "s3:PutLifecycleConfiguration",
    ]
    resources = ["arn:aws:s3:::${local.project}-${each.key}-state-*"]
  }

  # IAM wildcards cross "/", so the pattern above also matches .../state.db.
  statement {
    sid       = "NeverReadAppObjects"
    effect    = "Deny"
    actions   = ["s3:GetObject*"]
    resources = ["arn:aws:s3:::${local.project}-${each.key}-state-*/*"]
  }

  statement {
    sid = "Function"
    actions = [
      "lambda:Get*",
      "lambda:List*",
      "lambda:CreateFunction",
      "lambda:UpdateFunctionCode",
      "lambda:UpdateFunctionConfiguration",
      "lambda:TagResource",
      "lambda:UntagResource",
    ]
    resources = ["arn:aws:lambda:${local.region}:${local.account_id}:function:${local.project}-${each.key}-*"]
  }

  # The function and scheduler roles. Matches article-app-<env>-* only, so this
  # role can never edit the CI roles (article-app-ci-*).
  statement {
    sid = "AppRoles"
    actions = [
      "iam:GetRole",
      "iam:GetRolePolicy",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:ListRoleTags",
      "iam:CreateRole",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy",
    ]
    resources = ["arn:aws:iam::${local.account_id}:role/${local.project}-${each.key}-*"]
  }

  statement {
    sid       = "PassAppRoles"
    actions   = ["iam:PassRole"]
    resources = ["arn:aws:iam::${local.account_id}:role/${local.project}-${each.key}-*"]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["lambda.amazonaws.com", "scheduler.amazonaws.com"]
    }
  }

  statement {
    sid = "LogGroup"
    actions = [
      "logs:CreateLogGroup",
      "logs:PutRetentionPolicy",
      "logs:TagResource",
      "logs:UntagResource",
      "logs:ListTagsForResource",
    ]
    resources = ["arn:aws:logs:${local.region}:${local.account_id}:log-group:/aws/lambda/${local.project}-${each.key}-*"]
  }

  # DescribeLogGroups takes no resource ARN; AWS requires "*" here.
  statement {
    sid       = "DescribeLogGroups"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["*"]
  }

  statement {
    sid = "Schedule"
    actions = [
      "scheduler:GetSchedule",
      "scheduler:CreateSchedule",
      "scheduler:UpdateSchedule",
      "scheduler:GetScheduleGroup",
      "scheduler:CreateScheduleGroup",
      "scheduler:TagResource",
      "scheduler:UntagResource",
      "scheduler:ListTagsForResource",
    ]
    resources = [
      "arn:aws:scheduler:${local.region}:${local.account_id}:schedule/${local.project}-${each.key}/*",
      "arn:aws:scheduler:${local.region}:${local.account_id}:schedule-group/${local.project}-${each.key}",
    ]
  }
}

resource "aws_iam_role_policy" "deploy" {
  for_each = toset(["dev", "prod"])

  name   = "${local.project}-ci-deploy-${each.key}"
  role   = aws_iam_role.deploy[each.key].id
  policy = data.aws_iam_policy_document.deploy[each.key].json
}

# dev only: the post-deploy smoke test invokes the function once.
data "aws_iam_policy_document" "deploy_dev_smoke" {
  statement {
    sid       = "SmokeTest"
    actions   = ["lambda:InvokeFunction"]
    resources = ["arn:aws:lambda:${local.region}:${local.account_id}:function:${local.project}-dev-picker"]
  }
}

resource "aws_iam_role_policy" "deploy_dev_smoke" {
  name   = "${local.project}-ci-deploy-dev-smoke"
  role   = aws_iam_role.deploy["dev"].id
  policy = data.aws_iam_policy_document.deploy_dev_smoke.json
}

# prod only: the monitoring module (alarm topic, alarms, dashboard).
data "aws_iam_policy_document" "deploy_prod_monitoring" {
  statement {
    sid = "AlarmTopic"
    actions = [
      "sns:CreateTopic",
      "sns:GetTopicAttributes",
      "sns:SetTopicAttributes",
      "sns:TagResource",
      "sns:UntagResource",
      "sns:ListTagsForResource",
      "sns:Subscribe",
      "sns:Unsubscribe",
      "sns:GetSubscriptionAttributes",
    ]
    resources = ["arn:aws:sns:${local.region}:${local.account_id}:${local.project}-prod-*"]
  }

  statement {
    sid = "Alarms"
    actions = [
      "cloudwatch:PutMetricAlarm",
      "cloudwatch:DescribeAlarms",
      "cloudwatch:DeleteAlarms",
      "cloudwatch:TagResource",
      "cloudwatch:UntagResource",
      "cloudwatch:ListTagsForResource",
    ]
    resources = ["arn:aws:cloudwatch:${local.region}:${local.account_id}:alarm:${local.project}-prod-*"]
  }

  statement {
    sid       = "Dashboard"
    actions   = ["cloudwatch:PutDashboard", "cloudwatch:GetDashboard", "cloudwatch:DeleteDashboards"]
    resources = ["arn:aws:cloudwatch::${local.account_id}:dashboard/${local.project}-prod"]
  }
}

resource "aws_iam_role_policy" "deploy_prod_monitoring" {
  name   = "${local.project}-ci-deploy-prod-monitoring"
  role   = aws_iam_role.deploy["prod"].id
  policy = data.aws_iam_policy_document.deploy_prod_monitoring.json
}
