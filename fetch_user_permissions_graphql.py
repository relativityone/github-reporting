#!/usr/bin/env python3
"""
GraphQL-based script to fetch all users and their repository permissions from a GitHub organization.
Uses GitHub's GraphQL API for more efficient data retrieval compared to REST API.
Creates comprehensive CSV mapping users to repositories and their access levels.
"""

import requests
import json
import csv
import sys
import os
import time
from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, List, Any, Optional

class GitHubGraphQLPermissionsFetcher:
    def __init__(self, token: str, organization: str = "relativityone"):
        self.base_url = "https://api.github.com/graphql"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "RelativityOne-GraphQL-Permissions-Fetcher"
        }
        self.organization = organization
        self.rate_limit_remaining = None
        self.rate_limit_reset = None
        self.total_queries = 0
        self.start_time = datetime.now()
        
    def execute_graphql_query(self, query: str, variables: Dict[str, Any] = None, max_retries: int = 3) -> Dict[str, Any]:
        """Execute a GraphQL query with proper error handling, rate limiting, and retry logic."""
        payload = {
            "query": query,
            "variables": variables or {}
        }
        
        for attempt in range(max_retries + 1):
            try:
                self.wait_for_rate_limit()
                
                # Add timeout to prevent hanging requests
                response = requests.post(self.base_url, headers=self.headers, json=payload, timeout=60)
                self.total_queries += 1
                
                # Update rate limit info from response headers
                self.rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
                self.rate_limit_reset = int(response.headers.get('X-RateLimit-Reset', 0))
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'errors' in data:
                        # Handle different types of errors
                        forbidden_errors = [e for e in data['errors'] if e.get('type') == 'FORBIDDEN']
                        other_errors = [e for e in data['errors'] if e.get('type') != 'FORBIDDEN']
                        
                        if forbidden_errors:
                            print(f"⚠️  Access denied for {len(forbidden_errors)} repositories (insufficient permissions)")
                            print("   This is normal for private repositories your token cannot access")
                        
                        if other_errors:
                            print(f"❌ GraphQL errors: {other_errors}")
                            
                        # Only return empty if we have no data and non-forbidden errors
                        if 'data' not in data and other_errors:
                            return {}
                            
                    return data.get('data', {})
                
                # Handle server errors with retry
                elif response.status_code in [502, 503, 504, 520, 521, 522, 524]:
                    if attempt < max_retries:
                        wait_time = (2 ** attempt) + 1  # Exponential backoff: 2, 5, 9 seconds
                        print(f"⚠️  Server error {response.status_code}, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries + 1})")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"❌ GraphQL request failed after {max_retries + 1} attempts with status {response.status_code}")
                        print(f"Response: {response.text[:500]}..." if len(response.text) > 500 else f"Response: {response.text}")
                        return {}
                
                # Handle other HTTP errors
                else:
                    print(f"❌ GraphQL request failed with status {response.status_code}")
                    print(f"Response: {response.text[:500]}..." if len(response.text) > 500 else f"Response: {response.text}")
                    return {}
                    
            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    wait_time = (2 ** attempt) + 1
                    print(f"⏰ Request timeout, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries + 1})")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"❌ Request timed out after {max_retries + 1} attempts")
                    return {}
                    
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries:
                    wait_time = (2 ** attempt) + 1
                    print(f"🔌 Connection error, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries + 1})")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"❌ Connection failed after {max_retries + 1} attempts: {e}")
                    return {}
                    
            except Exception as e:
                print(f"❌ Unexpected error during GraphQL request: {e}")
                return {}
                
        return {}
    
    def test_api_connection(self) -> bool:
        """Test basic API connectivity and authentication before starting main process."""
        query = """
        query {
            viewer {
                login
                id
            }
            rateLimit {
                limit
                remaining
                resetAt
            }
        }
        """
        
        print("🔗 Testing GitHub API connection and authentication...")
        try:
            data = self.execute_graphql_query(query, max_retries=2)
            
            if not data or 'viewer' not in data:
                print("❌ API connection test failed")
                return False
                
            viewer = data['viewer']
            rate_limit = data.get('rateLimit', {})
            
            print(f"✅ API connection successful")
            print(f"👤 Authenticated as: {viewer.get('login', 'unknown')}")
            print(f"🔄 Rate limit: {rate_limit.get('remaining', 'unknown')}/{rate_limit.get('limit', 'unknown')}")
            
            return True
            
        except Exception as e:
            print(f"❌ API connection test failed: {e}")
            return False

    def check_token_permissions(self) -> bool:
        """Check if the token has the necessary permissions for the organization."""
        query = """
        query($org: String!) {
            organization(login: $org) {
                login
                viewerCanAdminister
                viewerIsAMember
                membersWithRole(first: 1) {
                    totalCount
                }
            }
            viewer {
                login
                organizations(first: 100) {
                    nodes {
                        login
                    }
                }
            }
        }
        """
        
        print(f"🔍 Checking token permissions for organization: {self.organization}...")
        data = self.execute_graphql_query(query, {"org": self.organization})
        
        if not data or 'viewer' not in data:
            print("❌ Failed to validate token permissions")
            return False
            
        viewer = data['viewer']
        org_data = data.get('organization')
        
        print(f"✅ Token belongs to user: {viewer.get('login', 'unknown')}")
        
        if not org_data:
            print(f"❌ Organization '{self.organization}' not found or not accessible")
            user_orgs = [org['login'] for org in viewer.get('organizations', {}).get('nodes', [])]
            if user_orgs:
                print(f"💡 Available organizations: {', '.join(user_orgs[:10])}")
            return False
            
        print(f"✅ Organization access: {self.organization}")
        print(f"📊 Member status: {'Member' if org_data.get('viewerIsAMember') else 'External'}")
        print(f"🔐 Admin access: {'Yes' if org_data.get('viewerCanAdminister') else 'No'}")
        
        if not org_data.get('viewerIsAMember'):
            print("⚠️  Warning: You are not a member of this organization")
            print("   Some private repositories may not be accessible")
            
        return True
    
    def check_rate_limit(self) -> bool:
        """Check current GraphQL rate limit status."""
        query = """
        query {
            rateLimit {
                limit
                remaining
                resetAt
                used
            }
        }
        """
        
        print("🔍 Checking GraphQL rate limit status...")
        data = self.execute_graphql_query(query)
        
        if 'rateLimit' in data:
            rate_limit = data['rateLimit']
            self.rate_limit_remaining = rate_limit['remaining']
            reset_at = datetime.fromisoformat(rate_limit['resetAt'].replace('Z', '+00:00'))
            
            print(f"✅ GraphQL Rate limit: {rate_limit['remaining']}/{rate_limit['limit']} remaining")
            print(f"📅 Resets at: {reset_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"🔄 Used: {rate_limit['used']} queries")
            return True
        return False
    
    def wait_for_rate_limit(self):
        """Wait if we're approaching GraphQL rate limit."""
        if self.rate_limit_remaining and self.rate_limit_remaining < 100:
            reset_time = datetime.fromtimestamp(self.rate_limit_reset)
            current_time = datetime.now()
            wait_seconds = max(0, (reset_time - current_time).total_seconds() + 10)
            
            print(f"⏳ GraphQL rate limit low ({self.rate_limit_remaining} remaining)")
            print(f"Waiting {wait_seconds:.0f} seconds until {reset_time}")
            
            # Show countdown
            while wait_seconds > 0:
                mins, secs = divmod(int(wait_seconds), 60)
                print(f"⏲️  Waiting: {mins:02d}:{secs:02d} remaining...", end='\r')
                time.sleep(1)
                wait_seconds -= 1
            print()
            
            # Re-check rate limit after waiting
            self.check_rate_limit()
    
    def fetch_all_collaborators_for_repo(self, repo_name: str, repo_full_name: str) -> List[Dict[str, Any]]:
        """Fetch all collaborators for a specific repository with pagination."""
        all_collaborators = []
        has_next_page = True
        after_cursor = None
        page_num = 1
        
        while has_next_page:
            query = """
            query($repo_owner: String!, $repo_name: String!, $first: Int!, $after: String) {
                repository(owner: $repo_owner, name: $repo_name) {
                    collaborators(first: $first, after: $after, affiliation: DIRECT) {
                        totalCount
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                        nodes {
                            login
                            name
                            avatarUrl
                            url
                            __typename
                            ... on User {
                                id
                                company
                                location
                            }
                        }
                        edges {
                            permission
                            node {
                                login
                                __typename
                            }
                        }
                    }
                }
            }
            """
            
            # Split the repo full name into owner and name
            repo_owner = repo_full_name.split('/')[0] if '/' in repo_full_name else self.organization
            
            variables = {
                "repo_owner": repo_owner,
                "repo_name": repo_name,
                "first": 100,
                "after": after_cursor
            }
            
            if page_num > 1:
                print(f"    📄 Fetching collaborators page {page_num} for {repo_name}...")
            
            data = self.execute_graphql_query(query, variables)
            
            if not data or 'repository' not in data or not data['repository']:
                print(f"    ⚠️  Failed to fetch collaborators for {repo_name}")
                break
                
            collaborators_data = data['repository'].get('collaborators', {})
            if not collaborators_data:
                break
                
            # Map collaborator nodes to edges (which contain permissions)
            collaborator_map = {}
            edges = collaborators_data.get('edges', [])
            for edge in edges:
                if edge and edge.get('node') and edge['node'].get('login'):
                    login = edge['node']['login']
                    permission = edge.get('permission', 'unknown')
                    collaborator_map[login] = permission

            # Process collaborator details
            nodes = collaborators_data.get('nodes', [])
            for collaborator in nodes:
                if not collaborator:
                    continue
                    
                login = collaborator.get('login')
                if not login:
                    continue
                    
                permission = collaborator_map.get(login, 'unknown')
                
                collaborator_data = {
                    'login': login,
                    'name': collaborator.get('name', ''),
                    'email': '',  # Email not accessible with current token scopes
                    'avatar_url': collaborator.get('avatarUrl', ''),
                    'url': collaborator.get('url', ''),
                    'permission': permission,
                    'type': collaborator.get('__typename', 'User'),
                    'id': collaborator.get('id', ''),
                    'company': collaborator.get('company', ''),
                    'location': collaborator.get('location', '')
                }
                all_collaborators.append(collaborator_data)
            
            # Check pagination
            page_info = collaborators_data.get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            after_cursor = page_info.get('endCursor')
            page_num += 1
            
            # Add small delay between pages
            if has_next_page:
                time.sleep(0.5)
        
        total_found = len(all_collaborators)
        expected_total = collaborators_data.get('totalCount', total_found) if 'collaborators_data' in locals() else total_found
        
        if total_found != expected_total:
            print(f"    ⚠️  {repo_name}: Retrieved {total_found}/{expected_total} collaborators")
        elif page_num > 2:  # More than 1 page
            print(f"    ✅ {repo_name}: Retrieved all {total_found} collaborators ({page_num-1} pages)")
            
        return all_collaborators

    def fetch_teams_for_repo(self, repo_name: str, repo_full_name: str) -> List[Dict[str, Any]]:
        """Fetch teams with access to a specific repository.
        
        Note: GitHub's GraphQL API doesn't provide a direct way to query team permissions
        for a specific repository. This function attempts to find teams but may not capture
        all team permissions accurately.
        """
        try:
            # Get organization teams that might have access to repositories
            query = """
            query($org: String!) {
                organization(login: $org) {
                    teams(first: 100) {
                        totalCount
                        nodes {
                            id
                            name
                            slug
                            description
                            privacy
                            url
                            repositories(first: 100) {
                                totalCount
                                nodes {
                                    nameWithOwner
                                }
                            }
                        }
                    }
                }
            }
            """
            
            # Split the repo full name into owner and name
            repo_owner = repo_full_name.split('/')[0] if '/' in repo_full_name else self.organization
            
            variables = {"org": repo_owner}
            
            data = self.execute_graphql_query(query, variables)
            
            if not data or 'organization' not in data or not data['organization']:
                return []
                
            org_data = data['organization']
            teams_info = org_data.get('teams', {})
            if not teams_info:
                return []
            
            all_teams = []
            target_repo_full_name = repo_full_name
            
            # Process teams and check if they have access to this specific repository
            nodes = teams_info.get('nodes', [])
            for team in nodes:
                if not team:
                    continue
                    
                slug = team.get('slug')
                if not slug:
                    continue
                
                # Check if this team has access to the specific repository
                team_repos = team.get('repositories', {})
                repo_nodes = team_repos.get('nodes', [])
                
                # Find if our target repository is in the team's accessible repositories
                team_has_access = False
                
                for repo_node in repo_nodes:
                    if repo_node and repo_node.get('nameWithOwner') == target_repo_full_name:
                        team_has_access = True
                        break
                
                if team_has_access:
                    team_data = {
                        'login': f"@{repo_owner}/{slug}",
                        'name': team.get('name', ''),
                        'email': '',
                        'avatar_url': '',
                        'url': team.get('url', ''),
                        'permission': 'team',  # Generic team permission - exact level not available via GraphQL
                        'type': 'Team',
                        'id': team.get('id', ''),
                        'company': '',
                        'location': '',
                        'team_slug': slug,
                        'team_description': team.get('description', ''),
                        'team_privacy': team.get('privacy', '')
                    }
                    all_teams.append(team_data)
            
            return all_teams
            
        except Exception as e:
            print(f"    ⚠️  Warning: Could not fetch team information: {e}")
            print(f"    📝 Note: GitHub's GraphQL API has limitations for team permission queries")
            return []

    def fetch_repositories_with_collaborators(self, include_archived: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch all repositories with their collaborators using GraphQL.
        This is much more efficient than the REST API approach.
        """
        all_repos_data = []
        has_next_page = True
        after_cursor = None
        page_num = 1
        
        print(f"🚀 Fetching repositories with collaborators for organization: {self.organization}")
        print(f"🎯 Include archived repositories: {include_archived}")
        print("=" * 80)
        
        self.check_rate_limit()
        
        while has_next_page:
            print(f"\n📄 Fetching page {page_num} of repositories...")
            
            # Simplified GraphQL query to get repositories without collaborators first
            query = """
            query($org: String!, $first: Int!, $after: String) {
                organization(login: $org) {
                    repositories(first: $first, after: $after, orderBy: {field: UPDATED_AT, direction: DESC}) {
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                        totalCount
                        nodes {
                            name
                            nameWithOwner
                            isPrivate
                            isArchived
                            isFork
                            isDisabled
                            updatedAt
                            createdAt
                        }
                    }
                }
            }
            """
            
            variables = {
                "org": self.organization,
                "first": 25,  # Reduced from 50 to 25 to avoid large query timeouts
                "after": after_cursor
            }
            
            print(f"🔄 Executing GraphQL query (attempt may include retries)...")
            data = self.execute_graphql_query(query, variables)
            
            if not data:
                print(f"⚠️  No data returned for page {page_num}, this might be due to server errors.")
                if page_num == 1:
                    print("❌ Failed to fetch any repository data - stopping")
                    break
                else:
                    print("⚠️  Continuing with partial data from previous pages")
                    break
            
            if 'organization' not in data:
                print("❌ No organization data in response")
                if page_num == 1:
                    print("❌ Failed to access organization - stopping")
                    break
                else:
                    print("⚠️  Continuing with partial data from previous pages")
                    break
                
            org_data = data['organization']
            if not org_data or 'repositories' not in org_data:
                print("❌ No repository data found")
                break
                
            repos = org_data['repositories']
            page_info = repos['pageInfo']
            repo_nodes = repos['nodes']
            
            print(f"✅ Found {len(repo_nodes)} repositories on page {page_num}")
            print(f"📊 Total repositories in org: {repos['totalCount']:,}")
            
            # Process each repository
            processed_repos = 0
            skipped_repos = 0
            for repo in repo_nodes:
                # Skip if repo data is incomplete (access denied)
                if not repo or not repo.get('name'):
                    skipped_repos += 1
                    continue
                    
                # Filter archived repositories if not including them
                if not include_archived and repo.get('isArchived', False):
                    continue
                    
                repo_data = {
                    'name': repo['name'],
                    'full_name': repo['nameWithOwner'],
                    'is_private': repo['isPrivate'],
                    'is_archived': repo['isArchived'],
                    'is_fork': repo['isFork'],
                    'is_disabled': repo['isDisabled'],
                    'updated_at': repo['updatedAt'],
                    'created_at': repo['createdAt'],
                    'collaborators': []
                }
                
                # Fetch direct collaborators for this repository
                print(f"  � Fetching direct collaborators for {repo['name']}...")
                collaborators = []
                try:
                    collaborators = self.fetch_all_collaborators_for_repo(repo['name'], repo['nameWithOwner'])
                    if collaborators:
                        print(f"    ✅ Found {len(collaborators)} direct collaborators")
                    else:
                        print(f"    👤 No direct collaborators found")
                except Exception as e:
                    print(f"    ❌ Failed to fetch collaborators: {e}")
                
                # Fetch teams with access to this repository
                print(f"  👥 Fetching teams for {repo['name']}...")
                teams = []
                try:
                    teams = self.fetch_teams_for_repo(repo['name'], repo['nameWithOwner'])
                    if teams:
                        print(f"    ✅ Found {len(teams)} teams with access")
                    else:
                        print(f"    👥 No teams found with access")
                except Exception as e:
                    print(f"    ❌ Failed to fetch teams: {e}")
                
                # Combine collaborators and teams
                repo_data['collaborators'] = collaborators + teams
                total_access = len(collaborators) + len(teams)
                
                if total_access > 0:
                    print(f"    📋 Total access entries: {total_access} ({len(collaborators)} users + {len(teams)} teams)")
                else:
                    print(f"    ⚠️  No direct access found (may be access restricted or owner-only)")
                
                all_repos_data.append(repo_data)
                processed_repos += 1
                
            if skipped_repos > 0:
                print(f"⚠️  Skipped {skipped_repos} repositories due to access restrictions")
            print(f"📈 Progress: Processed {len(all_repos_data)} repositories so far")
            print(f"🔄 GraphQL queries made: {self.total_queries}")
            print(f"📊 Rate limit remaining: {self.rate_limit_remaining}")
            
            # Update pagination
            has_next_page = page_info['hasNextPage']
            after_cursor = page_info['endCursor']
            page_num += 1
            
            # Small delay between pages to avoid overwhelming the API
            if has_next_page:
                print(f"⏳ Pausing 2 seconds before next page to ensure API stability...")
                time.sleep(2)
        
        if not all_repos_data:
            print("\n❌ No repository data was successfully fetched!")
            print("💡 This might be due to:")
            print("   • Network connectivity issues")
            print("   • GitHub API server problems (502/503/504 errors)")
            print("   • Insufficient token permissions")
            print("   • Organization access restrictions")
            return []
        
        elapsed_time = datetime.now() - self.start_time
        print(f"\n🎉 REPOSITORY FETCH COMPLETE!")
        print(f"⏱️  Total fetch time: {elapsed_time}")
        
        # Calculate comprehensive statistics
        total_access_entries = sum(len(repo['collaborators']) for repo in all_repos_data)
        total_users = sum(len([c for c in repo['collaborators'] if c['type'] != 'Team']) for repo in all_repos_data)
        total_teams = sum(len([c for c in repo['collaborators'] if c['type'] == 'Team']) for repo in all_repos_data)
        repos_with_access = sum(1 for repo in all_repos_data if repo['collaborators'])
        repos_without_access = len(all_repos_data) - repos_with_access
        
        print(f"📊 Final statistics (DIRECT access only):")
        print(f"   • Repositories processed: {len(all_repos_data):,}")
        print(f"   • Repositories with direct access: {repos_with_access:,}")
        print(f"   • Repositories without direct access: {repos_without_access:,}")
        print(f"   • Total direct access entries: {total_access_entries:,}")
        print(f"   • Direct user collaborators: {total_users:,}")
        print(f"   • Team collaborators: {total_teams:,}")
        print(f"   • Total GraphQL queries: {self.total_queries:,}")
        print(f"   • Average access entries per repo: {total_access_entries/max(len(all_repos_data),1):.1f}")
        print(f"   • Average processing time per repo: {elapsed_time.total_seconds()/max(len(all_repos_data),1):.2f}s")
        
        if repos_without_access > 0:
            print(f"\n⚠️  {repos_without_access} repositories have no direct access data")
            print("   This may be due to:")
            print("   • Owner-only repositories (no additional collaborators)")
            print("   • Private repositories you cannot access")
            print("   • Repositories with only inherited organization permissions")
            print("   • API permission restrictions")
        
        print(f"\n📝 Note: This report shows DIRECT collaborators and teams only")
        print(f"   • Excludes organization-wide inherited permissions")
        print(f"   • Shows explicit repository-level access grants")
        print(f"   • Teams are included as separate entries with @org/team format")
        print(f"   • Team permissions may be incomplete due to GitHub GraphQL API limitations")
        print(f"   • For complete team audit, consider using GitHub's web interface or REST API")
        
        return all_repos_data
    
    def process_repositories_to_permissions(self, repos_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert repository data with collaborators to flat permission records."""
        print(f"\n🔄 Converting {len(repos_data)} repositories to permission records...")
        
        user_repo_permissions = []
        total_collaborators = 0
        unique_users = set()
        
        for repo in repos_data:
            repo_name = repo['name']
            repo_full_name = repo['full_name']
            
            for collaborator in repo['collaborators']:
                username = collaborator['login']
                user_type = collaborator['type']
                permission = collaborator['permission']
                
                # Create permission record
                permission_record = {
                    'username': username,
                    'user_name': collaborator['name'],
                    'user_email': collaborator['email'],
                    'user_type': user_type,
                    'user_company': collaborator['company'],
                    'user_location': collaborator['location'],
                    'repo_name': repo_name,
                    'repo_full_name': repo_full_name,
                    'permission': permission.lower() if permission else 'unknown',
                    'is_private_repo': repo['is_private'],
                    'is_archived_repo': repo['is_archived'],
                    'is_fork_repo': repo['is_fork'],
                    'is_disabled_repo': repo['is_disabled'],
                    'repo_updated_at': repo['updated_at'],
                    'repo_created_at': repo['created_at'],
                    'data_source': 'graphql'
                }
                
                user_repo_permissions.append(permission_record)
                unique_users.add(username)
                total_collaborators += 1
        
        print(f"✅ Conversion complete:")
        print(f"   • Permission records: {len(user_repo_permissions):,}")
        print(f"   • Unique users: {len(unique_users):,}")
        print(f"   • Total collaborator instances: {total_collaborators:,}")
        
        return user_repo_permissions
    
    def create_user_permissions_csv(self, permissions_data: List[Dict[str, Any]], output_file: str):
        """Create CSV file with user permissions."""
        print(f"\n📝 Creating detailed permissions file: {output_file}")
        
        fieldnames = [
            'username', 'user_name', 'user_email', 'user_type', 'user_company', 'user_location',
            'repo_name', 'repo_full_name', 'permission', 
            'is_private_repo', 'is_archived_repo', 'is_fork_repo', 'is_disabled_repo',
            'repo_updated_at', 'repo_created_at', 'data_source'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Sort by username, then by repo name
            sorted_data = sorted(permissions_data, 
                               key=lambda x: (x['username'].lower(), x['repo_name'].lower()))
            
            for row in sorted_data:
                writer.writerow(row)
        
        print(f"✅ Created detailed permissions file: {output_file}")
    
    def create_user_summary_csv(self, permissions_data: List[Dict[str, Any]], output_file: str):
        """Create a summary CSV showing each user's total repository access."""
        print(f"\n📝 Creating user summary file: {output_file}")
        
        # Group by user
        user_summary = {}
        
        for perm in permissions_data:
            username = perm['username']
            if username not in user_summary:
                user_summary[username] = {
                    'username': username,
                    'user_name': perm['user_name'],
                    'user_email': perm['user_email'],
                    'user_type': perm['user_type'],
                    'user_company': perm['user_company'],
                    'user_location': perm['user_location'],
                    'total_repos': 0,
                    'admin_repos': 0,
                    'maintain_repos': 0,
                    'write_repos': 0,
                    'triage_repos': 0,
                    'read_repos': 0,
                    'private_repos': 0,
                    'public_repos': 0,
                    'archived_repos': 0,
                    'fork_repos': 0,
                    'original_repos': 0,
                    'disabled_repos': 0,
                    'data_source': 'graphql'
                }
            
            user_data = user_summary[username]
            user_data['total_repos'] += 1
            
            # Count by permission level
            perm_level = perm['permission']
            if perm_level == 'admin':
                user_data['admin_repos'] += 1
            elif perm_level == 'maintain':
                user_data['maintain_repos'] += 1
            elif perm_level in ['write', 'push']:
                user_data['write_repos'] += 1
            elif perm_level == 'triage':
                user_data['triage_repos'] += 1
            elif perm_level in ['read', 'pull']:
                user_data['read_repos'] += 1
            
            # Count by repo characteristics
            if perm['is_private_repo']:
                user_data['private_repos'] += 1
            else:
                user_data['public_repos'] += 1
                
            if perm['is_archived_repo']:
                user_data['archived_repos'] += 1
                
            if perm['is_fork_repo']:
                user_data['fork_repos'] += 1
            else:
                user_data['original_repos'] += 1
                
            if perm['is_disabled_repo']:
                user_data['disabled_repos'] += 1
        
        # Write summary CSV
        fieldnames = [
            'username', 'user_name', 'user_email', 'user_type', 'user_company', 'user_location',
            'total_repos', 'admin_repos', 'maintain_repos', 'write_repos', 'triage_repos', 'read_repos',
            'private_repos', 'public_repos', 'archived_repos', 'fork_repos', 'original_repos', 
            'disabled_repos', 'data_source'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Sort by total repos descending, then by username
            sorted_users = sorted(user_summary.values(), 
                                key=lambda x: (-x['total_repos'], x['username'].lower()))
            
            for user in sorted_users:
                writer.writerow(user)
        
        print(f"✅ Created user summary file: {output_file}")
        print(f"📊 Summary contains {len(user_summary)} unique users")
    
    def create_repository_summary_csv(self, repos_data: List[Dict[str, Any]], output_file: str):
        """Create a summary CSV of repositories with their collaborator counts."""
        print(f"\n📝 Creating repository summary file: {output_file}")
        
        repo_summary = []
        
        for repo in repos_data:
            # Count permissions by type
            permission_counts = {}
            for collaborator in repo['collaborators']:
                permission = collaborator['permission'].lower() if collaborator['permission'] else 'unknown'
                permission_counts[permission] = permission_counts.get(permission, 0) + 1
            
            repo_data = {
                'repo_name': repo['name'],
                'repo_full_name': repo['full_name'],
                'is_private': repo['is_private'],
                'is_archived': repo['is_archived'],
                'is_fork': repo['is_fork'],
                'is_disabled': repo['is_disabled'],
                'total_collaborators': len(repo['collaborators']),
                'admin_users': permission_counts.get('admin', 0),
                'maintain_users': permission_counts.get('maintain', 0),
                'write_users': permission_counts.get('write', 0),
                'triage_users': permission_counts.get('triage', 0),
                'read_users': permission_counts.get('read', 0),
                'updated_at': repo['updated_at'],
                'created_at': repo['created_at']
            }
            
            repo_summary.append(repo_data)
        
        fieldnames = [
            'repo_name', 'repo_full_name', 'is_private', 'is_archived', 'is_fork', 'is_disabled',
            'total_collaborators', 'admin_users', 'maintain_users', 'write_users', 
            'triage_users', 'read_users', 'updated_at', 'created_at'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Sort by total collaborators descending
            sorted_repos = sorted(repo_summary, 
                                key=lambda x: (-x['total_collaborators'], x['repo_name'].lower()))
            
            for repo in sorted_repos:
                writer.writerow(repo)
        
        print(f"✅ Created repository summary file: {output_file}")
    
    def print_summary(self, permissions_data: List[Dict[str, Any]], repos_data: List[Dict[str, Any]]):
        """Print a comprehensive summary of the permissions data."""
        total_permissions = len(permissions_data)
        unique_users = len(set(p['username'] for p in permissions_data))
        unique_repos = len(repos_data)
        
        # Count by permission level and user type
        permission_counts = {}
        user_types = {}
        team_count = 0
        user_count = 0
        
        for perm in permissions_data:
            perm_level = perm['permission']
            permission_counts[perm_level] = permission_counts.get(perm_level, 0) + 1
            
            user_type = perm['user_type']
            user_types[user_type] = user_types.get(user_type, 0) + 1
            
            if user_type == 'Team':
                team_count += 1
            else:
                user_count += 1
        
        # Count repository characteristics
        repo_characteristics = {
            'private': 0, 'public': 0, 'archived': 0, 'active': 0, 
            'fork': 0, 'original': 0, 'disabled': 0, 'enabled': 0
        }
        
        for repo in repos_data:
            if repo['is_private']:
                repo_characteristics['private'] += 1
            else:
                repo_characteristics['public'] += 1
                
            if repo['is_archived']:
                repo_characteristics['archived'] += 1
            else:
                repo_characteristics['active'] += 1
                
            if repo['is_fork']:
                repo_characteristics['fork'] += 1
            else:
                repo_characteristics['original'] += 1
                
            if repo['is_disabled']:
                repo_characteristics['disabled'] += 1
            else:
                repo_characteristics['enabled'] += 1
        
        elapsed_time = datetime.now() - self.start_time
        
        print("\n" + "="*80)
        print("🎉 GRAPHQL USER PERMISSIONS SUMMARY")
        print("="*80)
        print(f"⏱️  Total processing time: {elapsed_time}")
        print(f"🔄 Total GraphQL queries: {self.total_queries:,}")
        print(f"📊 Processing efficiency: {total_permissions/max(self.total_queries,1):.1f} records per query")
        
        print(f"\n📈 DATA SUMMARY (DIRECT ACCESS ONLY):")
        print(f"   • Total access records: {total_permissions:,}")
        print(f"   • Unique users: {user_count:,}")
        print(f"   • Team entries: {team_count:,}")
        print(f"   • Repositories processed: {unique_repos:,}")
        print(f"   • Average access entries per repo: {total_permissions/max(unique_repos,1):.1f}")
        
        print(f"\n🔐 Permission Levels:")
        for perm, count in sorted(permission_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"   • {perm}: {count:,}")
        
        print(f"\n👤 User Types:")
        for user_type, count in sorted(user_types.items(), key=lambda x: x[1], reverse=True):
            print(f"   • {user_type}: {count:,}")
        
        print(f"\n📦 Repository Characteristics:")
        print(f"   • Private: {repo_characteristics['private']:,} | Public: {repo_characteristics['public']:,}")
        print(f"   • Active: {repo_characteristics['active']:,} | Archived: {repo_characteristics['archived']:,}")
        print(f"   • Original: {repo_characteristics['original']:,} | Forks: {repo_characteristics['fork']:,}")
        print(f"   • Enabled: {repo_characteristics['enabled']:,} | Disabled: {repo_characteristics['disabled']:,}")
        
        # Add data completeness assessment
        repos_with_data = sum(1 for repo in repos_data if repo['collaborators'])
        repos_without_data = len(repos_data) - repos_with_data
        completeness_percentage = (repos_with_data / max(len(repos_data), 1)) * 100
        
        print(f"\n📈 Data Completeness Assessment:")
        print(f"   • Repositories with collaborator data: {repos_with_data:,} ({completeness_percentage:.1f}%)")
        print(f"   • Repositories without collaborator data: {repos_without_data:,} ({100-completeness_percentage:.1f}%)")
        
        if completeness_percentage < 90:
            print(f"\n⚠️  Data completeness is {completeness_percentage:.1f}% - some repositories may be inaccessible")
            print("💡 To improve completeness:")
            print("   • Ensure your token has 'repo' scope for private repositories")
            print("   • Check if you're a member of the organization")
            print("   • Some repositories may genuinely have no collaborators")
        else:
            print(f"\n✅ Good data completeness: {completeness_percentage:.1f}%")
        
        # Add data completeness assessment
        repos_with_data = sum(1 for repo in repos_data if repo['collaborators'])
        repos_without_data = len(repos_data) - repos_with_data
        completeness_percentage = (repos_with_data / max(len(repos_data), 1)) * 100
        
        print(f"\n📈 Data Completeness Assessment:")
        print(f"   • Repositories with collaborator data: {repos_with_data:,} ({completeness_percentage:.1f}%)")
        print(f"   • Repositories without collaborator data: {repos_without_data:,} ({100-completeness_percentage:.1f}%)")
        
        if completeness_percentage < 90:
            print(f"\n⚠️  Data completeness is {completeness_percentage:.1f}% - some repositories may be inaccessible")
            print("💡 To improve completeness:")
            print("   • Ensure your token has 'repo' scope for private repositories")
            print("   • Check if you're a member of the organization")
            print("   • Some repositories may genuinely have no collaborators")
        else:
            print(f"\n✅ Good data completeness: {completeness_percentage:.1f}%")


def main():
    print("🚀 GITHUB DIRECT ACCESS PERMISSIONS FETCHER")
    print("=" * 80)
    print("🎯 This script fetches DIRECT collaborators and teams only (no inherited permissions)")
    print("🔍 Uses GitHub's GraphQL API for efficient data retrieval")
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Configuration
    organization = "relativityone"  # Change this to your organization
    include_archived = False  # Set to True to include archived repositories
    
    # Output files
    permissions_output = f"{organization}_direct_permissions_graphql.csv"
    summary_output = f"{organization}_direct_summary_graphql.csv"
    repo_summary_output = f"{organization}_repository_summary_graphql.csv"
    
    # Check for GitHub token (prefer PAT over default GITHUB_TOKEN)
    github_token = os.getenv('GITHUB_PAT') or os.getenv('GITHUB_TOKEN')
    if not github_token:
        print("❌ Error: GitHub token is required.")
        print("💡 For organization access, please set a Personal Access Token:")
        print("   export GITHUB_PAT='your_personal_access_token'")
        print("💡 Alternatively, use the default token: export GITHUB_TOKEN=$(gh auth token)")
        print("")
        print("🔐 Required PAT scopes: 'repo', 'read:org', 'read:user'")
        sys.exit(1)
    else:
        token_type = "PAT" if os.getenv('GITHUB_PAT') else "default token"
        print(f"✅ GitHub {token_type} found and loaded")
    
    print(f"🏢 Target organization: {organization}")
    print(f"📦 Include archived repositories: {include_archived}")
    
    # Initialize fetcher
    fetcher = GitHubGraphQLPermissionsFetcher(github_token, organization)
    
    # Test API connection first
    if not fetcher.test_api_connection():
        print("❌ Cannot establish connection to GitHub API")
        print("💡 Please check your internet connection and try again")
        sys.exit(1)
    
    # Check token permissions
    if not fetcher.check_token_permissions():
        print("❌ Token validation failed. Please check your permissions.")
        print("💡 Required permissions: 'repo', 'read:org' scopes")
        sys.exit(1)
    
    print(f"\n⚠️  ESTIMATED TIME: 10-30 minutes (much faster than REST API)")
    print(f"🚀 GraphQL queries needed: ~50-200 queries vs 3000+ REST API calls")
    
    try:
        # Fetch repositories with collaborators
        print(f"\n🎬 Starting GraphQL data collection for '{organization}'...")
        repos_data = fetcher.fetch_repositories_with_collaborators(include_archived)
        
        if not repos_data:
            print("❌ No repository data found!")
            sys.exit(1)
        
        # Convert to permission records
        permissions_data = fetcher.process_repositories_to_permissions(repos_data)
        
        if not permissions_data:
            print("❌ No permissions data found!")
            sys.exit(1)
        
        print(f"\n✅ Collected {len(permissions_data)} permission records")
        
        # Create output files
        fetcher.create_user_permissions_csv(permissions_data, permissions_output)
        fetcher.create_user_summary_csv(permissions_data, summary_output)
        fetcher.create_repository_summary_csv(repos_data, repo_summary_output)
        
        # Print final summary
        fetcher.print_summary(permissions_data, repos_data)
        
        print(f"\n🎉 DIRECT ACCESS PERMISSIONS ANALYSIS COMPLETE!")
        print(f"⏱️  Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        print(f"\n📁 Files created:")
        print(f"   • {permissions_output} - Detailed direct access permissions (users + teams)")
        print(f"   • {summary_output} - User and team summary with permission counts")
        print(f"   • {repo_summary_output} - Repository summary with direct collaborator counts")
        print(f"\n🎯 Note: This report contains DIRECT access only (excludes inherited org permissions)")
        print(f"🚀 GraphQL API provided significant performance improvement over REST API!")
        
    except KeyboardInterrupt:
        print(f"\n⏸️  Processing interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error during processing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
