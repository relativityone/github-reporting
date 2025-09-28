# Personal Access Token (PAT) Setup Guide

This guide helps you set up a Personal Access Token (PAT) for enhanced GitHub organization access.

## Why Use a PAT?

The default `GITHUB_TOKEN` provided by GitHub Actions has limited permissions and cannot:
- Access private repositories across the organization
- Read organization member details
- Access repositories you don't directly collaborate on

A Personal Access Token (PAT) with proper scopes provides full organizational access.

## Creating a Personal Access Token

### Step 1: Generate the PAT

1. Go to **GitHub Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. Click **"Generate new token (classic)"**
3. Set the following:
   - **Note**: `GitHub Reporting Tool - RelativityOne`
   - **Expiration**: Choose appropriate duration (90 days recommended)
   - **Scopes**: Select these required scopes:

#### Required Scopes:
- ✅ **`repo`** - Full control of private repositories
  - Includes: `repo:status`, `repo_deployment`, `public_repo`, `repo:invite`
- ✅ **`read:org`** - Read org and team membership, read org projects
- ✅ **`read:user`** - Read user profile data

#### Optional Scopes (for enhanced reporting):
- 🔄 **`user:email`** - Access user email addresses (if needed for reporting)
- 🔄 **`read:project`** - Read project data

### Step 2: Save the Token Securely

⚠️ **Important**: Copy the token immediately after generation - you won't be able to see it again!

## Setting Up the PAT in GitHub Actions

### Repository Secrets Configuration

1. Navigate to your repository: `https://github.com/relativityone/github-reporting`
2. Go to **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"**
4. Add the secret:
   - **Name**: `GITHUB_PAT`
   - **Value**: `[paste your PAT here]`
5. Click **"Add secret"**

### Organization Secrets (Alternative)

For organization-wide use:
1. Go to RelativityOne organization settings
2. Navigate to **Secrets and variables** → **Actions**
3. Add organization secret with same name: `GITHUB_PAT`

## Local Development Setup

For running the script locally:

```bash
# Set the PAT as an environment variable
export GITHUB_PAT="your_personal_access_token_here"

# Or add it to your shell profile (.bashrc, .zshrc, etc.)
echo 'export GITHUB_PAT="your_personal_access_token_here"' >> ~/.zshrc
```

## Security Best Practices

### ✅ Do:
- Set appropriate expiration dates (90 days recommended)
- Use minimal required scopes
- Regularly rotate tokens
- Use repository/organization secrets, not hardcode in files
- Monitor token usage in GitHub's audit logs

### ❌ Don't:
- Share tokens in chat, email, or documentation
- Commit tokens to version control
- Use tokens with broader scopes than needed
- Set overly long expiration periods

## Token Validation

The script automatically validates your token permissions and will show:
- Organization access status
- Member vs. external collaborator status  
- Available organizations
- Required scope recommendations

Example output:
```
🔍 Checking token permissions for organization: relativityone...
✅ Token belongs to user: your-username
✅ Organization access: relativityone
📊 Member status: Member
🔐 Admin access: No
```

## Troubleshooting

### "Resource not accessible by integration"
- Token doesn't have `repo` scope
- Token doesn't have `read:org` scope
- You're not a member of the organization
- Repository is private and token lacks access

### "Organization not found or not accessible"
- Organization name is incorrect
- Token doesn't have `read:org` scope
- You don't have access to the organization

### "Token validation failed"
- Token is expired or invalid
- Token has insufficient scopes
- Network connectivity issues

## Token Management

### Monitoring Usage
- Check GitHub's "Personal access tokens" page for last used dates
- Monitor organization audit logs for token activity
- Set up alerts for unusual token usage

### Rotation Schedule
- Rotate tokens every 90 days
- Update repository secrets when tokens are rotated
- Test the new token before removing the old one

### Revoking Access
If a token is compromised:
1. Immediately revoke it in GitHub settings
2. Generate a new token with the same scopes
3. Update the repository secret
4. Monitor audit logs for unauthorized usage

## Support

If you encounter issues:
1. Check the workflow logs for specific error messages
2. Validate token permissions using the script's built-in checks
3. Review GitHub's audit logs for permission issues
4. Contact the repository maintainers for assistance