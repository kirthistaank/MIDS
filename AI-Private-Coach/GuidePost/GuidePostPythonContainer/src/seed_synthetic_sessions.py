import argparse
import math
import random
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

# Allow running as a plain script inside the container, where /app (parent of `src/`) may
# not be on sys.path depending on invocation.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.database import SessionLocal
from src.database_models import Session as DbSession
from src.database_models import User as DbUser


def _redact_email(email: str) -> str:
    e = (email or "").strip()
    if "@" not in e:
        return "***"
    local, domain = e.split("@", 1)
    if not local:
        return f"***@{domain}"
    if len(local) == 1:
        return f"{local}***@{domain}"
    return f"{local[0]}***{local[-1]}@{domain}"


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@dataclass(frozen=True)
class SeedPlan:
    email: str
    start: date
    end: date
    active_days: int
    target_cri_score_100: float
    target_cei_score_100: float

    @property
    def target_cri_rating_1_5(self) -> float:
        return (self.target_cri_score_100 - 50.0) / 10.0

    @property
    def target_cei_rating_1_5(self) -> float:
        return (self.target_cei_score_100 - 50.0) / 10.0


def _iter_days(start: date, end: date) -> Iterable[date]:
    d = start
    while d <= end:
        yield d
        d = d + timedelta(days=1)


def _choose_active_days(rng: random.Random, start: date, end: date, k: int) -> list[date]:
    days = list(_iter_days(start, end))
    if k >= len(days):
        return days
    if k == 1:
        return [start]
    # Even-ish spread: sample from indices with mild jitter.
    step = (len(days) - 1) / float(k - 1)
    chosen: set[date] = set()
    chosen.add(start)
    chosen.add(end)
    for i in range(k):
        base_idx = int(round(i * step))
        jitter = rng.randint(-1, 1)
        idx = max(0, min(len(days) - 1, base_idx + jitter))
        chosen.add(days[idx])
    # If we didn't hit k unique due to collisions, fill randomly.
    while len(chosen) < k:
        chosen.add(rng.choice(days))
    # If we overshot (possible due to forced endpoints), trim while keeping endpoints.
    if len(chosen) > k:
        pool = [d for d in chosen if d not in {start, end}]
        rng.shuffle(pool)
        keep = {start, end}
        # Keep the earliest items from the shuffled pool until reaching k.
        for d in pool:
            if len(keep) >= k:
                break
            keep.add(d)
        chosen = keep
    return sorted(chosen)


def _deltas_for_days(n: int) -> list[float]:
    """Create n deltas with mean ~ 0 for fluctuating scores."""
    if n <= 0:
        return []
    # Sine wave gives nice looking variation. We'll normalize to mean 0 exactly.
    raw = [math.sin((2 * math.pi * i) / max(1, (n - 1))) for i in range(n)]
    mean = sum(raw) / float(n)
    centered = [x - mean for x in raw]
    # Scale to keep ratings safely within [1, 5]
    max_abs = max(abs(x) for x in centered) or 1.0
    scale = 0.45 / max_abs  # up to ±0.45 rating points
    return [x * scale for x in centered]


def seed_synthetic_sessions(plan: SeedPlan) -> None:
    email_norm = (plan.email or "").strip().lower()
    if not email_norm:
        raise ValueError("email is required")
    if plan.active_days < 1:
        raise ValueError("active_days must be >= 1")
    if plan.start > plan.end:
        raise ValueError("start must be <= end")

    # Deterministic seed (no PII in logs; seed is internal only).
    rng = random.Random(f"seed:{email_norm}:{plan.start.isoformat()}:{plan.end.isoformat()}:{plan.active_days}")

    active_days = _choose_active_days(rng, plan.start, plan.end, plan.active_days)
    deltas = _deltas_for_days(len(active_days))

    cri_base = float(plan.target_cri_rating_1_5)
    cei_base = float(plan.target_cei_rating_1_5)

    with SessionLocal() as db:
        u = db.query(DbUser).filter(DbUser.email == email_norm).first()
        if not u:
            u = DbUser(email=email_norm)
            db.add(u)
            db.flush()  # ensure u.id exists

        # Idempotency: remove previously-seeded synthetic rows in the same range.
        range_start_dt = datetime(plan.start.year, plan.start.month, plan.start.day, 0, 0, 0, 0)
        range_end_dt = datetime(plan.end.year, plan.end.month, plan.end.day, 23, 59, 59, 999999)
        db.query(DbSession).filter(
            DbSession.user_id == u.id,
            DbSession.created_at >= range_start_dt,
            DbSession.created_at <= range_end_dt,
            DbSession.audio_id.like("synthetic-%"),
        ).delete(synchronize_session=False)

        # Insert 1 session per active day (enough for dashboard aggregation).
        # created_at is naive UTC; set midday to avoid date edge cases.
        for i, day in enumerate(active_days):
            d = float(deltas[i])
            cri = _clamp(cri_base + d, 1.0, 5.0)
            cei = _clamp(cei_base + d, 1.0, 5.0)

            audio_id = f"synthetic-{day.strftime('%Y%m%d')}-{i:02d}"
            created_at = datetime(day.year, day.month, day.day, 12, 0, 0, 0)
            s = DbSession(
                user_id=u.id,
                audio_id=audio_id,
                audio_url=None,
                transcript="Synthetic session (seeded for dashboard demo).",
                created_at=created_at,
                cri=cri,
                cei=cei,
                sentiment=None,
                speaker_volatility=None,
            )
            db.add(s)

        db.commit()

    # Keep stdout message minimal and non-sensitive (avoid printing full email).
    print(
        f"Seeded synthetic sessions for {_redact_email(email_norm)} "
        f"({len(active_days)} active days) covering {plan.start.isoformat()} → {plan.end.isoformat()}."
    )


def main() -> None:
    today = datetime.utcnow().date()
    p = argparse.ArgumentParser(description="Seed synthetic dashboard sessions for a user.")
    p.add_argument("--email", required=True, help="User email to seed (will be normalized to lowercase).")
    p.add_argument("--start", default=None, help="Start date YYYY-MM-DD (default: 35 days ago).")
    p.add_argument("--end", default=today.isoformat(), help="End date YYYY-MM-DD (default: today, UTC).")
    p.add_argument("--active-days", type=int, default=21, help="Number of unique active days to seed.")
    p.add_argument("--cei", type=float, default=86.0, help="Target CEI score (0-100).")
    p.add_argument("--cri", type=float, default=74.0, help="Target CRI score (0-100).")
    p.add_argument(
        "--wipe-window",
        action="store_true",
        help="DANGER: delete ALL sessions for this user in the date window before seeding (use for demos only).",
    )
    args = p.parse_args()

    end_d = date.fromisoformat(str(args.end).strip())
    if args.start:
        start_d = date.fromisoformat(str(args.start).strip())
    else:
        start_d = end_d - timedelta(days=35 - 1)

    plan = SeedPlan(
        email=str(args.email),
        start=start_d,
        end=end_d,
        active_days=int(args.active_days),
        target_cri_score_100=float(args.cri),
        target_cei_score_100=float(args.cei),
    )
    if args.wipe_window:
        email_norm = (plan.email or "").strip().lower()
        with SessionLocal() as db:
            u = db.query(DbUser).filter(DbUser.email == email_norm).first()
            if u:
                range_start_dt = datetime(plan.start.year, plan.start.month, plan.start.day, 0, 0, 0, 0)
                range_end_dt = datetime(plan.end.year, plan.end.month, plan.end.day, 23, 59, 59, 999999)
                db.query(DbSession).filter(
                    DbSession.user_id == u.id,
                    DbSession.created_at >= range_start_dt,
                    DbSession.created_at <= range_end_dt,
                ).delete(synchronize_session=False)
                db.commit()

    seed_synthetic_sessions(plan)


if __name__ == "__main__":
    main()

