# GitHub User Permissions Reporter

This repository contains a Python script and GitHub Actions pipeline for fetching and reporting on user permissions across repositories in a GitHub organization using the GraphQL API.

## Features

- **Efficient GraphQL API**: Uses GitHub's GraphQL API for faster data retrieval compared to REST API
- **Comprehensive Reports**: Generates detailed CSV reports with user permissions, summaries, and repository information
- **Automated Pipeline**: GitHub Actions workflow for scheduled and manual execution
- **Flexible Configuration**: Support for including/excluding archived repositories and custom organizations

## Files

- `fetch_user_permissions_graphql.py` - Main Python script that fetches user permissions
- `.github/workflows/fetch-user-permissions.yml` - GitHub Actions pipeline
- `requirements.txt` - Python dependencies

## Generated Reports

The script generates three CSV files:

1. **{organization}_user_permissions_graphql.csv** - Detailed user-to-repository permissions mapping
2. **{organization}_user_summary_graphql.csv** - Summary of each user's access across repositories
3. **{organization}_repository_summary_graphql.csv** - Summary of each repository with collaborator counts

## GitHub Actions Pipeline

### Triggers

The pipeline runs on:
- **Manual trigger** (`workflow_dispatch`) with optional parameters
- **Scheduled execution** (weekly on Mondays at 8 AM UTC)
- **Code changes** to the script or workflow file

### Manual Execution

To run the pipeline manually:

1. Go to the **Actions** tab in your GitHub repository
2. Select **"Fetch GitHub User Permissions"** workflow
3. Click **"Run workflow"**
4. Configure parameters:
   - **Organization**: GitHub organization name (default: "relativityone")
   - **Include archived**: Whether to include archived repositories (default: false)

### Required Permissions

The workflow uses the default `GITHUB_TOKEN` which needs:
- `contents: read` - To access repository content
- `actions: read` - To run the workflow

For organization-wide access, you may need to configure additional permissions or use a personal access token.

### Artifacts

Generated CSV files are automatically uploaded as workflow artifacts with:
- **Name**: `github-permissions-report-{run_number}`
- **Retention**: 30 days

## Local Development

### Prerequisites

- Python 3.9+
- GitHub token with appropriate permissions

### Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd github-reporting

# Install dependencies
pip install -r requirements.txt

# Set up GitHub token
export GITHUB_TOKEN=$(gh auth token)
# or
export GITHUB_TOKEN="your_github_token_here"
```

### Running Locally

```bash
python fetch_user_permissions_graphql.py
```

The script will:
1. Use the organization defined in the script (default: "relativityone")
2. Generate CSV files in the current directory
3. Display progress and summary statistics

### Configuration

Edit the script to modify:
- `organization` - Target GitHub organization
- `include_archived` - Whether to include archived repositories
- Output file names and paths

## Performance

- **GraphQL Efficiency**: ~50-200 queries vs 3000+ REST API calls
- **Rate Limiting**: Automatic handling of GitHub API rate limits
- **Processing Time**: Typically 10-30 minutes for large organizations
- **Memory Usage**: Optimized for large datasets

## Output Format

### User Permissions CSV
Contains detailed user-repository permission mappings with columns for user info, repository details, and access levels.

### User Summary CSV
Aggregated view showing each user's total repository access by permission level and repository characteristics.

### Repository Summary CSV
Repository-focused view showing collaborator counts and permission distribution per repository.

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Ensure `GITHUB_TOKEN` environment variable is set
   - Verify token has necessary scopes for the target organization

2. **Rate Limiting**
   - The script automatically handles rate limits with wait periods
   - GraphQL API has different limits than REST API

3. **Large Organizations**
   - Processing may take significant time for organizations with thousands of repositories
   - Monitor workflow logs for progress updates

4. **Permission Errors**
   - Ensure the token has access to the target organization
   - Some private repositories may not be accessible

### Monitoring

The workflow provides:
- Real-time progress logs
- Summary statistics upon completion
- Artifact upload confirmation
- Error reporting and debugging information

## Security Considerations

- Uses GitHub's built-in `GITHUB_TOKEN` (recommended)
- No hardcoded credentials in the code
- Artifacts are automatically cleaned up after 30 days
- Follows GitHub's API best practices for authentication and rate limiting