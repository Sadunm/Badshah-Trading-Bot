from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Column, DateTime, Float, Integer, MetaData, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from datetime import datetime
import orjson

from .utils import DB_PATH


class Base(DeclarativeBase):
	pass


class MarketData(Base):
	__tablename__ = "market_data"
	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	pair: Mapped[str] = mapped_column(String(32), index=True)
	timeframe: Mapped[str] = mapped_column(String(10), index=True)
	timestamp: Mapped[int] = mapped_column(Integer, index=True)
	open: Mapped[float] = mapped_column(Float)
	high: Mapped[float] = mapped_column(Float)
	low: Mapped[float] = mapped_column(Float)
	close: Mapped[float] = mapped_column(Float)
	volume: Mapped[float] = mapped_column(Float)


class RunArtifact(Base):
	__tablename__ = "run_artifacts"
	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	type: Mapped[str] = mapped_column(String(32), index=True)  # hyperopt|backtest|strategy|live_metrics
	name: Mapped[str] = mapped_column(String(128), index=True)
	payload: Mapped[Dict[str, Any]] = mapped_column(JSON)
	created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
	score: Mapped[float] = mapped_column(Float, default=0.0)


class PaperTrade(Base):
	__tablename__ = "paper_trades"
	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	pair: Mapped[str] = mapped_column(String(32), index=True)
	side: Mapped[str] = mapped_column(String(8))  # LONG/SHORT (only LONG used)
	qty: Mapped[float] = mapped_column(Float)
	entry_price: Mapped[float] = mapped_column(Float)
	entry_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
	exit_price: Mapped[float] = mapped_column(Float, default=0.0)
	exit_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
	status: Mapped[str] = mapped_column(String(16), default="OPEN")  # OPEN/CLOSED
	pnl: Mapped[float] = mapped_column(Float, default=0.0)


def get_engine(db_path: Path | str = DB_PATH):
	path = Path(db_path)
	path.parent.mkdir(parents=True, exist_ok=True)
	return create_engine(f"sqlite:///{path}", future=True)


def init_db() -> None:
	engine = get_engine()
	Base.metadata.create_all(engine)


def insert_market_rows(rows: List[dict]) -> None:
	engine = get_engine()
	with Session(engine) as s:
		objects = [MarketData(**r) for r in rows]
		s.add_all(objects)
		s.commit()


def fetch_market(pair: str, timeframe: str, limit: int = 1000) -> List[MarketData]:
	engine = get_engine()
	with Session(engine) as s:
		stmt = select(MarketData).where(MarketData.pair == pair, MarketData.timeframe == timeframe).order_by(MarketData.timestamp.desc()).limit(limit)
		return list(s.scalars(stmt))


def save_artifact(atype: str, name: str, payload: Dict[str, Any], score: float = 0.0) -> None:
	engine = get_engine()
	with Session(engine) as s:
		s.add(RunArtifact(type=atype, name=name, payload=payload, score=score))
		s.commit()


def load_latest_artifacts(atype: str, limit: int = 3) -> List[RunArtifact]:
	engine = get_engine()
	with Session(engine) as s:
		stmt = select(RunArtifact).where(RunArtifact.type == atype).order_by(RunArtifact.created_at.desc()).limit(limit)
		return list(s.scalars(stmt))


def atomic_write_json(path: Path, data: dict) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	tmp = path.with_suffix(path.suffix + ".tmp")
	tmp.write_bytes(orjson.dumps(data))
	tmp.replace(path)


# Paper broker helpers
def get_open_trades(pair: str | None = None) -> List[PaperTrade]:
	engine = get_engine()
	with Session(engine) as s:
		stmt = select(PaperTrade).where(PaperTrade.status == "OPEN")
		if pair:
			stmt = stmt.where(PaperTrade.pair == pair)
		return list(s.scalars(stmt))


def open_trade(pair: str, qty: float, price: float) -> int:
	engine = get_engine()
	with Session(engine) as s:
		trade = PaperTrade(pair=pair, side="LONG", qty=qty, entry_price=price)
		s.add(trade)
		s.commit()
		return trade.id  # type: ignore


def close_trade(trade_id: int, price: float) -> None:
	engine = get_engine()
	with Session(engine) as s:
		obj = s.get(PaperTrade, trade_id)
		if obj and obj.status == "OPEN":
			obj.exit_price = price
			obj.exit_time = datetime.utcnow()
			obj.status = "CLOSED"
			obj.pnl = (price - obj.entry_price) * obj.qty
			s.commit()


def compute_equity(starting_balance: float = 1000.0) -> dict:
	engine = get_engine()
	with Session(engine) as s:
		rows = s.scalars(select(PaperTrade).order_by(PaperTrade.entry_time.asc())).all()
		balance = starting_balance
		equity_curve = []
		peak = starting_balance
		max_drawdown = 0.0
		for r in rows:
			if r.status == "CLOSED":
				balance += r.pnl
				peak = max(peak, balance)
				dd = 0.0 if peak == 0 else (peak - balance) / peak
				max_drawdown = max(max_drawdown, dd)
			equity_curve.append({"t": r.exit_time.isoformat() if r.exit_time else r.entry_time.isoformat(), "balance": balance})
		return {"equity": equity_curve, "balance": balance, "max_drawdown": max_drawdown}
