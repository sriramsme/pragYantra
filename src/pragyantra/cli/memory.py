"""Explicit local note operations; no hosted inference or private history logging."""

import json
from datetime import UTC, datetime

from pragyantra.application.companion import CompanionEntry, ContextKind
from pragyantra.providers.memory import SQLiteNotes


def run_profile(args):
    with SQLiteNotes(args.database) as notes:
        context = notes.companion
        if args.operation == "set":
            context.set(
                CompanionEntry(
                    ContextKind(args.kind), args.key, args.value, datetime.now(UTC)
                )
            )
        elif args.operation == "delete":
            print(
                json.dumps(
                    {"deleted": context.delete(ContextKind(args.kind), args.key)}
                )
            )
            return
        print(json.dumps([entry.to_record() for entry in context.entries()]))


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
