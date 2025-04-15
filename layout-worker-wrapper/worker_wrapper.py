from fastapi import FastAPI
import uvicorn
import httpx

app = FastAPI()

@app.get("/layout")
async def layout(
    image_url: str,
    auto_deskew: bool = False,
    auto_bg_removal: bool = True,
    auto_denoise: bool = True,
    text_x_height_pixels: int = -1,
    # try_download_image: bool = False,
    ):
    """
    Simple wrapper for the real layout service.
    Download the image from the given URL and send it to the layout service.
    Layout service will return the layout of the image as a JSON object.
    We must send the image using a binary POST request.
    """

    # Debug output
    print(f"image_url: {image_url}")

    async with httpx.AsyncClient() as client:
        response = await client.get(image_url, timeout=10.0)
        if response.status_code == 200:
            # Debug output
            print(f"image downloaded: {len(response.content)} bytes")
            # Send the image to the layout service
            layout_service_url = "http://layout-worker:8000/imgproc/layout"
            layout_response = await client.post(
                layout_service_url,
                content=response.content,
                # headers={"Content-Type": "application/octet-stream"},
            )
            if layout_response.status_code == 200:
                return layout_response.json()
            else:
                return {
                    "message": "layout server error",
                    "status_code": layout_response.status_code,
                    "content": layout_response.content,
                    }
        else:
            return {
                "message": "image server error",
                "status_code": response.status_code,
                "content": response.content,
                }
    


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
