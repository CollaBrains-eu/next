from api.address_parser import build_maps_url, parse_address


def test_parses_street_and_house_number_only():
    assert parse_address("Achterweg 15") == {
        "street": "Achterweg", "house_number": "15",
        "postal_code": None, "city": None, "country": None,
    }


def test_parses_nl_postal_code_and_city_only():
    assert parse_address("9671 CT WINSCHOTEN") == {
        "street": None, "house_number": None,
        "postal_code": "9671 CT", "city": "WINSCHOTEN", "country": "NL",
    }


def test_parses_de_postal_code_and_city_only():
    assert parse_address("26831 Bunde") == {
        "street": None, "house_number": None,
        "postal_code": "26831", "city": "Bunde", "country": "DE",
    }


def test_parses_full_nl_address_in_one_string():
    result = parse_address("Gaslaan 16, 9671 CT Winschoten")
    assert result == {
        "street": "Gaslaan", "house_number": "16",
        "postal_code": "9671 CT", "city": "Winschoten", "country": "NL",
    }


def test_parses_full_address_without_comma():
    result = parse_address("Gaslaan 16 9671 CT Winschoten")
    assert result["street"] == "Gaslaan"
    assert result["house_number"] == "16"
    assert result["postal_code"] == "9671 CT"
    assert result["city"] == "Winschoten"


def test_unparseable_text_returns_all_none():
    assert parse_address("Beschermingsbewind@vkb.nl") == {
        "street": None, "house_number": None,
        "postal_code": None, "city": None, "country": None,
    }


def test_build_maps_url_from_full_address():
    url = build_maps_url(
        street="Gaslaan", house_number="16", postal_code="9671 CT",
        city="Winschoten", country="NL",
    )
    assert url == (
        "https://www.google.com/maps/search/?api=1&query="
        "Gaslaan%2016%2C%209671%20CT%2C%20Winschoten%2C%20NL"
    )


def test_build_maps_url_returns_none_for_insufficient_data():
    assert build_maps_url(street=None, house_number=None, postal_code=None, city=None, country="NL") is None
