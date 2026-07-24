"""Branded HTML template for "welcome" emails (Violet design system).

Every other transactional email in this codebase (verification, invitation,
payment-failed, onboarding-link) sends a bare `<p>`-tag fragment with no
styling -- this module is the first visually-branded template, scoped to
welcome emails specifically rather than retrofitting the others.

Pure rendering only: no I/O, no `send_email` import. Each service module
that needs a welcome email (registration_service.py, invitation_service.py)
imports the functions it needs and passes the result to its own
`send_*_email` wrapper, matching how every other email in the codebase is
composed and sent.

Table-based layout with inline styles throughout, a solid `background-color`
fallback behind every `linear-gradient`, and no external CSS/JS -- Outlook's
Word-based rendering engine ignores CSS gradients and strips <style> blocks
entirely, so this degrades to solid brand-purple rather than an unstyled or
broken email there.
"""
from api.config import settings

LOGO_URL = f"{settings.app_base_url}/email-assets/collabrains-logo.png"

_SUPPORTED_LOCALES = ("en", "nl", "de")


def _locale(preferred_language: str | None) -> str:
    return preferred_language if preferred_language in _SUPPORTED_LOCALES else "en"


def render_branded_email_html(
    *, preheader: str, heading: str, body_html: str, cta_label: str, cta_url: str, footer_note: str
) -> str:
    return f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background-color:#F0EFFF;">
    <span style="display:none;font-size:1px;color:#F0EFFF;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;">{preheader}</span>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F0EFFF;">
      <tr>
        <td align="center" style="padding:32px 16px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;background-color:#ffffff;border-radius:16px;border:1px solid #E8E6FF;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
            <tr>
              <td style="background-color:#6C63FF;background:linear-gradient(135deg,#6C63FF,#4C6EFF);padding:32px;text-align:center;border-radius:16px 16px 0 0;">
                <img src="{LOGO_URL}" alt="CollaBrains" width="140" height="70" style="display:block;margin:0 auto;border:0;">
              </td>
            </tr>
            <tr>
              <td style="padding:32px 32px 8px;">
                <h1 style="margin:0 0 16px;font-size:22px;line-height:1.3;color:#1E1B4B;">{heading}</h1>
                <div style="font-size:15px;line-height:1.6;color:#3F3B78;">{body_html}</div>
              </td>
            </tr>
            <tr>
              <td style="padding:8px 32px 32px;">
                <table role="presentation" cellpadding="0" cellspacing="0">
                  <tr>
                    <td style="border-radius:10px;background-color:#6C63FF;background:linear-gradient(135deg,#6C63FF,#4C6EFF);">
                      <a href="{cta_url}" style="display:inline-block;padding:12px 28px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;border-radius:10px;">{cta_label}</a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 32px 28px;border-top:1px solid #E8E6FF;">
                <p style="margin:0;font-size:12px;line-height:1.6;color:#8A86B8;">{footer_note}</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


_NEW_ORG_COPY = {
    "en": {
        "subject": "Welcome to CollaBrains, {display_name}!",
        "preheader": "Your CollaBrains workspace {organization_name} is ready to go.",
        "heading": "Welcome to CollaBrains \U0001F44B",
        "body_html": (
            "<p>Your workspace <strong>{organization_name}</strong> is ready. CollaBrains helps you "
            "organize documents, track tasks, and get AI-powered help with day-to-day admin — all "
            "in one place.</p><p>Ready to get started?</p>"
        ),
        "body_text": (
            "Your workspace {organization_name} is ready. CollaBrains helps you organize documents, "
            "track tasks, and get AI-powered help with day-to-day admin — all in one place.\n\n"
            "Ready to get started?"
        ),
        "cta": "Go to your dashboard",
        "footer": (
            "You're receiving this because you just created a CollaBrains account. If this wasn't "
            "you, you can safely ignore this email."
        ),
    },
    "nl": {
        "subject": "Welkom bij CollaBrains, {display_name}!",
        "preheader": "Je CollaBrains-werkruimte {organization_name} staat klaar.",
        "heading": "Welkom bij CollaBrains \U0001F44B",
        "body_html": (
            "<p>Je werkruimte <strong>{organization_name}</strong> staat klaar. CollaBrains helpt je "
            "documenten te organiseren, taken bij te houden en met AI-hulp je dagelijkse administratie "
            "te regelen — allemaal op één plek.</p><p>Klaar om te beginnen?</p>"
        ),
        "body_text": (
            "Je werkruimte {organization_name} staat klaar. CollaBrains helpt je documenten te "
            "organiseren, taken bij te houden en met AI-hulp je dagelijkse administratie te regelen "
            "— allemaal op één plek.\n\nKlaar om te beginnen?"
        ),
        "cta": "Ga naar je dashboard",
        "footer": (
            "Je ontvangt dit bericht omdat je zojuist een CollaBrains-account hebt aangemaakt. Als jij "
            "dit niet was, kun je deze e-mail negeren."
        ),
    },
    "de": {
        "subject": "Willkommen bei CollaBrains, {display_name}!",
        "preheader": "Dein CollaBrains-Arbeitsbereich {organization_name} ist bereit.",
        "heading": "Willkommen bei CollaBrains \U0001F44B",
        "body_html": (
            "<p>Dein Arbeitsbereich <strong>{organization_name}</strong> ist bereit. CollaBrains hilft "
            "dir, Dokumente zu organisieren, Aufgaben zu verfolgen und mit KI-Unterstützung deinen "
            "Alltag zu erledigen — alles an einem Ort.</p><p>Bereit loszulegen?</p>"
        ),
        "body_text": (
            "Dein Arbeitsbereich {organization_name} ist bereit. CollaBrains hilft dir, Dokumente zu "
            "organisieren, Aufgaben zu verfolgen und mit KI-Unterstützung deinen Alltag zu "
            "erledigen — alles an einem Ort.\n\nBereit loszulegen?"
        ),
        "cta": "Zum Dashboard",
        "footer": (
            "Du erhältst diese E-Mail, weil du gerade ein CollaBrains-Konto erstellt hast. Falls "
            "du das nicht warst, kannst du diese E-Mail ignorieren."
        ),
    },
}

_JOINED_ORG_COPY = {
    "en": {
        "subject": "You've joined {organization_name} on CollaBrains",
        "preheader": "You've joined {organization_name} on CollaBrains.",
        "heading": "Welcome to the team \U0001F44B",
        "body_html": (
            "<p>Hi {display_name}, you're now part of <strong>{organization_name}</strong> on "
            "CollaBrains.</p><p>You'll see shared documents, tasks, and cases as soon as you sign in.</p>"
        ),
        "body_text": (
            "Hi {display_name}, you're now part of {organization_name} on CollaBrains.\n\nYou'll see "
            "shared documents, tasks, and cases as soon as you sign in."
        ),
        "cta": "Open CollaBrains",
        "footer": "You're receiving this because you accepted an invitation to join this workspace.",
    },
    "nl": {
        "subject": "Je bent lid geworden van {organization_name} op CollaBrains",
        "preheader": "Je bent lid geworden van {organization_name} op CollaBrains.",
        "heading": "Welkom bij het team \U0001F44B",
        "body_html": (
            "<p>Hoi {display_name}, je maakt nu deel uit van <strong>{organization_name}</strong> op "
            "CollaBrains.</p><p>Je ziet gedeelde documenten, taken en dossiers zodra je inlogt.</p>"
        ),
        "body_text": (
            "Hoi {display_name}, je maakt nu deel uit van {organization_name} op CollaBrains.\n\nJe "
            "ziet gedeelde documenten, taken en dossiers zodra je inlogt."
        ),
        "cta": "Open CollaBrains",
        "footer": "Je ontvangt dit bericht omdat je een uitnodiging voor deze werkruimte hebt geaccepteerd.",
    },
    "de": {
        "subject": "Du bist {organization_name} auf CollaBrains beigetreten",
        "preheader": "Du bist {organization_name} auf CollaBrains beigetreten.",
        "heading": "Willkommen im Team \U0001F44B",
        "body_html": (
            "<p>Hallo {display_name}, du bist jetzt Teil von <strong>{organization_name}</strong> auf "
            "CollaBrains.</p><p>Sobald du dich anmeldest, siehst du gemeinsame Dokumente, Aufgaben und "
            "Fälle.</p>"
        ),
        "body_text": (
            "Hallo {display_name}, du bist jetzt Teil von {organization_name} auf CollaBrains.\n\n"
            "Sobald du dich anmeldest, siehst du gemeinsame Dokumente, Aufgaben und Fälle."
        ),
        "cta": "CollaBrains öffnen",
        "footer": "Du erhältst diese E-Mail, weil du eine Einladung zu diesem Arbeitsbereich angenommen hast.",
    },
}


def welcome_new_org_subject(*, display_name: str, preferred_language: str | None) -> str:
    return _NEW_ORG_COPY[_locale(preferred_language)]["subject"].format(display_name=display_name)


def welcome_new_org_html(*, display_name: str, organization_name: str, preferred_language: str | None) -> str:
    copy = _NEW_ORG_COPY[_locale(preferred_language)]
    return render_branded_email_html(
        preheader=copy["preheader"].format(organization_name=organization_name),
        heading=copy["heading"],
        body_html=copy["body_html"].format(organization_name=organization_name),
        cta_label=copy["cta"],
        cta_url=f"{settings.app_base_url}/",
        footer_note=copy["footer"],
    )


def welcome_new_org_text(*, display_name: str, organization_name: str, preferred_language: str | None) -> str:
    copy = _NEW_ORG_COPY[_locale(preferred_language)]
    body = copy["body_text"].format(organization_name=organization_name)
    return f"{copy['heading']}\n\n{body}\n\n{copy['cta']}: {settings.app_base_url}/\n\n{copy['footer']}"


def welcome_joined_org_subject(*, organization_name: str, preferred_language: str | None) -> str:
    return _JOINED_ORG_COPY[_locale(preferred_language)]["subject"].format(organization_name=organization_name)


def welcome_joined_org_html(*, display_name: str, organization_name: str, preferred_language: str | None) -> str:
    copy = _JOINED_ORG_COPY[_locale(preferred_language)]
    return render_branded_email_html(
        preheader=copy["preheader"].format(organization_name=organization_name),
        heading=copy["heading"],
        body_html=copy["body_html"].format(display_name=display_name, organization_name=organization_name),
        cta_label=copy["cta"],
        cta_url=f"{settings.app_base_url}/",
        footer_note=copy["footer"],
    )


def welcome_joined_org_text(*, display_name: str, organization_name: str, preferred_language: str | None) -> str:
    copy = _JOINED_ORG_COPY[_locale(preferred_language)]
    body = copy["body_text"].format(display_name=display_name, organization_name=organization_name)
    return f"{copy['heading']}\n\n{body}\n\n{copy['cta']}: {settings.app_base_url}/\n\n{copy['footer']}"


_ONBOARDING_WELCOME_COPY = {
    "en": {
        "subject": "Welcome to CollaBrains, {display_name}!",
        "preheader": "Activate your CollaBrains account to get started.",
        "heading": "Welcome to CollaBrains \U0001F44B",
        "body_html": (
            "<p>An account has been created for you on CollaBrains. Click below to activate it "
            "and get started.</p>"
        ),
        "body_text": "An account has been created for you on CollaBrains. Activate it to get started.",
        "cta": "Activate your account",
        "footer": (
            "This link is valid for 7 days. If you weren't expecting this, you can safely ignore "
            "this email."
        ),
    },
    "nl": {
        "subject": "Welkom bij CollaBrains, {display_name}!",
        "preheader": "Activeer je CollaBrains-account om te beginnen.",
        "heading": "Welkom bij CollaBrains \U0001F44B",
        "body_html": (
            "<p>Er is een account voor je aangemaakt op CollaBrains. Klik hieronder om het te "
            "activeren en te beginnen.</p>"
        ),
        "body_text": "Er is een account voor je aangemaakt op CollaBrains. Activeer het om te beginnen.",
        "cta": "Activeer je account",
        "footer": "Deze link is 7 dagen geldig. Als je dit niet verwachtte, kun je deze e-mail negeren.",
    },
    "de": {
        "subject": "Willkommen bei CollaBrains, {display_name}!",
        "preheader": "Aktiviere dein CollaBrains-Konto, um loszulegen.",
        "heading": "Willkommen bei CollaBrains \U0001F44B",
        "body_html": (
            "<p>Für dich wurde ein Konto bei CollaBrains erstellt. Klicke unten, um es zu "
            "aktivieren und loszulegen.</p>"
        ),
        "body_text": "Für dich wurde ein Konto bei CollaBrains erstellt. Aktiviere es, um loszulegen.",
        "cta": "Konto aktivieren",
        "footer": (
            "Dieser Link ist 7 Tage gültig. Falls du dies nicht erwartet hast, kannst du diese "
            "E-Mail ignorieren."
        ),
    },
}


def onboarding_welcome_subject(*, display_name: str, preferred_language: str | None) -> str:
    return _ONBOARDING_WELCOME_COPY[_locale(preferred_language)]["subject"].format(display_name=display_name)


def onboarding_welcome_html(*, display_name: str, onboard_url: str, preferred_language: str | None) -> str:
    copy = _ONBOARDING_WELCOME_COPY[_locale(preferred_language)]
    return render_branded_email_html(
        preheader=copy["preheader"],
        heading=copy["heading"],
        body_html=copy["body_html"],
        cta_label=copy["cta"],
        cta_url=onboard_url,
        footer_note=copy["footer"],
    )


def onboarding_welcome_text(*, display_name: str, onboard_url: str, preferred_language: str | None) -> str:
    copy = _ONBOARDING_WELCOME_COPY[_locale(preferred_language)]
    return f"{copy['heading']}\n\n{copy['body_text']}\n\n{copy['cta']}: {onboard_url}\n\n{copy['footer']}"
