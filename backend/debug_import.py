
try:
    print("Attempting to import from modelscope...")
    from modelscope import Qwen3VLForConditionalGeneration, AutoProcessor
    print("Successfully imported Qwen3VLForConditionalGeneration and AutoProcessor from modelscope")
except ImportError as e:
    print(f"Failed to import from modelscope: {e}")

try:
    print("Attempting to import from qwen_vl_utils...")
    from qwen_vl_utils import process_vision_info
    print("Successfully imported process_vision_info from qwen_vl_utils")
except ImportError as e:
    print(f"Failed to import from qwen_vl_utils: {e}")
