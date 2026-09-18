"""
Hardware abstraction layer over the Waveshare 7.5" B/W V2 e-paper panel.

The daemon in ``main.py`` only ever calls the high-level methods on
``EpdManager``; it never touches the raw driver. This is what lets us:

  * Build and test the rest of the codebase on a PC where the SDK is not
    installed.
  * Centralize the PRD-required refresh policy (partial updates during the
    day, full refresh + ``sleep()`` at night, periodic ghosting wash).

Reference calls (per the provided waveshare sample):

    epd.init()
    epd.Clear()
    epd.display(epd.getbuffer(image))
    epd.init_part()
    epd.display_Partial(epd.getbuffer(image), 0, 0, epd.width, epd.height)
    epd.sleep()
    epd7in5_V2_old.epdconfig.module_exit(cleanup=True)
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

from PIL import Image

log = logging.getLogger(__name__)


class EpdManager:
    """Thin wrapper around ``waveshare_epd.epd7in5_V2_old``.

    All public methods are no-ops if the SDK cannot be imported (so PC
    preview / unit tests run cleanly). They log a single warning at
    construction time so missing hardware is obvious.
    """

    def __init__(self) -> None:
        self._epd = None
        self._module = None
        self._init_partial_done = False
        try:
            from waveshare_epd import epd7in5_V2_old  # type: ignore
            self._module = epd7in5_V2_old
            self._epd = epd7in5_V2_old.EPD()
            log.info("EpdManager: e-paper initialised (driver=%s)",
                     epd7in5_V2_old.__name__)
        except Exception as exc:
            log.warning(
                "EpdManager: waveshare_epd SDK unavailable — "
                "all display calls will be no-ops (%s)",
                exc,
            )

    # ------------------------------------------------------------------
    # Capability check
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return self._epd is not None

    # ------------------------------------------------------------------
    # Low-level updates
    # ------------------------------------------------------------------

    def partial_update(self, image: Image.Image) -> None:
        """Push ``image`` using the partial-refresh path.

        Per the PRD this MUST NOT touch the sleep state — the panel stays
        primed for the next partial update.
        """
        if self._epd is None:
            return
        if not self._init_partial_done:
            self._epd.init_part()
            self._init_partial_done = True
        self._epd.display_Partial(
            self._epd.getbuffer(image),
            0, 0, self._epd.width, self._epd.height,
        )

    def full_update(self, image: Image.Image) -> None:
        """Push ``image`` with a full-refresh cycle."""
        if self._epd is None:
            return
        if not self._init_partial_done:
            # First paint after power-on — full init is mandatory
            self._epd.init()
        else:
            self._epd.init()
        self._epd.display(self._epd.getbuffer(image))
        self._init_partial_done = False  # full cycle wipes part state

    def clear(self) -> None:
        if self._epd is None:
            return
        self._epd.init()
        self._epd.Clear()
        self._init_partial_done = False

    # ------------------------------------------------------------------
    # High-level operations called from the daemon FSM
    # ------------------------------------------------------------------

    def wash(self, image: Image.Image) -> None:
        """Periodic ghosting wash: init -> Clear -> full update -> init_part."""
        if self._epd is None:
            return
        log.info("wash: full Clear + display")
        self._epd.init()
        self._epd.Clear()
        self._epd.display(self._epd.getbuffer(image))
        self._epd.init_part()
        self._init_partial_done = True

    def wake_to_partial(self, image: Image.Image) -> None:
        """06:00 transition: do one full refresh, then prime for partial."""
        if self._epd is None:
            return
        log.info("wake_to_partial: init + full update + init_part")
        self._epd.init()
        self._epd.display(self._epd.getbuffer(image))
        self._epd.init_part()
        self._init_partial_done = True

    def sleep(self) -> None:
        """Power the panel down. Called only at night."""
        if self._epd is None:
            return
        try:
            self._epd.sleep()
        except Exception as exc:
            log.warning("sleep() raised: %s", exc)
        self._init_partial_done = False

    def cleanup(self) -> None:
        """Release SPI / GPIO. Called from main.py on shutdown."""
        if self._module is None:
            return
        try:
            self._module.epdconfig.module_exit(cleanup=True)
            log.info("epdconfig.module_exit(cleanup=True) done")
        except Exception as exc:
            log.warning("module_exit raised: %s", exc)