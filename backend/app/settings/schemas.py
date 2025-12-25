from pydantic import Field, field_validator

from app.common.schema import BaseSchema


class NotificationSettingsResponse(BaseSchema):
    """알림 설정 응답"""
    enabled: bool
    times: list[str]
    timezone: str


class NotificationSettingsUpdateRequest(BaseSchema):
    """알림 설정 수정 요청"""
    enabled: bool | None = None
    times: list[str] | None = Field(
        default=None,
        description="알림 받을 시간 목록 (HH:00 또는 HH:30 형식)"
    )

    @field_validator("times")
    @classmethod
    def validate_times(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v

        for time in v:
            if len(time) != 5 or time[2] != ":":
                raise ValueError(f"Invalid time format: {time}. Use HH:MM")

            hour, minute = time.split(":")
            if not (0 <= int(hour) <= 23):
                raise ValueError(f"Invalid hour: {hour}")
            if minute not in ("00", "30"):
                raise ValueError(f"Minutes must be 00 or 30, got: {minute}")

        return v
