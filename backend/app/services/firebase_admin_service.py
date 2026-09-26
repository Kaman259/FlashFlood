import firebase_admin
from firebase_admin import credentials

from app.core.config import Settings, settings


REAL_FIREBASE_APP_NAME = "flashflood-real"


def _normalized_optional(value: str | None) -> str | None:
    if value is None:
        return None

    stripped = value.strip()
    return stripped or None


def get_real_firebase_app(
    app_settings: Settings | None = None,
):
    active_settings = app_settings or settings
    project_id = _normalized_optional(active_settings.firebase_project_id)
    credential_path = _normalized_optional(
        active_settings.google_application_credentials
    )

    if not project_id:
        raise ValueError(
            "FIREBASE_PROJECT_ID is required for real Firebase Admin services."
        )

    try:
        app = firebase_admin.get_app(REAL_FIREBASE_APP_NAME)
    except ValueError:
        app = None

    if app is not None:
        if app.project_id != project_id:
            raise ValueError(
                "The initialized Firebase app project does not match configuration."
            )

        return app

    if credential_path:
        credential = credentials.Certificate(credential_path)
    else:
        credential = credentials.ApplicationDefault()

    return firebase_admin.initialize_app(
        credential=credential,
        options={"projectId": project_id},
        name=REAL_FIREBASE_APP_NAME,
    )