import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const { url } = await request.json();

    if (!url) {
      return NextResponse.json({ valid: false, error: 'URL is required' }, { status: 400 });
    }

    // Validate URL format
    let parsedUrl;
    try {
      parsedUrl = new URL(url);
    } catch {
      return NextResponse.json({ valid: false, error: 'Invalid URL format' }, { status: 400 });
    }

    // Check if protocol is http or https
    if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
      return NextResponse.json({ valid: false, error: 'URL must use HTTP or HTTPS' }, { status: 400 });
    }

    // Attempt to reach the URL
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    try {
      const response = await fetch(url, {
        method: 'HEAD',
        signal: controller.signal,
        headers: {
          'User-Agent': 'DeplAI-Scanner/1.0',
        },
      });

      clearTimeout(timeoutId);
      return NextResponse.json({ valid: true });
    } catch {
      clearTimeout(timeoutId);

      // If HEAD fails, try GET (some servers don't support HEAD)
      try {
        const getController = new AbortController();
        const getTimeoutId = setTimeout(() => getController.abort(), 10000);

        await fetch(url, {
          method: 'GET',
          signal: getController.signal,
          headers: {
            'User-Agent': 'DeplAI-Scanner/1.0',
          },
        });

        clearTimeout(getTimeoutId);
        return NextResponse.json({ valid: true });
      } catch {
        return NextResponse.json({ valid: false, error: 'URL is not reachable' });
      }
    }
  } catch {
    return NextResponse.json({ valid: false, error: 'Validation failed' }, { status: 500 });
  }
}
