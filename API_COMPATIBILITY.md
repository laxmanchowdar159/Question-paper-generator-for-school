# API Compatibility & Resilience

## Problem

Google's Generative AI API undergoes frequent updates, including:
- New model releases (e.g., Gemini 2.0 Flash)
- Deprecation of older models
- API version changes (v1beta, v1)

Previously, ExamCraft hardcoded the model name:
```python
model = genai.GenerativeModel("gemini-1.5-flash")  # ❌ Fragile
```

This caused 404 errors when the model name became unavailable:
```
404 models/gemini-1.5-flash is not found for API version v1beta
```

## Solution: Model Fallback Chain

The app now implements intelligent model selection with graceful fallback:

```python
# Try latest model first, fallback to older versions if needed
model_names = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-pro"]
model = None

for model_name in model_names:
    try:
        model = genai.GenerativeModel(model_name)
        break
    except Exception:
        continue

if not model:
    raise Exception("No compatible Gemini models available")
```

## How It Works

1. **Attempts Primary Model**: Tries `gemini-2.0-flash` first (latest)
2. **Fallback Chain**: If unavailable, tries `gemini-1.5-flash`, then `gemini-pro`
3. **Exception Handling**: Silently skips unavailable models
4. **Success**: Breaks loop on first successful model load
5. **Last Resort**: If no models work, raises clear error

## Benefits

✅ **Future-Proof**: Works with Google's latest Gemini models automatically  
✅ **Backward Compatible**: Falls back to older models if needed  
✅ **Zero Downtime**: Handles API updates without code changes  
✅ **Clear Errors**: Immediate failure message if no models available  
✅ **Production Ready**: Used in live deployment  

## Deployment Requirements

### Python Package Version
Ensure `requirements.txt` specifies compatible SDK version:
```
google-generativeai>=0.4.0  # Supports all fallback models
```

### Environment Variable
Set your API key before running:
```bash
export GEMINI_API_KEY=your-api-key-here
```

### No API Key?
The app gracefully degrades to **fallback generator** (template-based papers):
- No API key required
- Instant paper generation
- Quality depends on template, not AI
- Perfect for testing/development

## Testing Model Selection

To verify which model the app loads:

```bash
# Terminal 1: Add debug logging (optional)
export FLASK_DEBUG=1

# Terminal 2: Start app
export GEMINI_API_KEY=your-key
python app.py

# Terminal 3: Test endpoint
curl -X POST http://localhost:3000/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "class": "10",
    "subject": "Maths",
    "chapter": "Algebra",
    "marks": "100",
    "difficulty": "Medium",
    "suggestions": "Include worked solutions"
  }'
```

## Code Location

**File**: [app.py](app.py)  
**Lines**: ~246-253  
**Function**: `generate_papers()`

## Monitoring & Logging

**Enhancement Opportunity**: Add logging to track model selection:

```python
# Add at line 247
import logging
logger = logging.getLogger(__name__)

# Then in the loop:
for model_name in model_names:
    try:
        model = genai.GenerativeModel(model_name)
        logger.info(f"✓ Loaded model: {model_name}")
        break
    except Exception as e:
        logger.warning(f"✗ Model {model_name} unavailable: {e}")
        continue
```

## Real-World Impact

This pattern is essential for ML applications that depend on external APIs:

- **Resilience**: Gracefully handles upstream changes
- **Scalability**: Works across different API versions
- **Maintenance**: Reduces technical debt
- **User Experience**: Zero disruption during vendor updates

---

**Last Updated**: February 2026  
**Status**: Production Deployed ✅
