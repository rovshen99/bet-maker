import asyncio
import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Union

import aio_pika
import aioredis
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

from services import get_event_from_line_provider, get_events_from_line_provider


redis = aioredis.from_url("redis://localhost:6379")
app = FastAPI()


class BetStatus(str, Enum):
    PENDING = "pending"
    WIN = "win"
    LOSE = "lose"

def validate_amount(v):
    if round(v, 2) != v:
        raise ValueError("Amount must have two decimal places")
    return v


class BetCreate(BaseModel):
    event_id: str
    amount: float = Field(
        gt=0, description="A strictly positive number with two decimal places"
    )
    _validate_amount = validator("amount", allow_reuse=True)(validate_amount)


class Bet(BaseModel):
    id: str
    event_id: str
    amount: float = Field(
        gt=0, description="A strictly positive number with two decimal places"
    )
    status: BetStatus = BetStatus.PENDING
    _validate_amount = validator("amount", allow_reuse=True)(validate_amount)


async def on_message(message: aio_pika.IncomingMessage) -> None:
    async with message.process():
        try:
            data = json.loads(message.body)
            event_id = data["event_id"]
            status = data["status"]
            keys = await redis.keys(f"bet:*:{event_id}")
            for key in keys:
                await redis.hset(key, "status", status)
            print(f"Received message: {data}")
        except Exception as e:
            print(f"Failed to process message: {e}")


async def consume_messages():
    try:
        connection = await aio_pika.connect("amqp://guest:guest@localhost:5672/")
        channel = await connection.channel()
        queue = await channel.declare_queue("events", durable=True)
        await queue.consume(on_message)
        print("Waiting for messages...")
        await asyncio.Future()
    except Exception as e:
        print(f"Failed to connect to RabbitMQ: {e}")


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(consume_messages())


@app.post("/bet", response_model=Bet)
async def make_bet(bet: BetCreate) -> Union[Bet, JSONResponse]:
    try:
        event = await get_event_from_line_provider(bet.event_id)
        if (
            datetime.fromisoformat(event["deadline"]) <= datetime.now()
            or event["status"] != BetStatus.PENDING
        ):
            return JSONResponse(
                content={
                    "detail": "Betting deadline for this event has passed or event has finished"
                },
                status_code=400,
            )

        bet_id = await redis.incr("bet_id")
        new_bet = Bet(
            id=str(bet_id),
            event_id=bet.event_id,
            amount=bet.amount,
            status=BetStatus.PENDING,
        )
        await redis.hmset(
            f"bet:{bet_id}:{bet.event_id}",
            {"amount": new_bet.amount, "status": new_bet.status.value},
        )
        return new_bet
    except HTTPException as e:
        return JSONResponse(content={"detail": e.detail}, status_code=e.status_code)
    except Exception as e:
        print(f"Failed to make a bet: {e}")
        return JSONResponse(
            content={"detail": "Internal server error"}, status_code=500
        )


@app.get("/bets", response_model=List[Bet])
async def get_bets() -> Union[List[Bet], JSONResponse]:
    try:
        bets = []
        keys = await redis.keys("bet:*")
        for key in keys:
            bet_data = await redis.hgetall(key)
            bet = Bet(
                id=key.decode("utf-8").split(":")[1],
                event_id=key.decode("utf-8").split(":")[2],
                amount=float(bet_data[b"amount"]),
                status=BetStatus(bet_data[b"status"].decode("utf-8")),
            )
            bets.append(bet)
        return bets
    except Exception as e:
        print(f"Failed to get bets: {e}")
        return JSONResponse(
            content={"detail": "Internal server error"}, status_code=500
        )


@app.get("/events")
async def get_events(
    events: List[Dict[str, Any]] = Depends(get_events_from_line_provider)
) -> List[Dict[str, Any]]:
    filtered_events = [
        event
        for event in events
        if datetime.fromisoformat(event["deadline"]) > datetime.now()
    ]
    return filtered_events


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
