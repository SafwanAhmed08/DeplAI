import { NextRequest, NextResponse } from "next/server";
import pool from "@/lib/db";
import { v4 as uuidv4 } from "uuid";

function toMysqlDatetime(value?: string) {
  if (!value) return new Date();
  return new Date(value.replace("Z", ""));
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();

    // 🔁 SAFE MAPPING HERE
    const fingerprint = body.fingerprint || body.entity_id;

    const {
      title,
      severity,
      category,
      location,
      project_id,
      repository_id,
      first_seen,
      last_seen,
    } = body;

    if (!fingerprint || !project_id) {
      return NextResponse.json(
        { error: "fingerprint (or entity_id) and project_id are required" },
        { status: 400 }
      );
    }

    const firstSeen = toMysqlDatetime(first_seen);
    const lastSeen = toMysqlDatetime(last_seen);

    // 1️⃣ Check existing ticket
    const [rows]: any = await pool.query(
      `
      SELECT id FROM tickets
      WHERE project_id = ? AND fingerprint = ?
      `,
      [project_id, fingerprint]
    );

    // 2️⃣ Update if exists
    if (rows.length > 0) {
      const ticketId = rows[0].id;

      await pool.query(
        `
        UPDATE tickets
        SET last_seen = ?, status = 'OPEN'
        WHERE id = ?
        `,
        [lastSeen, ticketId]
      );

      return NextResponse.json({
        message: "Ticket updated",
        ticket_id: ticketId,
      });
    }

    // 3️⃣ Create new ticket
    const ticketId = uuidv4();

    await pool.query(
      `
      INSERT INTO tickets (
        id,
        fingerprint,
        title,
        severity,
        status,
        category,
        location,
        project_id,
        repository_id,
        first_seen,
        last_seen
      ) VALUES (?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?)
      `,
      [
        ticketId,
        fingerprint,
        title,
        severity,
        category,
        location,
        project_id,
        repository_id,
        firstSeen,
        lastSeen,
      ]
    );

    return NextResponse.json({
      message: "Ticket created",
      ticket_id: ticketId,
    });
  } catch (err) {
    console.error("Ticketing error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
