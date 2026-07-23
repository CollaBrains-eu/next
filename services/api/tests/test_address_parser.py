from api.address_parser import build_maps_url, find_full_address_matches, parse_address


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


def test_find_full_address_matches_finds_address_in_surrounding_prose():
    text = "Informationen zu Ihrem Termin\n\nWo?\nJahnstr. 6, 26789 Leer\nRaum: Wartebereich"
    assert find_full_address_matches(text) == ["Jahnstr. 6, 26789 Leer"]


def test_find_full_address_matches_returns_empty_list_when_no_full_address():
    text = "Bitte bringen Sie Ihr Ausweisdokument mit. Halten Sie Ihre Rentenversicherungsnummer bereit."
    assert find_full_address_matches(text) == []


def test_find_full_address_matches_ignores_bare_numbers_in_prose():
    text = "Zie pagina 5 voor meer informatie, artikel 12 lid 3 is van toepassing."
    assert find_full_address_matches(text) == []
