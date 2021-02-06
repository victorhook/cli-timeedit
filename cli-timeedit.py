import argparse
from collections import namedtuple
from datetime import datetime, timedelta
import os
import re
import requests

from rich import print, style
from rich.table import Table


RAW_FILE = 'raw'
RAW_PATH = os.path.join(os.path.dirname(__file__), RAW_FILE)
DEFAULT_URL = 'https://cloud.timeedit.net/lu/web/hbg2/' + \
              'ri6965Qy7Z4275QZ69QQ545QZ76nY8506.ics'

Event = namedtuple('Event', ['start', 'end', 'course', 'summary'])
Day = namedtuple('Day', ['day', 'date', 'events'])
WEEKDAY = {
    1: 'Monday',
    2: 'Tuesday',
    3: 'Wednesday',
    4: 'Thursday',
    5: 'Friday'
}


def scrape(url):
    r = requests.get(url)
    with open(RAW_PATH, 'wb') as f:
        f.write(r.content)


def dateify(raw_date: str):
    date = datetime.strptime(raw_date, '%Y%m%dT%H%M%SZ')
    date += timedelta(hours=1)  # 1 hour behind, not sure how else to fix.
    return date


def delete_temp_raw_file():
    os.remove(RAW_PATH)


def parse_ics(data: str = None) -> dict:
    if data is None:
        with open(RAW_PATH) as f:
            data = f.read()

    events = []
    raw_events = re.findall('(?<=BEGIN:VEVENT\n).*?(?=END:VEVENT)', data,
                            flags=re.DOTALL)
    for event in raw_events:
        # Regex to find values.
        start = re.search('(?<=DTSTART:).*', event).group()
        end = re.search('(?<=DTEND:).*', event).group()
        summary = re.search('(?<=SUMMARY:).*?(?=LOCATION)', event,
                            flags=re.DOTALL).group()
        course, summary = summary.split('\\', maxsplit=1)
        summary = summary.replace('\\', ' - ').replace(',', '').replace('\n ',
                                                                        '')
        events.append(Event(start=dateify(start),
                            end=dateify(end),
                            course=course,
                            summary=summary))

    delete_temp_raw_file()
    return sorted(events, key=lambda e: e.start)


def get_week(date=None):
    if date is None:
        date = datetime.now()
    return date.isocalendar()[1]


def get_day(date=None):
    if date is None:
        date = datetime.now()
    return date.isoweekday()


def events_of_day(week: int, day: str, events: list):
    cleaned_events = []
    for event in events:
        if (get_week(event.start) == week and
           WEEKDAY[get_day(event.start)] == day):
            cleaned_events.append(event)

    return cleaned_events


def parse_week(events, week):
    week_events = {day: events_of_day(week, day, events)
                   for day in WEEKDAY.values()}
    return week_events


def events_at_time(day: str, events: list, hour: int):
    """ Returns if there exists an event on given day, at given hour. """
    all_events = []
    for event in events:
        if hour >= event.start.hour and hour <= event.end.hour:
            all_events.append(event)
    return None if len(all_events) == 0 else all_events


def event_start_at(event: Event, hour: int):
    return event.start.hour*60 + event.start.minute == hour*60


def event_end_at(event: Event, hour: int):
    return event.end.hour*60 + event.end.minute == hour*60


def get_start_event(events: list, hour: int):
    if len(events) == 1:
        return events[0]
    else:
        return events[0] if event_start_at(events[0], hour) else events[1]


def hourify(date) -> str:
    return date.strftime('%H:%M')


def get_date(week: int, day: str, formatted=True):
    year = datetime.now().year
    date = f'{year}-W{week}-{day}'
    fmt = '%G-W%V-%u'
    date = datetime.strptime(date, fmt)

    if formatted:
        date = date.strftime('%d/%m')

    return date


def print_schedule(week: int, events: dict):
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column(f'Week {week}', width=8, style=style.Style(
            bold=True, dim=True, color='light_salmon1'
        ))

    WIDTH = 15

    for i, day in enumerate(['Monday', 'Tuesday', 'Wednesday',
                             'Thursday', 'Friday']):
        day = f'{day} {get_date(week, i+1)}'

        table.add_column(day, width=WIDTH, style=style.Style(
            bold=True, dim=True, color='light_salmon1'
        ))

    rows = []

    for r, hour in enumerate(range(8, 18)):
        row = {
            'Time': f'  {str(hour).zfill(2)}\n\n\n\n',
            'Monday': ' ',
            'Tuesday': ' ',
            'Wednesday': ' ',
            'Thursday': ' ',
            'Friday': ' '
        }

        for day, e in events.items():
            curr_events = events_at_time(day, e, hour)

            if curr_events is not None:

                if len(curr_events) == 1:
                    curr_event = curr_events[0]

                    # Start of event - SINGLE
                    if event_start_at(curr_event, hour):
                        text = f'--{hourify(curr_event.start)}--------'\
                               f'\n    {curr_event.course}'

                    # End of event - SINGLE
                    elif event_end_at(curr_event, hour):
                        text = f'--------{hourify(curr_event.end)}--'

                    # Ongoing event
                    else:
                        text = '  '

                else:
                    # Start of event + End of event => event[1] must be startin
                    text = f'--{hourify(curr_events[1].start)}--------'\
                               f'\n    {curr_events[1].course}'

                    # Add end to last one!
                    rows[r-1][day] += '\n\n\n'
                    rows[r-1][day] += f'--------{hourify(curr_events[0].end)}--'

            else:
                # No event
                text = ' '

            row[day] = text
        rows.append(row)

    for row in rows:
        table.add_row(*row.values())

    print(table)


def parse_args():
    parser = argparse.ArgumentParser(
                            description='Visualize a schedule for timeedit')
    parser.add_argument('-w', '--week', type=int, required=False,
                        help=f'python {__file__} -w week',
                        default=get_week())
    parser.add_argument('-u', '--url', type=str, required=False,
                        help='URL of .ics file from time-edit.',
                        default=DEFAULT_URL)
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()

    # Get the .ics file from web and save it.
    scrape(args.url)

    # Parse all the data from .ics file into events.
    events = parse_ics()

    # Parse the evens of the given week.
    weekly_events = parse_week(events, args.week)

    # Print out the schedule!
    print_schedule(args.week, weekly_events)
