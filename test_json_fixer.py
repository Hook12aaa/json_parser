import pytest

from jason_fixer import JsonFixer, JsonResults

@pytest.fixture
def json_fixer():
    return JsonFixer(logging=True)

@pytest.fixture
def malformed_json_cases():
    return [
        # Missing quotes around keys
        ('{direction: "left"}', '{"direction":"left"}'),
        # Missing quotes around values
        ('{"direction": left}', '{"direction":"left"}'),
        # Extra commas
        ('{"direction": "left",,"speed": 50,}', '{"direction":"left","speed":50}'),
        # Missing commas
        ('{"direction": "left" "speed": 50}', '{"direction":"left","speed":50}'),
        # Mixed quote types
        ('{\'direction\': "left"}', '{"direction":"left"}'),
        # Unquoted numbers
        ('{"speed": 50.5}', '{"speed":50.5}'),
        # Boolean values
        ('{"active": true}', '{"active":true}'),
        # Nested objects with issues
        ('{"data": {nested: "value"}}', '{"data":{"nested":"value"}}'),
        # Arrays with issues
        ('{"items": [1, test, "three"]}', '{"items":[1,"test","three"]}'),
        # Multiple unquoted values
        ('{one: 1, two: two}', '{"one":1,"two":"two"}')
    ]

@pytest.mark.parametrize("malformed,expected", [
    ('{key: value}', {"key": "value"}),
    ('{"key": value}', {"key": "value"}),
    ('{key: "value"}', {"key": "value"}),
    ('{"key":value,}', {"key": "value"}),
    ('{key:value}', {"key": "value"}),
])
def test_basic_json_repairs(json_fixer, malformed, expected):
    assert json_fixer.repair_json(malformed) == expected

def test_basic_json_repairs(json_fixer, malformed_json_cases):
    for malformed, expected in malformed_json_cases:
        result = json_fixer.load_json(malformed)
        assert result.fixed == expected, f"Failed to repair: {malformed}"
        assert isinstance(result, JsonResults)

def test_array_parsing(json_fixer):
    cases = [
        ('[1,2,3]', '[1,2,3]'),
        ('[test, 2, three]', '["test",2,"three"]'),
        ('[[1,2],[3,4]]', '[[1,2],[3,4]]'),
        ('[1, 2, 3]', '[1,2,3]')  # Handle spaces
    ]
    for input_json, expected in cases:
        result = json_fixer.load_json(input_json)
        assert result.fixed == expected, f"Failed to parse array: {input_json}"

def test_number_parsing(json_fixer):
    cases = [
        ('{"num": 123}', '{"num":123}'),
        ('{"num": 123.45}', '{"num":123.45}'),
        ('{"num": -123}', '{"num":-123}'),
        ('{"num": 1e-10}', '{"num":1e-10}')
    ]
    for input_json, expected in cases:
        result = json_fixer.load_json(input_json)
        assert result.fixed == expected


