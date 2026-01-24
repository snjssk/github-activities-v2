"""Activities API router."""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_

from ..models import User, Activity, ACTIVITY_TYPES, get_session

router = APIRouter(prefix="/api/activities", tags=["activities"])


class ActivityBreakdown(BaseModel):
    """Activity breakdown by type."""
    commit: int = 0
    pr_opened: int = 0
    pr_merged: int = 0
    review: int = 0
    issue_opened: int = 0
    issue_closed: int = 0
    total: int = 0


class WeeklyData(BaseModel):
    """Weekly aggregated data."""
    week: str  # e.g., "2025-W03"
    start_date: str
    end_date: str
    commit: int = 0
    pr_opened: int = 0
    pr_merged: int = 0
    review: int = 0
    issue_opened: int = 0
    issue_closed: int = 0
    total: int = 0


class MonthlyData(BaseModel):
    """Monthly aggregated data."""
    month: str  # e.g., "2025-01"
    commit: int = 0
    pr_opened: int = 0
    pr_merged: int = 0
    review: int = 0
    issue_opened: int = 0
    issue_closed: int = 0
    total: int = 0


class WeeklyResponse(BaseModel):
    """Weekly activities response."""
    user: str
    period: str = "weekly"
    data: list[WeeklyData]


class MonthlyResponse(BaseModel):
    """Monthly activities response."""
    user: str
    period: str = "monthly"
    data: list[MonthlyData]


class SummaryResponse(BaseModel):
    """Summary response for dashboard."""
    user: str
    this_week: ActivityBreakdown
    last_week: ActivityBreakdown
    this_month: ActivityBreakdown
    last_month: ActivityBreakdown
    week_change: ActivityBreakdown
    month_change: ActivityBreakdown


class ComparisonData(BaseModel):
    """Comparison data for a user."""
    username: str
    total: int
    breakdown: ActivityBreakdown


class ComparisonResponse(BaseModel):
    """Comparison response."""
    period: str
    from_date: str
    to_date: str
    users: list[ComparisonData]


def get_week_range(d: date) -> tuple[date, date]:
    """Get start and end of ISO week for a date."""
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


def get_month_range(d: date) -> tuple[date, date]:
    """Get start and end of month for a date."""
    start = d.replace(day=1)
    if d.month == 12:
        end = d.replace(year=d.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = d.replace(month=d.month + 1, day=1) - timedelta(days=1)
    return start, end


def aggregate_activities(
    session,
    user_id: int,
    from_date: date,
    to_date: date,
) -> ActivityBreakdown:
    """Aggregate activities for a date range."""
    results = session.execute(
        select(Activity.activity_type, func.sum(Activity.count))
        .where(
            and_(
                Activity.user_id == user_id,
                Activity.activity_date >= from_date,
                Activity.activity_date <= to_date,
            )
        )
        .group_by(Activity.activity_type)
    ).all()

    breakdown = ActivityBreakdown()
    for activity_type, count in results:
        setattr(breakdown, activity_type, count or 0)
        breakdown.total += count or 0

    return breakdown


@router.get("/weekly", response_model=WeeklyResponse)
def get_weekly_activities(
    user: str,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
):
    """Get weekly aggregated activities."""
    with get_session() as session:
        db_user = session.execute(
            select(User).where(User.username == user)
        ).scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Default to last 12 weeks
        if to_date is None:
            to_date = date.today()
        if from_date is None:
            from_date = to_date - timedelta(weeks=12)

        # Generate weeks
        weeks = []
        current = from_date
        while current <= to_date:
            week_start, week_end = get_week_range(current)
            week_str = current.strftime("%G-W%V")

            if week_str not in [w.week for w in weeks]:
                breakdown = aggregate_activities(session, db_user.id, week_start, week_end)
                weeks.append(WeeklyData(
                    week=week_str,
                    start_date=week_start.isoformat(),
                    end_date=week_end.isoformat(),
                    commit=breakdown.commit,
                    pr_opened=breakdown.pr_opened,
                    pr_merged=breakdown.pr_merged,
                    review=breakdown.review,
                    issue_opened=breakdown.issue_opened,
                    issue_closed=breakdown.issue_closed,
                    total=breakdown.total,
                ))

            current += timedelta(days=7)

        return WeeklyResponse(user=user, data=weeks)


@router.get("/monthly", response_model=MonthlyResponse)
def get_monthly_activities(
    user: str,
    year: Optional[int] = None,
):
    """Get monthly aggregated activities."""
    with get_session() as session:
        db_user = session.execute(
            select(User).where(User.username == user)
        ).scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        if year is None:
            year = date.today().year

        months = []
        for month in range(1, 13):
            month_start = date(year, month, 1)
            _, month_end = get_month_range(month_start)

            breakdown = aggregate_activities(session, db_user.id, month_start, month_end)
            months.append(MonthlyData(
                month=f"{year}-{month:02d}",
                commit=breakdown.commit,
                pr_opened=breakdown.pr_opened,
                pr_merged=breakdown.pr_merged,
                review=breakdown.review,
                issue_opened=breakdown.issue_opened,
                issue_closed=breakdown.issue_closed,
                total=breakdown.total,
            ))

        return MonthlyResponse(user=user, data=months)


@router.get("/summary", response_model=SummaryResponse)
def get_summary(user: str):
    """Get summary for dashboard KPI cards."""
    with get_session() as session:
        db_user = session.execute(
            select(User).where(User.username == user)
        ).scalar_one_or_none()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        today = date.today()

        # This week
        this_week_start, this_week_end = get_week_range(today)
        this_week = aggregate_activities(session, db_user.id, this_week_start, this_week_end)

        # Last week
        last_week_start = this_week_start - timedelta(days=7)
        last_week_end = this_week_start - timedelta(days=1)
        last_week = aggregate_activities(session, db_user.id, last_week_start, last_week_end)

        # This month
        this_month_start, this_month_end = get_month_range(today)
        this_month = aggregate_activities(session, db_user.id, this_month_start, this_month_end)

        # Last month
        last_month_end = this_month_start - timedelta(days=1)
        last_month_start, _ = get_month_range(last_month_end)
        last_month = aggregate_activities(session, db_user.id, last_month_start, last_month_end)

        # Calculate changes
        week_change = ActivityBreakdown(
            commit=this_week.commit - last_week.commit,
            pr_opened=this_week.pr_opened - last_week.pr_opened,
            pr_merged=this_week.pr_merged - last_week.pr_merged,
            review=this_week.review - last_week.review,
            issue_opened=this_week.issue_opened - last_week.issue_opened,
            issue_closed=this_week.issue_closed - last_week.issue_closed,
            total=this_week.total - last_week.total,
        )

        month_change = ActivityBreakdown(
            commit=this_month.commit - last_month.commit,
            pr_opened=this_month.pr_opened - last_month.pr_opened,
            pr_merged=this_month.pr_merged - last_month.pr_merged,
            review=this_month.review - last_month.review,
            issue_opened=this_month.issue_opened - last_month.issue_opened,
            issue_closed=this_month.issue_closed - last_month.issue_closed,
            total=this_month.total - last_month.total,
        )

        return SummaryResponse(
            user=user,
            this_week=this_week,
            last_week=last_week,
            this_month=this_month,
            last_month=last_month,
            week_change=week_change,
            month_change=month_change,
        )


@router.get("/comparison", response_model=ComparisonResponse)
def get_comparison(
    users: str = Query(..., description="Comma-separated usernames"),
    period: str = Query("weekly", description="weekly or monthly"),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
):
    """Get comparison data for multiple users."""
    usernames = [u.strip() for u in users.split(",")]

    with get_session() as session:
        today = date.today()

        if period == "weekly":
            if from_date is None:
                from_date, _ = get_week_range(today)
            if to_date is None:
                _, to_date = get_week_range(today)
        else:  # monthly
            if from_date is None:
                from_date, _ = get_month_range(today)
            if to_date is None:
                _, to_date = get_month_range(today)

        comparison_data = []
        for username in usernames:
            db_user = session.execute(
                select(User).where(User.username == username)
            ).scalar_one_or_none()

            if db_user:
                breakdown = aggregate_activities(session, db_user.id, from_date, to_date)
                comparison_data.append(ComparisonData(
                    username=username,
                    total=breakdown.total,
                    breakdown=breakdown,
                ))

        return ComparisonResponse(
            period=period,
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
            users=comparison_data,
        )
