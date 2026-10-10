"""Person 4 tests: exchange workflow. Owned by Person 4 (branch p4-exchanges).

Stub created by Person 1 so the file exists. No tests yet.
Cover at least: third party cannot read messages/evidence, offer edits reset
both acceptances, competing acceptances reserve the item exactly once (use
server.reservation.reserve_listing), duplicate accept is idempotent, a loan
cannot complete without the return workflow, dispute never charges.
"""
