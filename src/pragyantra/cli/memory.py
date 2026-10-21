"""Explicit local note operations; no hosted inference or private history logging."""

import json
from datetime import UTC, datetime

from pragyantra.providers.memory import SQLiteNotes


def run_memory(args):
    with SQLiteNotes(args.database) as notes:
        if args.operation == "add":
            found = (notes.add(args.text, at=datetime.now(UTC)),)
        elif args.operation == "forget":
            print(json.dumps({"forgotten": notes.forget(args.id), "id": args.id}))
            return
        else:
            found = notes.search(
                args.query if args.operation == "search" else "",
                limit=args.limit,
                since=args.since,
                until=args.until,
            )
        print(
            json.dumps(
                [
                    {
                        "id": note.id,
                        "text": note.text,
                        "created_at": note.created_at.isoformat(),
                    }
                    for note in found
                ]
            )
        )
