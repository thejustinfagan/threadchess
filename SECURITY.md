# Security Guidelines

This document outlines security considerations and best practices for the Battle Dinghy Twitter bot.

## Critical Security Rules

### 1. **NEVER Commit Credentials**
- The `.env` file contains sensitive API keys and tokens
- **NEVER** commit `.env` to version control
- Always use `.env.example` or `env_example.txt` as templates
- Review commits before pushing to ensure no credentials leaked

### 2. **Environment Variables**
All sensitive data must be stored in environment variables:

```bash
# Required Environment Variables
X_API_KEY=               # Twitter API Key
X_API_SECRET=            # Twitter API Secret
X_ACCESS_TOKEN=          # Twitter Access Token
X_ACCESS_TOKEN_SECRET=   # Twitter Access Token Secret
BEARER_TOKEN=            # Twitter Bearer Token
SUPABASE_URL=           # Supabase Project URL
SUPABASE_KEY=           # Supabase Anon Key
```

### 3. **Input Validation**

All user inputs are validated and sanitized:

#### Coordinate Input
- Limited to alphanumeric characters
- Maximum length of 10 characters
- Must match pattern: `[A-F][1-6]`
- Prevents injection attacks

#### Username Input
- Validated through Twitter API
- No direct SQL queries with usernames
- Rate limiting prevents abuse

### 4. **API Rate Limiting**

Twitter API limits are respected:
- Bot polls every 60 seconds (not faster)
- `wait_on_rate_limit=True` in Tweepy client
- Implements exponential backoff on errors
- Monitors consecutive errors (max 5)

### 5. **Database Security**

#### Supabase Security
- Use Row Level Security (RLS) policies
- Limit database user permissions
- Never expose Supabase service key
- Use anon key for bot operations

#### Recommended RLS Policies
```sql
-- Enable RLS on games table
ALTER TABLE games ENABLE ROW LEVEL SECURITY;

-- Allow authenticated reads
CREATE POLICY "Authenticated read access"
ON games FOR SELECT
TO authenticated
USING (true);

-- Allow authenticated writes
CREATE POLICY "Authenticated write access"
ON games FOR INSERT, UPDATE
TO authenticated
WITH CHECK (true);
```

## Input Sanitization

### Process Shot Function
```python
# Sanitize coordinate input
coordinate = ''.join(c for c in coordinate if c.isalnum() or c.isspace())
coordinate = coordinate.strip().upper()

# Length validation
if len(coordinate) > 10:
    return error_message

# Format validation
if not re.match(r'^[A-F][1-6]$', coordinate):
    return error_message
```

### Username Validation
```python
# Twitter handles validation
username = re.sub(r'[^a-zA-Z0-9_]', '', username)

# Length check (Twitter usernames are max 15 chars)
if len(username) > 15:
    return error
```

## Preventing Common Attacks

### 1. **SQL Injection**
- Using Supabase client (parameterized queries)
- Never constructing raw SQL with user input
- All queries use `.eq()`, `.select()` methods

### 2. **XSS (Cross-Site Scripting)**
- Not applicable (no web interface)
- Tweet text is sanitized by Twitter API

### 3. **Command Injection**
- No shell commands use user input
- All file operations use safe paths
- No `eval()` or `exec()` with user data

### 4. **DoS (Denial of Service)**
- Rate limiting prevents spam
- Maximum 5 consecutive errors before stopping
- 60-second polling interval
- Thread ID deduplication

### 5. **Account Takeover**
- API keys stored securely
- No password authentication
- OAuth tokens regularly rotated (recommended)

## Access Control

### File Permissions
```bash
# .env file should be readable only by owner
chmod 600 .env

# Python files should not be world-writable
chmod 644 *.py

# Logs should be protected
chmod 600 *.log
```

### Supabase Access
- Use least privilege principle
- Bot account has minimal permissions
- No admin/service key in production
- Enable RLS on all tables

## Logging and Monitoring

### What to Log
- ✅ Game starts and completions
- ✅ API errors and rate limits
- ✅ Database connection issues
- ✅ Invalid inputs (for monitoring)

### What NOT to Log
- ❌ API keys or tokens
- ❌ Full tweet IDs (PII)
- ❌ User passwords (N/A but principle applies)
- ❌ Internal system paths

### Log Security
```python
# Good: Log sanitized coordinate
logger.info(f"Processing shot at {coordinate}")

# Bad: Log raw user input
logger.info(f"Raw input: {user_input}")  # Could contain injection attempts

# Bad: Log credentials
logger.info(f"Using token {access_token}")  # NEVER!
```

## Secrets Management

### Development
- Use `.env` file locally
- Never commit `.env` to git
- Use `.env.example` as template

### Production
- Use environment variables
- Consider secret management services:
  - AWS Secrets Manager
  - HashiCorp Vault
  - Azure Key Vault
  - Google Secret Manager

### Rotation Policy
- Rotate Twitter API keys quarterly
- Rotate Supabase keys quarterly
- Immediately rotate if compromised
- Keep old keys for 24h during rotation

## Network Security

### HTTPS Only
- All API calls use HTTPS
- Supabase uses SSL/TLS
- Twitter API uses HTTPS

### Firewall Rules
If running on server:
- Allow outbound HTTPS (443)
- Allow outbound HTTP (80) - redirects to HTTPS
- Block all other outbound ports
- Block all inbound ports (bot is client-only)

## Incident Response

### If Credentials are Compromised

1. **Immediate Actions**
   - Revoke compromised keys immediately
   - Generate new keys
   - Update `.env` file
   - Restart bot

2. **Twitter API Keys Compromised**
   - Go to Twitter Developer Portal
   - Regenerate API keys and tokens
   - Update all deployments
   - Monitor bot account for unauthorized activity

3. **Supabase Keys Compromised**
   - Go to Supabase Dashboard
   - Generate new API keys
   - Update all deployments
   - Review database audit logs
   - Check for unauthorized data access

4. **Post-Incident**
   - Document what happened
   - Review how credentials leaked
   - Implement preventive measures
   - Notify users if data was accessed

### If Bot is Compromised

1. **Stop the bot immediately**
```bash
# Find process
ps aux | grep bot.py

# Kill process
kill -9 <PID>
```

2. **Revoke all API access**
3. **Review logs for malicious activity**
4. **Restore from known-good backup**
5. **Security audit before restarting**

## Security Checklist

### Before Deployment
- [ ] All credentials in `.env`, not hardcoded
- [ ] `.env` is in `.gitignore`
- [ ] No credentials in git history
- [ ] Input validation on all user inputs
- [ ] Error handling doesn't expose internals
- [ ] Logging doesn't contain sensitive data
- [ ] Rate limiting is enabled
- [ ] Database RLS is configured
- [ ] File permissions are correct
- [ ] Dependencies are up to date

### Regular Maintenance
- [ ] Review logs for suspicious activity (weekly)
- [ ] Update dependencies (monthly)
- [ ] Rotate API keys (quarterly)
- [ ] Review and update security policies (quarterly)
- [ ] Test backup restoration (quarterly)
- [ ] Security audit (annually)

## Reporting Security Issues

If you discover a security vulnerability:

1. **DO NOT** open a public GitHub issue
2. **DO NOT** disclose publicly
3. Email security contact privately
4. Include:
   - Description of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will:
- Acknowledge receipt within 48 hours
- Investigate and fix the issue
- Keep you informed of progress
- Credit you in release notes (if desired)

## Dependencies Security

### Keeping Dependencies Updated
```bash
# Check for outdated packages
pip list --outdated

# Update specific package
pip install --upgrade tweepy

# Update all packages (carefully!)
pip install --upgrade -r requirements.txt
```

### Security Scanning
```bash
# Install safety
pip install safety

# Scan for known vulnerabilities
safety check

# Or use pip-audit
pip install pip-audit
pip-audit
```

### Dependency Pinning
In `requirements.txt`:
```
tweepy==4.14.0      # Pin exact version
supabase>=2.0.0     # Allow patch updates
Pillow>=10.0.0      # Allow minor updates
```

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Twitter API Security Best Practices](https://developer.twitter.com/en/docs/authentication/guides/authentication-best-practices)
- [Supabase Security](https://supabase.com/docs/guides/auth/row-level-security)
- [Python Security Guidelines](https://python.readthedocs.io/en/stable/library/security_warnings.html)

## Contact

For security concerns, contact: [Add security contact email]
