import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.AGENTIC_LAYER_URL || 'http://localhost:8000';

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ scanId: string }> }
) {
  try {
    const { scanId } = await params;

    const response = await fetch(`${BACKEND_URL}/scan/${scanId}/results`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store',
    });

    const payload = await response.json();

    if (!response.ok) {
      return NextResponse.json(
        { error: payload?.detail || 'Failed to fetch scan results' },
        { status: response.status }
      );
    }

    return NextResponse.json(payload, { status: 200 });
  } catch (error) {
    console.error('Scan results proxy error:', error);
    return NextResponse.json({ error: 'Failed to fetch scan results' }, { status: 500 });
  }
}
