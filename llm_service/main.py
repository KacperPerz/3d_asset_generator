# llm_service/main.py
from fastapi import FastAPI, HTTPException, Body
from openai import OpenAI
import os
import json
from pydantic import BaseModel


class PromptRequest(BaseModel):
    prompt: str

app = FastAPI()

try:
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    OPENAI_CLIENT_INITIALIZED = True
except Exception as e:
    print(f"Error initializing OpenAI client: {e}. OPENAI_API_KEY might be missing.")
    OPENAI_CLIENT_INITIALIZED = False

@app.post("/expand-prompt/")
# Using Body(..., embed=True) makes FastAPI expect {"prompt": "your prompt text"}
# Or define PromptRequest Pydantic model and use: async def expand_prompt_endpoint(request_data: PromptRequest):
async def expand_prompt_endpoint(request_data: PromptRequest):
    if not OPENAI_CLIENT_INITIALIZED:
        raise HTTPException(status_code=500, detail="OpenAI client not initialized in llm_service. Check API key.")

    user_prompt_text = request_data.prompt
    if not user_prompt_text:
        raise HTTPException(status_code=400, detail="Field 'prompt' not found in request body.")

    system_message_content = """
    You are an AI assistant that expands a user's concept for a 3D game asset
    into a detailed JSON specification. The JSON should include fields like
    'original_prompt', 'expanded_prompt', 'style_keywords', 'primary_colors',
    'materials', and 'key_features'.
    Example output:
    {
      "original_prompt": "a healing potion",
      "expanded_prompt": "A bubbling, ethereal blue liquid in a corked glass vial with elven script glowing faintly on the glass.",
      "style_keywords": ["magical", "elven", "glowing"],
      "primary_colors": ["ethereal blue", "brown (cork)", "silver (script)"],
      "materials": ["glass", "cork", "magical liquid"],
      "key_features": ["bubbling liquid", "glowing elven script"]
    }
    Ensure the output is a valid JSON object.
    """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo-preview", # Or "gpt-4", "gpt-4o"
            messages=[
                {"role": "system", "content": system_message_content},
                {"role": "user", "content": user_prompt_text}
            ],
            response_format={"type": "json_object"}
        )
        expanded_json_string = response.choices[0].message.content
        # FastAPI will automatically convert the Python dict (from json.loads) to a JSON response.
        return json.loads(expanded_json_string)
    except HTTPException: # Re-raise HTTPExceptions directly
        raise
    except Exception as e:
        print(f"Error in llm_service OpenAI call: {e}")
        raise HTTPException(status_code=500, detail=f"Error calling OpenAI in llm_service: {str(e)}")

# To run locally for testing (though uvicorn in CMD is for Docker):
# if __name__ == "__main__":
#    import uvicorn
#    uvicorn.run(app, host="0.0.0.0", port=5001) 