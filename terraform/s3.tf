# S3 bucket for uploaded media (gallery images). django-storages writes here;
# browsers read straight from the bucket (public-read via bucket policy).

resource "aws_s3_bucket" "media" {
  bucket = var.media_bucket_name
  tags   = { Name = var.media_bucket_name }
}

resource "aws_s3_bucket_ownership_controls" "media" {
  bucket = aws_s3_bucket.media.id
  rule {
    object_ownership = "BucketOwnerEnforced" # ACLs disabled; access via bucket policy
  }
}

# Leave ACLs blocked, allow public *policy* (matches the guide: uncheck "block all public access")
resource "aws_s3_bucket_public_access_block" "media" {
  bucket = aws_s3_bucket.media.id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = false
  restrict_public_buckets = false
}

data "aws_iam_policy_document" "media_public_read" {
  statement {
    sid     = "PublicReadMedia"
    effect  = "Allow"
    actions = ["s3:GetObject"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    resources = ["${aws_s3_bucket.media.arn}/*"]
  }
}

resource "aws_s3_bucket_policy" "media" {
  bucket     = aws_s3_bucket.media.id
  policy     = data.aws_iam_policy_document.media_public_read.json
  depends_on = [aws_s3_bucket_public_access_block.media]
}

resource "aws_s3_bucket_cors_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  cors_rule {
    # Public, GET-only media bucket. In test mode (no domain) we allow any origin;
    # with a domain, restrict to the real site origins.
    allowed_origins = local.test_mode ? ["*"] : ["https://${var.domain_name}", "https://www.${var.domain_name}"]
    allowed_methods = ["GET"]
    allowed_headers = ["*"]
    max_age_seconds = 3000
  }
}
