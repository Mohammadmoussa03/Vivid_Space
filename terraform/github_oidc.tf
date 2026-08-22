# GitHub Actions -> AWS via OIDC.
#
# Lets the CI workflow (.github/workflows/deploy.yml) assume a role and run
# deploy.sh on the instance through SSM. No access keys are stored in GitHub:
# Actions presents a short-lived OIDC token, and the trust policy below only
# accepts one repo, on the main branch (or the "production" environment).
#
# After `tofu apply`, put the outputs in the repo's Actions *variables*:
#   AWS_ROLE_ARN = <github_actions_role_arn>   AWS_REGION = <aws_region>
#   INSTANCE_ID  = <web_instance_id>

variable "github_repository" {
  description = "owner/repo allowed to assume the deploy role (empty = don't create it)."
  type        = string
  default     = ""
}

locals {
  gha_enabled = var.github_repository != ""
}

# One OIDC provider per account. If the account already has one for GitHub,
# import it (`tofu import aws_iam_openid_connect_provider.github <arn>`)
# instead of creating a duplicate — AWS rejects a second provider for the
# same URL.
resource "aws_iam_openid_connect_provider" "github" {
  count          = local.gha_enabled ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # GitHub's OIDC endpoint is fronted by a widely-rotated CA; AWS validates the
  # thumbprint itself for this provider, but the field is still required.
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_policy_document" "github_assume" {
  count = local.gha_enabled ? 1 : 0
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github[0].arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Scope hard: only this repo, only pushes to main and only jobs running in
    # the "production" environment. A fork or a feature branch cannot assume it.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repository}:ref:refs/heads/main",
        "repo:${var.github_repository}:environment:production",
      ]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  count              = local.gha_enabled ? 1 : 0
  name               = "${var.project_name}-github-deploy"
  description        = "Assumed by GitHub Actions to deploy via SSM"
  assume_role_policy = data.aws_iam_policy_document.github_assume[0].json
}

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "github_deploy" {
  count = local.gha_enabled ? 1 : 0

  # Run commands on the project's instances only, and only the shell-script
  # document. Scoped by tag rather than by aws_instance.web.arn on purpose: a
  # direct reference would pull the instance into the graph of a targeted
  # apply, and this stack currently plans a REPLACEMENT for it (see README).
  statement {
    sid       = "RunDeployOnProjectInstances"
    effect    = "Allow"
    actions   = ["ssm:SendCommand"]
    resources = ["arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/*"]
    condition {
      test     = "StringEquals"
      variable = "ssm:resourceTag/Project"
      values   = ["vivid-space"]
    }
  }
  statement {
    sid       = "UseRunShellScriptDocument"
    effect    = "Allow"
    actions   = ["ssm:SendCommand"]
    resources = ["arn:aws:ssm:${var.aws_region}::document/AWS-RunShellScript"]
  }
  # Read back the command's status and output so the workflow can report it.
  statement {
    sid       = "ReadCommandResults"
    effect    = "Allow"
    actions   = ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations", "ssm:ListCommands"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  count  = local.gha_enabled ? 1 : 0
  name   = "${var.project_name}-github-deploy"
  role   = aws_iam_role.github_actions[0].id
  policy = data.aws_iam_policy_document.github_deploy[0].json
}

output "github_actions_role_arn" {
  description = "Set as the AWS_ROLE_ARN repository variable in GitHub Actions."
  value       = local.gha_enabled ? aws_iam_role.github_actions[0].arn : "(set github_repository to enable)"
}

