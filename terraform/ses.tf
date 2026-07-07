# SES domain identity + DKIM. Publishing the DKIM CNAMEs is automatic only when
# manage_dns = true (the hosted zone is in Route 53). New SES accounts start in the
# sandbox — request production access separately.

resource "aws_ses_domain_identity" "this" {
  count  = var.manage_ses ? 1 : 0
  domain = var.domain_name
}

resource "aws_ses_domain_dkim" "this" {
  count  = var.manage_ses ? 1 : 0
  domain = aws_ses_domain_identity.this[0].domain
}

# Publish the three DKIM CNAME records when we manage DNS.
resource "aws_route53_record" "dkim" {
  count   = var.manage_ses && var.manage_dns ? 3 : 0
  zone_id = var.route53_zone_id
  name    = "${aws_ses_domain_dkim.this[0].dkim_tokens[count.index]}._domainkey.${var.domain_name}"
  type    = "CNAME"
  ttl     = 600
  records = ["${aws_ses_domain_dkim.this[0].dkim_tokens[count.index]}.dkim.amazonses.com"]
}
