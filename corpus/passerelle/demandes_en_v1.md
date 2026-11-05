# Internal requests — Passerelle guide

Entirely synthetic document. Version 1 published on 1 April 2026.

## Preparing a request

An equipment request includes a subject, a justification and the requested equipment type.
Preparing a request creates a draft; it does not submit it.
Before submission, the user must see a summary and explicitly confirm.

## Available statuses

BROUILLON: the request has been prepared but not submitted.
SOUMISE: the request has been recorded for review.
EN_COURS: the responsible department is processing the request.
TERMINEE: processing of the request is complete.
REJETEE: the request has not been accepted; a reason is available.

## Looking up a request

The current status must be obtained from the tracking tool using the request identifier.
This guide explains the statuses; it contains no current individual request status.
Access to a request is limited to people authorised for that request.

## Submission error

After an interruption, the application must check the outcome before submitting again.
The same operation must retain its idempotency identifier to avoid a duplicate.
