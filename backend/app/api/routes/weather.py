from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.models.weather import (
    WeatherCoverageStatus,
    WeatherLocationRole,
    WeatherSnapshot,
)
from app.services.rainfall_aggregation_service import aggregate_weather
from app.services.weather_service import (
    OpenMeteoWeatherProvider,
    WeatherLocationRequest,
)
from app.services.weatherapi_service import (
    ResilientWeatherProvider,
    WeatherApiProvider,
)


UPSTREAM_LOCATION_NAME = "Mokokchung, Nagaland, India"
DOWNSTREAM_LOCATION_NAME = "Sonari, Charaideo, Assam, India"


router = APIRouter(
    prefix="/api/weather",
    tags=["Weather"],
)


open_meteo_provider = OpenMeteoWeatherProvider(
    forecast_horizon_hours=settings.weather_forecast_horizon_hours,
    timeout_seconds=settings.weather_timeout_seconds,
    cache_ttl_seconds=settings.weather_cache_ttl_seconds,
)

weatherapi_provider = WeatherApiProvider(
    forecast_horizon_hours=settings.weather_forecast_horizon_hours,
    timeout_seconds=settings.weather_timeout_seconds,
    api_key=settings.weatherapi_api_key,
)

weather_provider = ResilientWeatherProvider(
    primary_provider=open_meteo_provider,
    fallback_provider=weatherapi_provider,
    fallback_enabled=settings.weatherapi_enabled,
    cache_ttl_seconds=settings.weather_cache_ttl_seconds,
)


@router.get(
    "",
    response_model=WeatherSnapshot,
    responses={503: {"model": WeatherSnapshot}},
    summary="Get normalized two-location rainfall weather",
)
def get_weather() -> WeatherSnapshot | JSONResponse:
    upstream, downstream = weather_provider.fetch_locations(
        upstream=WeatherLocationRequest(
            location_role=WeatherLocationRole.UPSTREAM,
            location_name=UPSTREAM_LOCATION_NAME,
            latitude=settings.weather_upstream_latitude,
            longitude=settings.weather_upstream_longitude,
        ),
        downstream=WeatherLocationRequest(
            location_role=WeatherLocationRole.DOWNSTREAM,
            location_name=DOWNSTREAM_LOCATION_NAME,
            latitude=settings.weather_downstream_latitude,
            longitude=settings.weather_downstream_longitude,
        ),
    )

    snapshot = aggregate_weather(
        upstream=upstream,
        downstream=downstream,
    )

    if snapshot.coverage_status == WeatherCoverageStatus.UNAVAILABLE:
        return JSONResponse(
            status_code=503,
            content=snapshot.model_dump(mode="json"),
        )

    return snapshot