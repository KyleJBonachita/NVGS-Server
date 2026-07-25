# Apps Script to PostgreSQL field map

This is the contract between the existing ticketing interface and NVGS Server.
Names on the left are the current Google Sheet headers. Names on the right are
the protected database fields.

## Tickets

| Google Sheet | PostgreSQL/Django | Notes |
| --- | --- | --- |
| `ticketId` | `source_ticket_id` | Original `GRTKT-` ID is preserved |
| `createdAt` | `created_at` | Original date is preserved during import |
| `updatedAt` | `updated_at` | Original date is preserved during import |
| `downtimeStart` | `downtime_start` | Start of production interruption |
| `downtimeEnd` | `downtime_end` | Filled when resolved |
| `downtimeMinutes` | `downtime_minutes` | Calculated for new tickets |
| `title` | `title` | Required |
| `description` | `description` | Required |
| `ticketType` | `category` | Uses the same seven choices |
| `priority` | `priority` | Urgent, High, Moderate, or Low |
| `priorityColor` | not stored | The interface derives color from priority |
| `workstation` | `workstation` | Text value |
| `location` | `location` | Text value |
| `status` | `status` | Same seven statuses and transition rules |
| `assignedTo` | `assignee.email` | References an approved team account |
| `assignedName` | `assignee.display_name` | Derived from the account |
| `assignedRole` | `assignee.role` | Derived from the account |
| `requesterEmail` | `reporter.email` | Person needing assistance |
| `requesterName` | `reporter.display_name` | Derived from the account |
| `createdByEmail` | `created_by.email` | Person who submitted the form |
| `createdByName` | `created_by.display_name` | Derived from the account |
| `resolvedByEmail` | `resolved_by.email` | Team member who resolved it |
| `resolvedByName` | `resolved_by.display_name` | Derived from the account |
| `resolutionNotes` | `resolution_notes` | Required when resolving |
| `resolutionMinutes` | `resolution_minutes` | Calculated for new tickets |
| `responseMinutes` | `response_minutes` | Calculated on first assignment |
| `escalatedCount` | `escalated_count` | Server-controlled counter |
| `escalatedTo` | `escalated_to` | Escalation target |
| `reopenCount` | `reopen_count` | Server-controlled counter |
| `tags` | `tags` | Existing text format is preserved |
| `rootCause` | `root_cause` | Same eight choices |
| `impactLevel` | `impact_level` | Critical, High, Medium, or Low |
| `affectedStations` | `affected_stations` | Existing text is preserved |

## Other data

| Google Sheet | PostgreSQL/Django |
| --- | --- |
| `Users.email` | `accounts_user.email` |
| `Users.role` | `accounts_user.role` |
| `Users.department` | `accounts_user.department` |
| `Comments.commentId` | `tickets_ticketcomment.source_comment_id` |
| `Comments.content` | `tickets_ticketcomment.body` |
| `Comments.isInternal` | `tickets_ticketcomment.is_internal` |
| `StatusHistory.eventId` | `tickets_ticketevent.source_event_id` |
| `StatusHistory.eventType` | `tickets_ticketevent.action` |
| `StatusHistory.fromStatus` | `tickets_ticketevent.from_status` |
| `StatusHistory.toStatus` | `tickets_ticketevent.to_status` |
| `StatusHistory.note` | `tickets_ticketevent.note` |

Settings, mention mappings, shift logs, and notification/action queues are not
yet migrated. They should be added only with the interface or notification
feature that uses them.
