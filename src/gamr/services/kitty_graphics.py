"""Kitty terminal graphics protocol support and logo rendering."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.driver import Driver


class KittyGraphics:
    """Low-level kitty terminal graphics protocol operations."""

    @staticmethod
    def is_supported() -> bool:
        """Check if the terminal supports the kitty graphics protocol."""
        term = os.environ.get("TERM", "").lower()
        term_program = os.environ.get("TERM_PROGRAM", "").lower()
        return (
            "KITTY_WINDOW_ID" in os.environ
            or term == "xterm-ghostty"
            or "GHOSTTY_RESOURCES_DIR" in os.environ
            or "wezterm" in term_program
        )

    @staticmethod
    def transmit_png(image_id: int, png_data: bytes) -> bool:
        """Transmit PNG image data to the terminal. Returns True on success."""
        encoded = base64.standard_b64encode(png_data).decode("ascii")
        chunks = [encoded[i : i + 4096] for i in range(0, len(encoded), 4096)]

        buf = []
        for idx, chunk in enumerate(chunks):
            is_first = idx == 0
            is_last = idx == len(chunks) - 1
            m = 0 if is_last else 1
            if is_first:
                buf.append(f"\033_Ga=t,f=100,q=2,i={image_id},m={m};{chunk}\033\\")
            else:
                buf.append(f"\033_Gm={m};{chunk}\033\\")

        try:
            fd = os.open("/dev/tty", os.O_WRONLY)
            os.write(fd, "".join(buf).encode())
            os.close(fd)
        except OSError:
            return False
        return True

    @staticmethod
    def place(driver: Driver, image_id: int, x: int, y: int, cols: int, rows: int) -> None:
        """Place an image at absolute terminal coordinates (1-based)."""
        seq = f"\033[s\033[{y};{x}H\033_Ga=p,i={image_id},q=2,c={cols},r={rows},C=1;\033\\\033[u"
        driver.write(seq)

    @staticmethod
    def delete(driver: Driver, image_id: int) -> None:
        """Delete all placements of an image."""
        driver.write(f"\033_Ga=d,d=i,i={image_id},q=2;\033\\")


# Row/column diacritics table from kitty protocol spec (unused currently but
# kept for future Unicode placeholder support).
ROW_COL_DIACRITICS = (
    "\u0305\u030d\u030e\u0310\u0312\u033d\u033e\u033f"
    "\u0346\u034a\u034b\u034c\u0350\u0351\u0352\u0357"
    "\u035b\u0363\u0364\u0365\u0366\u0367\u0368\u0369"
    "\u036a\u036b\u036c\u036d\u036e\u036f\u0483\u0484"
    "\u0485\u0486\u0487\u0592\u0593\u0594\u0595\u0597"
    "\u0598\u0599\u059c\u059d\u059e\u059f\u05a0\u05a1"
    "\u05a8\u05a9\u05ab\u05ac\u05af\u05c4\u0610\u0611"
    "\u0612\u0613\u0614\u0615\u0616\u0617\u0657\u0658"
)


class KittyLogo:
    """Manages the gamr PNG logo via the kitty graphics protocol."""

    IMAGE_ID = 42
    COLS = 20

    def __init__(self) -> None:
        self._transmitted = False
        self._png_data: bytes | None = None
        logo_path = Path(__file__).parent.parent / "logo.png"
        if logo_path.exists():
            self._png_data = logo_path.read_bytes()

    @property
    def available(self) -> bool:
        """True if kitty graphics is supported and logo data exists."""
        return KittyGraphics.is_supported() and self._png_data is not None

    def transmit(self) -> bool:
        """Transmit logo image data to the terminal. Returns True on success."""
        if not self.available:
            return False
        self._transmitted = KittyGraphics.transmit_png(self.IMAGE_ID, self._png_data)  # type: ignore[arg-type]
        return self._transmitted

    def place(self, driver: Driver, x: int, y: int, rows: int) -> None:
        """Delete old placement and place logo at given position."""
        if not self._transmitted:
            return
        KittyGraphics.delete(driver, self.IMAGE_ID)
        KittyGraphics.place(driver, self.IMAGE_ID, x, y, self.COLS, rows)

    def delete(self, driver: Driver) -> None:
        """Remove the logo from screen."""
        if not self._transmitted:
            return
        KittyGraphics.delete(driver, self.IMAGE_ID)

    def retransmit_and_place(self, driver: Driver, x: int, y: int, rows: int) -> None:
        """Re-transmit image data and place (use after screen switch)."""
        if not self.available:
            return
        self.transmit()
        self.place(driver, x, y, rows)
