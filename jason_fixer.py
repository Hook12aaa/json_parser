import json
from typing import Any, Dict, List, Union, Optional
import os
from multiprocessing import Pool, cpu_count
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor


class JsonResults:
    def __init__(self, original: str, fixed: str):
        self.original = original
        self.fixed = fixed
        self.errors: Dict[str, List[int]] = {}  # {char: [positions]}
        
    def add_error(self, char: str, index: int):
        if char not in self.errors:
            self.errors[char] = []
        self.errors[char].append(index)

    def __str__(self) -> str:
        return self.fixed
        
    def get_errors(self) -> Dict[str, List[int]]:
        return self.errors.copy()
    
    def to_dict(self) -> Dict:
        try:
            return json.loads(self.fixed)
        except json.JSONDecodeError:
            return {}


def _process_json_chunk(chunk: str) -> Dict:
    """Standalone function for processing JSON chunks"""
    try:
        return json.loads(chunk)
    except json.JSONDecodeError:
        return {}

def _parallel_process(json_str: str) -> JsonResults:
    """Standalone function for parallel processing"""
    fixer = JsonFixer()
    return fixer.load_json(json_str)

class JsonFixer:
    """
    A utility class for parsing and fixing malformed JSON strings.
    This class implements a custom JSON parser that can handle and fix common JSON formatting
    issues and malformed JSON strings. It provides methods for parsing different JSON data types
    and cleaning up invalid JSON structures.
    Attributes:
        STRING_DELIMITERS (List[str]): List of valid string delimiters including single, double, and curly quotes
        index (int): Current position in the JSON string being parsed
        json_str (str): The JSON string being processed
        logging (bool): Whether to log parsing errors and operations
        logger (List[Dict]): List of logged errors and their context if logging is enabled
        result (JsonResults): Container for original, rough, and fixed JSON results
    Methods:
        parse(): Parse any JSON value from the current position
        parse_object(): Parse a JSON object (dictionary)
        parse_array(): Parse a JSON array (list)
        parse_string(): Parse a JSON string value
        parse_number(): Parse a JSON number value
        load_json(text): Load and fix a potentially malformed JSON string
        from_file(filename): Load and fix JSON from a file
        >>> fixer = JsonFixer(logging=True)
        >>> result = fixer.load_json('{"key": "value",}')  # Malformed JSON
        {"key":"value"}
    """
    STRING_DELIMITERS = ['"', "'", """, """]

    def __init__(self, logging: bool = False, max_workers: Optional[int] = None):
        self.index = 0
        self.json_str = ""
        self.logging = logging
        self.logger = [] if logging else None
        self.result = None
        self.max_workers = max_workers or max(1, cpu_count() - 1)
        
    @staticmethod
    def batch_process(json_strings: List[str], max_workers: Optional[int] = None) -> List[JsonResults]:
        """Static method for batch processing JSON strings"""
        workers = max_workers or max(1, cpu_count() - 1)
        with Pool(processes=workers) as pool:
            results = pool.map(_parallel_process, json_strings)
        return results

    @lru_cache(maxsize=1024)
    def _cached_parse(self, json_str: str) -> Union[Dict, List, str, int, float, bool, None]:
        """Cached version of parse for repeated JSON patterns"""
        self.json_str = json_str
        self.index = 0
        return self.parse()

    def _batch_process(self, json_strings: List[str]) -> List[JsonResults]:
        """Process multiple JSON strings in parallel"""
        with Pool(processes=self.max_workers) as pool:
            results = pool.map(self.load_json, json_strings)
        return results

    @staticmethod
    @lru_cache(maxsize=128)
    def _standardize_json(obj_str: str) -> str:
        """Cached version of JSON standardization"""
        try:
            if isinstance(obj_str, str):
                try:
                    obj = json.loads(obj_str)
                except json.JSONDecodeError:
                    return obj_str
            else:
                obj = obj_str
            return json.dumps(obj, separators=(',', ':'))
        except (json.JSONDecodeError, TypeError):
            return obj_str

    def __has_array_before_object(self, text: str) -> bool:
        return text.count('[') > text.count('{')

    def __has_minimum_one_brace(self, text: str) -> bool:
        return text.count('{') >= 1 and text.count('}') >= 1

    def _is_special_value(self, value: str) -> Any:
        """Check if string is a special JSON value (number, bool, null)"""
        value = value.strip().lower()
        if value == 'true':
            return True
        if value == 'false':
            return False
        if value == 'null':
            return None
        try:
            return int(value) if value.isdigit() else float(value)
        except ValueError:
            return None

    def _standardize_json(self, obj: Union[Dict, List, str, int, float, bool, None]) -> str:
        """
        Standardizes JSON output format by removing unnecessary whitespace.
        
        Args:
            obj: The parsed JSON object
            
        Returns:
            str: Compact JSON string without extra whitespace
        """
        
        return json.dumps(obj, separators=(',', ':'))


    def _track_error(self, char: str, pos: int):
        """
        Track JSON parsing errors with position information.

        This method records encountered errors during JSON string parsing by adding them to
        the result object and optionally logging them with context.

        Args:
            char (str): The invalid character that caused the error.
            pos (int): The position of the invalid character in the JSON string.

        Returns:
            None

        Side Effects:
            - Adds error to self.result if result object exists
            - Appends error details to self.logger if logging is enabled

        Example:
            self._track_error('}', 10)  # Tracks unexpected closing brace at position 10
        """
        if self.result:
            self.result.add_error(char, pos)
            if self.logging:
                context_start = max(0, pos-10)
                context_end = min(len(self.json_str), pos+10)
                self.logger.append({
                    "error": f"Invalid character '{char}' at position {pos}",
                    "context": self.json_str[context_start:context_end] if pos >= 0 else "Unknown context"
                })

    def parse(self) -> Union[Dict, List, str, int, float, bool, None]:
        """
        Parse the JSON string starting from the current index and return parsed value.
        This method processes the JSON string character by character and delegates parsing
        to specific methods based on the encountered character type:
        - '{' -> parse_object() for dictionaries
        - '[' -> parse_array() for lists  
        - string delimiters or letters -> parse_string() for strings
        - digits or '.' or '-' -> parse_number() for numbers
        Returns:
            Union[Dict, List, str, int, float, bool, None]: The parsed JSON value which can be:
                - Dictionary for JSON objects
                - List for JSON arrays 
                - String for JSON strings
                - int/float for JSON numbers
                - bool for JSON booleans
                - None for JSON null or if parsing fails
        """
        while self.index < len(self.json_str):
            char = self.json_str[self.index]
            
            if char.isspace():
                self.index += 1
                continue
                
            if char == '{':
                self.index += 1
                return self.parse_object()
            elif char == '[':
                self.index += 1
                return self.parse_array()
            elif char in self.STRING_DELIMITERS or char.isalpha():
                return self.parse_string()
            elif char.isdigit() or char in '.-':
                return self.parse_number()
            
            self.index += 1
        
        return None

    def parse_object(self) -> Dict:
        obj = {}
        expect_key = True
        current_key = None
        
        while self.index < len(self.json_str):
            char = self.json_str[self.index]
            
            if char.isspace() or char == ',':
                self.index += 1
                continue
                
            if char == '}':
                self.index += 1
                break
                
            if expect_key:
                current_key = self._cleanup_string(self.parse_string(), is_key=True)
                expect_key = False
            elif char == ':':
                self.index += 1
            else:
                value = self.parse()
                if current_key is not None and value is not None:
                    obj[current_key] = value
                current_key = None
                expect_key = True
                
        return obj

    def parse_array(self) -> List:
        """
        Parse a JSON array from the current position in the JSON string.
        This method reads the JSON string from the current index position and parses an array,
        handling nested elements, whitespace, and commas between array elements.
        Returns:
            List: The parsed array containing JSON elements (can be nested objects, arrays, or primitive values)
        """
        arr = []
        
        while self.index < len(self.json_str):
            while self.index < len(self.json_str) and self.json_str[self.index].isspace():
                self.index += 1
                
            if self.index >= len(self.json_str) or self.json_str[self.index] == ']':
                self.index += 1
                break
                
            value = self.parse()
            if value is not None:
                arr.append(value)
                
            while self.index < len(self.json_str) and (self.json_str[self.index].isspace() or self.json_str[self.index] == ','):
                self.index += 1
                
        return arr

    def _remove_duplicate_quotes(self) -> str:
        """
        Removes consecutive duplicate quote characters (single or double quotes) from the fixed string.
        This method processes the string character by character, skipping consecutive identical
        quote characters while preserving single occurrences of quotes. The processed string
        is stored back in self.result.fixed.
        Returns:
            str: The processed string with duplicate quotes removed. If the input string is empty,
                 returns the empty string unchanged.
        Example:
            Input: "Hello""World"
            Output: "HelloWorld"
        """
        
        
        s = self.result.fixed
        if not s:
            return s
        
       
        result = ''
        prev_char = ''
        for char in s:
            if char in ['"', "'"] and prev_char == char:
                continue
            result += char
            prev_char = char
        
        print(result)
        self.result.fixed = result

    def _cleanup_string(self, s: str, is_key: bool = False) -> str:
        if not s:
            return s
            
        result = s.strip()
        
        if is_key:
            result = result.replace(':', '').replace(';', '')
        else:
            result = result.strip('"\'\\')
            
        return result

    def parse_string(self) -> str:
        """
        Parse and extract a string or number value from the JSON string starting at the current index.
        This method handles both quoted strings and unquoted values (like numbers). For quoted strings,
        it properly handles escape sequences and tracks unmatched quotes. For unquoted values, it attempts
        to convert them to integers or floats when possible.
        Returns:
            str | int | float: The parsed value. Returns:
                - For quoted strings: The cleaned string value
                - For unquoted numeric strings: int or float
                - For other unquoted strings: The stripped string value
                - Empty string if at end of input
        Side Effects:
            - Advances the index pointer to position after the parsed value
            - May update error tracking for unmatched quotes
        Example:
            "hello" -> "hello"
            hello -> "hello" 
            123 -> 123
            12.34 -> 12.34
        """
        
        if self.index >= len(self.json_str):
            return ""
            
        start_pos = self.index
        is_quoted = self.json_str[self.index] in self.STRING_DELIMITERS
        
        if is_quoted:
            quote = self.json_str[self.index]
            self.index += 1
            found_end = False
        else:
            quote = None
            
        string = ''
        escaped = False
        
        while self.index < len(self.json_str):
            char = self.json_str[self.index]
            
            if escaped:
                escaped = False
                string += char
                self.index += 1
                continue
                
            if char == '\\':
                escaped = True
                self.index += 1
                continue
                
            if is_quoted and char == quote:
                found_end = True
                self.index += 1
                break
                
            if not is_quoted:
                if char in ',:]}':
                    break
                if char.isspace() and string.strip():
                    break
                    
            string += char
            self.index += 1
        
        # Track unmatched quotes
        if is_quoted and not found_end:
            self._track_error(quote, start_pos)
            
        result = string.strip()
        
        if not is_quoted:
            try:
                if '.' in result:
                    return float(result)
                return int(result)
            except ValueError:
                pass
                
        return self._cleanup_string(result)

    def parse_number(self) -> Union[int, float]:
        """Parse a number from the JSON string at the current index.
        This method reads characters from the current index position until it encounters a 
        character that cannot be part of a valid JSON number. It supports integers, 
        floating point numbers, negative numbers, and scientific notation (e.g., 1e-10).
        Returns:
            Union[int, float]: The parsed number value. Returns integer if the number has no
            decimal point or scientific notation, float otherwise. Returns 0 if the parsing fails.
        Example:
            If json_str = "123.45" and index points to the start:
            >>> parse_number()
            123.45
        """
        number = ''
        while self.index < len(self.json_str) and (self.json_str[self.index].isdigit() or self.json_str[self.index] in '.-eE'):
            number += self.json_str[self.index]
            self.index += 1
            
        try:
            return int(number) if '.' not in number and 'e' not in number.lower() else float(number)
        except ValueError:
            return 0

    def load_json(self, text: str) -> JsonResults:
        """
        Attempts to load and parse a JSON string, handling both valid JSON and malformed JSON cases.
        This method first attempts to identify valid JSON boundaries in the input text and then
        tries to parse it. If standard parsing fails, it employs a custom parsing strategy.
        Args:
            text (str): The input text containing JSON data, which may be malformed or contain
                       surrounding non-JSON content.
        Returns:
            JsonResults: An object containing the original text, rough parsed text, and the
                        final fixed JSON string.
        Raises:
            ValueError: If no JSON-like structure (no braces or brackets) is found in the input text.
        Example:
            >>> fixer = JsonFixer()
            >>> result = fixer.load_json('{"key": "value"}')
            >>> print(result.fixed)
            {"key": "value"}
        """
        if len(text) > 10000:  # Process large inputs in parallel chunks
            chunks = self._split_into_chunks(text)
            with Pool(processes=self.max_workers) as pool:
                parsed_chunks = pool.map(_process_json_chunk, chunks)
            
            # Merge parsed chunks
            merged = {}
            for chunk in parsed_chunks:
                merged.update(chunk)
                
            result = JsonResults(text, json.dumps(merged, separators=(',', ':')))
            return result
            
        return self._process_chunk(text)

    def _split_into_chunks(self, text: str, chunk_size: int = 5000) -> List[str]:
        """
        Split a text string into chunks of specified size.
        This method divides a given text into smaller chunks, where each chunk has
        a maximum length specified by chunk_size. The last chunk might be smaller
        than chunk_size if the text length is not perfectly divisible by chunk_size.
        Args:
            text (str): The input text string to be split into chunks.
            chunk_size (int, optional): The maximum size of each chunk. Defaults to 5000.
        Returns:
            List[str]: A list of text chunks, where each chunk has a maximum length
                      of chunk_size characters.
        Example:
            >>> text = "Hello World!"
            >>> _split_into_chunks(text, 5)
            ['Hello', ' Worl', 'd!']
        """
        
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    def _process_chunk(self, chunk: str) -> JsonResults:
        """Process a chunk of text to extract and validate JSON content."""
        original = chunk
        rough = chunk.strip()
        
        self.result = JsonResults(original, rough)
        
        quote_stack = []  # [(quote_char, position)]
        bracket_stack = []  # [(bracket_char, position)]
        key_mode = True  # True when expecting a key in an object
        
        for i, char in enumerate(rough):
            # Quote handling
            if char in self.STRING_DELIMITERS:
                if not quote_stack:
                    quote_stack.append((char, i))
                else:
                    last_quote, last_pos = quote_stack[-1]
                    if char == last_quote:
                        quote_stack.pop()
                    else:

                        self._track_error(char, i)
                        self._track_error(last_quote, last_pos)
                continue
                

            if quote_stack:
                continue
                

            if char in '[{':
                bracket_stack.append((char, i))
                if char == '{':
                    key_mode = True
            elif char in ']}':
                if not bracket_stack:
                    self._track_error(char, i)
                else:
                    open_char, open_pos = bracket_stack.pop()
                    expected = ']' if open_char == '[' else '}'
                    if char != expected:
                        self._track_error(char, i)
                        self._track_error(open_char, open_pos)
            elif char == ':':
                if not key_mode:
                    self._track_error(char, i)
                key_mode = False
            elif char == ',':
                key_mode = True
                

        for quote_char, pos in quote_stack:
            self._track_error(quote_char, pos)

            self._track_error(quote_char, len(rough))


        for char, pos in bracket_stack:
            self._track_error(char, pos)

            expected = ']' if char == '[' else '}'
            self._track_error(expected, len(rough))


        try:
            if self.__has_array_before_object(rough):
                rough = rough[rough.find('['):rough.rfind(']') + 1]
            elif self.__has_minimum_one_brace(rough):
                rough = rough[rough.find('{'):rough.rfind('}') + 1]

            parsed = json.loads(rough)
            self.result.fixed = self._standardize_json(parsed)
        except json.JSONDecodeError as e:
            self._track_error(rough[e.pos], e.pos)
            try:
                parsed = self._cached_parse(rough)
                if isinstance(parsed, (list, dict)):
                    self.result.fixed = self._standardize_json(parsed)
                else:
                    self.result.fixed = str(parsed)
            except Exception as ex:
                self._track_error(str(ex), -1)
                self._save_failure(rough)
                raise ValueError("Failed to parse JSON")

        return self.result

    @staticmethod
    def _merge_results(results: List[JsonResults]) -> JsonResults:
        """Merge multiple JsonResults into one.

        Args:
            results (List[JsonResults]): A list of JsonResults objects to merge.

        Returns:
            JsonResults: A new JsonResults object containing:
                - Combined 'fixed' strings from all input results concatenated
                - Union of all 'errors' from input results

        Example:
            >>> results = [JsonResults("a", "1"), JsonResults("b", "2")]
            >>> merged = _merge_results(results)
            >>> merged.fixed == "ab"
            True
        """
        merged = JsonResults("", "")
        merged.fixed = "".join(r.fixed for r in results)
        for r in results:
            merged.errors.update(r.errors)
        return merged

    @staticmethod
    def from_file(filename: str, logging: bool = False, max_size_mb: int = 10) -> JsonResults:
        """
        Reads a JSON file and attempts to fix any formatting issues.

        Used primarily for testing purposes to load and validate JSON files.

        Args:
            filename (str): Path to the JSON file to read
            logging (bool, optional): Whether to log fixing operations. Defaults to False.
            max_size_mb (int, optional): Maximum file size in MB. Defaults to 10.

        Returns:
            JsonResults: Contains the fixed JSON data and any errors encountered

        Raises:
            ValueError: If file is too large or empty

        Example:
            >>> results = from_file("test.json")
            >>> print(results.json_str)
        """
        if not filename:
            raise ValueError("Filename cannot be None or empty")

        file_size = os.path.getsize(filename) / (1024 * 1024) 
        if file_size > max_size_mb:
            raise ValueError(f"File size ({file_size:.1f}MB) exceeds maximum allowed size ({max_size_mb}MB)")

        with open(filename, 'r') as f:
            content = f.read()
            if not content:
                raise ValueError("File is empty")
            fixer = JsonFixer(logging=logging)
            return fixer.load_json(content)
    
    @staticmethod
    def _save_failure(failed: str):
        """
        Save failed JSON string to debug file.

        Args:
            failed (str): The JSON string that failed to parse/process.

        Notes:
            Writes the failed JSON string to 'failed_json.txt' in the 'debug' directory.
            Overwrites existing file if present.
        """
        debug_dir = 'debug'
        if not os.path.exists(debug_dir):
            os.makedirs(debug_dir)
        with open(os.path.join(debug_dir, 'failed_json.txt'), 'w') as f:
            f.write(failed)



if __name__ == '__main__':
    # Example of batch processing
    jsons = [
        '{"key1": "value1"}',
        '{"key2": "value2"}',
        '{"key3": "value3"}'
    ]
    
    # Use static batch processing
    results = JsonFixer.batch_process(jsons)
    print(results)
    
    # Or process individual JSON strings    
    fixer = JsonFixer()
    for json_str in jsons:
        result = fixer.load_json(json_str)
        print(result)


# I was inspired by https://github.com/mangiucugna/json_repair but wanted to simplify and innovate on the concept