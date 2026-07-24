from api.email_templates import (
    onboarding_welcome_html,
    onboarding_welcome_subject,
    onboarding_welcome_text,
    welcome_joined_org_html,
    welcome_joined_org_subject,
    welcome_joined_org_text,
    welcome_new_org_html,
    welcome_new_org_subject,
    welcome_new_org_text,
)


def test_welcome_new_org_subject_includes_display_name():
    subject = welcome_new_org_subject(display_name="Ada Lovelace", preferred_language="en")
    assert "Ada Lovelace" in subject


def test_welcome_new_org_html_includes_organization_name_and_cta_link():
    html = welcome_new_org_html(display_name="Ada", organization_name="Acme Legal", preferred_language="en")
    assert "Acme Legal" in html
    assert "https://collabrains.eu/" in html
    assert "<html>" in html


def test_welcome_new_org_falls_back_to_english_for_unsupported_locale():
    en_html = welcome_new_org_html(display_name="Ada", organization_name="Acme", preferred_language="en")
    unknown_html = welcome_new_org_html(display_name="Ada", organization_name="Acme", preferred_language="fr")
    assert en_html == unknown_html


def test_welcome_new_org_falls_back_to_english_when_language_is_none():
    en_html = welcome_new_org_html(display_name="Ada", organization_name="Acme", preferred_language="en")
    none_html = welcome_new_org_html(display_name="Ada", organization_name="Acme", preferred_language=None)
    assert en_html == none_html


def test_welcome_new_org_supports_dutch_and_german():
    nl_html = welcome_new_org_html(display_name="Ada", organization_name="Acme", preferred_language="nl")
    de_html = welcome_new_org_html(display_name="Ada", organization_name="Acme", preferred_language="de")
    en_html = welcome_new_org_html(display_name="Ada", organization_name="Acme", preferred_language="en")
    assert nl_html != en_html
    assert de_html != en_html
    assert "Welkom" in nl_html
    assert "Willkommen" in de_html


def test_welcome_new_org_text_has_no_html_tags():
    text = welcome_new_org_text(display_name="Ada", organization_name="Acme", preferred_language="en")
    assert "<" not in text
    assert "Acme" in text


def test_welcome_joined_org_subject_includes_organization_name():
    subject = welcome_joined_org_subject(organization_name="Acme Legal", preferred_language="en")
    assert "Acme Legal" in subject


def test_welcome_joined_org_html_includes_display_name_and_organization_name():
    html = welcome_joined_org_html(display_name="Grace", organization_name="Acme Legal", preferred_language="en")
    assert "Grace" in html
    assert "Acme Legal" in html


def test_welcome_joined_org_text_has_no_html_tags():
    text = welcome_joined_org_text(display_name="Grace", organization_name="Acme", preferred_language="de")
    assert "<" not in text
    assert "Acme" in text


def test_new_org_and_joined_org_copy_are_distinct():
    new_org = welcome_new_org_html(display_name="Ada", organization_name="Acme", preferred_language="en")
    joined_org = welcome_joined_org_html(display_name="Ada", organization_name="Acme", preferred_language="en")
    assert new_org != joined_org


def test_onboarding_welcome_subject_includes_display_name():
    subject = onboarding_welcome_subject(display_name="Ada Lovelace", preferred_language="en")
    assert "Ada Lovelace" in subject


def test_onboarding_welcome_html_includes_onboard_url_and_branded_wrapper():
    html = onboarding_welcome_html(
        display_name="Ada", onboard_url="https://collabrains.eu/onboard?token=abc123", preferred_language="en"
    )
    assert "https://collabrains.eu/onboard?token=abc123" in html
    assert "<html>" in html


def test_onboarding_welcome_falls_back_to_english_for_unsupported_locale():
    en_html = onboarding_welcome_html(
        display_name="Ada", onboard_url="https://collabrains.eu/onboard?token=abc", preferred_language="en"
    )
    unknown_html = onboarding_welcome_html(
        display_name="Ada", onboard_url="https://collabrains.eu/onboard?token=abc", preferred_language="fr"
    )
    assert en_html == unknown_html


def test_onboarding_welcome_supports_dutch_and_german():
    url = "https://collabrains.eu/onboard?token=abc"
    nl_html = onboarding_welcome_html(display_name="Ada", onboard_url=url, preferred_language="nl")
    de_html = onboarding_welcome_html(display_name="Ada", onboard_url=url, preferred_language="de")
    assert "Welkom" in nl_html
    assert "Willkommen" in de_html


def test_onboarding_welcome_text_has_no_html_tags_and_includes_url():
    text = onboarding_welcome_text(
        display_name="Ada", onboard_url="https://collabrains.eu/onboard?token=abc123", preferred_language="en"
    )
    assert "<" not in text
    assert "https://collabrains.eu/onboard?token=abc123" in text
