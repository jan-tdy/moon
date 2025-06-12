#!/usr/bin/env python3
import sys, calendar, csv, math
from datetime import datetime, timedelta
from skyfield.api import load, Topos
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QGridLayout, QVBoxLayout, QScrollArea,
    QPushButton, QFileDialog, QMessageBox, QHBoxLayout
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4

# ─────────────────────── Ephemeris ───────────────────────
E = load('de421.bsp')
earth, sun, moon = E['earth'], E['sun'], E['moon']
location = earth + Topos('48.935 N', '22.274 E')
ts = load.timescale()
EXPORT_DATA = []

# ───────────────────── Helper functions ──────────────────

def find_sun_below_horizon(date, target=-18):
    start, end = ts.utc(date.year, date.month, date.day, 12, 0), ts.utc(date.year, date.month, date.day, 23, 59)
    if location.at(end).observe(sun).apparent().altaz()[0].degrees > target:
        return None
    for _ in range(30):  # binary search
        mid = ts.tt(jd=(start.tt + end.tt) / 2)
        alt = location.at(mid).observe(sun).apparent().altaz()[0].degrees
        if alt < target:
            end = mid
        else:
            start = mid
    return end

def illumination(sep_deg):
    return (1 - math.cos(math.radians(sep_deg))) / 2 * 100

def moon_emoji(pct, waxing):
    if pct is None: return "❔"
    if pct < 5:     return "🌑"
    if pct < 40:    return "🌒" if waxing else "🌘"
    if pct < 60:    return "🌓" if waxing else "🌗"
    if pct < 95:    return "🌔" if waxing else "🌖"
    return "🌕"

# ───────────────────── Year calculation ──────────────────

def compute_year(year=2025):
    start = datetime(year, 1, 1)
    days = 365 + (1 if calendar.isleap(year) else 0)
    dates, emojis, stars = [], [], []
    EXPORT_DATA.clear()

    for i in range(days):
        date = start + timedelta(days=i)
        t_obs = find_sun_below_horizon(date, -18)
        if t_obs is None:
            t_obs = find_sun_below_horizon(date, -12)

        if t_obs:
            sun_app  = location.at(t_obs).observe(sun).apparent()
            moon_app = location.at(t_obs).observe(moon).apparent()
            pct      = illumination(sun_app.separation_from(moon_app).degrees)

            # Next‑day illumination
            next_t   = find_sun_below_horizon(date + timedelta(days=1), -18)
            if next_t is None:
                next_t = find_sun_below_horizon(date + timedelta(days=1), -12)
            pct_next = pct
            if next_t:
                sun_n  = location.at(next_t).observe(sun).apparent()
                moon_n = location.at(next_t).observe(moon).apparent()
                pct_next = illumination(sun_n.separation_from(moon_n).degrees)
            waxing = pct_next > pct
            emoji  = moon_emoji(pct, waxing)
            up     = moon_app.altaz()[0].degrees > 0
        else:
            emoji, up = "❔", False

        dates.append(date)
        emojis.append(emoji)
        stars.append(not up)
        EXPORT_DATA.append((date.strftime('%Y-%m-%d'), emoji, up))
    return dates, emojis, stars

# ───────────────────────── GUI ───────────────────────────
class MoonCalendar(QWidget):
    def __init__(self, dates, emojis, stars):
        super().__init__()
        self.setWindowTitle("Moon Phases 2025")
        main = QVBoxLayout(self)

        # Buttons
        hl = QHBoxLayout()
        b_csv = QPushButton("Export CSV"); b_csv.clicked.connect(self.export_csv)
        b_pdf = QPushButton("Export PDF"); b_pdf.clicked.connect(self.export_pdf)
        hl.addWidget(b_csv); hl.addWidget(b_pdf); hl.addStretch(); main.addLayout(hl)

        # Scroll
        scroll = QScrollArea(); scroll.setWidgetResizable(True); main.addWidget(scroll)
        cont = QWidget(); scroll.setWidget(cont); v = QVBoxLayout(cont)

        fe, fs, fd = QFont("Sans Serif", 18), QFont("Sans Serif", 14), QFont("Sans Serif", 10)
        start_idx = datetime(2025,1,1)
        for m in range(1, 13):
            v.addWidget(self._label(calendar.month_name[m], fs, bold=True))
            grid = QGridLayout(); v.addLayout(grid)
            for d in range(1, calendar.monthrange(2025, m)[1] + 1):
                idx = (datetime(2025, m, d) - start_idx).days
                grid.addWidget(self._label(emojis[idx], fe), 0, d - 1)
                if stars[idx]: grid.addWidget(self._label("⭐", fs), 1, d - 1)
                grid.addWidget(self._label(str(d), fd), 2, d - 1)
        legend = self._label("🌑 New 🌒 WC 🌓 1Q 🌔 WG 🌕 Full 🌖 WGib 🌗 3Q 🌘 WC ⭐ Below", fs)
        v.addWidget(legend)
        self.resize(1200, 800)

    def _label(self, txt, font, bold=False):
        l = QLabel(txt); l.setFont(font); l.setAlignment(Qt.AlignCenter)
        if bold: l.setStyleSheet("font-weight: bold")
        return l

    # ---------- CSV ----------
    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "CSV", "moon.csv", "*.csv")
        if path:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f); w.writerow(["Date", "Phase", "Up"]); w.writerows(EXPORT_DATA)
            QMessageBox.information(self, "Done", path)

    # ---------- PDF ----------
    def export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "PDF", "moon.pdf", "*.pdf")
        if not path: return
        w, h = landscape(A4); c = canvas.Canvas(path, pagesize=(w, h))
        margin, cw, ch = 40, (w - 80) / 31, (h - 80) / 6
        fs = min(cw, ch) * 0.7
        start_idx = datetime(2025, 1, 1)
        for page, months in enumerate((range(1, 7), range(7, 13))):
            for r, m in enumerate(months):
                y = h - margin - r * ch - ch / 2
                c.setFont("Helvetica-Bold", fs)
                c.drawString(margin, y + ch / 4, calendar.month_name[m])
                c.setFont("Helvetica", fs)
                for d in range(1, calendar.monthrange(2025, m)[1] + 1):
                    idx = (datetime(2025, m, d) - start_idx).days
                    txt = EXPORT_DATA[idx][1] + ("*" if not EXPORT_DATA[idx][2] else "")
                    x = margin + (d - 1) * cw + cw / 2
                    c.drawCentredString(x, y, txt)
            if page == 0: c.showPage()
        c.save()

# ───────────────────────── Main ──────────────────────────
if __name__ == '__main__':
    app = QApplication(sys.argv)
    dates, emojis, stars = compute_year()
    win = MoonCalendar(dates, emojis, stars)
    win.show()
    sys.exit(app.exec())