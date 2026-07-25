# Moving the existing Apps Script ticketing system

The current Google Apps Script system is useful because it already tells us:

- Which ticket fields agents use
- Which screens Tech Team and TLs need
- What categories and statuses exist
- How the existing workflow behaves

We should reuse that knowledge instead of inventing a second workflow.

## What will change

Today the existing interface probably follows this path:

```text
Browser -> Google Apps Script -> Google Sheet
```

The local version will follow:

```text
Browser -> NVGS HTTPS API -> PostgreSQL
```

The visible HTML, CSS, and JavaScript may be reusable. Calls such as
`google.script.run` will need to become normal web requests using `fetch()`.

## Information needed before conversion

Add these to the repository only after removing real employee/ticket data:

1. Apps Script `.gs` source files
2. HTML, CSS, and browser JavaScript files
3. A list of Google Sheet column names
4. Existing ticket statuses and categories
5. A few fake example tickets
6. Any automatic email or notification rules

Do not commit a real Sheet export containing names, emails, workstation IDs, or
ticket descriptions.

## Safe migration order

1. Copy the existing user interface into a development branch.
2. Map its ticket fields to the PostgreSQL ticket model.
3. Replace Google Sheet reads/writes with API calls.
4. Test using fake tickets.
5. Export the real Sheet once the new system is ready.
6. Import into a temporary database and compare row counts.
7. Ask a small Tech Team/TL group to test.
8. Perform the final export and switch users to the local URL.
9. Keep the old Sheet read-only for an agreed period.

Do not make both systems writable for a long period. Two writable databases will
eventually disagree about the correct ticket status.

## Authentication

The current server uses administrator-created local accounts. Corporate NVIDIA
SSO can be added later when an approved identity application is available.

Checking only that text ends in `@nvidia.com` is not authentication. The user
must prove ownership through a password managed by this server or through
corporate SSO.
