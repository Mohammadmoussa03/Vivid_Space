# IAM role attached to the EC2 instance so boto3/django-storages picks up S3
# credentials automatically — no access keys in .env.

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2" {
  name               = "${var.project_name}-ec2"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

data "aws_iam_policy_document" "s3_media" {
  statement {
    sid       = "MediaObjectRW"
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.media.arn}/*"]
  }
  statement {
    sid       = "MediaListBucket"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.media.arn]
  }
}

resource "aws_iam_role_policy" "s3_media" {
  name   = "${var.project_name}-s3-media"
  role   = aws_iam_role.ec2.id
  policy = data.aws_iam_policy_document.s3_media.json
}

# Let the instance send mail through SES via the API too (optional; SMTP creds also work).
data "aws_iam_policy_document" "ses_send" {
  statement {
    effect    = "Allow"
    actions   = ["ses:SendRawEmail", "ses:SendEmail"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "ses_send" {
  name   = "${var.project_name}-ses-send"
  role   = aws_iam_role.ec2.id
  policy = data.aws_iam_policy_document.ses_send.json
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${var.project_name}-ec2"
  role = aws_iam_role.ec2.name
}
