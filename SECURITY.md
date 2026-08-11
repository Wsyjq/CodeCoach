# Security Policy

## Supported Versions

Security fixes are applied to the latest version on the `main` branch. Older tags may not receive backports.

## Reporting a Vulnerability

Do not open a public issue for suspected vulnerabilities, leaked credentials, or exposed user data.

Use GitHub's private vulnerability reporting page:

https://github.com/Wsyjq/CodeCoach/security/advisories/new

Include affected versions, impact, reproduction steps, and any suggested mitigation. Remove real credentials and personal data from the report.

Maintainers aim to acknowledge reports within 7 days and provide a status update within 14 days. Timelines may vary for a volunteer-maintained project.

## Deployment Responsibility

CodeCoach is an educational Beta. Source availability does not make the default configuration appropriate for an unrestricted public service. Operators are responsible for TLS, rate limiting, account controls, backups, monitoring, data retention, privacy compliance, and LLM spending limits.

Secrets belong only in local `.env` files or deployment secret stores. Any secret exposed in Git, logs, screenshots, terminals, issues, or support conversations must be revoked, not merely deleted.
