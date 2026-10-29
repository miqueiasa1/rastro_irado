"""
Conversões de fuso horário do IRAI.

CONVENÇÃO DE ARMAZENAMENTO (coluna `market_bars.timestamp_utc`):
    Apesar do nome, os timestamps NÃO são UTC real. Estão no "horário do broker"
    (servidor MT5 Tickmill/Axi), que segue Nova York + 7h:
        - Horário de verão dos EUA (mar→nov): GMT+3
        - Horário padrão dos EUA  (nov→mar): GMT+2
    Assim, 00:00 do broker = 17:00 de Nova York (fechamento do dia forex) o ano todo.

    As barras da B3 (terminal XP) chegam do MT5 em horário de Brasília (BRT, UTC-3,
    sem horário de verão desde 2019) e são convertidas para o horário do broker
    com offset DINÂMICO (+6h no verão americano, +5h no inverno americano).

Todas as funções trabalham com datetimes "naive" ou tz-aware em UTC usados como
"relógio de parede" (wall clock) da convenção indicada no nome.
"""

from datetime import datetime, timedelta, timezone, date as _date
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
BRT_TZ = ZoneInfo("America/Sao_Paulo")

# Horário oficial de abertura dos futuros B3 (WIN/WDO) em BRT
B3_OPEN_BRT = (9, 0)
# Horário de encerramento do pregão regular B3 (inclui call de fechamento) em BRT
B3_CLOSE_BRT = (18, 30)


def broker_offset_hours(real_utc: datetime) -> int:
    """Offset do broker em relação ao UTC real no instante dado (+3 ou +2)."""
    if real_utc.tzinfo is None:
        real_utc = real_utc.replace(tzinfo=timezone.utc)
    ny_off = real_utc.astimezone(NY_TZ).utcoffset()
    return int(ny_off.total_seconds() // 3600) + 7


def brt_offset_hours(real_utc: datetime) -> int:
    """Offset de Brasília em relação ao UTC real (−3 desde 2019)."""
    if real_utc.tzinfo is None:
        real_utc = real_utc.replace(tzinfo=timezone.utc)
    return int(real_utc.astimezone(BRT_TZ).utcoffset().total_seconds() // 3600)


def brt_epoch_to_broker_epoch(brt_epoch: float) -> float:
    """Converte um epoch "BRT como se fosse UTC" (formato do MT5 XP) para o
    epoch "broker como se fosse UTC" (formato gravado no banco)."""
    real_utc = datetime.fromtimestamp(brt_epoch, tz=timezone.utc).replace(tzinfo=None)
    real_utc = real_utc.replace(tzinfo=BRT_TZ).astimezone(timezone.utc)
    return real_utc.timestamp() + broker_offset_hours(real_utc) * 3600


def brt_wall_to_broker_wall(brt_wall: datetime) -> datetime:
    """Relógio de parede BRT → relógio de parede do broker (naive/UTC-aware preservado)."""
    tz = brt_wall.tzinfo
    naive = brt_wall.replace(tzinfo=None)
    real_utc = naive.replace(tzinfo=BRT_TZ).astimezone(timezone.utc)
    broker = (real_utc + timedelta(hours=broker_offset_hours(real_utc))).replace(tzinfo=None)
    return broker.replace(tzinfo=tz) if tz is not None else broker


def broker_wall_to_real_utc(broker_wall: datetime) -> datetime:
    """Relógio de parede do broker → UTC real (tz-aware).
    Ambiguidade de 1h na virada do DST americano (domingo de madrugada, mercado fechado) é irrelevante."""
    naive = broker_wall.replace(tzinfo=None)
    guess = naive.replace(tzinfo=timezone.utc) - timedelta(hours=3)
    off = broker_offset_hours(guess)
    return naive.replace(tzinfo=timezone.utc) - timedelta(hours=off)


def broker_wall_to_brt_wall(broker_wall: datetime) -> datetime:
    """Relógio de parede do broker → relógio de parede BRT (preserva tzinfo do input)."""
    tz = broker_wall.tzinfo
    real_utc = broker_wall_to_real_utc(broker_wall)
    brt = real_utc.astimezone(BRT_TZ).replace(tzinfo=None)
    return brt.replace(tzinfo=tz) if tz is not None else brt


def now_broker_wall() -> datetime:
    """Agora, no relógio do broker, como datetime tz-aware 'UTC' (mesma convenção do banco)."""
    real = datetime.now(timezone.utc)
    return (real + timedelta(hours=broker_offset_hours(real))).replace(tzinfo=timezone.utc)


def broker_to_brt_offset_hours(session_date) -> int:
    """Quantas horas somar ao relógio do broker para obter BRT em uma data (−6 ou −5)."""
    if isinstance(session_date, str):
        session_date = _date.fromisoformat(session_date[:10])
    noon_utc = datetime(session_date.year, session_date.month, session_date.day, 15, tzinfo=timezone.utc)
    return brt_offset_hours(noon_utc) - broker_offset_hours(noon_utc)


def b3_session_open_broker(session_date, tz_aware: bool = True) -> datetime:
    """Abertura do pregão B3 (09:00 BRT) do dia `session_date`, no relógio do broker."""
    if isinstance(session_date, str):
        session_date = _date.fromisoformat(session_date[:10])
    h, m = B3_OPEN_BRT
    broker = brt_wall_to_broker_wall(datetime(session_date.year, session_date.month, session_date.day, h, m))
    return broker.replace(tzinfo=timezone.utc) if tz_aware else broker


def b3_session_bounds_broker(session_date):
    """(abertura, encerramento) do pregão B3 em relógio do broker, tz-aware 'UTC'."""
    if isinstance(session_date, str):
        session_date = _date.fromisoformat(session_date[:10])
    oh, om = B3_OPEN_BRT
    ch, cm = B3_CLOSE_BRT
    o = brt_wall_to_broker_wall(datetime(session_date.year, session_date.month, session_date.day, oh, om))
    c = brt_wall_to_broker_wall(datetime(session_date.year, session_date.month, session_date.day, ch, cm))
    return o.replace(tzinfo=timezone.utc), c.replace(tzinfo=timezone.utc)


def b3_bars_per_session(timeframe: str = "M5") -> int:
    """Número de barras do pregão regular B3 (09:00–18:30 BRT) no timeframe."""
    minutes = (B3_CLOSE_BRT[0] * 60 + B3_CLOSE_BRT[1]) - (B3_OPEN_BRT[0] * 60 + B3_OPEN_BRT[1])
    step = {"M1": 1, "M2": 2, "M5": 5, "M15": 15, "M30": 30, "H1": 60}.get(timeframe, 5)
    return max(1, minutes // step)


def now_brt_wall() -> datetime:
    """Agora, no relógio de Brasília, como datetime naive."""
    return datetime.now(timezone.utc).astimezone(BRT_TZ).replace(tzinfo=None)


def broker_today() -> str:
    """Data corrente (YYYY-MM-DD) no relógio do broker — dia de sessão dos ativos globais."""
    return now_broker_wall().date().isoformat()


def brt_today() -> str:
    """Data corrente (YYYY-MM-DD) em Brasília — dia de sessão da B3."""
    return now_brt_wall().date().isoformat()


def current_session_date(is_b3: bool) -> str:
    """Dia de sessão corrente: B3 usa a data de Brasília; globais usam a data do broker
    (que vira às 17:00 de Nova York = 18:00/19:00 BRT)."""
    return brt_today() if is_b3 else broker_today()


def is_current_session_date(session_date: str) -> bool:
    """True se a data é a sessão corrente da B3 ou dos ativos globais."""
    return session_date in (brt_today(), broker_today())
