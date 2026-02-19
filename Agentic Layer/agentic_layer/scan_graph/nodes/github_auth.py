from __future__ import annotations

from urllib.parse import urlparse

import httpx

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


def _extract_owner_repo(repo_url: str) -> tuple[str | None, str | None]:
    parsed = urlparse(repo_url)
    if "github.com" not in parsed.netloc.lower():
        return None, None

    parts = [segment for segment in parsed.path.strip("/").split("/") if segment]
    if len(parts) < 2:
        return None, None

    owner = parts[0]
    repo = parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]

    if not owner or not repo:
        return None, None

    return owner, repo


async def github_auth_node(state: ScanState) -> ScanState:
    # Validates token against GitHub API and confirms repository access.
    log_agent(state["scan_id"], "GitHubAuth", "Validating GitHub token")

    repo_metadata = dict(state["repo_metadata"])
    errors = list(state["errors"])

    token = state["github_token"]
    token_present = token is not None and bool(token.strip())
    token_valid = False
    repo_access = False
    authenticated_login: str | None = None
    token_type: str | None = None

    owner, repo = _extract_owner_repo(state["repo_url"])

    if not token_present:
        errors.append("GitHub token is required")
    elif owner is None or repo is None:
        errors.append("Repository URL is not a valid GitHub repository path")
    else:
        headers = {
            "Authorization": f"Bearer {token.strip()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "deplai-agent/1.0",
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                user_response = await client.get("https://api.github.com/user", headers=headers)
                if user_response.status_code == 200:
                    token_valid = True
                    token_type = "user"
                    user_payload = user_response.json()
                    authenticated_login = user_payload.get("login")
                else:
                    repo_response = await client.get(
                        f"https://api.github.com/repos/{owner}/{repo}",
                        headers=headers,
                    )
                    if repo_response.status_code == 200:
                        token_valid = True
                        repo_access = True
                        token_type = "installation"
                    elif repo_response.status_code in {401, 403}:
                        errors.append("GitHub token is invalid or lacks required scopes")
                    elif repo_response.status_code == 404:
                        errors.append("Target repository not found or inaccessible")
                    else:
                        errors.append("Repository access validation failed")

                if token_valid and not repo_access:
                    repo_response = await client.get(
                        f"https://api.github.com/repos/{owner}/{repo}",
                        headers=headers,
                    )
                    if repo_response.status_code == 200:
                        repo_access = True
                    elif repo_response.status_code in {401, 403}:
                        errors.append("Token does not have access to the target repository")
                    elif repo_response.status_code == 404:
                        errors.append("Target repository not found or inaccessible")
                    else:
                        errors.append("Repository access validation failed")
        except httpx.RequestError:
            errors.append("Unable to reach GitHub API for authentication")

    if token_valid and not repo_access:
        token_valid = False


    repo_metadata["github_auth"] = {
        "token_present": token_present,
        "token_valid": token_valid,
        "repo_access": repo_access,
        "token_type": token_type,
        "authenticated_login": authenticated_login,
        "repo": f"{owner}/{repo}" if owner and repo else None,
    }

    log_agent(
        state["scan_id"],
        "GitHubAuth",
        f"Token validation complete: present={token_present}, valid={token_valid}, repo_access={repo_access}",
    )

    return merge_state(
        state,
        {
            "phase": "github_auth",
            "errors": errors,
            "repo_metadata": repo_metadata,
        },
    )
