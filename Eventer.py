import requests
import yfinance as yf
from ics import Calendar, Event
from datetime import datetime, timedelta, date
import pytz
import pandas as pd
import cloudscraper
from bs4 import BeautifulSoup
import re
import calendar
import time

def fetch_economic_releases(start_date, end_date):
    economic_events = []
    current_date = start_date
    while current_date <= end_date:
        date_str = "calendar?day=" + current_date.strftime('%b').lower() + str(current_date.day) + '.' + str(current_date.year)
        getEventsForDate(date_str, current_date, economic_events)
        current_date += timedelta(days=1)
    return economic_events

def getEventsForDate(date_str, date_obj, economic_events):
    scraper = cloudscraper.create_scraper()
    url = 'https://www.forexfactory.com/' + date_str
    page = scraper.get(url).text
    soup = BeautifulSoup(page, 'html.parser')
    table = soup.find('table', class_='calendar__table')
    if not table:
        print(f"No data found for {date_str}")
        return
    # Event Rows
    event_rows = table.find_all('tr', class_=re.compile('calendar__row'))
    event_time_holder = ''
    for row in event_rows:
        time_cell = row.find('td', class_='calendar__time')
        if time_cell:
            event_time_text = time_cell.text.strip()
            if event_time_text:
                event_time_holder = event_time_text
            else:
                event_time_text = event_time_holder
        else:
            continue

        curr_cell = row.find('td', class_='calendar__currency')
        curr = curr_cell.text.strip() if curr_cell else ''
        impact_span = row.find('td', class_='calendar__impact').find('span')
        impact = impact_span.get('title', '') if impact_span else ''
        event_cell = row.find('td', class_='calendar__event')
        event_title_span = event_cell.find('span', class_='calendar__event-title') if event_cell else None
        event = event_title_span.text.strip() if event_title_span else ''
        previous_cell = row.find('td', class_='calendar__previous')
        previous = previous_cell.text.strip() if previous_cell else ''
        forecast_cell = row.find('td', class_='calendar__forecast')
        forecast = forecast_cell.text.strip() if forecast_cell else ''
        actual_cell = row.find('td', class_='calendar__actual')
        actual = actual_cell.text.strip() if actual_cell else ''

        # Parse event_time_text
        try:
            if 'Tentative' in event_time_text:
                event_time = 'Tentative'
            else:
                matchObj = re.search('([0-9]+)(:[0-9]{2})([a|p]m)', event_time_text)
                if matchObj:
                    event_time_hour = matchObj.group(1)
                    event_time_minutes = matchObj.group(2)
                    am_or_pm = matchObj.group(3)
                    adjusted_time = time.strptime(f"{event_time_hour}{event_time_minutes} {am_or_pm}", "%I:%M %p")
                    event_time = time.strftime("%H:%M", adjusted_time)
                elif re.search('All Day', event_time_text):
                    event_time = '00:00'
                elif re.search('Day [0-9]+', event_time_text):
                    event_time = '00:00'
                else:
                    event_time = event_time_holder  # Use previous event_time_holder

            event_date = date_obj.strftime("%Y-%m-%d")

        except Exception as e:
            print(f"There was an error parsing event time: {e}")
            continue

        description = f"{curr} {impact} {event}\nPrevious: {previous}\nForecast: {forecast}\nActual: {actual}"

        event_info = {
            'title': event,
            'date': event_date,
            'time': event_time,
            'description': description,
            'timezone': 'US/Eastern',  # Forex Factory times are in US Eastern Time
        }
        economic_events.append(event_info)

def fetch_earnings_dates(tickers):
    earnings_events = []
    for ticker in tickers:
        stock = yf.Ticker(ticker)
        try:
            earnings_calendar = stock.get_earnings_dates(limit=1)
            if not earnings_calendar.empty:
                earnings_date = earnings_calendar.index[0]
                earnings_time = '00:00'  # Default time, as exact time may not be available
                event_info = {
                    'title': f"{ticker} Earnings Release",
                    'date': earnings_date.strftime('%Y-%m-%d'),
                    'time': earnings_time,
                    'description': f"Earnings release for {ticker}.",
                    'timezone': 'US/Eastern',
                }
                earnings_events.append(event_info)
        except Exception as e:
            print(f"Error fetching earnings for {ticker}: {e}")
    return earnings_events

def create_calendar_events(events):
    calendar = Calendar()
    for event_info in events:
        event = Event()
        event.name = event_info['title']
        event.description = event_info['description']
        event_timezone = pytz.timezone(event_info['timezone'])
        try:
            if event_info['time'] == 'Tentative':
                # Create an all-day event
                event_begin = datetime.strptime(event_info['date'], "%Y-%m-%d")
                event.begin = event_begin.date()
                event.make_all_day()
            else:
                event_time_str = f"{event_info['date']} {event_info['time']}"
                event_begin = datetime.strptime(event_time_str, "%Y-%m-%d %H:%M")
                event_begin = event_timezone.localize(event_begin)
                event.begin = event_begin
                event.duration = timedelta(hours=1)
            calendar.events.add(event)
        except Exception as e:
            print(f"Error creating event '{event_info['title']}': {e}")
    return calendar

def main():
    # Fetch economic releases
    start_date = date.today()
    end_date = start_date + timedelta(days=30)
    economic_events = fetch_economic_releases(start_date, end_date)

    # Define the list of tickers you're interested in
    tickers = ['AAPL', 'MSFT', 'GOOG', 'AMZN']
    earnings_events = fetch_earnings_dates(tickers)

    # Combine all events
    all_events = economic_events + earnings_events

    # Create calendar events
    calendar = create_calendar_events(all_events)

    # Export to .ics file
    with open('events_calendar.ics', 'w') as f:
        f.writelines(calendar)
    print("Calendar file 'events_calendar.ics' has been created.")

if __name__ == '__main__':
    main()
