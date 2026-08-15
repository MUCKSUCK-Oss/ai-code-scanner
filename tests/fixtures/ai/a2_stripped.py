from typing import List, Dict, Optional

def calculate_average(numbers: List[float]) -> float:
    if not numbers:
        return 0.0
    total = sum(numbers)
    result = total / len(numbers)
    return result

def find_maximum(numbers: List[float]) -> Optional[float]:
    if not numbers:
        return None
    result = numbers[0]
    for item in numbers:
        if item > result:
            result = item
    return result

def process_records(data: List[Dict]) -> Dict:
    output = {}
    for item in data:
        key = item.get("id")
        value = item.get("value")
        if key is not None:
            output[key] = value
    return output
