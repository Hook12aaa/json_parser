# JSON Fixer

A lightweight, high-performance JSON repair utility designed specifically for handling malformed JSON, with special consideration for LLM output processing.

## Why Another JSON Fixer?

While solutions like [json_repair](https://github.com/mangiucugna/json_repair) exist, JSON Fixer was created to address specific needs:

- **Performance**: Optimized for speed with parallel processing capabilities
- **Error Tracking**: Detailed error tracking for each malformed character
- **LLM Focus**: Specifically designed to handle common JSON issues in LLM outputs
- **Memory Efficient**: Lightweight implementation without excessive loop iterations
- **Caching**: Implements LRU caching for repeated patterns

## Features

- 🚀 High-performance parallel processing for large JSON files
- 📝 Detailed error tracking with position information
- 🔄 Handles common JSON formatting issues:
  - Unmatched quotes and brackets
  - Trailing commas
  - Missing colons
  - Invalid number formats
- 💾 LRU caching for repeated JSON patterns
- 🧵 Thread-safe batch processing
- 📊 Memory efficient implementation

## Installation

```bash
pip install json-fixer  # Coming soon to PyPI
```

## Quick Start

```python
from jason_fixer import JsonFixer

# Simple usage
fixer = JsonFixer()
result = fixer.load_json('{"key": "value",}')  # Note the trailing comma
print(result.fixed)  # {"key":"value"}

# Batch processing
jsons = [
    '{"key1": "value1"}',
    '{"key2": "value2",}',  # Malformed
    '{"key3": "value3"}'
]
results = JsonFixer.batch_process(jsons)

# File processing
result = JsonFixer.from_file('data.json')
```

## Error Tracking

```python
fixer = JsonFixer(logging=True)
result = fixer.load_json('{"key": "value"')
print(result.get_errors())  # Shows missing closing brace position
```

## Performance

- Parallel processing for large JSON files
- LRU caching for repeated patterns
- Optimized string parsing
- Minimal memory footprint

## Contributing

Contributions are welcome! Feel free to:

1. Fork the repository
2. Create your feature branch
3. Submit a pull request

## License

This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or distribute this software, either in source code form or as a compiled binary, for any purpose, commercial or non-commercial, and by any means.

For more information, please refer to [http://unlicense.org/](http://unlicense.org/)

Just don't go creating AGI or something...

## Credits

Inspired by [json_repair](https://github.com/mangiucugna/json_repair), but reimagined with focus on performance and LLM processing requirements.
