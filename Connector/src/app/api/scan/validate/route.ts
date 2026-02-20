import { NextRequest, NextResponse } from 'next/server';
import { getAuthenticatedUser } from '@/lib/auth';
import { githubService } from '@/lib/github';

const BACKEND_URL = process.env.AGENTIC_LAYER_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const user = await getAuthenticatedUser();
    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const body = await request.json();
    const {
      project_id,
      project_name,
      project_type,
      deployment_url,
      // GitHub-specific fields from frontend
      installation_id,
      owner,
      repo,
    } = body;

    // Build the payload for the backend
    const backendPayload: Record<string, any> = {
      project_id,
      project_name,
      project_type,
      user_id: user.id,
    };

    // Add deployment URL only if provided
    if (deployment_url) {
      backendPayload.deployment_url = deployment_url;
    }

    if (project_type === 'github' && (!installation_id || !owner || !repo)) {
      return NextResponse.json(
        { error: 'Missing GitHub installation context (installation_id/owner/repo)' },
        { status: 400 }
      );
    }

    // For GitHub projects, get the token and add repo URL
    if (project_type === 'github' && installation_id && owner && repo) {
      try {
        const installationCheck = await githubService.verifyInstallationForRepo(
          installation_id,
          owner,
          repo
        );
        if (!installationCheck.matches) {
          return NextResponse.json(
            {
              error: `Installation mismatch for ${owner}/${repo}. Expected installation ${installationCheck.expectedInstallationId}, but repo is installed under ${installationCheck.actualInstallationId}.`,
            },
            { status: 409 }
          );
        }

        const token = await githubService.getInstallationToken(installation_id);
        if (!token) {
          return NextResponse.json(
            { error: 'Failed to generate GitHub installation token' },
            { status: 502 }
          );
        }
        backendPayload.github_token = token;
        backendPayload.repository_url = `https://github.com/${owner}/${repo}`;
      } catch (error) {
        console.error('Failed to get GitHub token:', error);
        return NextResponse.json(
          { error: 'Unable to verify installation or obtain GitHub installation token for this repository' },
          { status: 502 }
        );
      }
    }

    // Forward to the backend
    const response = await fetch(`${BACKEND_URL}/api/scan/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(backendPayload),
    });

    if (!response.ok) {
      throw new Error('Backend request failed');
    }

    const data = await response.json();
    const sanitized = {
      ...data,
      data: data?.data
        ? {
            ...data.data,
            github_token: undefined,
          }
        : data?.data,
      state: data?.state
        ? {
            ...data.state,
            github_token: undefined,
          }
        : data?.state,
    };
    return NextResponse.json(sanitized);
  } catch (error: any) {
    console.error('Scan validation error:', error);
    return NextResponse.json(
      { error: 'Failed to validate scan' },
      { status: 500 }
    );
  }
}
