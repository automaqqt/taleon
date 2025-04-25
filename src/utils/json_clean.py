import json
import re
import ast
from json.decoder import JSONDecodeError

def robust_json_load(json_string):
    """
    Try multiple approaches to load potentially malformed JSON data.
    Returns the parsed data or None if all methods fail.
    """
    # Attempt 1: Direct JSON loading (fastest if it works)
    try:
        return json.loads(json_string)
    except JSONDecodeError:
        pass
    
    # Attempt 2: Clean and fix common JSON issues
    try:
        cleaned_json = clean_json_string(json_string)
        return json.loads(cleaned_json)
    except (JSONDecodeError, Exception):
        pass
    
    # Attempt 3: Try using ast.literal_eval if it looks like a Python dict/list
    try:
        if (json_string.strip().startswith('{') and json_string.strip().endswith('}')) or \
           (json_string.strip().startswith('[') and json_string.strip().endswith(']')):
            return ast.literal_eval(json_string)
    except (SyntaxError, ValueError):
        pass
    
    # All methods failed
    return None

def clean_json_string(json_string):
    """Clean and repair common JSON issues."""
    # Handle non-string inputs
    if not isinstance(json_string, str):
        if isinstance(json_string, bytes):
            json_string = json_string.decode('utf-8', errors='replace')
        else:
            json_string = str(json_string)
    
    # Remove user style tags and other custom tags
    json_string = re.sub(r'<userStyle>.*?</userStyle>', '', json_string)
    json_string = re.sub(r'<\|[^>]+\|>', '', json_string)
    json_string = re.sub(r'<[a-zA-Z0-9_]+>.*?</[a-zA-Z0-9_]+>', '', json_string)
    
    # Fix escape sequences in the text
    # First, temporarily replace valid escape sequences
    placeholders = {
        '\\\\': '__DOUBLE_BACKSLASH__',
        '\\"': '__ESCAPED_QUOTE__',
        '\\n': '__NEWLINE__',
        '\\t': '__TAB__',
        '\\r': '__RETURN__',
        '\\b': '__BACKSPACE__',
        '\\f': '__FORMFEED__'
    }
    
    for escape_seq, placeholder in placeholders.items():
        json_string = json_string.replace(escape_seq, placeholder)
    
    # Now handle the problematic escape sequence: backslash followed by quote
    # This is tricky because we want to preserve actual quotes in the text
    json_string = json_string.replace('\"', '\\"')
    
    # Restore valid escape sequences
    for escape_seq, placeholder in placeholders.items():
        json_string = json_string.replace(placeholder, escape_seq)
    
    # Fix unquoted keys
    json_string = re.sub(r'([{,])\s*([a-zA-Z0-9_]+)\s*:', r'\1"\2":', json_string)
    
    # Replace single quotes with double quotes for property values
    json_string = re.sub(r':\s*\'(.*?)\'', r':"\1"', json_string)
    
    # Remove trailing commas
    json_string = re.sub(r',\s*([}\]])', r'\1', json_string)
    
    return json_string

def robust_json_load(json_string):
    """Try multiple approaches to load potentially malformed JSON data."""
    # Attempt 1: Direct JSON loading
    try:
        return json.loads(json_string)
    except JSONDecodeError:
        pass
    
    # Attempt 2: Clean and fix common JSON issues
    try:
        cleaned_json = clean_json_string(json_string)
        return json.loads(cleaned_json)
    except (JSONDecodeError, Exception) as e:
        print(f"Error after initial cleaning: {e}")
        
        # Attempt 3: More aggressive cleaning - replace all escape characters
        try:
            # Replace problematic backslashes before quotes
            aggressive_clean = cleaned_json.replace('\\', '\\\\').replace('\\"', '"')
            # Then ensure all internal quotes are properly escaped
            aggressive_clean = aggressive_clean.replace('"', '\\"')
            # Fix the outermost quotes (first and last in the string)
            if aggressive_clean.startswith('\\"'):
                aggressive_clean = '"' + aggressive_clean[2:]
            if aggressive_clean.endswith('\\"'):
                aggressive_clean = aggressive_clean[:-2] + '"'
            
            return json.loads(aggressive_clean)
        except (JSONDecodeError, Exception) as e2:
            print(f"Error after aggressive cleaning: {e2}")
            
            # Attempt 4: Manual parsing as last resort
            try:
                # Find the main content between outer braces
                match = re.search(r'\{(.*)\}', json_string, re.DOTALL)
                if match:
                    inner_content = match.group(1)
                    
                    # Extract key-value pairs
                    result = {}
                    
                    # Split by top-level commas (not those inside nested structures)
                    pairs = []
                    current = ""
                    brace_level = 0
                    bracket_level = 0
                    quote_mode = False
                    escape_next = False
                    
                    for char in inner_content:
                        if escape_next:
                            current += char
                            escape_next = False
                            continue
                            
                        if char == '\\':
                            current += char
                            escape_next = True
                            continue
                            
                        if char == '"' and not escape_next:
                            quote_mode = not quote_mode
                            
                        if not quote_mode:
                            if char == '{':
                                brace_level += 1
                            elif char == '}':
                                brace_level -= 1
                            elif char == '[':
                                bracket_level += 1
                            elif char == ']':
                                bracket_level -= 1
                                
                        if char == ',' and brace_level == 0 and bracket_level == 0 and not quote_mode:
                            pairs.append(current.strip())
                            current = ""
                        else:
                            current += char
                            
                    if current.strip():
                        pairs.append(current.strip())
                    
                    # Process each key-value pair
                    for pair in pairs:
                        parts = pair.split(':', 1)
                        if len(parts) == 2:
                            key = parts[0].strip().strip('"')
                            value = parts[1].strip()
                            
                            # Try to parse the value
                            try:
                                if value.startswith('[') and value.endswith(']'):
                                    # It's an array
                                    items = []
                                    item_content = value[1:-1].strip()
                                    
                                    # Split the array items
                                    array_items = []
                                    current_item = ""
                                    a_brace_level = 0
                                    a_bracket_level = 0
                                    a_quote_mode = False
                                    a_escape_next = False
                                    
                                    for char in item_content:
                                        if a_escape_next:
                                            current_item += char
                                            a_escape_next = False
                                            continue
                                            
                                        if char == '\\':
                                            current_item += char
                                            a_escape_next = True
                                            continue
                                            
                                        if char == '"' and not a_escape_next:
                                            a_quote_mode = not a_quote_mode
                                            
                                        if not a_quote_mode:
                                            if char == '{':
                                                a_brace_level += 1
                                            elif char == '}':
                                                a_brace_level -= 1
                                            elif char == '[':
                                                a_bracket_level += 1
                                            elif char == ']':
                                                a_bracket_level -= 1
                                                
                                        if char == ',' and a_brace_level == 0 and a_bracket_level == 0 and not a_quote_mode:
                                            array_items.append(current_item.strip())
                                            current_item = ""
                                        else:
                                            current_item += char
                                            
                                    if current_item.strip():
                                        array_items.append(current_item.strip())
                                    
                                    # Process each array item
                                    for item in array_items:
                                        item = item.strip()
                                        if item.startswith('"') and item.endswith('"'):
                                            items.append(item[1:-1].replace('\\"', '"'))
                                        else:
                                            items.append(item)
                                    
                                    result[key] = items
                                else:
                                    # It's a scalar value
                                    if value.startswith('"') and value.endswith('"'):
                                        result[key] = value[1:-1].replace('\\"', '"')
                                    else:
                                        result[key] = value
                            except Exception as e3:
                                print(f"Error parsing value for key {key}: {e3}")
                                result[key] = value
                    
                    return result
            except Exception as e4:
                print(f"Error during manual parsing: {e4}")
    
    # All methods failed
    return None

def parse_json_with_recovery(file_path, encoding='utf-8'):
    """
    Parse a JSON file with recovery mechanisms for malformed JSON.
    Returns the parsed data or None if unable to parse.
    """
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            json_string = f.read()
        
        return robust_json_load(json_string)
    
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return None
    except Exception as e:
        print(f"Error reading or parsing file: {e}")
        return None

def stream_repair_json(file_path, output_path=None, encoding='utf-8'):
    """
    Stream read a large JSON file and attempt to repair/clean it.
    Useful for very large files that won't fit in memory.
    """
    if output_path is None:
        output_path = file_path + '.fixed.json'
    
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            # Check if the file starts with an array
            content_start = f.read(1000)  # Read a sample
            f.seek(0)  # Go back to start
            
            is_array = content_start.lstrip().startswith('[')
            if not is_array:
                # If not an array, process the whole file at once
                json_string = f.read()
                result = robust_json_load(json_string)
                
                if result:
                    with open(output_path, 'w', encoding=encoding) as out:
                        json.dump(result, out, ensure_ascii=False, indent=2)
                    return True
                return False
            
            # It's an array, process objects individually
            with open(output_path, 'w', encoding=encoding) as out:
                out.write('[\n')  # Start array
                
                # Track object boundaries
                in_object = False
                object_text = ""
                first_object = True
                bracket_count = 0
                
                for line in f:
                    for char in line:
                        if not in_object and char == '{':
                            in_object = True
                            bracket_count = 1
                            object_text = char
                        elif in_object:
                            object_text += char
                            if char == '{':
                                bracket_count += 1
                            elif char == '}':
                                bracket_count -= 1
                                
                            # Complete object found
                            if bracket_count == 0:
                                in_object = False
                                
                                # Process individual object
                                cleaned_object = clean_json_string(object_text)
                                try:
                                    # Validate it parses correctly
                                    obj = json.loads(cleaned_object)
                                    
                                    # Write to output file
                                    if not first_object:
                                        out.write(',\n')
                                    else:
                                        first_object = False
                                        
                                    json.dump(obj, out, ensure_ascii=False, indent=2)
                                except JSONDecodeError:
                                    print(f"Warning: Couldn't fix object: {object_text[:50]}...")
                                
                                object_text = ""
                
                out.write('\n]')  # End array
            
            return True
    
    except Exception as e:
        print(f"Error processing file: {e}")
        return False

if __name__ == "__main__":
    # Example 1: LLM Output with custom tags
    llm_json = """{"storySegment": "Ein leichter Morgennebel hing noch über dem Wald, als Rotkäppchen mit dem Korb voller selbstgebackenem Kuchen und Wein den schmalen Pfad zur Großmutter einschlug.", "choices": ["Option A", "Option B", "Option C"]} <|end_header_id|>"""
    
    # Process and show the result
    result = robust_json_load(llm_json)
    if result:
        print("Successfully parsed JSON with custom tags:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Failed to parse JSON with custom tags")
    
    # Example 2: JSON with markdown formatting
    markdown_json = """```json
    {"storySegment": "Story text here", "choices": ["A", "B", "C"]}
    ```"""
    
    # Process and show the result
    result2 = robust_json_load(markdown_json)
    if result2:
        print("\nSuccessfully parsed JSON with markdown formatting:")
        print(json.dumps(result2, indent=2, ensure_ascii=False))
    else:
        print("\nFailed to parse JSON with markdown formatting")
    
    # Example 3: JSON with unquoted keys and single quotes
    problem_json = """
    {
        name: 'John',
        "age": 30,
        'hobbies': ["reading", "coding",],
        "address": {
            'city': "New York",
            "zip": 10001,
        }
    }
    """
    
    # Process and show the result
    result3 = robust_json_load(problem_json)
    if result3:
        print("\nSuccessfully parsed JSON with formatting issues:")
        print(json.dumps(result3, indent=2, ensure_ascii=False))
    else:
        print("\nFailed to parse JSON with formatting issues")