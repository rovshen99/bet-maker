import httpx
from fastapi import HTTPException


async def get_event_from_line_provider(event_id: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:8000/event/{event_id}")
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as e:
        print(f"An error occurred while requesting line-provider: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    except httpx.HTTPStatusError as e:
        print(
            f"Error response {e.response.status_code} while requesting line-provider: {str(e)}"
        )
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Event not found")
        raise HTTPException(status_code=500, detail="Internal server error")


async def get_events_from_line_provider():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/events")
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as e:
        print(f"An error occurred while requesting line-provider: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    except httpx.HTTPStatusError as e:
        print(
            f"Error response {e.response.status_code} while requesting line-provider: {str(e)}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")
