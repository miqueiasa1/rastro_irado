"""
Registro imutável de versões de modelo (fase 16, v2.0 — REQ-P01..P06, REQ-N06).

Regra 5 (.agents/AGENTS.md): parâmetros de modelo nunca são apagados. Recalibrar = nova versão.
Recalcular uma data passada = usar a versão vigente naquela data.

Tabelas (migração aditiva, ver ``ensure_schema``):
  - ``model_versions``: uma linha por calibração/treino. Imutável, exceto ``status``,
    ``effective_from`` e ``effective_to`` (promoção/aposentadoria), garantido por trigger.
  - ``model_version_events``: trilha de auditoria append-only (registro, promoção, aposentadoria).
  - ``model_params.version_id``: liga as linhas novas de ``model_params`` à versão (NULL = legado).
  - ``irai_live_snapshots.model_version`` e ``kalman_state.model_version``: versão usada.
  - ``asset_models.forecast_mode`` / ``forecast_ui``: flags por alvo (padrão 'off'; usadas na fase 19+).

Enquanto ``model_versions`` não existir (migração não aplicada) o engine segue o caminho legado
(MAX(effective_from) por parâmetro), com comportamento idêntico ao de antes da fase 16.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from datetime import date, datetime, timedelta, timezone
from typing import Optional

KIND_NOWCAST = "nowcast"
KINDS = ("nowcast", "forecast")
STATUSES = ("shadow", "active", "retired", "rejected")
LEGACY_VERSION = "legacy"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ModelVersionUnavailable(Exception):
    """Não há versão registrada vigente na data pedida (ex.: data anterior à primeira versão).

    Recalcular essa data com os parâmetros atuais seria repaint; a verdade é o snapshot gravado ao vivo.
    """

    def __init__(self, slug: str, session_date: str, first_effective: Optional[str] = None):
        self.slug = slug
        self.session_date = session_date
        self.first_effective = first_effective
        msg = (f"Sem versão de modelo vigente para '{slug}' em {session_date}"
               + (f" (primeira versão registrada vale a partir de {first_effective})" if first_effective else "")
               + ". Recálculo bloqueado para evitar repaint; use o snapshot ao vivo.")
        super().__init__(msg)


# ── Schema ────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS model_versions (
    version_id      TEXT PRIMARY KEY,
    slug            TEXT NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('nowcast','forecast')),
    status          TEXT NOT NULL CHECK (status IN ('shadow','active','retired','rejected')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    fitted_at       TEXT,
    effective_from  TEXT,
    effective_to    TEXT,
    train_start     TEXT,
    train_end       TEXT,
    config_json     TEXT NOT NULL,
    artifact_json   TEXT NOT NULL,
    metrics_json    TEXT,
    code_git_sha    TEXT,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_mv_slug_kind ON model_versions(slug, kind, effective_from);

CREATE TABLE IF NOT EXISTS model_version_events (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id      TEXT NOT NULL,
    event           TEXT NOT NULL,
    from_status     TEXT,
    to_status       TEXT,
    effective_from  TEXT,
    effective_to    TEXT,
    actor           TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_mve_version ON model_version_events(version_id);

-- Imutabilidade (REQ-N06): versões nunca são apagadas; só status/vigência mudam.
CREATE TRIGGER IF NOT EXISTS trg_model_versions_no_delete
BEFORE DELETE ON model_versions
BEGIN
    SELECT RAISE(ABORT, 'model_versions e imutavel: DELETE proibido (Regra 5)');
END;

CREATE TRIGGER IF NOT EXISTS trg_model_versions_immutable
BEFORE UPDATE ON model_versions
WHEN NEW.version_id IS NOT OLD.version_id
  OR NEW.slug IS NOT OLD.slug
  OR NEW.kind IS NOT OLD.kind
  OR NEW.created_at IS NOT OLD.created_at
  OR NEW.fitted_at IS NOT OLD.fitted_at
  OR NEW.train_start IS NOT OLD.train_start
  OR NEW.train_end IS NOT OLD.train_end
  OR NEW.config_json IS NOT OLD.config_json
  OR NEW.artifact_json IS NOT OLD.artifact_json
  OR NEW.metrics_json IS NOT OLD.metrics_json
  OR NEW.code_git_sha IS NOT OLD.code_git_sha
  OR NEW.notes IS NOT OLD.notes
BEGIN
    SELECT RAISE(ABORT, 'model_versions e imutavel: so status/effective_from/effective_to podem mudar (Regra 5)');
END;

CREATE TRIGGER IF NOT EXISTS trg_model_version_events_no_delete
BEFORE DELETE ON model_version_events
BEGIN
    SELECT RAISE(ABORT, 'model_version_events e append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_model_version_events_no_update
BEFORE UPDATE ON model_version_events
BEGIN
    SELECT RAISE(ABORT, 'model_version_events e append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_model_params_no_delete
BEFORE DELETE ON model_params
BEGIN
    SELECT RAISE(ABORT, 'model_params e imutavel: recalibrar = nova versao (Regra 5)');
END;

CREATE TRIGGER IF NOT EXISTS trg_model_params_no_update
BEFORE UPDATE ON model_params
BEGIN
    SELECT RAISE(ABORT, 'model_params e imutavel: recalibrar = nova versao (Regra 5)');
END;
"""

# (tabela, coluna, tipo) — todas aditivas (ALTER TABLE ADD COLUMN), nunca removidas/renomeadas.
ADDED_COLUMNS = [
    ("model_params", "version_id", "TEXT"),
    ("irai_live_snapshots", "model_version", "TEXT"),
    ("kalman_state", "model_version", "TEXT"),
    ("asset_models", "forecast_mode", "TEXT DEFAULT 'off'"),
    ("asset_models", "forecast_ui", "TEXT DEFAULT 'off'"),
]


def table_exists(conn, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def column_exists(conn, table: str, column: str) -> bool:
    try:
        cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.Error:
        return False
    return any((c[1] if not isinstance(c, sqlite3.Row) else c["name"]) == column for c in cols)


def has_registry(conn) -> bool:
    """True se a migração da fase 16 foi aplicada (tabela model_versions existe)."""
    return table_exists(conn, "model_versions")


def ensure_schema(conn) -> list[str]:
    """Aplica as migrações aditivas da fase 16 (idempotente). Não faz commit nem DROP.

    Retorna a lista de mudanças efetivamente feitas (vazia se já estava migrado).
    """
    changes: list[str] = []
    before_tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','trigger','index')")}
    for stmt in _split_sql(SCHEMA_SQL):
        conn.execute(stmt)
    after_tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','trigger','index')")}
    for name in sorted(after_tables - before_tables):
        changes.append(f"+ {name}")
    for table, col, ctype in ADDED_COLUMNS:
        if not table_exists(conn, table):
            continue
        if column_exists(conn, table, col):
            continue
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ctype}")
            changes.append(f"+ {table}.{col}")
        except sqlite3.OperationalError as exc:  # corrida com outro processo
            if "duplicate column" not in str(exc).lower():
                raise
    return changes


def _split_sql(script: str) -> list[str]:
    """Divide o script em comandos, respeitando BEGIN...END dos triggers."""
    stmts, buf, in_trigger = [], [], False
    for line in script.splitlines():
        s = line.strip()
        if not s or s.startswith("--"):
            continue
        buf.append(line)
        up = s.upper()
        if up.startswith("CREATE TRIGGER"):
            in_trigger = True
        if in_trigger:
            if up == "END;":
                stmts.append("\n".join(buf))
                buf, in_trigger = [], False
        elif s.endswith(";"):
            stmts.append("\n".join(buf))
            buf = []
    if buf:
        stmts.append("\n".join(buf))
    return stmts


# ── Parâmetros ────────────────────────────────────────────────────────────

def parse_param_map(param_map: dict) -> tuple[dict, dict, float, float]:
    """Converte {nome_sem_prefixo: valor} em (weights, sigmas, alpha, intercept).

    Mesma regra que o engine sempre usou em ``_load_params`` (mantida idêntica para não mudar P).
    """
    weights, sigmas = {}, {}
    alpha, intercept = 1.0, 0.0
    for clean, value in param_map.items():
        if clean.startswith("w_"):
            weights[clean] = value
        elif clean.startswith("sigma_"):
            label = clean.replace("sigma_", "").replace("_session", "").replace("_daily", "")
            sigmas[label] = value
        elif clean == "alpha":
            alpha = value
        elif clean == "intercept":
            intercept = value
    return weights, sigmas, alpha, intercept


# Fase 17 (REQ-M01/M04): opções de cálculo gravadas como params numéricos da versão.
# Versões sem essas chaves (legado e a adotada na fase 16) mantêm o cálculo antigo, bit a bit.
ENGINE_OPTION_DEFAULTS = {
    "unit_fix": 0.0,            # 1 = score no espaço certo: Σ βᵢ·σᵢ·zᵢ (= Σ βᵢ·rᵢ) ÷ score_scale
    "score_scale": 1.0,         # desvio de Σ βᵢ·rᵢ na janela de calibração (score fica em "desvios")
    "kalman_obs_cov": 1e-3,     # R (%²): padrão antigo; a fase 17 grava a variância real do resíduo
    "kalman_trans_cov": 1e-5,   # Q por barra (random walk dos β)
}


def engine_options(param_map: dict) -> dict:
    """Opções de cálculo de uma versão (defaults = comportamento anterior à fase 17)."""
    out = dict(ENGINE_OPTION_DEFAULTS)
    for k in out:
        if k in param_map and param_map[k] is not None:
            out[k] = float(param_map[k])
    if out["score_scale"] <= 0:
        out["score_scale"] = 1.0
    return out


def legacy_params_sql(conn) -> str:
    """SQL do caminho legado (MAX(effective_from) por parâmetro), com 2 placeholders LIKE.

    Depois da migração, linhas com ``version_id`` (gravadas por calibrações versionadas, inclusive
    'shadow') ficam FORA do caminho legado — senão uma versão shadow viraria "a mais recente".
    Antes da migração a coluna não existe e o SQL é exatamente o de sempre.
    """
    only_legacy = column_exists(conn, "model_params", "version_id")
    flt = " AND version_id IS NULL" if only_legacy else ""
    flt_mp = " AND mp.version_id IS NULL" if only_legacy else ""
    return f"""
        SELECT mp.param_name, mp.value, mp.effective_from FROM model_params mp
        INNER JOIN (
            SELECT param_name, MAX(effective_from) as max_eff
            FROM model_params
            WHERE param_name LIKE ?{flt}
            GROUP BY param_name
        ) latest ON mp.param_name = latest.param_name
                 AND mp.effective_from = latest.max_eff
        WHERE mp.param_name LIKE ?{flt_mp}
    """


def legacy_param_rows(conn, slug: str) -> list[tuple[str, float, str]]:
    """Linhas (param_name, value, effective_from) que o caminho legado carrega: MAX(effective_from) por nome."""
    prefix = f"{slug}_"
    rows = conn.execute(legacy_params_sql(conn), (f"{prefix}%", f"{prefix}%")).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def legacy_param_map(conn, slug: str) -> dict:
    prefix = f"{slug}_"
    out = {}
    for name, value, _eff in legacy_param_rows(conn, slug):
        clean = name[len(prefix):] if name.startswith(prefix) else name
        out[clean] = value
    return out


# ── Versões ───────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def make_version_id(conn, slug: str, kind: str, fitted_at: str) -> str:
    stamp = _parse_ts(fitted_at).strftime("%Y%m%dT%H%M%SZ")
    base = f"{slug}-{kind}-{stamp}"
    vid, n = base, 1
    while conn.execute("SELECT 1 FROM model_versions WHERE version_id=?", (vid,)).fetchone():
        n += 1
        vid = f"{base}-{n}"
    return vid


def _unique_fitted_at(conn, slug: str, kind: str, fitted_at: str, check_params: bool = True) -> str:
    """Garante unicidade de (version_id) e da PK (param_name, effective_from) de model_params.

    Duas calibrações no mesmo segundo: avança 1 s (nunca sobrescreve nem colide).
    """
    dt = _parse_ts(fitted_at)
    while True:
        ts = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        vid = f"{slug}-{kind}-{dt.strftime('%Y%m%dT%H%M%SZ')}"
        taken = conn.execute("SELECT 1 FROM model_versions WHERE version_id=?", (vid,)).fetchone()
        if not taken and check_params and kind == KIND_NOWCAST:
            taken = conn.execute("SELECT 1 FROM model_params WHERE param_name LIKE ? AND effective_from=? LIMIT 1",
                                 (f"{slug}_%", ts)).fetchone()
        if not taken:
            return ts
        dt += timedelta(seconds=1)


def code_git_sha(repo_root: str = REPO_ROOT) -> Optional[str]:
    """SHA do HEAD (+ '-dirty' se houver mudanças rastreadas não commitadas)."""
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True,
                             text=True, timeout=10).stdout.strip()
        if not sha:
            return None
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no", "--", "backend", "scripts"],
                               cwd=repo_root, capture_output=True, text=True, timeout=10).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except Exception:
        return None


def _log_event(conn, version_id, event, from_status=None, to_status=None,
               effective_from=None, effective_to=None, actor=None, notes=None):
    conn.execute("""
        INSERT INTO model_version_events
            (version_id, event, from_status, to_status, effective_from, effective_to, actor, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (version_id, event, from_status, to_status, effective_from, effective_to, actor, notes))


def register_version(conn, *, slug: str, param_map: dict, factors: list, factor_labels: dict,
                     kind: str = KIND_NOWCAST, status: str = "shadow", fitted_at: Optional[str] = None,
                     effective_from: Optional[str] = None, train_start: Optional[str] = None,
                     train_end: Optional[str] = None, config: Optional[dict] = None,
                     metrics: Optional[dict] = None, git_sha: Optional[str] = None,
                     notes: Optional[str] = None, actor: str = "calibrate_universal",
                     write_params: bool = True) -> str:
    """Cria uma versão NOVA (INSERT only). Nunca altera nem apaga versões/parâmetros existentes.

    ``write_params=True`` também grava as linhas em ``model_params`` com ``version_id``
    (``effective_from`` = ``fitted_at``), mantendo a tabela compatível com leitores antigos.
    """
    if kind not in KINDS:
        raise ValueError(f"kind inválido: {kind}")
    if status not in ("shadow", "active"):
        raise ValueError("versão nova nasce 'shadow' (ou 'active' só no bootstrap do legado)")
    if status == "active" and not effective_from:
        raise ValueError("versão 'active' exige effective_from")
    if status == "active" and current_active(conn, slug, kind) is not None:
        raise ValueError(f"já existe versão active para {slug}/{kind}; use promote()")
    fitted_at = _unique_fitted_at(conn, slug, kind, fitted_at or _utc_now_iso(), check_params=write_params)
    version_id = make_version_id(conn, slug, kind, fitted_at)
    artifact = {
        "params": {k: float(v) for k, v in param_map.items()},
        "factors": list(factors),
        "factor_labels": dict(factor_labels),
    }
    conn.execute("""
        INSERT INTO model_versions (version_id, slug, kind, status, fitted_at, effective_from, effective_to,
                                    train_start, train_end, config_json, artifact_json, metrics_json,
                                    code_git_sha, notes)
        VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?)
    """, (version_id, slug, kind, status, fitted_at, effective_from, train_start, train_end,
          json.dumps(config or {}, ensure_ascii=False, sort_keys=True),
          json.dumps(artifact, ensure_ascii=False, sort_keys=True),
          json.dumps(metrics, ensure_ascii=False, sort_keys=True) if metrics is not None else None,
          git_sha, notes))
    if write_params and kind == KIND_NOWCAST:
        prefix = f"{slug}_"
        conn.executemany(
            "INSERT INTO model_params (param_name, value, effective_from, version_id) VALUES (?, ?, ?, ?)",
            [(f"{prefix}{k}", float(v), fitted_at, version_id) for k, v in param_map.items()],
        )
    _log_event(conn, version_id, "registered", None, status, effective_from, None, actor, notes)
    return version_id


def _row_to_dict(row, with_artifact: bool = False) -> dict:
    d = dict(row)
    for k in ("config_json", "metrics_json", "artifact_json"):
        if k in d:
            if k == "artifact_json" and not with_artifact:
                d.pop(k)
                continue
            v = d.pop(k)
            d[k[:-5]] = json.loads(v) if v else None
    return d


def get_version(conn, version_id: str, with_artifact: bool = True) -> Optional[dict]:
    row = conn.execute("SELECT * FROM model_versions WHERE version_id=?", (version_id,)).fetchone()
    if row is None:
        return None
    return _row_to_dict(_as_row(conn, row), with_artifact=with_artifact)


def _as_row(conn, row):
    if isinstance(row, sqlite3.Row):
        return row
    cols = [c[1] for c in conn.execute("PRAGMA table_info(model_versions)")]
    return dict(zip(cols, row))


def slug_has_versions(conn, slug: str, kind: str = KIND_NOWCAST) -> bool:
    row = conn.execute("""
        SELECT 1 FROM model_versions WHERE slug=? AND kind=? AND status IN ('active','retired') LIMIT 1
    """, (slug, kind)).fetchone()
    return row is not None


def first_effective_from(conn, slug: str, kind: str = KIND_NOWCAST) -> Optional[str]:
    row = conn.execute("""
        SELECT MIN(effective_from) FROM model_versions
        WHERE slug=? AND kind=? AND status IN ('active','retired') AND effective_from IS NOT NULL
    """, (slug, kind)).fetchone()
    return row[0] if row else None


def resolve_version(conn, slug: str, session_date: str, kind: str = KIND_NOWCAST,
                    with_artifact: bool = True) -> Optional[dict]:
    """Versão vigente na sessão (SPEC §9.2). None se não houver (ex.: data anterior à primeira versão)."""
    row = conn.execute("""
        SELECT * FROM model_versions
        WHERE slug=? AND kind=? AND status IN ('active','retired')
          AND effective_from IS NOT NULL AND effective_from <= ?
          AND (effective_to IS NULL OR effective_to > ?)
        ORDER BY effective_from DESC, created_at DESC LIMIT 1
    """, (slug, kind, session_date, session_date)).fetchone()
    if row is None:
        return None
    return _row_to_dict(_as_row(conn, row), with_artifact=with_artifact)


def current_active(conn, slug: str, kind: str = KIND_NOWCAST, with_artifact: bool = True) -> Optional[dict]:
    row = conn.execute("""
        SELECT * FROM model_versions
        WHERE slug=? AND kind=? AND status='active' AND effective_to IS NULL
        ORDER BY effective_from DESC LIMIT 1
    """, (slug, kind)).fetchone()
    if row is None:
        return None
    return _row_to_dict(_as_row(conn, row), with_artifact=with_artifact)


def list_versions(conn, slug: Optional[str] = None, kind: Optional[str] = None) -> list[dict]:
    """Lista versões SEM artifact_json (REQ-A03)."""
    sql = ("SELECT version_id, slug, kind, status, created_at, fitted_at, effective_from, effective_to, "
           "train_start, train_end, config_json, metrics_json, code_git_sha, notes FROM model_versions")
    where, args = [], []
    if slug:
        where.append("slug=?"); args.append(slug)
    if kind:
        where.append("kind=?"); args.append(kind)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY slug, kind, COALESCE(effective_from, '9999'), created_at"
    cur = conn.execute(sql, args)
    cols = [c[0] for c in cur.description]
    return [_row_to_dict(dict(zip(cols, r))) for r in cur.fetchall()]


def list_events(conn, version_id: Optional[str] = None) -> list[dict]:
    sql = "SELECT * FROM model_version_events"
    args = []
    if version_id:
        sql += " WHERE version_id=?"; args.append(version_id)
    sql += " ORDER BY event_id"
    cur = conn.execute(sql, args)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def promote(conn, version_id: str, effective_from: str, *, actor: str, notes: Optional[str] = None,
            today: Optional[str] = None, allow_today: bool = False, update_asset_models: bool = True) -> dict:
    """shadow → active a partir de ``effective_from`` (REQ-P06: explícito e auditável).

    Fecha a vigência da active anterior (status='retired', effective_to=effective_from).
    ``effective_from`` precisa ser uma sessão FUTURA (> hoje, ou = hoje com ``allow_today``):
    vigência retroativa repintaria sessões já mostradas ao vivo.
    Não faz commit (o chamador decide).
    """
    v = get_version(conn, version_id, with_artifact=True)
    if v is None:
        raise ValueError(f"versão inexistente: {version_id}")
    if v["status"] != "shadow":
        raise ValueError(f"só versões 'shadow' podem ser promovidas (status atual: {v['status']})")
    date.fromisoformat(effective_from)
    if today is None:
        from backend.timeconv import brt_today, broker_today
        today = max(brt_today(), broker_today())
    if effective_from < today or (effective_from == today and not allow_today):
        raise ValueError(f"effective_from={effective_from} não é futuro (hoje={today}); vigência retroativa = repaint")
    prev = current_active(conn, v["slug"], v["kind"], with_artifact=False)
    if prev and prev["effective_from"] and effective_from <= prev["effective_from"]:
        raise ValueError(f"effective_from precisa ser > vigência da active atual ({prev['effective_from']})")
    if prev:
        conn.execute("UPDATE model_versions SET status='retired', effective_to=? WHERE version_id=?",
                     (effective_from, prev["version_id"]))
        _log_event(conn, prev["version_id"], "retired", "active", "retired", prev["effective_from"],
                   effective_from, actor, f"substituída por {version_id}")
    conn.execute("UPDATE model_versions SET status='active', effective_from=? WHERE version_id=?",
                 (effective_from, version_id))
    _log_event(conn, version_id, "promoted", "shadow", "active", effective_from, None, actor, notes)
    if update_asset_models and v["kind"] == KIND_NOWCAST and table_exists(conn, "asset_models"):
        art = v["artifact"]
        metrics = v.get("metrics") or {}
        conn.execute("""
            UPDATE asset_models SET factors=?, factor_labels=?,
                   accuracy=COALESCE(?, accuracy), r_squared=COALESCE(?, r_squared),
                   n_sessions=COALESCE(?, n_sessions), calibrated_at=?
            WHERE slug=?
        """, (json.dumps(art["factors"]), json.dumps(art["factor_labels"]),
              metrics.get("accuracy"), metrics.get("r2"), metrics.get("n_sessions"),
              v.get("fitted_at"), v["slug"]))
    return {"promoted": version_id, "retired": prev["version_id"] if prev else None,
            "effective_from": effective_from}


def reject(conn, version_id: str, *, actor: str, notes: Optional[str] = None) -> None:
    v = get_version(conn, version_id, with_artifact=False)
    if v is None:
        raise ValueError(f"versão inexistente: {version_id}")
    if v["status"] != "shadow":
        raise ValueError("só versões 'shadow' podem ser rejeitadas")
    conn.execute("UPDATE model_versions SET status='rejected' WHERE version_id=?", (version_id,))
    _log_event(conn, version_id, "rejected", "shadow", "rejected", None, None, actor, notes)


# ── Bootstrap do legado ───────────────────────────────────────────────────

def first_full_session_after(calibrated_at: str, is_b3: bool) -> str:
    """Primeira sessão inteira após o instante da calibração.

    B3: se a calibração ocorreu antes das 09:00 BRT, a sessão do mesmo dia já nasce com ela;
    senão a sessão do dia é mista (parte com os parâmetros antigos) e a vigência começa no dia seguinte.
    Globais (dia do broker, 24h): sempre o dia seguinte do broker.
    """
    from backend.timeconv import brt_offset_hours, broker_offset_hours
    utc = _parse_ts(calibrated_at)
    if is_b3:
        wall = utc + timedelta(hours=brt_offset_hours(utc))
        if (wall.hour, wall.minute) < (9, 0):
            return wall.date().isoformat()
        return (wall.date() + timedelta(days=1)).isoformat()
    wall = utc + timedelta(hours=broker_offset_hours(utc))
    return (wall.date() + timedelta(days=1)).isoformat()


def bootstrap_from_legacy(conn, *, actor: str = "migrate_fase16", git_sha: Optional[str] = None,
                          only_active_targets: bool = True) -> list[dict]:
    """Adota os parâmetros atuais (caminho legado) como a primeira versão 'active' de cada slug.

    Idempotente: slugs que já têm qualquer versão são pulados. Não grava em model_params
    (as linhas legadas continuam lá, intocadas; o artefato guarda a cópia exata).
    """
    out = []
    sql = "SELECT target, slug, factors, factor_labels, session_start_h, accuracy, r_squared, n_sessions, calibrated_at FROM asset_models"
    if only_active_targets:
        sql += " WHERE active=1"
    for row in conn.execute(sql + " ORDER BY target").fetchall():
        target, slug = row[0], row[1]
        if conn.execute("SELECT 1 FROM model_versions WHERE slug=? AND kind=? LIMIT 1", (slug, KIND_NOWCAST)).fetchone():
            out.append({"slug": slug, "target": target, "skipped": "já possui versão"})
            continue
        rows = legacy_param_rows(conn, slug)
        if not rows:
            out.append({"slug": slug, "target": target, "skipped": "sem parâmetros em model_params"})
            continue
        prefix = f"{slug}_"
        param_map = {(n[len(prefix):] if n.startswith(prefix) else n): v for n, v, _ in rows}
        legacy_effs = sorted({e for _, _, e in rows})
        fitted_at = legacy_effs[-1]
        calibrated_at = row[8] or fitted_at
        is_b3 = (row[4] or 0) != 0
        eff = first_full_session_after(fitted_at, is_b3)
        factors = json.loads(row[2]) if row[2] else []
        labels = json.loads(row[3]) if row[3] else {}
        config = {
            "adopted_from_legacy": True,
            "source": "model_params MAX(effective_from) por parametro (caminho legado do engine)",
            "legacy_effective_from": legacy_effs,
            "calibrated_at": calibrated_at,
            "target": target,
            "is_b3": is_b3,
            "effective_from_rule": "primeira sessao inteira apos a calibracao",
            "fitting_code": "desconhecido (calibracao anterior ao registro)",
        }
        metrics = {"accuracy": row[5], "r2": row[6], "n_sessions": row[7], "in_sample": True}
        vid = register_version(
            conn, slug=slug, param_map=param_map, factors=factors, factor_labels=labels,
            status="active", fitted_at=fitted_at, effective_from=eff, config=config, metrics=metrics,
            git_sha=git_sha, actor=actor, write_params=False,
            notes=(f"Versão adotada do legado (calibração de {calibrated_at}). Sessões anteriores a {eff}: "
                   "parâmetros originais foram apagados pela recalibração destrutiva; a verdade é o snapshot."),
        )
        out.append({"slug": slug, "target": target, "version_id": vid, "effective_from": eff,
                    "n_params": len(param_map)})
    return out


def is_adopted_from_legacy(version: Optional[dict]) -> bool:
    return bool(version and (version.get("config") or {}).get("adopted_from_legacy"))
