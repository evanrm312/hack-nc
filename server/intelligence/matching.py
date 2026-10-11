"""Deterministic compatibility checks against supplied inventory only."""
from __future__ import annotations

from datetime import datetime, timedelta


def _same(left, right):
    if isinstance(left, str) and isinstance(right, str):
        return left.strip().casefold() == right.strip().casefold()
    return type(left) is type(right) and left == right


def _money(value):
    return type(value) is int and value >= 0


def _date(value):
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.utcoffset() is None:
        raise ValueError('Timezone required')
    return parsed


def _candidate(request, listing, mode):
    entry = dict(listing_id=listing['id'], mode=mode, score=None,
                 reasons=[], shortcomings=[], unknown_required=[])
    reasons, shortcomings, unknown = entry['reasons'], entry['shortcomings'], entry['unknown_required']
    rejected = []

    def uncertain(field, reason):
        if field not in unknown:
            unknown.append(field)
        shortcomings.append(reason)

    if listing.get('status') != 'available' or listing.get('active_exchange_id'):
        rejected.append('Listing is unavailable or already reserved.')
    if mode is None:
        if not request.get('modes'):
            uncertain('modes', 'Requested mode needs confirmation.')
        else:
            rejected.append('Listing does not support any requested mode.')
    else:
        reasons.append(f'Listing supports requested mode: {mode}.')

    request_modes = request.get('modes') or []
    listing_modes = listing.get('allowed_modes') or []
    if ('service' in request_modes) != ('service' in listing_modes):
        rejected.append('Service requests and item listings cannot match each other.')
    if ('service' in request_modes and request_modes != ['service']) or ('service' in listing_modes and listing_modes != ['service']):
        rejected.append('Service and item modes cannot be combined.')

    category = request.get('category')
    if category is None or listing.get('category') is None:
        uncertain('category', 'Category needs confirmation.')
    elif not _same(category, listing['category']):
        rejected.append(f"Category mismatch: requested {category}, listing is {listing['category']}.")
    else:
        reasons.append(f'Category matches: {category}.')
    specs = listing.get('specifications') or {}
    for name, expected in (request.get('required_specifications') or {}).items():
        actual = specs.get(name)
        if expected is None or actual is None:
            uncertain(name, f'Required specification {name} needs confirmation.')
        elif not _same(expected, actual):
            rejected.append(f'Required {name} mismatch: requested {expected}, listing has {actual}.')
        else:
            reasons.append(f'Required {name} matches: {actual}.')
    preference_count = 0
    for name, expected in (request.get('preferred_specifications') or {}).items():
        actual = specs.get(name)
        if expected is not None and actual is not None and _same(expected, actual):
            preference_count += 1
            reasons.append(f'Preferred {name} matches: {actual}.')
        else:
            shortcomings.append(f'Preferred {name} is unknown or not matched.')

    cost = None
    if mode:
        cost_field = ('sale_price_cents' if mode == 'sale' else
                      'service_price_cents' if mode == 'service' else 'rental_fee_cents')
        label = 'Sale price' if mode == 'sale' else 'Service price' if mode == 'service' else 'Rental fee'
        cost = listing.get(cost_field)
        budget = request.get('budget_cents')
        if not _money(cost):
            uncertain(cost_field, f'{label} needs confirmation; unknown is not free.')
            cost = None
        elif budget is not None and (not _money(budget) or cost > budget):
            rejected.append(f'{label} {cost} cents exceeds or cannot be checked against budget {budget} cents.')
        else:
            reasons.append(f'{label}: {cost} cents' + (f', within budget {budget} cents.' if budget is not None else '.'))
        if mode == 'borrow':
            value, percent = listing.get('proposed_item_value_cents'), listing.get('collateral_percent')
            maximum = request.get('max_deposit_cents')
            if not _money(value) or type(percent) is not int or not 0 <= percent <= 100:
                uncertain('proposed_deposit_cents', 'Proposed deposit needs confirmation: item value or collateral percentage is unknown/invalid.')
            else:
                # Round up fractional cents so affordability is not understated.
                deposit = (value * percent + 99) // 100
                reasons.append(f'Proposed deposit: {deposit} cents ({percent}% of {value} cents item value), separate from rental fee.')
                if maximum is not None and (not _money(maximum) or deposit > maximum):
                    shortcomings.append(f'deposit negotiation required: proposed deposit {deposit} cents exceeds maximum {maximum} cents.')
                    unknown.append('deposit_agreement')

        if mode == 'service':
            offered = listing.get('service_duration_minutes')
            requested = request.get('service_duration_minutes')
            valid_offered = type(offered) is int and 1 <= offered <= 1440
            valid_requested = type(requested) is int and 1 <= requested <= 1440
            if not valid_offered:
                uncertain('service_duration_minutes', 'Provider service duration needs confirmation.')
            if not valid_requested:
                uncertain('service_duration_minutes', 'Requested service duration needs confirmation.')
            elif valid_offered and requested > offered:
                rejected.append(f'Service duration {offered} minutes is shorter than requested {requested} minutes.')
            elif valid_offered:
                reasons.append(f'Provider duration {offered} minutes covers requested {requested} minutes.')

            def parse_windows(values):
                if not values:
                    return []
                parsed = [(_date(window['start']), _date(window['end'])) for window in values]
                if any(start is None or end is None or start >= end for start, end in parsed):
                    raise ValueError('Invalid service interval')
                return parsed

            windows, wanted = [], []
            for field, source in (('service_available_windows', listing), ('service_time_windows', request)):
                try:
                    parsed = parse_windows(source.get(field))
                    if not parsed:
                        uncertain(field, f'{field} missing; scheduling needs confirmation.')
                    if field == 'service_available_windows':
                        windows = parsed
                    else:
                        wanted = parsed
                except (ValueError, TypeError, AttributeError, KeyError):
                    uncertain(field, f'{field} invalid; scheduling needs confirmation.')
            try:
                deadline = _date(request.get('needed_by'))
            except (ValueError, TypeError, AttributeError):
                deadline = None
                uncertain('needed_by', 'Service deadline needs confirmation.')
            # A deadline caps completion; it never supplies the user's availability.
            if windows and (wanted or deadline):
                span = timedelta(minutes=requested) if valid_requested else timedelta(0)
                overlaps = [(max(start, want_start), min(end, want_end, deadline or end))
                            for start, end in windows
                            for want_start, want_end in (wanted or [(start, end)])]
                if not any(start < end and start + span <= end for start, end in overlaps):
                    rejected.append('No feasible service overlap is long enough for the requested duration before the deadline.')
                elif wanted and valid_requested:
                    reasons.append(f'Service time windows overlap for at least {requested} minutes before any deadline.')
            if any(date.get('needs_confirmation') for date in (request.get('ambiguous_dates') or [])):
                uncertain('service_schedule_confirmation', 'Proposed service dates require user confirmation.')
        else:
            try:
                availability = listing.get('availability') or {}
                start = _date(availability.get('available_from'))
                end = _date(availability.get('available_until'))
                needed = _date(request.get('needed_by'))
                use_start = _date(request.get('use_start')) if mode == 'borrow' else None
                use_end = _date(request.get('use_end')) if mode == 'borrow' else None
                points = [d for d in (needed, use_start, use_end) if d is not None]
                if (start and end and start > end) or (use_start and use_end and use_start >= use_end):
                    rejected.append('Invalid availability or requested date interval.')
                elif any((start and point < start) or (end and point > end) for point in points):
                    rejected.append('Listing is unavailable for the requested dates.')
                elif points:
                    if start is None or end is None:
                        uncertain('availability', 'Availability for requested dates needs confirmation; listing date bounds are unknown.')
                    else:
                        reasons.append('Listing availability covers the requested dates.')
            except (ValueError, TypeError, AttributeError):
                uncertain('availability', 'Invalid or timezone-less dates need confirmation.')

    shortcomings.extend(rejected)
    bucket = 'rejected' if rejected else 'needs_confirmation' if unknown else 'confirmed'
    # Each preference outweighs cost; cost breaks ties using a bounded component.
    entry['score'] = None if rejected else float(preference_count + (1 / (cost + 1) if cost is not None else 0))
    key = (len(unknown), -preference_count, cost is None, cost or 0, mode or '', listing['id'])
    return bucket, entry, key


def match_listings(request: dict, listings: list[dict]) -> dict:
    """Return contracted MatchEntries; no Gemini, inventory creation or mutations.

    Owner-view fields override normalized fields, including explicit nulls.
    Each listing appears once using its best eligible mode (confirmed first).
    """
    constraints = dict(request.get('normalized') or {})
    constraints.update({key: value for key, value in request.items() if key != 'normalized'})
    result = dict(source='deterministic', confirmed=[], needs_confirmation=[], rejected=[])
    ranked = {bucket: [] for bucket in ('confirmed', 'needs_confirmation', 'rejected')}
    priority = dict(confirmed=0, needs_confirmation=1, rejected=2)
    for listing in listings:
        modes = [mode for mode in ('sale', 'borrow', 'service')
                 if mode in (constraints.get('modes') or []) and mode in (listing.get('allowed_modes') or [])]
        candidates = [_candidate(constraints, listing, mode) for mode in modes or [None]]
        bucket, entry, key = min(candidates, key=lambda candidate: (priority[candidate[0]], candidate[2]))
        ranked[bucket].append((key, entry))
    for bucket, entries in ranked.items():
        result[bucket] = [entry for _, entry in sorted(entries, key=lambda item: item[0])]
    return result
