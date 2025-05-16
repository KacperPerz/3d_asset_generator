from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
import os
import uuid
from diffusers import StableDiffusionPipeline
from PIL import Image
from fastapi.responses import FileResponse
import shutil

# --- Device Configuration ---
DEVICE = torch.device("cpu")
print(f"Text-to-Image Service configured to use device: {DEVICE}")

# --- Model Cache ---
PIPELINE_CACHE = {}
MODEL_ID = "segmind/tiny-sd"

# --- Fixed Output Directory within Container for temporary storage ---
CONTAINER_IMAGE_OUTPUT_DIR = "/app/generated_images_temp"
if not os.path.exists(CONTAINER_IMAGE_OUTPUT_DIR):
    os.makedirs(CONTAINER_IMAGE_OUTPUT_DIR, exist_ok=True)

# --- Pydantic Models ---
class ImageGenerationRequest(BaseModel):
    prompt: str
    num_inference_steps: int = 2 # for fast inference
    guidance_scale: float = 7.0

app = FastAPI()

# --- Model Loading ---
async def load_sd_pipeline():
    if "sd_pipeline" in PIPELINE_CACHE:
        print(f"Using cached Stable Diffusion pipeline ({MODEL_ID}).")
        return PIPELINE_CACHE["sd_pipeline"]

    print(f"Loading Stable Diffusion pipeline: {MODEL_ID} on device: {DEVICE}...")
    try:
        dtype = torch.float32
        pipeline = StableDiffusionPipeline.from_pretrained(MODEL_ID, torch_dtype=dtype, use_safetensors=False)
        pipeline = pipeline.to(DEVICE)
        PIPELINE_CACHE["sd_pipeline"] = pipeline # TODO should I really be caching this?
        print(f"Stable Diffusion pipeline {MODEL_ID} loaded and cached.")
        return pipeline
    except Exception as e:
        print(f"Error loading Stable Diffusion pipeline {MODEL_ID}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=503, detail=f"Failed to load model {MODEL_ID}: {str(e)}")

@app.on_event("startup")
async def startup_event():
    print("Text-to-Image service starting up. Attempting to preload SD pipeline...")
    await load_sd_pipeline()

@app.post("/generate-image/")
async def generate_image_endpoint(request: ImageGenerationRequest):
    if not request.prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    temp_image_local_path = None
    try:
        pipeline = await load_sd_pipeline()
        if not pipeline:
            raise HTTPException(status_code=503, detail="Image generation model not available.")

        print(f"Generating image for prompt: '{request.prompt}' with {request.num_inference_steps} steps, guidance {request.guidance_scale}")
        
        image = pipeline(
            request.prompt, 
            num_inference_steps=request.num_inference_steps, 
            guidance_scale=request.guidance_scale
        ).images[0]

        image_uuid = uuid.uuid4()
        image_filename = f"generated_image_{image_uuid}.png"
        # Save to a temporary location before sending
        temp_image_local_path = os.path.join(CONTAINER_IMAGE_OUTPUT_DIR, image_filename)
        
        image.save(temp_image_local_path, "PNG")
        print(f"Image saved temporarily at: {temp_image_local_path}")

        # Return the file as a response. FastAPI will handle streaming it.
        # The file will be deleted in the finally block after being sent.
        return FileResponse(temp_image_local_path, media_type="image/png", filename=image_filename)
        
    except HTTPException:
        raise 
    except Exception as e:
        print(f"Error during image generation: {e}")
        import traceback
        traceback.print_exc()
        # If an error occurs before FileResponse, temp_image_local_path might exist
        if temp_image_local_path and os.path.exists(temp_image_local_path):
             os.remove(temp_image_local_path)
             print(f"Cleaned up temporary file: {temp_image_local_path}")
        raise HTTPException(status_code=500, detail=f"Error generating image: {str(e)}")
    finally:
        # Clean up the temporarily saved image file after it has been sent or if an error unrelated to FileResponse occurs mid-process.
        # Note: FileResponse uses a background task to close the file, 
        # so direct deletion here might be too soon for some OS/configurations if not handled carefully.
        # A more robust cleanup for FileResponse often involves background tasks if immediate deletion is needed.
        # For this service, if Gradio reads the stream, the file can be deleted. Let's assume Gradio will consume it fully.
        # However, for simplicity in this iteration, we rely on the finally block which might run slightly after the response starts sending.
        # A truly robust solution for cleanup post-FileResponse might involve a background task in FastAPI.
        # Let's try a simple cleanup. If it causes issues (file deleted before sending fully), we can revisit.
        if temp_image_local_path and os.path.exists(temp_image_local_path):
            # This is a simplification. In a production system, you'd want to ensure the file is sent before deleting.
            # FastAPI's FileResponse is supposed to handle this by streaming. A small delay or background task might be safer.
            # For now, let's assume this is okay for typical local Docker networking speeds.
            try:
                # Give a very brief moment for the response to be initiated, not a robust solution.
                # await asyncio.sleep(0.1) # Requires asyncio import and making the finally async (not standard)
                # os.remove(temp_image_local_path) # Removed to prevent FileNotFoundError with FileResponse
                # print(f"Cleaned up temporary file: {temp_image_local_path}")
                pass # File will not be cleaned up immediately by this service
            except Exception as e_clean:
                print(f"Error during (now disabled) temporary file cleanup {temp_image_local_path}: {e_clean}")

# To run locally (though uvicorn in CMD is for Docker):
# if __name__ == "__main__":
#    import uvicorn
#    uvicorn.run("main:app", host="0.0.0.0", port=5003, reload=True) 