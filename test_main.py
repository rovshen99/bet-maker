from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from main import app
import fakeredis

base_url = "http://localhost"

MOCKED_EVENT_DATA = {
    "id": "1",
    "name": "Sample Event",
    "deadline": str(datetime.now() + timedelta(minutes=2)),
    "status": "pending",
}
MOCKED_EVENTS_LIST = [
  {
    "id": "1",
    "coefficient": 1.2,
    "deadline": "2023-10-29T21:54:56.516676",
    "status": "pending"
  },
  {
    "id": "2",
    "coefficient": 1.15,
    "deadline": "2023-10-29T21:45:56.517540",
    "status": "pending"
  },
]
MOCKED_BET_ID = 123


@pytest.mark.asyncio
@patch("main.redis", return_value=fakeredis.FakeStrictRedis())
@patch("main.get_event_from_line_provider", return_value=MOCKED_EVENT_DATA)
async def test_create_bet(mock_get_event, mock_fakeredis):
    async with AsyncClient(app=app, base_url=base_url) as client:
        mock_fakeredis.incr.return_value = MOCKED_BET_ID

        bet_data = {
            "event_id": "1",
            "amount": 10.5
        }

        response = await client.post("/bet", json=bet_data)

        assert response.status_code == 200

        response_data = response.json()
        assert "id" in response_data
        assert response_data["event_id"] == bet_data["event_id"]
        assert response_data["amount"] == bet_data["amount"]
        assert response_data["status"] == "pending"


@pytest.mark.asyncio
@patch("main.redis", return_value=fakeredis.FakeStrictRedis())
@patch("main.get_event_from_line_provider", return_value=MOCKED_EVENT_DATA)
async def test_get_bets(mock_get_event, mock_fakeredis):
    async with AsyncClient(app=app, base_url=base_url) as client:
        response = await client.get("/bets")

        assert response.status_code == 200

        assert isinstance(response.json(), list)


# @patch("main.get_events_from_line_provider", return_value=MOCKED_EVENTS_LIST)
# @pytest.mark.asyncio
# async def test_get_events(mock_get_events_from_line_provider):
#     async with AsyncClient(app=app, base_url=base_url) as client:
#         response = await client.get("/events")
#
#         assert response.status_code == 200
#
#         assert isinstance(response.json(), list)


@pytest.mark.asyncio
@patch("main.redis", return_value=fakeredis.FakeStrictRedis())
@patch("main.get_event_from_line_provider", return_value=MOCKED_EVENT_DATA)
async def test_create_bet_invalid_amount(mock_get_event, mock_fakeredis):
    async with AsyncClient(app=app, base_url=base_url) as client:
        bet_data = {
            "event_id": "1",
            "amount": 10.555
        }
        response = await client.post("/bet", json=bet_data)

        assert response.status_code == 422

        response_data = response.json()
        assert "detail" in response_data
        assert "Amount must have two decimal places" == response_data["detail"][0]["msg"]


@pytest.mark.asyncio
@patch("main.redis", return_value=fakeredis.FakeStrictRedis())
@patch("main.get_event_from_line_provider")
async def test_create_bet_event_finished(mock_get_event, mock_fakeredis):
    mock_finished_event = {
        "id": "1",
        "name": "Sample Event",
        "deadline": str(datetime.now() - timedelta(minutes=2)),
        "status": "lose",
    }
    mock_get_event.return_value = mock_finished_event
    async with AsyncClient(app=app, base_url="http://localhost") as client:
        mock_fakeredis.incr.return_value = MOCKED_BET_ID
        bet_data = {
            "event_id": "1",
            "amount": 10.5
        }
        response = await client.post("/bet", json=bet_data)

        assert response.status_code == 400

        response_data = response.json()
        assert "detail" in response_data
        assert "Betting deadline for this event has passed or event has finished" in response_data["detail"]