from datetime import date
from duka.app.app import app
from duka.core.utils import TimeFrame

print("Testing duka download...")
app(
    symbols=["EURUSD"],
    start=date(2023, 1, 1),
    end=date(2023, 1, 2),
    threads=1,
    timeframe=TimeFrame.M1,
    folder=".",
    header=True
)
print("Download finished.")
