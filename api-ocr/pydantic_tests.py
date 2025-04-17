# Pydantixc tests
from datatypes import ImageRegion

from pydantic import ValidationError


def main():
    test_str = '{"xtl": 0.0, "ytl": 0.0, "xbr": 100.0, "ybr": 100.0}'

    # Try to parse the JSON string with Pydantic
    try:
        parsed_region = ImageRegion.model_validate_json(test_str)
        print("Parsed region:", parsed_region)
    except ValidationError as e:
        print("Error parsing JSON:", e)
    
    # Convert the Pydantic model to a JSON string
    try:
        json_str = parsed_region.model_dump_json()
        print("JSON string:", json_str)
    except Exception as e:
        print("Error converting to JSON:", e)

if __name__ == "__main__":
    main()
