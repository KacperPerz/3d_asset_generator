from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
import os
import uuid
from diffusers import StableDiffusionPipeline
from PIL import Image # For saving the image

# --- Device Configuration ---
DEVICE = torch.device("cpu")
print(f"Text-to-Image Service configured to use device: {DEVICE}")

# --- Model Cache ---
PIPELINE_CACHE = {}
MODEL_ID = "segmind/tiny-sd" # Using Segmind Tiny SD

# --- Fixed Output Directory within Container ---
CONTAINER_IMAGE_OUTPUT_DIR = "/app/generated_images"
if not os.path.exists(CONTAINER_IMAGE_OUTPUT_DIR):
    os.makedirs(CONTAINER_IMAGE_OUTPUT_DIR, exist_ok=True)

# --- Pydantic Models ---
class ImageGenerationRequest(BaseModel):
    prompt: str
    num_inference_steps: int = 20
    guidance_scale: float = 7.0

class ImageGenerationResponse(BaseModel):
    status: str
    message: str | None = None
    image_local_path: str | None = None # Path to the generated image *inside the container*
    prompt_used: str | None = None

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

        PIPELINE_CACHE["sd_pipeline"] = pipeline
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
    await load_sd_pipeline() # Preload the model at startup

@app.post("/generate-image/", response_model=ImageGenerationResponse)
async def generate_image_endpoint(request: ImageGenerationRequest):
    if not request.prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    try:
        pipeline = await load_sd_pipeline() # Ensure pipeline is loaded (should be from startup)
        if not pipeline:
            raise HTTPException(status_code=503, detail="Image generation model not available.")

        print(f"Generating image for prompt: '{request.prompt}' with {request.num_inference_steps} steps, guidance {request.guidance_scale}")
        
        # Generate image
        # Note: Some pipelines might benefit from a torch.Generator for reproducibility
        image = pipeline(
            request.prompt, 
            num_inference_steps=request.num_inference_steps, 
            guidance_scale=request.guidance_scale
        ).images[0] # Take the first image from the list

        # Save the image locally
        image_filename = f"generated_image_{uuid.uuid4()}.png"
        image_local_path = os.path.join(CONTAINER_IMAGE_OUTPUT_DIR, image_filename)
        
        image.save(image_local_path, "PNG")
        print(f"Image saved locally at: {image_local_path}")

        return ImageGenerationResponse(
            status="success",
            message=f"Image generated successfully for prompt: {request.prompt}",
            image_local_path=image_local_path,
            prompt_used=request.prompt
        )
    except HTTPException:
        raise # Re-raise HTTPExceptions directly
    except Exception as e:
        print(f"Error during image generation: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating image: {str(e)}")

# To run locally (though uvicorn in CMD is for Docker):
# if __name__ == "__main__":
#    import uvicorn
#    uvicorn.run("main:app", host="0.0.0.0", port=5003, reload=True) 