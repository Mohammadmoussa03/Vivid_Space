# Point the domain at the Elastic IP. Only when manage_dns = true and the zone exists.

resource "aws_route53_record" "apex" {
  count   = var.manage_dns ? 1 : 0
  zone_id = var.route53_zone_id
  name    = var.domain_name
  type    = "A"
  ttl     = 300
  records = [aws_eip.web.public_ip]
}

resource "aws_route53_record" "www" {
  count   = var.manage_dns ? 1 : 0
  zone_id = var.route53_zone_id
  name    = "www.${var.domain_name}"
  type    = "A"
  ttl     = 300
  records = [aws_eip.web.public_ip]
}
