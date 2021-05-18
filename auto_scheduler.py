#!/usr/bin/env python
import io
import subprocess
import os
import datetime
from operator import itemgetter

from typing import Dict

import sync
from colorama import Fore, Back, Style
from tqdm import tqdm

regular_working = {'Monday': 0, 'Tuesday': 0, 'Wednesday': 0, 'Thursday': 0, 'Friday': 0, 'Saturday': 0, 'Sunday': 0}
weekday_conversion = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 4: 'Friday', 5: 'Saturday', 6: 'Sunday'}
one_off_working = {}

time_inc = 1/60
day_start_time = datetime.time(5, 0, 0)


def bool_input(query: str, default: bool = True) -> bool:
    query = query[0].upper() + query[1:]
    if default:
        option_string = '[Y/n]'
    else:
        option_string = '[y/N]'
    while True:
        input_str = input(f'{query}? {option_string}: ')
        if input_str in ['y', '']:
            return True
        elif input_str == "n":
            return False
        print('Invalid input, please try again')


def input_start_date() -> datetime.date:
    # Get date to start on (i.e. current day, tomorrow)
    initial_date = datetime.datetime.now().date()
    if datetime.datetime.now().time() < day_start_time:
        # Before day start time, so count as yesterday
        initial_date -= datetime.timedelta(days=1)
    include_today = bool_input('include today')
    if not include_today:
        initial_date += datetime.timedelta(days=1)
    return initial_date


def get_screen_width(default: int = 30) -> int:
    try:
        return int(os.popen('stty size', 'r').read().split()[1])
    except IndexError:
        return default


def separate_output() -> None:
    output = ''
    print(Back.GREEN)
    for j in range(get_screen_width()):
        output += ':'
    for i in range(20):
        print(output)
    print(Style.RESET_ALL)


def datetime_to_date_string(input_date: datetime.datetime.date) -> str:
    return str(input_date.day) + '/' + str(input_date.month) + '/' + str(input_date.year)[2:]


def date_string_to_datetime(input_date_string: str) -> datetime.date:
    split_string = input_date_string.split('/')
    try:
        local_day = int(split_string[0])
        month = int(split_string[1])
        year = int('20' + split_string[2])
        try:
            return datetime.date(year, month, local_day)
        except ValueError:
            print("Invalid date:", year, month, local_day)
    except IndexError:
        print("Invalid date-string:", input_date_string)


def decimal_to_timestring(value: float) -> str:
    hours = round(value - value % 1)
    minutes = round((value - hours) * 60)
    if minutes == 60:
        hours += 1
        minutes = 0

    if minutes >= 10:
        return str(hours) + ":" + str(minutes)
    else:
        return str(hours) + ":0" + str(minutes)


def timestring_to_decimal(timestring: str) -> float:
    split_time = timestring.split(':')
    hours = float(split_time[0])
    if len(split_time) > 1:
        minutes = float(split_time[1])
    else:
        minutes = 0

    decimal_time = hours + minutes / 60
    return decimal_time


def get_work_on_day(requested_day: datetime.date) -> float:
    weekday = weekday_conversion[requested_day.weekday()]
    regular_work = regular_working[weekday]
    if requested_day in one_off_working:
        one_off_work = one_off_working[requested_day]
        total_work = regular_work + one_off_work
    else:
        total_work = regular_work

    return total_work


def load_fixed_tasks(filename: str = 'day_fixed_work.txt') -> Dict[datetime.date, Dict[str, float]]:
    day_fixed_work = io.open(filename)
    fixed_work_lines = day_fixed_work.readlines()
    # Bring fixed work data into memory structures
    _daily_tasks = {}
    for day_info in fixed_work_lines:
        if day_info == '\n' or day_info[0] == '#':
            continue

        _split_info = day_info.split(';')
        day = _split_info[0]
        work_time = timestring_to_decimal(_split_info[1].split('\n')[0])
        if day in regular_working.keys():
            regular_working[day] += work_time
        elif date_string_to_datetime(day) in one_off_working.keys():
            one_off_working[date_string_to_datetime(day)] += work_time
        else:
            one_off_working[date_string_to_datetime(day)] = work_time

        # Deal with titled work data
        if len(_split_info) >= 3:
            work_title = _split_info[2].strip()
            if day in regular_working.keys():
                # TODO: Deal with regulars
                pass
            else:
                _date = date_string_to_datetime(day)
                if _date in _daily_tasks:
                    if work_title in _daily_tasks[_date]:
                        _daily_tasks[_date][work_title] += work_time
                    else:
                        _daily_tasks[_date][work_title] = work_time
                else:
                    _daily_tasks[_date] = {}
                    _daily_tasks[_date][work_title] = work_time

    return _daily_tasks


def load_flexi_tasks(filename: str = 'one-off_tasks'):
    one_off_tasks = io.open(filename)
    one_off_tasks_lines = one_off_tasks.readlines()
    # Bring task list data into memory structures
    _tasks = []
    due_dateless_task_indices = []
    for _index, _task in enumerate(one_off_tasks_lines):
        split_info = _task.split(';')

        if _task[0] == '#' or split_info == '\n' or '\n' in split_info:
            continue

        _title = split_info[0]
        try:
            _required_hours = timestring_to_decimal(split_info[1].split(' ')[1])
        except IndexError:
            print(split_info)
            continue

        _due_date = split_info[2].split(' ')[1].split('\n')[0]
        if len(split_info) >= 4:
            _min_time = timestring_to_decimal(split_info[3].split(' ')[1])
        else:
            _min_time = 1/60

        if _due_date == 'none':
            due_dateless_task_indices.append(_index)
            _start_date = max(date_string_to_datetime(_due_date[0]), cur_date)
            _due_date = date_string_to_datetime('1/1/01')
        elif len(_due_date.split('-')) > 1:
            _due_date = _due_date.split('-')
            _start_date = max(date_string_to_datetime(_due_date[0]), cur_date)
            _due_date = date_string_to_datetime(_due_date[1])
        else:
            _start_date = cur_date
            _due_date = date_string_to_datetime(_due_date)

        _actual_due_date = _due_date
        _due_date = max(_due_date, cur_date + datetime.timedelta(days=1))
        if _due_date.weekday() in [6, 5] and not include_weekends:
            _due_date = _due_date - datetime.timedelta(days=_due_date.weekday() - 4)
            if _start_date > _due_date:
                _start_date = _due_date - datetime.timedelta(days=1)

        if len(split_info) >= 5:
            _subtitle = split_info[4]
        else:
            _subtitle = _title

        if _subtitle[0] == ' ':
            _subtitle = _subtitle[1:]

        if _subtitle[-1] == '\n':
            _subtitle = _subtitle[:-1]

        _tasks.append([_title, _required_hours, _start_date, _due_date, _min_time, _subtitle, _actual_due_date])

    # Set due date for any tasks without due date to maximum due date
    max_due_date = sorted(_tasks, key=itemgetter(3))[-1][3]
    for _index in due_dateless_task_indices:
        _tasks[_index][3] = max_due_date

    # Sort tasks by due date
    _tasks = sorted(sorted(_tasks, key=itemgetter(6)), key=itemgetter(3))
    return _tasks


def remove_fixed_from_flexi(fixed, flexi):
    # Remove set work from task requirements
    for _date in fixed:
        for _title in fixed[_date]:
            time_to_remove = fixed[_date][_title]
            for _task in flexi:
                if time_to_remove <= time_inc:
                    break
                elif _title == _task[5]:
                    _task[1] -= min(time_to_remove, _task[1])
                    time_to_remove -= min(time_to_remove, _task[1])


# Input choices
cur_date = input_start_date()
include_weekends = bool_input('include weekends')
reverse_output = bool_input('reverse output')
if bool_input('clear terminal history'):
    subprocess.call('reset')
elif bool_input('separate output'):
    separate_output()

screen_width = get_screen_width()

# Load data
daily_tasks = load_fixed_tasks()
tasks = load_flexi_tasks()
remove_fixed_from_flexi(daily_tasks, tasks)

print("All input data imported")

# Work out how many hours to work a day
required_hour_sum = 0
auto_work_per_day = {}
work_on_days_to_due = {}
for index, task in enumerate(tqdm(tasks, desc='Calculating total hours')):
    title, required_hours, start_date, due_date, min_time, subtitle, actual_due_date = task

    # Get list of days which could possibly be used
    available_days = [start_date + datetime.timedelta(days=x) for x in range(0, (due_date - start_date).days)]

    # Get total work on each day and slate weekends for removal if necessary
    indices_to_delete = []
    for day_index, date in enumerate(available_days):
        if date.weekday() in [6, 5] and not include_weekends:
            indices_to_delete.append(day_index)
            continue
        if date in auto_work_per_day:
            work_on_days_to_due[date] = get_work_on_day(date) + auto_work_per_day[date]
        else:
            work_on_days_to_due[date] = get_work_on_day(date)

    # Can't delete while iterating over list, so actually remove weekends now
    for deletable_index in reversed(indices_to_delete):
        del available_days[deletable_index]

    if len(available_days) <= 0:
        date = due_date - datetime.timedelta(days=1)
        available_days = [date]
        if date in auto_work_per_day:
            work_on_days_to_due[date] = get_work_on_day(date) + auto_work_per_day[date]
        else:
            work_on_days_to_due[date] = get_work_on_day(date)

    # Add hours to day with smallest amount of work so far
    while required_hours > 0 and len(work_on_days_to_due) > 0:
        min_work_day = min(available_days, key=lambda x: work_on_days_to_due[x])
        auto_work_to_add = min([min_time, required_hours])
        if min_work_day in auto_work_per_day:
            auto_work_per_day[min_work_day] += auto_work_to_add
            work_on_days_to_due[min_work_day] += auto_work_to_add
        elif min_work_day in work_on_days_to_due:
            auto_work_per_day[min_work_day] = auto_work_to_add
            work_on_days_to_due[min_work_day] += auto_work_to_add
        else:
            auto_work_per_day[min_work_day] = auto_work_to_add
            work_on_days_to_due[min_work_day] += auto_work_to_add

        required_hours -= auto_work_to_add

# Assign subjects to each day
daily_titles = {}
warning_str = ''
for index, task in enumerate(tqdm(tasks, desc='Assigning subjects')):
    title, required_hours, start_date, due_date, min_time, subtitle, actual_due_date = task

    available_days = [start_date + datetime.timedelta(days=x) for x in range(0, (due_date - start_date).days)]

    failed_min_time = False
    while required_hours >= time_inc and len(available_days) > 0:
        previous_hours = required_hours
        for date in available_days:
            if date in auto_work_per_day:
                if required_hours > 0 and auto_work_per_day[date] > 0:
                    if auto_work_per_day[date] < min_time:
                        continue
                    if date not in daily_tasks or title not in daily_tasks[date]:
                        auto_work_to_add = min_time
                    elif daily_tasks[date][title] < min_time:
                        auto_work_to_add = min_time - daily_tasks[date][title]
                    elif failed_min_time:
                        auto_work_to_add = time_inc
                    else:
                        auto_work_to_add = min(required_hours, auto_work_per_day[date], min_time)

                    # Safely add work to daily tasks
                    if date in daily_tasks:
                        if title in daily_tasks[date]:
                            daily_tasks[date][title] += auto_work_to_add
                        else:
                            daily_tasks[date][title] = auto_work_to_add

                    else:
                        daily_tasks[date] = {title: auto_work_to_add}

                    # Update total amount of auto-work
                    auto_work_per_day[date] -= auto_work_to_add

                    # Safely add work to daily titles
                    if date in daily_titles:
                        if title in daily_titles[date]:
                            daily_titles[date][title] += auto_work_to_add
                        else:
                            daily_titles[date][title] = auto_work_to_add
                    else:
                        daily_titles[date] = {title: auto_work_to_add}

                    required_hours -= auto_work_to_add

        if previous_hours == required_hours:
            if failed_min_time:
                warning_str += "Not enough time for " + title + " (" + subtitle + ") with " + str(required_hours) + \
                                                                                                   " hour(s) extra.\n"
                break
            min_time = 0
            failed_min_time = True
    if len(available_days) <= 0:
        if required_hours > 1:
            warning_str += 'Do ' + str(required_hours) + ' hours of ' + subtitle + ' now!\n'
        else:
            warning_str += 'Do ' + str(required_hours) + ' hour of ' + subtitle + ' now!\n'
print(warning_str)

# Assign specific tasks to dates
daily_subtitles = {}
for task in tqdm(tasks, desc="Assigning tasks"):
    title, required_hours, start_date, due_date, min_time, subtitle, actual_due_date = task

    for date in sorted(filter(lambda x: x >= start_date, daily_titles)):
        if title in daily_titles[date] and required_hours > 0 and daily_titles[date][title] > 0:
            auto_work_to_add = min(required_hours, daily_titles[date][title])
            required_hours -= auto_work_to_add
            daily_titles[date][title] -= auto_work_to_add
            output_subtitle = subtitle
            overdue = due_date - actual_due_date

            # Ensure they close cleanly to zero
            if 0 < required_hours < time_inc:
                print('Minimising ' + subtitle + ': required hours = ' + str(required_hours))
                required_hours = 0
            if 0 < daily_titles[date][title] < time_inc:
                print('Minimising ' + subtitle + ': daily titles = ' + str(daily_titles[date][title]))
                daily_titles[date][title] = 0

            if required_hours <= 0:
                output_subtitle = "(Complete) " + output_subtitle
            if overdue > datetime.timedelta(0):
                output_subtitle = "(OVERDUE " + str(overdue.days) + " DAYS)" + output_subtitle
            elif due_date == date + datetime.timedelta(days=1):
                output_subtitle = "(DUE) " + output_subtitle
            if date in daily_subtitles:
                if output_subtitle in daily_subtitles[date]:
                    daily_subtitles[date][output_subtitle] += auto_work_to_add
                else:
                    daily_subtitles[date][output_subtitle] = auto_work_to_add
            else:
                daily_subtitles[date] = {output_subtitle: auto_work_to_add}
    if required_hours >= time_inc:
        print('%s: %s' % (subtitle, required_hours))


def print_results(_daily_subtitles, _work_on_days_to_due):
    # Display results
    actual_hours_sum = 0
    for _date in sorted(_daily_subtitles, reverse=reverse_output):
        total_auto = 0
        for _task in _daily_subtitles[_date]:
            total_auto += _daily_subtitles[_date][_task]

        # Create correct number of title dashes
        output = weekday_conversion[_date.weekday()] + ' ' + str(_date) + ' (' + decimal_to_timestring(total_auto) + \
            ' auto/' + decimal_to_timestring(_work_on_days_to_due[_date]) + ' total)'
        cur_side_left = True
        if len(output) >= screen_width:
            output = '-' * screen_width + '\n' + output + '\n' + '.' * screen_width
        while len(output) < screen_width:
            if cur_side_left:
                output = '-' + output
            else:
                output = output + '-'

            cur_side_left = not cur_side_left

        print(Fore.GREEN)
        print(output)
        print(Style.RESET_ALL)

        for _task in _daily_subtitles[_date]:
            print(_task + ': ' + decimal_to_timestring(_daily_subtitles[_date][_task]))
            actual_hours_sum += _daily_subtitles[_date][_task]

        # Show if there's a miss-match in work amounts
        excess_work = total_auto + get_work_on_day(_date) - _work_on_days_to_due[_date]
        if excess_work > 0:
            print(Fore.RED + decimal_to_timestring(excess_work) + ' hours of extra work' + Style.RESET_ALL)
        elif excess_work < 0:
            print(Fore.RED + 'Missing ' + decimal_to_timestring(-excess_work) + ' hours of work' + Style.RESET_ALL)


if __name__ == '__main__':
    print("Updating data from drive")
    sync.safe_sync()

    print_results(daily_subtitles, work_on_days_to_due)
