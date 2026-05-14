import holidays
from datetime import date

# Initialize the Bangladesh holiday object
# You can specify the year or let it default to the current year
bd_holidays = holidays.Bangladesh(years=2026)

print(f"--- Bangladesh Public Holidays {2026} ---")

# Sort and display the holidays
for date_obj, name in sorted(bd_holidays.items()):
    print(f"{date_obj} : {name}")

# Example: Check if a specific date is a holiday
check_date = "2026-12-16"
if check_date in bd_holidays:
    print(f"\nTarget Check: {check_date} is {bd_holidays.get(check_date)}")