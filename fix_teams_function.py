#!/usr/bin/env python3

# This script will fix the fetch_teams_for_repo function to use proper GitHub CLI authentication

import re

def fix_teams_function():
    # Read the current file
    with open('fetch_user_permissions_graphql.py', 'r') as f:
        content = f.read()
    
    # New function content
    new_function = '''    def fetch_teams_for_repo(self, repo_name: str, repo_full_name: str) -> List[Dict[str, Any]]:
        """Fetch teams with access to a specific repository using GitHub CLI with REL_TOKEN.
        
        This approach uses GitHub CLI but ensures it uses the correct PAT token.
        """
        # Ensure GitHub CLI uses the correct token
        token = os.getenv('REL_TOKEN') or os.getenv('GITHUB_PAT') or os.getenv('GITHUB_TOKEN')
        if not token:
            print(f"    ❌ No authentication token available for team queries")
            return []
        
        # Set the GH_TOKEN environment variable for GitHub CLI
        env = os.environ.copy()
        env['GH_TOKEN'] = token
        
        try:
            # Check if GitHub CLI is available
            version_result = subprocess.run(['gh', '--version'], capture_output=True, text=True, check=True, env=env)
            print(f"    🔧 GitHub CLI version: {version_result.stdout.strip().split()[2] if len(version_result.stdout.strip().split()) > 2 else 'unknown'}")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"    ⚠️  GitHub CLI (gh) not found or not authenticated: {e}")
            print(f"    💡 Install with: brew install gh && gh auth login")
            return []
        
        # Check GitHub CLI authentication status
        try:
            auth_result = subprocess.run(['gh', 'auth', 'status'], capture_output=True, text=True, timeout=10, env=env)
            if auth_result.returncode != 0:
                print(f"    🔐 GitHub CLI auth status: {auth_result.stderr.strip()}")
            else:
                print(f"    ✅ GitHub CLI authenticated")
            
            # Test if we can access organization teams via GitHub CLI with REL_TOKEN
            test_result = subprocess.run(['gh', 'api', f'/orgs/{self.organization}/teams', '--jq', 'length'], 
                                       capture_output=True, text=True, timeout=10, env=env)
            if test_result.returncode == 0:
                team_count = test_result.stdout.strip()
                print(f"    ✅ GitHub CLI can access organization teams (found {team_count} teams)")
            else:
                print(f"    ❌ GitHub CLI cannot access organization teams: {test_result.stderr.strip()}")
                print(f"    💡 This may indicate insufficient REL_TOKEN permissions for team access")
                
        except Exception as e:
            print(f"    ⚠️  Could not check auth status: {e}")
        
        print(f"    🔍 Querying teams via GitHub CLI for {repo_name}...")
        all_teams = []
        
        # Strategy 1: Try the direct repo teams endpoint
        try:
            cmd = [
                'gh', 'api',
                f'/repos/{repo_full_name}/teams',
                '--paginate',
                '--jq', '.[] | {id: .id, name: .name, slug: .slug, description: .description, privacy: .privacy, permission: .permission, url: .html_url}'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
            
            print(f"    🔧 Direct endpoint - Return code: {result.returncode}")
            if result.stderr:
                print(f"    🔧 Direct endpoint - STDERR: {result.stderr.strip()}")
            if result.stdout:
                print(f"    🔧 Direct endpoint - STDOUT length: {len(result.stdout)} chars")
            
            if result.returncode == 0 and result.stdout.strip():
                print(f"    ✅ Found teams via direct endpoint")
                all_teams.extend(self._parse_team_output(result.stdout))
            else:
                print(f"    📝 Direct endpoint returned no teams, trying organization approach...")
                
        except Exception as e:
            print(f"    ⚠️  Direct endpoint failed: {e}")
        
        # Strategy 2: Get all org teams and check which have access to this repo
        if not all_teams:
            try:
                # First, get all organization teams
                cmd_teams = [
                    'gh', 'api',
                    f'/orgs/{self.organization}/teams',
                    '--paginate',
                    '--jq', '.[] | {id: .id, name: .name, slug: .slug, description: .description, privacy: .privacy, url: .html_url}'
                ]
                
                print(f"    🔧 Getting organization teams via GitHub CLI...")
                teams_result = subprocess.run(cmd_teams, capture_output=True, text=True, timeout=60, env=env)
                
                print(f"    🔧 Org teams - Return code: {teams_result.returncode}")
                if teams_result.stderr:
                    print(f"    🔧 Org teams - STDERR: {teams_result.stderr.strip()}")
                
                if teams_result.returncode == 0 and teams_result.stdout.strip():
                    org_teams = []
                    for line in teams_result.stdout.strip().split('\\n'):
                        if line.strip():
                            try:
                                org_teams.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                    
                    print(f"    🔍 Checking {len(org_teams)} organization teams for repository access...")
                    
                    # Check each team's repositories to see if they have access to our repo
                    for i, team in enumerate(org_teams):
                        team_slug = team.get('slug', '')
                        if not team_slug:
                            continue
                        
                        if i % 20 == 0 and i > 0:  # Progress indicator
                            print(f"    📊 Progress: checked {i}/{len(org_teams)} teams, found {len(all_teams)} with access")
                            
                        try:
                            # Check if this team has access to the repository
                            cmd_check = [
                                'gh', 'api',
                                f'/orgs/{self.organization}/teams/{team_slug}/repos/{repo_full_name}',
                                '--jq', '.permissions // empty'
                            ]
                            
                            check_result = subprocess.run(cmd_check, capture_output=True, text=True, timeout=10, env=env)
                            
                            if check_result.returncode == 0 and check_result.stdout.strip():
                                # Team has access to this repository
                                try:
                                    permissions = json.loads(check_result.stdout.strip())
                                    
                                    # Determine the permission level
                                    permission_level = 'read'  # default
                                    if permissions.get('admin'):
                                        permission_level = 'admin'
                                    elif permissions.get('maintain'):
                                        permission_level = 'maintain'
                                    elif permissions.get('push'):
                                        permission_level = 'write'
                                    elif permissions.get('triage'):
                                        permission_level = 'triage'
                                    
                                    team_data = {
                                        'login': f"@{self.organization}/{team_slug}",
                                        'name': team.get('name', ''),
                                        'email': '',
                                        'avatar_url': '',
                                        'url': team.get('url', ''),
                                        'permission': permission_level,
                                        'type': 'Team',
                                        'id': str(team.get('id', '')),
                                        'company': '',
                                        'location': '',
                                        'team_slug': team_slug,
                                        'team_description': team.get('description', ''),
                                        'team_privacy': team.get('privacy', '')
                                    }
                                    all_teams.append(team_data)
                                    print(f"    ✅ Found team: {team_slug} ({permission_level})")
                                    
                                except json.JSONDecodeError:
                                    continue
                            elif check_result.returncode == 404:
                                # Team doesn't have access - this is normal, don't log
                                continue
                            elif check_result.returncode == 403:
                                # Access forbidden - might indicate token permission issues
                                if i < 5:  # Only log first few to avoid spam
                                    print(f"    🔒 Team permission check forbidden (403) for {team_slug}")
                                    print(f"    💡 REL_TOKEN may lack sufficient permissions")
                                continue
                            else:
                                # Other error
                                if "404" not in check_result.stderr:
                                    print(f"    🔧 Team {team_slug} check failed: RC={check_result.returncode}")
                                    
                        except subprocess.TimeoutExpired:
                            print(f"    ⏰ Timeout checking team {team_slug}")
                            continue
                        except Exception as e:
                            print(f"    ⚠️  Error checking team {team_slug}: {e}")
                            continue
                else:
                    print(f"    ❌ Failed to get organization teams: RC={teams_result.returncode}")
                    if teams_result.stderr:
                        print(f"    ❌ Error: {teams_result.stderr.strip()}")
                            
            except Exception as e:
                print(f"    ⚠️  Organization teams approach failed: {e}")
        
        if not all_teams:
            print(f"    📝 No team permissions found for {repo_name} after trying both strategies")
        else:
            print(f"    ✅ Found {len(all_teams)} team(s) with access to {repo_name}")
            
        return all_teams'''

    # Find the pattern for the function definition and replace everything until the next function
    pattern = r'(    def fetch_teams_for_repo\(self, repo_name: str, repo_full_name: str\) -> List\[Dict\[str, Any\]\]:.*?)(?=    def [^_]|class |^$|\Z)'
    
    # Replace with new function
    new_content = re.sub(pattern, new_function, content, flags=re.DOTALL)
    
    # Write back
    with open('fetch_user_permissions_graphql.py', 'w') as f:
        f.write(new_content)
    
    print("✅ Updated fetch_teams_for_repo function with proper GitHub CLI authentication")

if __name__ == '__main__':
    fix_teams_function()