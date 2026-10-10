"""Mock SDK responses: tests require neither credentials nor network."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from server.intelligence import normalize as module

NOW = datetime(2026, 10, 10, 16, tzinfo=timezone.utc)


def payload(**changes):
    data = dict(modes=None, category=None, required_specifications=[],
                preferred_specifications=[], budget_dollars=None, max_deposit_dollars=None,
                needed_by=None, use_start=None, use_end=None, area=None,
                ambiguous_dates=[], follow_up_questions=[])
    data.update(changes)
    return data


@pytest.fixture
def sdk(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'mock-secret')
    monkeypatch.delenv('GEMINI_MODEL', raising=False)
    client = MagicMock()
    client.__enter__.return_value = client
    constructor = MagicMock(return_value=client)
    monkeypatch.setattr(module.genai, 'Client', constructor)
    def respond(data):
        client.models.generate_content.return_value = SimpleNamespace(text=json.dumps(data))
    return constructor, client, respond


def normalize(text='I need an item'):
    return module.normalize_request(text, NOW, 'America/New_York')


def assert_manual(result):
    assert result == module.manual('I need an item')
    assert 'mock-secret' not in json.dumps(result)


def test_suit_and_sdk_contract(sdk):
    constructor, client, respond = sdk
    respond(payload(modes=['borrow'], category='formalwear', budget_dollars='20',
                    required_specifications=[dict(name='jacket_size', value='40R')],
                    preferred_specifications=[dict(name='color', value='navy')]))
    text = 'I need to borrow a navy suit, size 40R, for under $20.'
    result = normalize(text)
    assert result['source'] == 'gemini'
    assert result['modes'] == ['borrow']
    assert result['category'] == 'formalwear'
    assert result['required_specifications'] == {'jacket_size': '40R'}
    assert result['preferred_specifications'] == {'color': 'navy'}
    assert result['budget_cents'] == 2000
    assert result['max_deposit_cents'] is None
    assert result['original_text'] == text
    assert any('deposit' in q for q in result['follow_up_questions'])
    assert constructor.call_args.kwargs['api_key'] == 'mock-secret'
    assert constructor.call_args.kwargs['http_options'].timeout == module.ATTEMPT_TIMEOUT_MS
    assert constructor.call_args.kwargs['http_options'].retry_options.attempts == 1
    call = client.models.generate_content.call_args.kwargs
    assert call['config'].response_json_schema == module.Extraction.model_json_schema()
    assert call['config'].response_mime_type == 'application/json'
    assert json.loads(call['contents'])['now'] == '2026-10-10T12:00:00-04:00'


@pytest.mark.parametrize('amount,cents', [('0', 0), ('0.01', 1), ('19.99', 1999), ('20', 2000)])
def test_decimal_conversion_and_separate_deposit(sdk, amount, cents):
    sdk[2](payload(budget_dollars=amount, max_deposit_dollars='60.50'))
    result = normalize()
    assert result['budget_cents'] == cents
    assert result['max_deposit_cents'] == 6050


def test_unknowns_and_followups(sdk):
    sdk[2](payload(required_specifications=[dict(name='size', value=None)]))
    result = normalize()
    for field in ('modes', 'category', 'budget_cents', 'max_deposit_cents', 'needed_by', 'use_start', 'use_end', 'area'):
        assert result[field] is None
    assert result['required_specifications'] == {'size': None}
    assert len(result['follow_up_questions']) >= 4


@pytest.mark.parametrize('offset,expected', [('-04:00', '06'), ('-05:00', '07')])
def test_ambiguous_date_and_utc_conversion(sdk, offset, expected):
    proposed = '2026-10-11T02:00:00' + offset
    sdk[2](payload(needed_by=proposed, ambiguous_dates=[dict(text='2 a.m.', proposed=proposed, needs_confirmation=True)]))
    result = normalize('Need it at 2 a.m.')
    assert result['needed_by'] == f'2026-10-11T{expected}:00:00Z'
    assert result['ambiguous_dates'][0]['proposed'] == result['needed_by']
    assert any('confirm' in q and '2 a.m.' in q for q in result['follow_up_questions'])


@pytest.mark.parametrize('changes', [dict(budget_dollars='-1'), dict(budget_dollars='NaN'),
    dict(budget_dollars='1.001'), dict(modes=['buy']), dict(modes=[]),
    dict(needed_by='2026-10-11T02:00:00'),
    dict(use_start='2026-10-12T00:00:00Z', use_end='2026-10-11T00:00:00Z'),
    dict(ambiguous_dates=[dict(text='tomorrow', proposed=None, needs_confirmation=False)]),
    dict(required_specifications=[dict(name='size', value='40R'), dict(name='size', value='42R')])])
def test_invalid_output_falls_back(sdk, changes):
    sdk[2](payload(**changes))
    assert_manual(normalize())


@pytest.mark.parametrize('failure', [TimeoutError('mock-secret'), RuntimeError('mock-secret')])
def test_api_failure(sdk, failure):
    sdk[1].models.generate_content.side_effect = failure
    assert_manual(normalize())


@pytest.mark.parametrize('response', [None, 'not JSON', '{}'])
def test_malformed_response(sdk, response):
    sdk[1].models.generate_content.return_value = SimpleNamespace(text=response)
    assert_manual(normalize())


def test_missing_key_skips_sdk(sdk, monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY')
    assert_manual(normalize())
    sdk[0].assert_not_called()


def api_error(code):
    cls = module.errors.ServerError if code >= 500 else module.errors.ClientError
    return cls(code, {'error': {'code': code, 'message': 'mock-secret'}})


def test_primary_succeeds_and_logs_only_model(sdk, caplog):
    sdk[2](payload())
    with caplog.at_level('INFO', logger=module.__name__):
        assert normalize()['source'] == 'gemini'
    calls = sdk[1].models.generate_content.call_args_list
    assert [call.kwargs['model'] for call in calls] == [module.DEFAULT_MODELS[0]]
    assert module.DEFAULT_MODELS[0] in caplog.text
    assert 'mock-secret' not in caplog.text
    assert 'I need an item' not in caplog.text


@pytest.mark.parametrize('code', [503, 429])
def test_retryable_primary_falls_back(sdk, code):
    sdk[1].models.generate_content.side_effect = [api_error(code), SimpleNamespace(text=json.dumps(payload()))]
    assert normalize()['source'] == 'gemini'
    assert [call.kwargs['model'] for call in sdk[1].models.generate_content.call_args_list] == list(module.DEFAULT_MODELS[:2])


def test_all_models_fail_manual(sdk):
    sdk[1].models.generate_content.side_effect = [api_error(503), api_error(429), api_error(503)]
    assert_manual(normalize())
    assert sdk[1].models.generate_content.call_count == 3


@pytest.mark.parametrize('code', [400, 401, 403, 404, 504])
def test_non_retryable_does_not_cycle(sdk, code):
    sdk[1].models.generate_content.side_effect = api_error(code)
    assert_manual(normalize())
    assert sdk[1].models.generate_content.call_count == 1


def test_invalid_output_does_not_cycle(sdk):
    sdk[2](payload(budget_dollars='-1'))
    assert_manual(normalize())
    assert sdk[1].models.generate_content.call_count == 1


def test_preferred_model_order_and_three_model_limit(sdk, monkeypatch):
    monkeypatch.setenv('GEMINI_MODEL', 'models/gemini-3.8-flash')
    sdk[1].models.generate_content.side_effect = api_error(503)
    assert_manual(normalize())
    assert [call.kwargs['model'] for call in sdk[1].models.generate_content.call_args_list] == ['gemini-3.8-flash', 'gemini-3.5-flash-lite', 'gemini-3.5-flash']
    monkeypatch.setenv('GEMINI_MODEL', 'gemini-3.7-flash')
    assert module._model_order() == ['gemini-3.7-flash', 'gemini-3.5-flash-lite', 'gemini-3.5-flash']


def test_total_deadline_prevents_more_calls(sdk, monkeypatch):
    monkeypatch.setattr(module.time, 'monotonic', MagicMock(side_effect=[0, 0, 33]))
    sdk[1].models.generate_content.side_effect = api_error(503)
    assert_manual(normalize())
    assert sdk[1].models.generate_content.call_count == 1
    options = sdk[1].models.generate_content.call_args.kwargs['config'].http_options
    assert options.timeout == module.ATTEMPT_TIMEOUT_MS


# Reference-photo tests share the mocked SDK; images never reach a network.
from server.intelligence.vision import (
    normalize_reference_image, ReferenceImageError, MAX_REFERENCE_IMAGE_BYTES,
)

PNG = b'\x89PNG\r\n\x1a\nsynthetic-image-for-mocked-sdk'


def visual_payload(**changes):
    data = dict(category=None, type=None, color=None, pattern=None, style=None)
    data.update(changes)
    return data


def vision(text=None, image=PNG, mime='image/png'):
    return normalize_reference_image(image, mime, NOW, 'America/New_York', text)


def test_suit_photo_preferred_attributes_and_confirmation(sdk):
    sdk[2](visual_payload(category='formalwear', type='suit', color='navy', pattern='solid', style='formal'))
    result = vision()
    assert result['source'] == 'gemini'
    assert result['category'] == 'formalwear'
    assert result['required_specifications'] == {}
    assert result['preferred_specifications'] == dict(type='suit', color='navy', pattern='solid', style='formal')
    for field in ('modes', 'budget_cents', 'max_deposit_cents', 'needed_by', 'use_start', 'use_end', 'area'):
        assert result[field] is None
    assert set(result) == set(module.manual(''))
    assert any('confirm or edit all' in q and 'color=navy' in q for q in result['follow_up_questions'])
    parts = sdk[1].models.generate_content.call_args.kwargs['contents']
    assert parts[1].inline_data.data == PNG
    assert parts[1].inline_data.mime_type == 'image/png'


def test_unclear_reference_image(sdk):
    sdk[2](visual_payload())
    result = vision()
    assert result['source'] == 'gemini'
    assert result['category'] is None
    assert result['preferred_specifications'] == {}
    assert any('unclear' in q for q in result['follow_up_questions'])


@pytest.mark.parametrize('mime,image', [('image/gif', b'GIF89a'), ('image/png', b'not-image'), ('image/jpeg', PNG)])
def test_invalid_reference_mime_and_signature(sdk, mime, image):
    with pytest.raises(ReferenceImageError) as error:
        vision(image=image, mime=mime)
    assert error.value.code == 'unsupported_image'
    assert error.value.status == 400
    sdk[0].assert_not_called()


def test_oversized_reference_input(sdk):
    with pytest.raises(ReferenceImageError) as error:
        vision(image=PNG + b'x' * MAX_REFERENCE_IMAGE_BYTES)
    assert error.value.code == 'payload_too_large'
    assert error.value.status == 413
    sdk[0].assert_not_called()


def test_empty_reference_input(sdk):
    with pytest.raises(ReferenceImageError) as error:
        vision(image=b'')
    assert error.value.code == 'invalid_image'
    sdk[0].assert_not_called()


def test_reference_primary_503_fallback(sdk):
    sdk[1].models.generate_content.side_effect = [api_error(503), SimpleNamespace(text=json.dumps(visual_payload(category='formalwear', color='navy')))]
    assert vision()['source'] == 'gemini'
    assert [call.kwargs['model'] for call in sdk[1].models.generate_content.call_args_list] == list(module.DEFAULT_MODELS[:2])


def test_reference_total_failure(sdk):
    sdk[1].models.generate_content.side_effect = api_error(503)
    assert vision() == module.manual('')
    assert sdk[1].models.generate_content.call_count == 3


@pytest.mark.parametrize('forbidden', ['jacket_size', 'model', 'authenticity', 'condition', 'price', 'deposit', 'availability', 'location', 'ownership'])
def test_reference_schema_rejects_nonvisual_fields(sdk, forbidden):
    sdk[2](dict(visual_payload(color='navy'), **{forbidden: 'invented'}))
    assert vision() == module.manual('')
    assert sdk[1].models.generate_content.call_count == 1


def test_reference_text_is_separate_and_constraints_take_priority(sdk):
    sdk[1].models.generate_content.side_effect = [
        SimpleNamespace(text=json.dumps(visual_payload(category='formalwear', type='suit', color='navy'))),
        SimpleNamespace(text=json.dumps(payload(modes=['borrow'], category='formalwear', budget_dollars='20',
            required_specifications=[dict(name='jacket_size', value='40R'), dict(name='color', value='black')]))),
    ]
    result = vision('Borrow size 40R under $20; must be black.')
    assert result['required_specifications'] == {'jacket_size': '40R', 'color': 'black'}
    assert result['preferred_specifications'] == {'type': 'suit'}
    assert result['budget_cents'] == 2000
    calls = sdk[1].models.generate_content.call_args_list
    assert isinstance(calls[1].kwargs['contents'], str)
    assert 'Borrow size 40R' in calls[1].kwargs['contents']
    assert 'Borrow size 40R' not in calls[0].kwargs['contents'][0].text


def test_reference_explicit_required_visual_attribute(sdk):
    sdk[1].models.generate_content.side_effect = [
        SimpleNamespace(text=json.dumps(visual_payload(color='navy'))),
        SimpleNamespace(text=json.dumps(payload())),
    ]
    result = vision('Must be navy.')
    assert result['required_specifications'] == {'color': 'navy'}
    assert result['preferred_specifications'] == {}


def test_reference_text_failure_discards_visual_partial_success(sdk):
    sdk[1].models.generate_content.side_effect = [
        SimpleNamespace(text=json.dumps(visual_payload(color='navy'))), api_error(401)]
    assert vision('Borrow a suit') == module.manual('Borrow a suit')


def test_reference_suit_followups_reconciled_after_merge(sdk):
    specific = [
        'What jacket size do you need?',
        'What is your purchase or rental fee budget in USD?',
        'Which campus area works for pickup?',
        'What is the maximum refundable deposit you can afford?',
        'When does your borrowing period start?',
        'When can you return the item?',
        'Would you like to buy, borrow, or consider either?',
    ]
    sdk[1].models.generate_content.side_effect = [
        SimpleNamespace(text=json.dumps(visual_payload(category='formalwear', type='suit', color='blue', style='business'))),
        SimpleNamespace(text=json.dumps(payload(modes=['borrow'], follow_up_questions=[
            'What type of item are you looking to borrow?',
            'What specific item or category are you looking to borrow?',
            'What kind of item do you need?', *specific, specific[0]]))),
    ]
    result = vision('I want to borrow something like this.')
    assert result['follow_up_questions'] == specific + [
        'Before searching, confirm or edit all proposed visual attributes: category=formalwear, type=suit, color=blue, style=business.']


@pytest.mark.parametrize('category,type_location,type_value,expected', [
    ('formalwear', 'preferred_specifications', 'suit', []),
    ('formalwear', 'required_specifications', 'suit', []),
    ('formalwear', 'preferred_specifications', None, ['What type of item are you looking to borrow?']),
    (None, 'preferred_specifications', 'suit', ['What kind of item do you need?']),
    (None, 'preferred_specifications', None, ['What kind of item do you need?', 'What type of item are you looking to borrow?']),
])
def test_reference_followup_unknowns_required_types_and_dedup(category, type_location, type_value, expected):
    from server.intelligence.vision import _reconcile_questions
    result = module.manual('')
    result['category'] = category
    result[type_location]['type'] = type_value
    specific = 'What type of suit lapel do you prefer?'
    confirmation = 'Before searching, confirm or edit all proposed visual attributes: color=blue.'
    result['follow_up_questions'] = [
        'What kind of item do you need?', 'What type of item are you looking to borrow?',
        specific, specific, confirmation, confirmation,
    ]
    _reconcile_questions(result)
    assert result['follow_up_questions'] == expected + [specific, confirmation]
