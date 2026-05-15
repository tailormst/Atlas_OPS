"""
Distributed Circuit Breaker for ATLAS-OPS.

One PyBreaker instance per gateway. Provides async-compatible
success/failure recording and force-open/close for outage simulation.
"""
import json
from datetime import datetime, timezone
from typing import Callable

import pybreaker
import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

SUPPORTED_GATEWAYS = ["stripe", "razorpay", "paypal", "square"]


class GatewayCircuitBreakers:
    """
    Registry of circuit breakers, one per gateway.
    """

    def __init__(self) -> None:
        self._breakers: dict[str, pybreaker.CircuitBreaker] = {}

    def initialise(self) -> None:
        """Create circuit breakers for all supported gateways."""
        for gw in SUPPORTED_GATEWAYS:
            breaker = pybreaker.CircuitBreaker(
                fail_max=settings.circuit_breaker_fail_max,
                reset_timeout=settings.circuit_breaker_reset_timeout,
                name=gw,
                listeners=[CircuitBreakerEventListener(gw)],
            )
            self._breakers[gw] = breaker
            logger.info("circuit_breaker_initialised", gateway=gw)

    def get(self, gateway_name: str) -> pybreaker.CircuitBreaker:
        name = gateway_name.lower()
        if name not in self._breakers:
            raise ValueError(f"No circuit breaker for gateway: {gateway_name}")
        return self._breakers[name]

    def is_open(self, gateway_name: str) -> bool:
        """Check if a gateway's circuit breaker is open."""
        try:
            breaker = self.get(gateway_name)
            return breaker.current_state == pybreaker.STATE_OPEN
        except Exception:
            return False

    def record_success(self, gateway_name: str) -> None:
        """Record a successful gateway call. Resets fail counter."""
        try:
            breaker = self.get(gateway_name)
            # Call a no-op function through the breaker to record success
            breaker.call(lambda: None)
        except pybreaker.CircuitBreakerError:
            # Circuit is open — that's fine, we tried
            pass
        except Exception as exc:
            logger.debug("cb_record_success_failed", gateway=gateway_name, error=str(exc))

    def record_failure(self, gateway_name: str) -> None:
        """Record a failed gateway call. Increments fail counter."""
        try:
            breaker = self.get(gateway_name)
            # Call a function that raises through the breaker to record failure
            try:
                breaker.call(lambda: (_ for _ in ()).throw(Exception("gateway_failure")))
            except pybreaker.CircuitBreakerError:
                # Circuit just opened — that's expected
                logger.warning("circuit_breaker_opened_by_failure", gateway=gateway_name)
            except Exception:
                # The lambda's exception — expected, breaker counted it
                pass
        except Exception as exc:
            logger.debug("cb_record_failure_failed", gateway=gateway_name, error=str(exc))

    def get_all_states(self) -> dict[str, dict]:
        states = {}
        for name, breaker in self._breakers.items():
            states[name] = {
                "state": breaker.current_state,
                "fail_counter": breaker.fail_counter,
                "fail_max": breaker.fail_max,
                "reset_timeout": breaker.reset_timeout,
            }
        return states

    def force_open(self, gateway_name: str) -> None:
        """Force-open a circuit (for outage simulation)."""
        breaker = self.get(gateway_name)
        # Record enough failures to trigger the circuit breaker to open
        for _ in range(breaker.fail_max + 2):
            try:
                breaker.call(lambda: (_ for _ in ()).throw(Exception("forced_outage")))
            except (pybreaker.CircuitBreakerError, Exception):
                pass
        logger.warning(
            "circuit_breaker_force_opened",
            gateway=gateway_name,
            state=breaker.current_state,
            fail_counter=breaker.fail_counter,
        )

    def force_close(self, gateway_name: str) -> None:
        """Force-close a circuit (recover from simulation)."""
        breaker = self.get(gateway_name)
        # Reset by creating a new breaker with same config
        new_breaker = pybreaker.CircuitBreaker(
            fail_max=breaker.fail_max,
            reset_timeout=breaker.reset_timeout,
            name=gateway_name,
            listeners=[CircuitBreakerEventListener(gateway_name)],
        )
        self._breakers[gateway_name.lower()] = new_breaker
        logger.info(
            "circuit_breaker_force_closed",
            gateway=gateway_name,
            state=new_breaker.current_state,
        )


class CircuitBreakerEventListener(pybreaker.CircuitBreakerListener):
    """Log every state transition as a structured JSON event."""

    def __init__(self, gateway: str) -> None:
        self.gateway = gateway

    def state_change(self, cb: pybreaker.CircuitBreaker, old_state, new_state) -> None:
        logger.warning(
            "circuit_breaker_state_change",
            gateway=self.gateway,
            old_state=str(old_state),
            new_state=str(new_state),
            fail_counter=cb.fail_counter,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def failure(self, cb: pybreaker.CircuitBreaker, exc: Exception) -> None:
        logger.error(
            "circuit_breaker_failure",
            gateway=self.gateway,
            error=str(exc),
            fail_counter=cb.fail_counter,
        )

    def success(self, cb: pybreaker.CircuitBreaker) -> None:
        logger.debug("circuit_breaker_success", gateway=self.gateway)


# Global singleton — initialised at app startup
circuit_breakers = GatewayCircuitBreakers()
