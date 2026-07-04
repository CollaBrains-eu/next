from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from api.rdw_client import RdwLookupError, fetch_vehicle_data

FAKE_VEHICLE_ROW = {
    "voertuigsoort": "Personenauto",
    "merk": "TOYOTA",
    "handelsbenaming": "AYGO",
    "eerste_kleur": "GRIJS",
    "datum_eerste_toelating": "20180501",
    "vervaldatum_apk": "20270501",
    "wam_verzekerd": "Ja",
    "openstaande_terugroepactie_indicator": "Nee",
    "massa_ledig_voertuig": "840",
    "aantal_cilinders": "3",
    "wielbasis": "2340",
    "catalogusprijs": "12500",
    "aantal_zitplaatsen": "4",
    "aantal_deuren": "5",
    "vermogen_massarijklaar": "51",
    "lengte": "3455",
    "europese_voertuigcategorie": "M1",
}
FAKE_FUEL_ROW = {"brandstof_omschrijving": "Benzine"}


def _mock_response(json_data, status_code=200):
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_data
    response.raise_for_status = MagicMock()
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=response
        )
    return response


async def test_fetch_vehicle_data_returns_merged_vehicle_and_fuel_fields():
    vehicle_response = _mock_response([FAKE_VEHICLE_ROW])
    fuel_response = _mock_response([FAKE_FUEL_ROW])

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[vehicle_response, fuel_response])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("api.rdw_client.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_vehicle_data("AB12CD")

    assert result["merk"] == "TOYOTA"
    assert result["handelsbenaming"] == "AYGO"
    assert result["brandstofomschrijving"] == "Benzine"


async def test_fetch_vehicle_data_returns_none_when_rdw_has_no_record():
    vehicle_response = _mock_response([])

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=vehicle_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("api.rdw_client.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_vehicle_data("ZZ99ZZ")

    assert result is None


async def test_fetch_vehicle_data_raises_rdw_lookup_error_on_http_error():
    error_response = _mock_response({}, status_code=500)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=error_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("api.rdw_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RdwLookupError):
            await fetch_vehicle_data("AB12CD")


async def test_fetch_vehicle_data_raises_rdw_lookup_error_on_timeout():
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("api.rdw_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RdwLookupError):
            await fetch_vehicle_data("AB12CD")
