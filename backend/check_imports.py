try:
    from transformers import Qwen2_5_VLForConditionalGeneration
    print("Qwen2_5_VLForConditionalGeneration imported")
except ImportError as e:
    print(f"Qwen2_5_VLForConditionalGeneration failed: {e}")
